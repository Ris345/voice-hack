import asyncio
import logging
from datetime import datetime, timedelta, timezone
from pathlib import Path

import httpx
from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import Response
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient

from .config import settings
from .db import supabase
from .services.escalation import raise_alert, send_digest

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Pill Buddy Backend")


@app.middleware("http")
async def _no_cache_portal(request, call_next):
    """The portal is a single evolving HTML file — stale browser cache has
    repeatedly shipped judges old JS. Force revalidation on every load."""
    resp = await call_next(request)
    if request.url.path in ("/", "/index.html", "/design-board.html"):
        resp.headers["Cache-Control"] = "no-store"
    return resp


@app.on_event("startup")
async def _start_scheduler():
    from .services.scheduler import scheduler_loop

    asyncio.create_task(scheduler_loop())

_twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)


# ---------------------------------------------------------------- calls

class TriggerCallIn(BaseModel):
    senior_id: str
    reason: str = ""  # why this call is happening — passed to the agent


@app.post("/calls/trigger")
def trigger_call(body: TriggerCallIn):
    """Kick off an outbound reminder call to a senior (demo button / scheduler)."""
    senior = (
        supabase().table("seniors").select("*").eq("id", body.senior_id).single().execute()
    ).data
    if not senior:
        raise HTTPException(404, "senior not found")

    call_log = (
        supabase()
        .table("call_logs")
        .insert(
            {"senior_id": senior["id"], "status": "initiated", "call_reason": body.reason or None}
        )
        .execute()
    ).data[0]

    twiml_url = settings.voice_agent_twiml_url or f"{settings.public_base_url}/twilio/voice"
    call = _twilio.calls.create(
        to=senior["phone"],
        from_=settings.twilio_from_number,
        url=f"{twiml_url}?call_log_id={call_log['id']}",
        status_callback=f"{settings.public_base_url}/twilio/status-callback",
        status_callback_event=["completed"],
    )
    supabase().table("call_logs").update({"twilio_call_sid": call.sid}).eq(
        "id", call_log["id"]
    ).execute()
    return {"call_log_id": call_log["id"], "call_sid": call.sid}


class InvokeCallIn(BaseModel):
    phone: str          # E.164 e.g. +19176559764
    name: str = "Friend"


@app.post("/calls/invoke")
def invoke_call(body: InvokeCallIn):
    """Demo endpoint — trigger a call to any phone number directly.
    Looks up existing senior by phone; creates a minimal record if unknown."""
    phone = body.phone if body.phone.startswith("+") else f"+1{body.phone}"

    rows = supabase().table("seniors").select("id").eq("phone", phone).execute().data
    if rows:
        senior_id = rows[0]["id"]
    else:
        senior_id = supabase().table("seniors").insert({
            "name": body.name,
            "phone": phone,
        }).execute().data[0]["id"]
        # link to the first caregiver as primary so escalation has a target
        caregiver_id = supabase().table("caregivers").select("id").limit(1).execute().data[0]["id"]
        supabase().table("care_relationships").insert({
            "senior_id": senior_id,
            "caregiver_id": caregiver_id,
            "is_primary": True,
        }).execute()

    call_log = supabase().table("call_logs").insert(
        {"senior_id": senior_id, "status": "initiated"}
    ).execute().data[0]

    twiml_url = settings.voice_agent_twiml_url or f"{settings.public_base_url}/twilio/voice"
    call = _twilio.calls.create(
        to=phone,
        from_=settings.twilio_from_number,
        url=f"{twiml_url}?call_log_id={call_log['id']}",
        status_callback=f"{settings.public_base_url}/twilio/status-callback",
        status_callback_event=["completed"],
    )
    supabase().table("call_logs").update({"twilio_call_sid": call.sid}).eq(
        "id", call_log["id"]
    ).execute()
    return {"call_log_id": call_log["id"], "call_sid": call.sid, "to": phone}


class CallResultIn(BaseModel):
    transcript_summary: str
    meds_confirmed: bool | None = None
    transcript: list[dict] | None = None  # [{speaker, text}, ...]
    wellness_note: str | None = None
    action_items: list[dict] = []  # [{text, priority}]


