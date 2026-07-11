import logging
from datetime import datetime, timezone

from fastapi import FastAPI, Form, HTTPException
from fastapi.responses import Response
from pydantic import BaseModel
from twilio.rest import Client as TwilioClient

from .config import settings
from .db import supabase
from .services.escalation import raise_alert, send_digest

logging.basicConfig(level=logging.INFO)

app = FastAPI(title="Pill Buddy Backend")

_twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)


# ---------------------------------------------------------------- calls

class TriggerCallIn(BaseModel):
    senior_id: str


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
        .insert({"senior_id": senior["id"], "status": "initiated"})
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


class CallResultIn(BaseModel):
    transcript_summary: str
    meds_confirmed: bool | None = None


@app.post("/calls/{call_log_id}/result")
def write_call_result(call_log_id: str, body: CallResultIn):
    """Voice agent writes its outcome here when the conversation ends."""
    supabase().table("call_logs").update(
        {
            "transcript_summary": body.transcript_summary,
            "meds_confirmed": body.meds_confirmed,
            "status": "completed",
            "ended_at": datetime.now(timezone.utc).isoformat(),
        }
    ).eq("id", call_log_id).execute()
    sent = send_digest(call_log_id)
    return {"ok": True, "digest_sent": sent}


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
    """Twilio tells us the call finished. Safety net: if the voice agent never
    posted a result (crash, no-answer), still update status and send the digest."""
    rows = (
        supabase().table("call_logs").select("*").eq("twilio_call_sid", CallSid).execute()
    ).data
    if not rows:
        return {"ok": False}
    call = rows[0]

    update: dict = {"ended_at": datetime.now(timezone.utc).isoformat()}
    if call["status"] not in ("completed",):  # don't clobber the agent's result
        update["status"] = "completed" if CallStatus == "completed" else CallStatus
    supabase().table("call_logs").update(update).eq("id", call["id"]).execute()

    if CallStatus == "no-answer":
        raise_alert(call["id"], "no_answer", "Call was not answered.", "warn")
    if not call.get("digest_sent"):
        send_digest(call["id"])
    return {"ok": True}


@app.get("/health")
def health():
    return {"ok": True}
