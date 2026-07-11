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


def report_result(call_log_id: str, transcript_summary: str, meds_confirmed: bool | None) -> None:
    """End of conversation → marks call completed, triggers caregiver digest SMS."""
    if not call_log_id:
        print("[backend] no call_log_id, skipping result")
        return
    try:
        requests.post(
            f"{BACKEND_URL}/calls/{call_log_id}/result",
            json={"transcript_summary": transcript_summary, "meds_confirmed": meds_confirmed},
            timeout=5,
        ).raise_for_status()
    except Exception as e:
        print(f"[backend] result POST failed: {e}")
