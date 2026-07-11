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
from fastapi.responses import PlainTextResponse

import agent
import backend_client
import patients
import sessions

app = FastAPI()

BASE_URL = os.environ.get("BASE_URL", "http://localhost:8000")
GATHER_URL = f"{BASE_URL}/voice/gather"


# ---------------------------------------------------------------------------
# TwiML helpers
# ---------------------------------------------------------------------------

def _twiml(xml_body: str) -> Response:
    return Response(content=xml_body, media_type="text/xml")


def say_and_gather(text: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Gather input="speech" action="{GATHER_URL}" method="POST"
          speechTimeout="auto" speechModel="experimental_conversations" enhanced="true">
    <Say voice="Polly.Joanna-Neural">{text}</Say>
  </Gather>
  <Say voice="Polly.Joanna-Neural">I didn't catch that — let me try again.</Say>
  <Redirect method="POST">{GATHER_URL}</Redirect>
</Response>"""


def say_and_hangup(text: str) -> str:
    return f"""<?xml version="1.0" encoding="UTF-8"?>
<Response>
  <Say voice="Polly.Joanna-Neural">{text}</Say>
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

    session = sessions.create(
        call_sid=CallSid,
        patient_name=name,
        phone=phone,
        med_summary=summary,
        call_log_id=call_log_id,
    )

    result = agent.run_turn(
        history=session["history"],
        stage=session["stage"],
        user_speech="",
        patient_name=name,
        med_summary=summary,
    )

    _update_session_from_result(CallSid, result)

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

    # Append patient turn to history
    sessions.append_history(CallSid, "user", user_speech)

    result = agent.run_turn(
        history=session["history"],
        stage=session["stage"],
        user_speech=user_speech,
        patient_name=session["patientName"],
        med_summary=session["medSummary"],
    )

    _update_session_from_result(CallSid, result)

    # Write med flag when status becomes known
    _handle_med_flag(session, result["med_status"])

    if result["should_close"]:
        closed = sessions.close(CallSid)
        _report_call_result(closed)
        return _twiml(say_and_hangup(result["speech"]))

    return _twiml(say_and_gather(result["speech"]))


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
    """Send the conversation outcome to the backend (idempotent there)."""
    if not session:
        return
    med_status = session.get("medStatus", "unknown")
    meds_confirmed = {"taken": True, "missed": False}.get(med_status)
    name = session.get("patientName", "the patient")
    n_turns = len(session.get("history", []))
    summary = (
        f"Chatted with {name} ({n_turns // 2} exchanges). "
        f"Medication status: {med_status}."
    )
    backend_client.report_result(session.get("callLogId", ""), summary, meds_confirmed)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _update_session_from_result(call_sid: str, result: dict) -> None:
    sessions.append_history(call_sid, "assistant", result["_assistant_raw"])
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
