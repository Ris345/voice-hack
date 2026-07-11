"""
Judge agent service — receives completed call data from the voice agent,
evaluates it with Claude, and appends learnings to learnings.json.

Voice agent POSTs here at call end. Learnings are read back by the voice
agent at startup to improve future calls.
"""

import json
import os
from datetime import datetime, timezone
from pathlib import Path

from dotenv import load_dotenv
load_dotenv()

from fastapi import FastAPI
from fastapi.responses import PlainTextResponse
from pydantic import BaseModel

import judge

app = FastAPI(title="Pill Buddy Judge Agent")

LEARNINGS_FILE = Path("learnings.json")


def _load_learnings() -> list[dict]:
    if LEARNINGS_FILE.exists():
        return json.loads(LEARNINGS_FILE.read_text())
    return []


def _save_learnings(learnings: list[dict]) -> None:
    LEARNINGS_FILE.write_text(json.dumps(learnings, indent=2))


class CallData(BaseModel):
    patient_name: str
    med_summary: str
    notes: str = ""
    history: list[dict]   # list of {role, content}


@app.post("/evaluate")
def evaluate_call(data: CallData):
    """Voice agent calls this at the end of every conversation."""
    if len(data.history) < 2:
        return {"ok": False, "reason": "transcript too short to evaluate"}

    result = judge.evaluate(
        history=data.history,
        patient_name=data.patient_name,
        med_summary=data.med_summary,
        notes=data.notes,
    )

    entry = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "patient": data.patient_name,
        "scores": result["scores"],
        "overall": result["overall"],
        "lessons": result["lessons"],
    }

    learnings = _load_learnings()
    learnings.append(entry)
    # Keep only the 20 most recent so the prompt doesn't balloon
    learnings = learnings[-20:]
    _save_learnings(learnings)

    print(f"[judge] {data.patient_name} — overall {result['overall']}/5")
    for lesson in result["lessons"]:
        print(f"  → {lesson}")

    return {"ok": True, "overall": result["overall"], "lessons": result["lessons"]}


@app.get("/learnings")
def get_learnings():
    """Voice agent fetches this at startup to inject into its system prompt."""
    learnings = _load_learnings()
    if not learnings:
        return {"lessons": []}

    # Deduplicate and return the most impactful recent lessons
    seen = set()
    unique_lessons = []
    for entry in reversed(learnings):
        for lesson in entry["lessons"]:
            if lesson not in seen:
                seen.add(lesson)
                unique_lessons.append(lesson)
        if len(unique_lessons) >= 6:
            break

    return {"lessons": unique_lessons}


@app.get("/health")
def health():
    return {"ok": True}


if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=8001, reload=True)
