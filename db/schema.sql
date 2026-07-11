-- Grandma's Pill Buddy — Supabase schema
-- Run in Supabase SQL Editor (or: supabase db push)

create table caregivers (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text not null,
  created_at timestamptz not null default now()
);

create table seniors (
  id uuid primary key default gen_random_uuid(),
  name text not null,
  phone text not null unique,
  grandkid_names text[] not null default '{}',
  notes text,                          -- personality hooks: hobbies, recent topics
  caregiver_id uuid not null references caregivers(id),
  created_at timestamptz not null default now()
);
create index seniors_phone_idx on seniors (phone);

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
  medication_id uuid not null references medications(id) on delete cascade,
  call_time time not null,
  active boolean not null default true,
  created_at timestamptz not null default now()
);
create index schedules_call_time_idx on schedules (call_time) where active;

create table call_logs (
  id uuid primary key default gen_random_uuid(),
  senior_id uuid not null references seniors(id),
  twilio_call_sid text unique,
  status text not null default 'initiated',   -- initiated | in-progress | completed | failed | no-answer
  started_at timestamptz not null default now(),
  ended_at timestamptz,
  transcript_summary text,
  meds_confirmed boolean,
  digest_sent boolean not null default false
);
create index call_logs_senior_idx on call_logs (senior_id);
create index call_logs_sid_idx on call_logs (twilio_call_sid);

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
