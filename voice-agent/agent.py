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
_learnings: list[str] = []


def set_learnings(lessons: list[str]) -> None:
    global _learnings
    _learnings = lessons

_SYSTEM = """You are Emily from Pill Buddy, a warm, caring companion who calls elderly \
patients for a brief daily check-in. Introduce yourself as "Emily from Pill Buddy" and \
refer to yourself as Emily. You sound like a kind neighbor — natural, unhurried, \
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
You: "Hi Dorothy! It's Emily from Pill Buddy calling to check in on you. How are you doing today?"

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

REMINDERS — you can schedule a real callback:
If the patient asks to be called back or reminded later ("call me again in 20
minutes", "remind me tonight", "I'll take it in an hour, check on me then"),
set reminder_minutes to how many minutes from now the callback should happen,
and confirm it in your speech ("I'll give you a ring in 20 minutes then!").
Otherwise reminder_minutes is null. Only set it when the patient clearly asks.

You MUST reply with JSON only — no other text:
{
  "speech": "<what to say — plain conversational text, max 2 sentences>",
  "next_stage": "<greeting|med_check|wellness|closing>",
  "med_status": "<taken|missed|unknown>",
  "should_close": <true|false>,
  "reminder_minutes": <number|null>
}

med_status stays "unknown" until the patient clearly answers about medications.
should_close is true only in the closing stage after a proper goodbye.
If the patient says goodbye or wants to end the call, move to closing gracefully."""


def _strip_json(raw: str) -> dict[str, Any]:
    cleaned = raw.strip().removeprefix("```json").removeprefix("```").removesuffix("```").strip()
    if not cleaned:
        raise ValueError(f"Claude returned empty response. Raw: {raw!r}")
    # Find the first { ... } block in case Claude adds surrounding text
    start = cleaned.find("{")
    end = cleaned.rfind("}") + 1
    if start != -1 and end > start:
        cleaned = cleaned[start:end]
    return json.loads(cleaned)


def _goodbye_signal(text: str) -> bool:
    hits = ["goodbye", "bye", "got to go", "gotta go", "talk later", "hang up"]
    return any(h in text.lower() for h in hits)


def run_turn(
    history: list[dict],
    stage: str,
    user_speech: str,
    patient_name: str,
    med_summary: str,
    notes: str = "",
    grandkid_names: list[str] | None = None,
    past_calls: str = "",
    call_reason: str = "",
) -> dict[str, Any]:
    """Process one conversation turn."""

    grandkids = grandkid_names or []

    # Rich context injected only on the first turn
    if not history:
        personality = ""
        if call_reason:
            personality += (
                f"\nWhy you're calling right now: {call_reason} — mention this "
                f"naturally when you check in (it's the point of the call)."
            )
        if notes:
            personality += f"\nPersonality notes: {notes}"
        if grandkids:
            personality += f"\nGrandchildren: {', '.join(grandkids)}"
        if past_calls:
            personality += (
                f"\nRecent check-ins (use for continuity — follow up naturally on "
                f"things they mentioned, e.g. 'how's the knee feeling today?', and "
                f"gently re-confirm anything that was missed; never recite this list):\n"
                f"{past_calls}"
            )

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

    clean_history = [m for m in history if m.get("content", "").strip()]
    messages = clean_history + [{"role": "user", "content": user_content}]

    system = _SYSTEM
    if _learnings:
        system += "\n\nLESSONS FROM PREVIOUS CALLS (apply these):\n" + "\n".join(f"- {l}" for l in _learnings)

    resp = _client.messages.create(
        model=_MODEL,
        max_tokens=300,
        system=system,
        messages=messages,
    )
    raw = resp.content[0].text if resp.content else ""
    try:
        result = _strip_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        print(f"[agent] JSON parse failed: {e} | raw={raw!r}", flush=True)
        result = {}

    result.setdefault("speech", "I'm sorry, I didn't catch that — could you say that again?")
    result.setdefault("next_stage", stage)
    result.setdefault("med_status", "unknown")
    result.setdefault("should_close", False)
    result.setdefault("reminder_minutes", None)
    result["_assistant_raw"] = raw
    return result


def summarize(
    transcript: list[tuple[str, str]], patient_name: str, past_calls: str = "", notes: str = ""
) -> dict[str, Any]:
    """Post-call: caregiver-facing summary, wellness note, and action items —
    informed by this call AND the recent history (recurring pain, repeated
    missed doses, requests for family contact...)."""
    convo = "\n".join(f"{speaker}: {text}" for speaker, text in transcript)
    context = f"Patient: {patient_name}\n"
    if notes:
        context += f"About the patient (match their gender/pronouns in your writing): {notes}\n"
    if past_calls:
        context += f"\nRecent check-in history:\n{past_calls}\n"
    context += f"\nToday's call:\n{convo}"
    try:
        resp = _client.messages.create(
            model=_MODEL,
            max_tokens=500,
            system=(
                "You review an eldercare check-in call for the patient's family "
                "caregiver. Consider today's call AND the recent history — spot "
                "patterns (recurring pain, repeated missed doses, loneliness). "
                "Reply with JSON only: "
                '{"summary": "<2-3 warm plain-English sentences: what was discussed, '
                'medication outcome, anything the family should know>", '
                '"wellness_note": "<1 sentence on mood/health signals>", '
                '"action_items": [{"text": "<concrete thing the caregiver should do, '
                "e.g. 'Ask her doctor about the recurring knee pain — mentioned 3 calls "
                "in a row'>\", \"priority\": \"<normal|high>\"}] — 0 to 3 items, only "
                "genuinely useful ones, empty list if nothing actionable}"
            ),
            messages=[{"role": "user", "content": context}],
        )
        result = _strip_json(resp.content[0].text)
        result.setdefault("action_items", [])
        return result
    except Exception:
        return {
            "summary": f"Completed a check-in call with {patient_name}.",
            "wellness_note": "",
            "action_items": [],
        }
