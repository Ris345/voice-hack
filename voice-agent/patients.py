"""
Patient registry — reads seniors + medications from Supabase (source of truth).

Falls back to a hardcoded dict when SUPABASE_URL/SUPABASE_ANON_KEY aren't set
(or the lookup fails), so the agent still runs standalone.
"""

import os
from typing import Any

import requests

SUPABASE_URL = os.environ.get("SUPABASE_URL", "")
SUPABASE_KEY = os.environ.get("SUPABASE_ANON_KEY", "")

# Standalone fallback — used only when Supabase isn't configured/reachable.
_PATIENTS: dict[str, dict[str, Any]] = {
    "+15551234567": {
        "name": "Dorothy",
        "medications": ["Lisinopril 10mg", "Metformin 500mg"],
    },
    "+15559876543": {
        "name": "Harold",
        "medications": ["Atorvastatin 20mg"],
    },
}


def _from_supabase(phone: str) -> dict[str, Any] | None:
    resp = requests.get(
        f"{SUPABASE_URL}/rest/v1/seniors",
        params={
            "phone": f"eq.{phone}",
            "select": "id,name,grandkid_names,notes,medications(name,dosage,instructions)",
        },
        headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
        timeout=5,
    )
    resp.raise_for_status()
    rows = resp.json()
    if not rows:
        return None
    s = rows[0]
    return {
        "senior_id": s["id"],
        "name": s["name"].split()[0],  # first name for the conversation
        "medications": [f"{m['name']} {m['dosage']}" for m in s["medications"]],
        "grandkid_names": s.get("grandkid_names") or [],
        "notes": s.get("notes") or "",
    }


def get_patient(phone: str) -> dict[str, Any] | None:
    if SUPABASE_URL and SUPABASE_KEY:
        try:
            patient = _from_supabase(phone)
            if patient:
                return patient
        except Exception as e:
            print(f"[patients] supabase lookup failed, using fallback: {e}")
    return _PATIENTS.get(phone)


def call_reason(call_log_id: str) -> str:
    """Why this call was placed (schedule label / reminder reason), if any."""
    if not (SUPABASE_URL and SUPABASE_KEY and call_log_id):
        return ""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/call_logs",
            params={"id": f"eq.{call_log_id}", "select": "call_reason"},
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=5,
        )
        resp.raise_for_status()
        rows = resp.json()
        return (rows[0].get("call_reason") or "") if rows else ""
    except Exception as e:
        print(f"[patients] call_reason lookup failed: {e}")
        return ""


def call_history_context(senior_id: str, limit: int = 3) -> str:
    """Compact digest of recent calls so the agent has continuity —
    what was discussed, how they seemed, what to follow up on."""
    if not (SUPABASE_URL and SUPABASE_KEY and senior_id):
        return ""
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/rest/v1/call_logs",
            params={
                "senior_id": f"eq.{senior_id}",
                "status": "eq.completed",
                "select": "started_at,transcript_summary,wellness_note,meds_confirmed",
                "order": "started_at.desc",
                "limit": str(limit),
            },
            headers={"apikey": SUPABASE_KEY, "Authorization": f"Bearer {SUPABASE_KEY}"},
            timeout=5,
        )
        resp.raise_for_status()
        lines = []
        for c in resp.json():
            if not (c.get("transcript_summary") or c.get("wellness_note")):
                continue
            day = (c.get("started_at") or "")[:10]
            meds = {True: "meds taken", False: "meds MISSED", None: "meds unconfirmed"}[
                c.get("meds_confirmed")
            ]
            bits = [b for b in (c.get("transcript_summary"), c.get("wellness_note")) if b]
            lines.append(f"- {day} ({meds}): {' '.join(bits)}")
        return "\n".join(lines)
    except Exception as e:
        print(f"[patients] call history lookup failed: {e}")
        return ""


def med_summary(patient: dict[str, Any]) -> str:
    meds = patient.get("medications", [])
    if not meds:
        return "your medication"
    if len(meds) == 1:
        return meds[0]
    return ", ".join(meds[:-1]) + f" and {meds[-1]}"
