"""
Conversational AI agent — drives the pill check phone call via Claude.

Stages: greeting → med_check → wellness → closing
Returns structured dict so main.py can build TwiML and write flags.
"""

import json
import os
from typing import Any

import anthropic

_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
_MODEL = "claude-sonnet-4-6"

_SYSTEM = """You are Pill Buddy, a warm voice assistant that calls elderly patients \
to check on their medications and wellbeing.

Rules:
- Keep responses to 1-2 sentences — this is a phone call
- Use the patient's first name
- Be encouraging, never scolding
- Plain spoken English only — no asterisks, lists, or markdown

You MUST reply with JSON only:
{
  "speech": "<what to say aloud>",
  "next_stage": "<greeting|med_check|wellness|closing>",
  "med_status": "<taken|missed|unknown>",
  "should_close": <true|false>
}

Stage flow (follow in order):
  greeting  → introduce yourself, ask how they are
  med_check → ask if they took their medications today
  wellness  → one brief wellness question
  closing   → warm goodbye; set should_close: true

med_status stays "unknown" until the patient clearly answers the med question.
If the patient says goodbye or wants to hang up, jump straight to closing."""


def _strip_json(raw: str) -> dict[str, Any]:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def _goodbye_signal(text: str) -> bool:
    hits = ["goodbye", "bye", "got to go", "gotta go", "talk later", "hang up"]
    return any(h in text.lower() for h in hits)


def run_turn(
    history: list[dict],
    stage: str,
    user_speech: str,
    patient_name: str,
    med_summary: str,
) -> dict[str, Any]:
    """
    Process one conversation turn.

    history   — list of {role, content} accumulated this call
    stage     — current stage string
    user_speech — what the patient just said (empty string on first turn)
    """
    context = (
        f"[Patient: {patient_name} | Meds today: {med_summary} | Stage: {stage}]"
    )
    user_content = context + "\n" + (user_speech or "(call just connected)")

    if _goodbye_signal(user_speech):
        user_content += "\n[Patient signalled end of call — move to closing]"

    messages = history + [{"role": "user", "content": user_content}]

    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=200,
        system=_SYSTEM,
        messages=messages,
    )
    raw = resp.content[0].text
    result = _strip_json(raw)

    result.setdefault("speech", "I'm sorry, could you repeat that?")
    result.setdefault("next_stage", stage)
    result.setdefault("med_status", "unknown")
    result.setdefault("should_close", False)
    result["_assistant_raw"] = raw
    return result
