"""
Voice agent runtime — FastAPI server that handles Twilio voice webhooks.

Flow:
  POST /voice/incoming  → greet patient, start gather
  POST /voice/gather    → receive speech, run agent turn, respond
  POST /voice/status    → log call completion (optional)

Point Twilio's voice webhook at: {BASE_URL}/voice/incoming
"""

import os

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI, Form, Request, Response
from fastapi.background import BackgroundTasks
from fastapi.responses import FileResponse, PlainTextResponse

import agent
import backend_client
import judge_client
import patients
import sessions
import tts

app = FastAPI()

@app.on_event("startup")
def startup():
    agent.set_learnings(judge_client.fetch_learnings())

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
GATHER_URL = f"{BASE_URL}/voice/gather"


# ---------------------------------------------------------------------------
# TwiML helpers
# ---------------------------------------------------------------------------

def _twiml(xml_body: str) -> Response:
    return Response(content=xml_body, media_type="text/xml")


def _audio_url(text: str) -> str:
    file_id = tts.synthesize(text)
    return f"{BASE_URL}/audio/{file_id}"


def say_and_gather(text: str) -> str:
    audio_url = _audio_url(text)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Gather input="speech" action="{GATHER_URL}" method="POST"
          speechTimeout="auto" speechModel="experimental_conversations" enhanced="true">
  </Gather>
  <Redirect method="POST">{GATHER_URL}</Redirect>
</Response>"""


def say_and_hangup(text: str) -> str:
    audio_url = _audio_url(text)
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Play>{audio_url}</Play>
  <Hangup/>
</Response>"""


# ---------------------------------------------------------------------------
# Routes
# ---------------------------------------------------------------------------

@app.post("/voice/incoming")
async def incoming(
    request: Request,
    CallSid: str = Form(...),
    From: str = Form(...),
    To: str = Form(default=""),
    Direction: str = Form(default="inbound"),
):
    """Twilio calls this when the patient picks up.

    Outbound (backend-triggered) calls: the patient is `To` and the backend
    passes its call_log_id in the query string. Inbound: patient is `From`.
    """
    phone = To if Direction.startswith("outbound") else From
    call_log_id = request.query_params.get("call_log_id", "")

    patient = patients.get_patient(phone)
    if patient is None:
        # Unknown caller — still be gracious
        patient = {"name": "there", "medications": []}

    name = patient["name"]
    summary = patients.med_summary(patient)

    notes = patient.get("notes", "")
    grandkid_names = patient.get("grandkid_names", [])
    past_calls = patients.call_history_context(patient.get("senior_id", ""))
    reason = patients.call_reason(call_log_id)
    if past_calls:
        print(f"[TX {CallSid[:8]}] continuity context:\n{past_calls}", flush=True)
    if reason:
        print(f"[TX {CallSid[:8]}] call reason: {reason}", flush=True)

    session = sessions.create(
        call_sid=CallSid,
        patient_name=name,
        phone=phone,
        med_summary=summary,
        call_log_id=call_log_id,
        notes=notes,
        grandkid_names=grandkid_names,
    )
    session["pastCalls"] = past_calls

    agent.set_learnings(judge_client.fetch_learnings())

    result = agent.run_turn(
        history=session["history"],
        stage=session["stage"],
        user_speech="",
        patient_name=name,
        med_summary=summary,
        notes=notes,
        grandkid_names=grandkid_names,
        past_calls=past_calls,
        call_reason=reason,
    )

    _update_session_from_result(CallSid, result)
    session.setdefault("transcript", []).append(("AGENT", result["speech"]))
    print(f"[TX {CallSid[:8]}] AGENT-OPEN [{result['next_stage']}]: {result['speech']}", flush=True)

    if result["should_close"]:
        return _twiml(say_and_hangup(result["speech"]))
    return _twiml(say_and_gather(result["speech"]))


