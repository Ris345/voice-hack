# Voice Agent ↔ Backend Contract

For the voice-agent dev (Rishav). The backend owns Supabase writes, escalation
SMS, and the caregiver digest — your agent just calls three things.

## What the backend gives you

When the backend triggers a call, Twilio requests TwiML from your endpoint with
the call context in the query string:

```
POST <VOICE_AGENT_TWIML_URL>?call_log_id=<uuid>
```

Keep `call_log_id` — it's the key for everything you send back.

## Reading the senior's profile

Read Supabase directly (URL + anon key in the shared env, tables are seeded):

- `seniors` — name, phone, `grandkid_names[]`, `notes` (personality hooks for chat)
- `medications` — name, dosage, instructions (filter by `senior_id`)
- `schedules` — which med this call is about (`call_time`)

Or ask us and we'll add a `GET /seniors/{id}/context` endpoint that bundles it.

## What your agent must call (backend base URL in shared env)

### 1. Mid-call, the moment you detect a concern
```
POST /alerts
{ "call_log_id": "...", "type": "health_concern|missed_dose|distress",
  "detail": "Rose said her knee pain is much worse today", "severity": "info|warn|urgent" }
```
Backend writes the alert row (dashboard updates live) **and** SMSes the
caregiver immediately. Don't batch these — fire as soon as you classify.

### 2. When the conversation ends
```
POST /calls/{call_log_id}/result
{ "transcript_summary": "Chatted about the garden; confirmed evening Metformin.",
  "meds_confirmed": true }
```
This marks the call completed and triggers the caregiver digest SMS. Keep the
summary 1–2 sentences, plain English — it goes verbatim into the SMS.

### 3. Nothing else
No-answer, call-status bookkeeping, and digest fallback are handled by the
backend via Twilio status callbacks. If your agent crashes mid-call, the
caregiver still gets a digest.

## Guardrail expectations (judged!)

- Never give new medical advice. Deflect + `POST /alerts` instead.
- Anything urgent-sounding (chest pain, fall, dizziness) → `severity: "urgent"`.

## Demo phone numbers

Seed data keys seniors to phone numbers (`db/seed.sql`). Before the demo we
swap in real cell numbers for whoever plays grandma + caregiver.
