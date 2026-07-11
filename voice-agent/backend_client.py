"""
Thin client for the Pill Buddy backend (dual-channel escalation + digest).

All calls are fire-and-forget with short timeouts — a backend hiccup must
never break the live phone call.
"""

import os

import requests

BACKEND_URL = os.environ.get("BACKEND_URL", "http://localhost:8080")


def report_alert(call_log_id: str, type_: str, detail: str, severity: str = "warn") -> None:
    """Mid-call concern → Supabase alert row + immediate caregiver SMS."""
    if not call_log_id:
        print(f"[backend] no call_log_id, skipping alert: {detail}")
        return
    try:
        requests.post(
            f"{BACKEND_URL}/alerts",
            json={"call_log_id": call_log_id, "type": type_, "detail": detail, "severity": severity},
            timeout=5,
        ).raise_for_status()
    except Exception as e:
        print(f"[backend] alert POST failed: {e}")


def report_result(
    call_log_id: str,
    transcript_summary: str,
    meds_confirmed: bool | None,
    transcript: list[dict] | None = None,
    wellness_note: str = "",
) -> None:
    """End of conversation → marks call completed, triggers caregiver digest."""
    if not call_log_id:
        print("[backend] no call_log_id, skipping result")
        return
    try:
        requests.post(
            f"{BACKEND_URL}/calls/{call_log_id}/result",
            json={
                "transcript_summary": transcript_summary,
                "meds_confirmed": meds_confirmed,
                "transcript": transcript,
                "wellness_note": wellness_note,
            },
            timeout=15,  # includes an LLM summary upstream; give it headroom
        ).raise_for_status()
    except Exception as e:
        print(f"[backend] result POST failed: {e}")


def request_reminder(call_log_id: str, minutes: int, reason: str) -> None:
    """Mid-call: senior asked to be called back → schedule a real callback."""
    if not call_log_id:
        print(f"[backend] no call_log_id, skipping reminder ({minutes}m)")
        return
    try:
        requests.post(
            f"{BACKEND_URL}/calls/{call_log_id}/reminder",
            json={"minutes_from_now": minutes, "reason": reason},
            timeout=5,
        ).raise_for_status()
        print(f"[backend] reminder scheduled in {minutes}m")
    except Exception as e:
        print(f"[backend] reminder POST failed: {e}")