@app.post("/calls/{call_log_id}/result")
def write_call_result(call_log_id: str, body: CallResultIn):
    """Voice agent writes its outcome here when the conversation ends."""
    update = {
        "transcript_summary": body.transcript_summary,
        "meds_confirmed": body.meds_confirmed,
        "status": "completed",
        "ended_at": datetime.now(timezone.utc).isoformat(),
    }
    if body.transcript is not None:
        update["transcript"] = body.transcript
    if body.wellness_note is not None:
        update["wellness_note"] = body.wellness_note
    supabase().table("call_logs").update(update).eq("id", call_log_id).execute()

    if body.action_items:
        call = (
            supabase().table("call_logs").select("senior_id").eq("id", call_log_id).single().execute()
        ).data
        supabase().table("action_items").insert(
            [
                {
                    "senior_id": call["senior_id"],
                    "text": a.get("text", ""),
                    "priority": a.get("priority", "normal"),
                    "source_call_id": call_log_id,
                }
                for a in body.action_items
                if a.get("text")
            ]
        ).execute()

    sent = send_digest(call_log_id)
    return {"ok": True, "digest_sent": sent}


class ReminderIn(BaseModel):
    minutes_from_now: int
    reason: str = "medication reminder"


@app.post("/calls/{call_log_id}/reminder")
def create_reminder(call_log_id: str, body: ReminderIn):
    """Agent calls this when the senior asks to be called back later
    ('remind me in 20 minutes'). The scheduler loop places the callback."""
    call = (
        supabase().table("call_logs").select("senior_id").eq("id", call_log_id).single().execute()
    ).data
    due = datetime.now(timezone.utc) + timedelta(minutes=body.minutes_from_now)
    row = (
        supabase()
        .table("reminders")
        .insert(
            {
                "senior_id": call["senior_id"],
                "due_at": due.isoformat(),
                "reason": body.reason,
                "source": "agent",
            }
        )
        .execute()
    ).data[0]
    return {"reminder_id": row["id"], "due_at": row["due_at"]}


# ---------------------------------------------------------------- alerts

class AlertIn(BaseModel):
    call_log_id: str
    type: str  # health_concern | missed_dose | distress | no_answer
    detail: str
    severity: str = "warn"  # info | warn | urgent


@app.post("/alerts")
def create_alert(body: AlertIn):
    """Voice agent calls this the moment it detects a concern mid-call.
    Writes the Supabase alert row AND fires the caregiver SMS."""
    alert = raise_alert(body.call_log_id, body.type, body.detail, body.severity)
    return {"alert_id": alert["id"], "sms_sent": alert.get("sms_sent", False)}


# ---------------------------------------------------------------- twilio webhooks

@app.post("/twilio/voice")
def voice_placeholder(call_log_id: str = ""):
    """Placeholder TwiML so the pipeline is testable end-to-end before the
    real voice agent is wired in (set VOICE_AGENT_TWIML_URL to replace)."""
    twiml = (
        '<?xml version="1.0" encoding="UTF-8"?>'
        "<Response><Say voice=\"alice\">Hello! This is Pill Buddy. "
        "The voice agent is not connected yet, but the call pipeline works. "
        "Goodbye!</Say></Response>"
    )
    return Response(content=twiml, media_type="application/xml")


@app.post("/twilio/status-callback")
def status_callback(CallSid: str = Form(...), CallStatus: str = Form(...)):
    """Twilio tells us the call finished. First give the voice agent a chance
    to file its full report (summary + transcript + action items) — its session
    is only in memory, and if the patient hangs up mid-call nothing else
    triggers it. Then act as the safety net for status + digest."""
    rows = (
        supabase().table("call_logs").select("*").eq("twilio_call_sid", CallSid).execute()
    ).data
    if not rows:
        return {"ok": False}
    call = rows[0]

    if settings.voice_agent_twiml_url:
        agent_status_url = settings.voice_agent_twiml_url.replace(
            "/voice/incoming", "/voice/status"
        )
        try:
            httpx.post(
                agent_status_url,
                data={"CallSid": CallSid, "CallStatus": CallStatus},
                timeout=20.0,  # includes the agent's LLM summarization
            )
        except Exception:
            logging.getLogger(__name__).exception("agent finalize failed, using safety net")

    update: dict = {"ended_at": datetime.now(timezone.utc).isoformat()}
    if call["status"] not in ("completed",):  # don't clobber the agent's result
        update["status"] = "completed" if CallStatus == "completed" else CallStatus
    supabase().table("call_logs").update(update).eq("id", call["id"]).execute()

    if CallStatus == "no-answer":
        raise_alert(call["id"], "no_answer", "Call was not answered.", "warn")

    # refetch — the agent's report above may have already sent the digest
    call = (
        supabase().table("call_logs").select("digest_sent").eq("id", call["id"]).single().execute()
    ).data
    if not call.get("digest_sent"):
        send_digest(rows[0]["id"])
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True}


# Caregiver portal (dashboard/ at repo root) — served last so API routes win.
_dashboard = Path(__file__).resolve().parents[2] / "dashboard"
if _dashboard.is_dir():
    app.mount("/", StaticFiles(directory=_dashboard, html=True), name="dashboard")
