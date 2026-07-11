-- Grandma's Pill Buddy — Supabase schema
-- Run in Supabase SQL Editor (or: supabase db push)

create table caregivers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text not null,
  email text unique,                   -- maps a Supabase auth login to this caregiver
  created_at timestamptz not null default now()
);

create table seniors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text not null unique,
  grandkid_names text[] not null default '{}',
  notes text,                          -- personality hooks: hobbies, recent topics
  date_of_birth date,                  -- medical profile, shown to caregivers
  conditions text[] not null default '{}',
  allergies text[] not null default '{}',
  primary_doctor text,
  created_at timestamptz not null default now()
);
create index seniors_phone_idx on seniors (phone);

-- M:N caregiver <-> senior; exactly one primary per senior (gets the WhatsApp)
create table care_relationships (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id) on delete cascade,
  caregiver_id uuid not null references caregivers(id) on delete cascade,
  relationship text not null default 'family',   -- caregiver's relation to the senior: grandson, nurse, ...
  senior_label text not null default '',          -- senior's relation to the caregiver: grandmother, patient, ...
  is_primary boolean not null default false,
  created_at timestamptz not null default now(),
  unique (senior_id, caregiver_id)
);
create unique index care_rel_one_primary_idx on care_relationships (senior_id) where is_primary;
create index care_rel_caregiver_idx on care_relationships (caregiver_id);

create table medications (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id) on delete cascade,
  name text not null,
  dosage text not null,
  instructions text,                   -- "with food", etc.
  created_at timestamptz not null default now()
);
create index medications_senior_idx on medications (senior_id);

create table schedules (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id) on delete cascade,
  medication_id uuid references medications(id) on delete cascade,  -- optional link
  label text not null default 'medication reminder',  -- what the call is about
  call_time time not null,
  active boolean not null default true,
  last_fired_on date,                  -- scheduler dedup: one call per schedule per day
  created_at timestamptz not null default now()
);
create index schedules_call_time_idx on schedules (call_time) where active;
create index schedules_senior_idx on schedules (senior_id);

-- one-off callbacks ("remind me in 20 min"), from caregiver or the agent itself
create table reminders (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id) on delete cascade,
  due_at timestamptz not null,
  reason text not null default 'medication reminder',
  source text not null default 'caregiver',      -- caregiver | agent
  status text not null default 'pending',        -- pending | done | cancelled
  created_at timestamptz not null default now()
);
create index reminders_due_idx on reminders (due_at) where status = 'pending';

create table call_logs (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id),
  twilio_call_sid text unique,
  status text not null default 'initiated',   -- initiated | in-progress | completed | failed | no-answer
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  transcript_summary text,
  transcript jsonb,                    -- [{speaker, text}, ...] full turn-by-turn
  wellness_note text,                  -- AI note on how they seemed
  call_reason text,                    -- schedule label / reminder reason → agent context
  meds_confirmed boolean,
  digest_sent boolean not null default false
);
create index call_logs_senior_idx on call_logs (senior_id);
create index call_logs_sid_idx on call_logs (twilio_call_sid);

-- AI-generated caregiver to-dos, distilled from current + past calls
create table action_items (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id) on delete cascade,
  text text not null,
  priority text not null default 'normal',     -- normal | high
  status text not null default 'open',         -- open | done
  source_call_id uuid references call_logs(id) on delete set null,
  created_at timestamptz not null default now()
);
create index action_items_senior_idx on action_items (senior_id) where status = 'open';

create table alerts (
  id uuid primary key default gen_random_uuid(),
  call_log_id uuid not null references call_logs(id) on delete cascade,
  type text not null,                  -- health_concern | missed_dose | distress | no_answer
  detail text not null,
  severity text not null default 'info',       -- info | warn | urgent
  sms_sent boolean not null default false,
  created_at timestamptz not null default now()
);
create index alerts_call_idx on alerts (call_log_id);

-- Realtime for the Lovable dashboard (Alerts + Call History panels)
alter publication supabase_realtime add table call_logs;
alter publication supabase_realtime add table alerts;
alter publication supabase_realtime add table reminders;

-- RLS: anon key is read-only (voice agent profile reads, Lovable dashboard).
-- Logged-in caregivers (authenticated) can also read everything and manage
-- schedules/reminders from the dashboard. All other writes go through the
-- backend's service_role key, which bypasses RLS.
alter table caregivers         enable row level security;
alter table seniors            enable row level security;
alter table care_relationships enable row level security;
alter table medications        enable row level security;
alter table schedules          enable row level security;
alter table reminders          enable row level security;
alter table call_logs          enable row level security;
alter table alerts             enable row level security;

create policy "anon read" on caregivers         for select to anon using (true);
create policy "anon read" on seniors            for select to anon using (true);
create policy "anon read" on care_relationships for select to anon using (true);
create policy "anon read" on medications        for select to anon using (true);
create policy "anon read" on schedules          for select to anon using (true);
create policy "anon read" on reminders          for select to anon using (true);
create policy "anon read" on call_logs          for select to anon using (true);
create policy "anon read" on alerts             for select to anon using (true);

create policy "auth read" on caregivers         for select to authenticated using (true);
create policy "auth read" on seniors            for select to authenticated using (true);
create policy "auth read" on care_relationships for select to authenticated using (true);
create policy "auth read" on medications        for select to authenticated using (true);
create policy "auth read" on schedules          for select to authenticated using (true);
create policy "auth read" on reminders          for select to authenticated using (true);
create policy "auth read" on call_logs          for select to authenticated using (true);
create policy "auth read" on alerts             for select to authenticated using (true);

create policy "auth write"  on reminders for insert to authenticated with check (true);
create policy "auth update" on reminders for update to authenticated using (true);
create policy "auth write"  on schedules for insert to authenticated with check (true);
create policy "auth update" on schedules for update to authenticated using (true);
