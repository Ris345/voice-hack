# Lovable Dashboard — paste-in prompt

1. Go to lovable.dev → new project.
2. Connect Supabase via Lovable's native integration (Settings → Integrations →
   Supabase) — do this FIRST so it generates against the real schema.
3. Paste the prompt below.

---

Build a caregiver dashboard called "Pill Buddy" for a voice AI that calls
seniors to check on their medications. Warm, friendly design — soft colors,
rounded cards, large readable text. Data lives in Supabase (already connected);
use supabase realtime subscriptions so new rows appear without refresh.

Three sections:

1. **Alerts** (top, most prominent): live feed from the `alerts` table joined
   through `call_logs` to `seniors` (senior name). Show severity as a colored
   badge (urgent = red, warn = amber, info = blue), the `detail` text, time
   ago, and an "SMS sent ✓" indicator when `sms_sent` is true. Newest first.

2. **Call History**: table of `call_logs` joined to `seniors` — senior name,
   started_at, status, meds_confirmed (✅/❌/—), transcript_summary. Newest
   first, realtime.

3. **Adherence Tracking**: per senior, a 7-day grid of daily med confirmation
   computed from `call_logs` (meds_confirmed by day), plus an adherence
   percentage. Simple green/red/gray day dots.

Header: "Pill Buddy 💊" with a subtitle "Keeping an eye on the people you love."
Single page, no auth for the demo, mobile friendly.

---

After it generates: verify it reads the seeded rows (2 seniors), then trigger a
test call and watch the Alerts panel update live — that's the demo beat.
