# Lovable Caregiver Portal — paste-in prompt (v2)

## Before pasting

1. In Lovable: **Settings → Integrations → Supabase** → connect project
   `svvmarfbnrabmtcyjufm`. **This must be done first** — if Lovable was never
   connected, it builds against mock data and the app shows nothing.
2. If a previous version of the app exists, paste this as a follow-up prompt
   ("rebuild the app as follows…").

Demo login (already created in Supabase auth): `grandson@demo.com` / `pillbuddy123`

---

Build "Pill Buddy", a caregiver portal for a voice AI that calls seniors to
check on their medications. Warm, friendly design — soft colors, rounded
cards, large readable text. Supabase is already connected; use it for BOTH
auth and data, with realtime subscriptions so new rows appear without refresh.

AUTH: email/password login via Supabase auth. After login, find the caregiver
row in `caregivers` where `email` = the logged-in user's email. Show their
name in the header.

DATA MODEL (all in Supabase):
- `caregivers` (id, name, phone, email)
- `seniors` (id, name, phone, grandkid_names, notes)
- `care_relationships` (senior_id, caregiver_id, relationship, is_primary) —
  which seniors this caregiver tracks
- `medications` (senior_id, name, dosage, instructions)
- `schedules` (medication_id, call_time, active) — daily reminder-call times
- `reminders` (senior_id, due_at, reason, source, status) — one-off callbacks
- `call_logs` (senior_id, status, started_at, transcript_summary, transcript
  jsonb [{speaker, text}], wellness_note, meds_confirmed)
- `alerts` (call_log_id, type, detail, severity, sms_sent, created_at)

PAGES:

1. **My Loved Ones (home)** — a card per senior this caregiver tracks (join
   care_relationships → seniors, filtered by the caregiver id; show the
   relationship label and a "primary caregiver" badge where is_primary).
   Each card: senior name, last call time + status, meds confirmed today
   (✅/❌/—), count of open alerts, 7-day adherence dots. Click → detail page.

2. **Senior detail** — for one senior:
   - Header: name, phone, notes, medication list with dosages
   - **Current state strip**: latest wellness_note, last call summary,
     adherence % over last 7 days
   - **Call history**: table of call_logs newest-first — time, status,
     meds_confirmed, transcript_summary. Each row expands (or opens a modal)
     to show the FULL transcript from the `transcript` jsonb column, rendered
     as a chat thread (agent left, senior right).
   - **Alerts timeline**: alerts for this senior's calls, severity badges
     (urgent = red, warn = amber, info = blue), "WhatsApp sent ✓" indicator.
   - **Schedules panel**: list schedules for this senior's medications with
     an edit control (time picker, active toggle) writing back to `schedules`;
     plus "Schedule a one-off reminder call" (datetime + reason) inserting
     into `reminders` with source 'caregiver' and status 'pending'.

3. **Alerts (global)** — live feed across all tracked seniors, newest first,
   realtime. Filter by severity.

Header: "Pill Buddy 💊 — Keeping an eye on the people you love."
Realtime subscriptions on call_logs, alerts, reminders. Mobile friendly.

---

After it generates, log in as grandson@demo.com and confirm: Abhinav appears
under My Loved Ones (with Marcus as second caregiver on the detail page),
his call history shows real calls with transcripts, and the alerts feed shows
the seeded test alert.
