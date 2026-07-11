"""
In-memory session store — fine for a hackathon since calls are short-lived.
Keyed by Twilio CallSid.
"""

from typing import Any

_store: dict[str, dict[str, Any]] = {}


def create(
    call_sid: str, patient_name: str, phone: str, med_summary: str,
    call_log_id: str = "", notes: str = "", grandkid_names: list = []
) -> dict[str, Any]:
    session = {
        "callSid": call_sid,
        "patientName": patient_name,
        "phone": phone,
        "medSummary": med_summary,
        "callLogId": call_log_id,
        "notes": notes,
        "grandkidNames": grandkid_names,
        "stage": "greeting",
        "medStatus": "unknown",
        "history": [],
    }
    _store[call_sid] = session
    return session


def get(call_sid: str) -> dict[str, Any] | None:
    return _store.get(call_sid)


def update(call_sid: str, **kwargs) -> None:
    if call_sid in _store:
        _store[call_sid].update(kwargs)


def append_history(call_sid: str, role: str, content: str) -> None:
    if call_sid in _store:
        _store[call_sid]["history"].append({"role": role, "content": content})


def close(call_sid: str) -> dict[str, Any] | None:
    return _store.pop(call_sid, None)
