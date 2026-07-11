"""
Judge agent — evaluates a completed call transcript and produces
actionable prompt improvements for the voice agent.
"""

import json
import os
from typing import Any

import anthropic

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
_MODEL = "claude-sonnet-4-6"

_SYSTEM = """You are a conversation quality judge for Pill Buddy, an AI voice agent \
that calls elderly patients to check on their medications and wellbeing.

You will receive a transcript of a completed call. Evaluate it and produce \
specific, reusable guidance to make future calls better.

Score the call on:
- naturalness: did it sound like a real conversation or a robot script?
- empathy: did it acknowledge what the patient said before moving on?
- med_check: did it clearly confirm or detect a missed dose?
- hooks: did it use the patient's personal details (hobbies, family) to connect?
- close: did the call end warmly and at the right time?

Then write 1-3 SHORT, specific lessons learned — concrete rules the agent \
can apply on future calls. Focus only on what actually went wrong or could be better.

Reply with JSON only:
{
  "scores": {
    "naturalness": <1-5>,
    "empathy": <1-5>,
    "med_check": <1-5>,
    "hooks": <1-5>,
    "close": <1-5>
  },
  "overall": <1-5>,
  "lessons": [
    "<specific actionable rule>",
    "<specific actionable rule>"
  ]
}"""


def evaluate(
    history: list[dict],
    patient_name: str,
    med_summary: str,
    notes: str = "",
) -> dict[str, Any]:
    transcript = "\n".join(
        f"{'AGENT' if m['role'] == 'assistant' else 'PATIENT'}: {m['content']}"
        for m in history
        if not m["content"].startswith("[")  # strip context injections
    )

    user_msg = (
        f"Patient: {patient_name}\n"
        f"Medications: {med_summary}\n"
        f"Notes: {notes or 'none'}\n\n"
        f"TRANSCRIPT:\n{transcript}"
    )

    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = resp.content[0].text.strip()
    raw = raw.removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)
