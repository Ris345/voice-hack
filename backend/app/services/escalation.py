"""Dual-channel escalation: alert row in Supabase (feeds Lovable Alerts panel)
plus an immediate SMS to the senior's caregiver."""

import logging

from twilio.rest import Client as TwilioClient

from ..config import settings
from ..db import supabase

log = logging.getLogger(__name__)

_twilio = TwilioClient(settings.twilio_account_sid, settings.twilio_auth_token)

SEVERITY_PREFIX = {"urgent": "🚨 URGENT", "warn": "⚠️", "info": "ℹ️"}


def _caregiver_for_call(call_log_id: str) -> tuple[dict, dict]:
    """Returns (senior, caregiver) for a call_log id."""
    call = (
        supabase().table("call_logs").select("senior_id").eq("id", call_log_id).single().execute()
    ).data
    senior = (
        supabase()
        .table("seniors")
        .select("*, caregivers(*)")
        .eq("id", call["senior_id"])
        .single()
        .execute()
    ).data
    return senior, senior["caregivers"]


def raise_alert(call_log_id: str, type_: str, detail: str, severity: str = "warn") -> dict:
    """Insert the alert row, then SMS the caregiver. The row is written first so
    the dashboard shows the alert even if the SMS provider fails."""
    alert = (
        supabase()
        .table("alerts")
        .insert(
            {"call_log_id": call_log_id, "type": type_, "detail": detail, "severity": severity}
        )
        .execute()
    ).data[0]

    senior, caregiver = _caregiver_for_call(call_log_id)
    prefix = SEVERITY_PREFIX.get(severity, "")
    body = f"{prefix} Pill Buddy alert for {senior['name']}: {detail}"

    try:
        _twilio.messages.create(
            to=caregiver["phone"], from_=settings.twilio_from_number, body=body
        )
        supabase().table("alerts").update({"sms_sent": True}).eq("id", alert["id"]).execute()
        alert["sms_sent"] = True
    except Exception:
        log.exception("alert SMS failed (alert row %s is still saved)", alert["id"])

    return alert


def send_digest(call_log_id: str) -> bool:
    """Plain-English post-call recap SMS to the caregiver. Returns True if sent."""
    call = (
        supabase().table("call_logs").select("*").eq("id", call_log_id).single().execute()
    ).data
    if call.get("digest_sent"):
        return False

    senior, caregiver = _caregiver_for_call(call_log_id)
    alerts = (
        supabase().table("alerts").select("detail, severity").eq("call_log_id", call_log_id).execute()
    ).data

    meds = {True: "took her meds ✅", False: "did NOT confirm meds ❌", None: "meds unconfirmed"}[
        call.get("meds_confirmed")
    ]
    lines = [f"Pill Buddy: just chatted with {senior['name']} — {meds}."]
    if call.get("transcript_summary"):
        lines.append(call["transcript_summary"])
    for a in alerts:
        lines.append(f"{SEVERITY_PREFIX.get(a['severity'], '')} {a['detail']}")

    try:
        _twilio.messages.create(
            to=caregiver["phone"], from_=settings.twilio_from_number, body="\n".join(lines)
        )
        supabase().table("call_logs").update({"digest_sent": True}).eq("id", call_log_id).execute()
        return True
    except Exception:
        log.exception("digest SMS failed for call %s", call_log_id)
        return False
