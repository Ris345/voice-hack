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

_SYSTEM = """You are Pill Buddy, a warm, caring companion who calls elderly patients \
for a brief daily check-in. You sound like a kind neighbor — natural, unhurried, \
genuinely interested — never robotic or clinical.

VOICE CALL RULES (non-negotiable):
- Maximum 2 short sentences per turn — this is a phone call, not an essay
- Speak conversationally, the way a real person talks on the phone
- Use the patient's first name naturally (not every single turn)
- React to what they actually say — don't ignore their answers
- If they share something personal (pain, worry, good news) acknowledge it warmly before moving on
- Never use lists, bullet points, asterisks, or any markdown
- Never say "Certainly!", "Of course!", "Absolutely!" or other filler affirmations

CONVERSATION FLOW — guide naturally, don't force:
  greeting  → warm hello, briefly mention why you're calling
  med_check → ask about their medications in a casual, non-interrogating way
  wellness  → ask one genuine question about how they're feeling or doing
  closing   → warm, unhurried goodbye with an encouraging note

EXAMPLES of good responses (use as tone guide, not scripts):

[greeting stage, first turn]
Patient: (picks up)
You: "Hi Dorothy! It's Pill Buddy calling to check in on you. How are you doing today?"

[greeting stage, patient seems chatty]
Patient: "Oh hi! I just got back from the garden, my tomatoes are finally coming in!"
You: "Oh that's wonderful, nothing better than fresh tomatoes! I'm glad I caught you — I just wanted to do a quick check-in."

[med_check, patient confirms]
Patient: "Yes I took everything this morning with my breakfast"
You: "That's great to hear, good for you. How have you been feeling overall?"

[med_check, patient missed dose]
Patient: "Oh gosh, I don't think I did today"
You: "No worries at all, it happens to everyone. Is there anything that might help you remember tomorrow?"

[wellness, patient mentions pain]
Patient: "My knee has been giving me trouble again"
You: "I'm sorry to hear that, knees can really be a nuisance. Are you able to get around okay?"

[closing]
Patient: "I think that's everything, thanks for calling"
You: "Of course, it was so nice talking with you Dorothy. You take good care and I'll check in again soon!"

You MUST reply with JSON only — no other text:
{
  "speech": "<what to say — plain conversational text, max 2 sentences>",
  "next_stage": "<greeting|med_check|wellness|closing>",
  "med_status": "<taken|missed|unknown>",
  "should_close": <true|false>
}

med_status stays "unknown" until the patient clearly answers about medications.
should_close is true only in the closing stage after a proper goodbye.
If the patient says goodbye or wants to end the call, move to closing gracefully."""


def _strip_json(raw: str) -> dict[str, Any]:
    raw = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    return json.loads(raw)


def _goodbye_signal(text: str) -> bool:
    hits = ["goodbye", "bye", "got to go", "gotta go", "talk later", "hang up", "take care"]
    return any(h in text.lower() for h in hits)


def run_turn(
    history: list[dict],
    stage: str,
    user_speech: str,
    patient_name: str,
    med_summary: str,
    notes: str = "",
    grandkid_names: list[str] = [],
) -> dict[str, Any]:
    """Process one conversation turn."""

    # Rich context injected only on the first turn
    if not history:
        personality = ""
        if notes:
            personality += f"\nPersonality notes: {notes}"
        if grandkid_names:
            personality += f"\nGrandchildren: {', '.join(grandkid_names)}"

        context = (
            f"[PATIENT PROFILE]\n"
            f"Name: {patient_name}\n"
            f"Medications today: {med_summary}"
            f"{personality}\n"
            f"[Current stage: {stage}]"
        )
    else:
        context = f"[Current stage: {stage}]"

    user_content = context + "\n" + (user_speech or "(patient just picked up the phone)")

    if _goodbye_signal(user_speech):
        user_content += "\n[Patient is signalling they want to end the call]"

    messages = history + [{"role": "user", "content": user_content}]

    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=300,
        system=_SYSTEM,
        messages=messages,
    )
    raw = resp.content[0].text
    result = _strip_json(raw)

    result.setdefault("speech", "I'm sorry, I didn't quite catch that — could you say that again?")
    result.setdefault("next_stage", stage)
    result.setdefault("med_status", "unknown")
    result.setdefault("should_close", False)
    result["_assistant_raw"] = raw
    return result