@app.post("/voice/gather")
async def gather(
    CallSid: str = Form(...),
    SpeechResult: str = Form(default=""),
    Confidence: str = Form(default="0"),
):
    """Twilio calls this after the patient speaks."""
    session = sessions.get(CallSid)
    if session is None:
        return _twiml(say_and_hangup("Sorry, something went wrong. Goodbye!"))

    user_speech = SpeechResult.strip()
    print(f"[TX {CallSid[:8]}] GRANDMA (conf={Confidence}): {user_speech!r}", flush=True)

    # Append patient turn to history
    sessions.append_history(CallSid, "user", user_speech)
    session.setdefault("transcript", []).append(("GRANDMA", user_speech))

    result = agent.run_turn(
        history=session["history"],
        stage=session["stage"],
        user_speech=user_speech,
        patient_name=session["patientName"],
        med_summary=session["medSummary"],
        notes=session.get("notes", ""),
        grandkid_names=session.get("grandkidNames", []),
    )

    _update_session_from_result(CallSid, result)
    session.setdefault("transcript", []).append(("AGENT", result["speech"]))
    print(f"[TX {CallSid[:8]}] AGENT [{result['next_stage']}/med={result['med_status']}]: {result['speech']}", flush=True)

    # Write med flag when status becomes known
    _handle_med_flag(session, result["med_status"])

    # Patient asked for a callback ("remind me in 20 minutes") → real reminder
    if result.get("reminder_minutes"):
        backend_client.request_reminder(
            session.get("callLogId", ""),
            int(result["reminder_minutes"]),
            f"{session['patientName']} asked to be called back during the last check-in.",
        )

    if result["should_close"]:
        closed = sessions.close(CallSid)
        _report_call_result(closed)
        return _twiml(say_and_hangup(result["speech"]))

    return _twiml(say_and_gather(result["speech"]))


@app.get("/audio/{file_id}")
async def serve_audio(file_id: str, background_tasks: BackgroundTasks):
    path = tts.AUDIO_DIR / f"{file_id}.mp3"
    if not path.exists():
        return PlainTextResponse("not found", status_code=404)
    background_tasks.add_task(path.unlink, missing_ok=True)
    return FileResponse(path, media_type="audio/mpeg")


@app.post("/voice/status")
async def status(
    CallSid: str = Form(...),
    CallStatus: str = Form(...),
):
    """Twilio status callback — fires on call completion. Safety net: if the
    patient hung up before the closing stage, still report the result."""
    print(f"[status] {CallSid} → {CallStatus}")
    closed = sessions.close(CallSid)
    _report_call_result(closed)
    return PlainTextResponse("ok")


def _report_call_result(session: dict | None) -> None:
    """Send the conversation outcome to the backend (AI summary + wellness
    note + full transcript) and to the judge agent for quality learnings."""
    if not session:
        return
    judge_client.submit_call(
        history=session.get("history", []),
        patient_name=session.get("patientName", ""),
        med_summary=session.get("medSummary", ""),
        notes=session.get("notes", ""),
    )
    med_status = session.get("medStatus", "unknown")
    meds_confirmed = {"taken": True, "missed": False}.get(med_status)
    name = session.get("patientName", "the patient")
    transcript = session.get("transcript", [])

    if transcript:
        summarized = agent.summarize(transcript, name, session.get("pastCalls", ""))
        summary = summarized.get("summary", f"Completed a check-in call with {name}.")
        wellness_note = summarized.get("wellness_note", "")
        action_items = summarized.get("action_items", [])
    else:
        summary = f"Call with {name} ended before any conversation."
        wellness_note = ""
        action_items = []

    backend_client.report_result(
        session.get("callLogId", ""),
        summary,
        meds_confirmed,
        transcript=[{"speaker": s, "text": t} for s, t in transcript],
        wellness_note=wellness_note,
        action_items=action_items,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_session_from_result(call_sid: str, result: dict) -> None:
    sessions.append_history(call_sid, "assistant", result["speech"])
    sessions.update(
        call_sid,
        stage=result["next_stage"],
        medStatus=result["med_status"],
    )


_flagged: set[str] = set()  # avoid double-writing per call

def _handle_med_flag(session: dict, med_status: str) -> None:
    call_sid = session["callSid"]
    if call_sid in _flagged or med_status == "unknown":
        return
    _flagged.add(call_sid)

    phone = session["phone"]
    name = session["patientName"]
    if med_status == "taken":
        print(f"[med] {name} ({phone}) → TAKEN")
    elif med_status == "missed":
        print(f"[med] {name} ({phone}) → MISSED — flag raised")
        backend_client.report_alert(
            session.get("callLogId", ""),
            "missed_dose",
            f"{name} did not take their medication today.",
            severity="warn",
        )


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8000, reload=True)
