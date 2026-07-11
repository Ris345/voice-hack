"""
Client for the judge agent — fire-and-forget, never blocks a live call.
"""

import os
import requests

JUDGE_URL = os.environ.get("JUDGE_URL", "http://localhost:8001")

_cached_lessons: list[str] = []


def fetch_learnings() -> list[str]:
    """Called once at startup — returns lessons to inject into the system prompt."""
    global _cached_lessons
    try:
        resp = requests.get(f"{JUDGE_URL}/learnings", timeout=3)
        _cached_lessons = resp.json().get("lessons", [])
        print(f"[judge] loaded {len(_cached_lessons)} learnings")
    except Exception as e:
        print(f"[judge] could not fetch learnings: {e}")
    return _cached_lessons


def submit_call(
    history: list[dict],
    patient_name: str,
    med_summary: str,
    notes: str = "",
) -> None:
    """Submit completed call for evaluation — non-blocking."""
    try:
        requests.post(
            f"{JUDGE_URL}/evaluate",
            json={
                "patient_name": patient_name,
                "med_summary": med_summary,
                "notes": notes,
                "history": history,
            },
            timeout=5,
        )
    except Exception as e:
        print(f"[judge] submit failed: {e}")
