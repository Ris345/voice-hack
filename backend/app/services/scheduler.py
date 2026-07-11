"""Background scheduler: places outbound calls when reminders come due and
when a daily medication schedule hits its call_time.

Runs as an asyncio task inside the FastAPI app — no external cron needed,
which suits a hackathon demo (one process, visible logs).
"""

import asyncio
import logging
from datetime import datetime, timezone

from ..db import supabase

log = logging.getLogger(__name__)

POLL_SECONDS = 20


def _due_reminders() -> list[dict]:
    now = datetime.now(timezone.utc).isoformat()
    return (
        supabase()
        .table("reminders")
        .select("*")
        .eq("status", "pending")
        .lte("due_at", now)
        .execute()
    ).data


def _due_schedules() -> list[dict]:
    """Daily schedules whose call_time has passed today and haven't fired yet."""
    now = datetime.now()  # server-local; hackathon demo runs in one timezone
    today = now.date().isoformat()
    rows = (
        supabase()
        .table("schedules")
        .select("*")
        .eq("active", True)
        .lte("call_time", now.strftime("%H:%M:%S"))
        .execute()
    ).data
    return [r for r in rows if r.get("last_fired_on") != today]


async def scheduler_loop():
    # import here to avoid a circular import (main imports this module)
    from ..main import trigger_call, TriggerCallIn

    log.info("scheduler loop started (poll every %ss)", POLL_SECONDS)
    while True:
        try:
            for r in _due_reminders():
                log.info("reminder due for senior %s: %s", r["senior_id"], r["reason"])
                supabase().table("reminders").update({"status": "done"}).eq(
                    "id", r["id"]
                ).execute()
                trigger_call(TriggerCallIn(senior_id=r["senior_id"], reason=r["reason"]))

            for s in _due_schedules():
                log.info("daily schedule %s due: %s", s["id"], s["label"])
                supabase().table("schedules").update(
                    {"last_fired_on": datetime.now().date().isoformat()}
                ).eq("id", s["id"]).execute()
                trigger_call(TriggerCallIn(senior_id=s["senior_id"], reason=s["label"]))
        except Exception:
            log.exception("scheduler tick failed (will retry)")
        await asyncio.sleep(POLL_SECONDS)
