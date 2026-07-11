-- Demo seed data — Grandma's Pill Buddy
-- IMPORTANT: replace the phone numbers below with your team's real cell numbers
-- before the demo so calls/WhatsApp actually reach the people on stage.

insert into caregivers (id, name, phone, email) values
  ('c0000000-0000-0000-0000-000000000001', 'Grandson', '+19176559764', 'grandson@demo.com'),
  ('c0000000-0000-0000-0000-000000000002', 'Marcus (son)', '+15550002002', null);

insert into seniors (id, name, phone, grandkid_names, notes) values
  ('a0000000-0000-0000-0000-000000000001', 'Abhinav', '+19293312368',
   '{Grandson}',
   'Suffering from amnesia — often forgets whether he has taken his medication today. Be extra gentle and patient; confirm each medication clearly.'),
  ('a0000000-0000-0000-0000-000000000002', 'Harold Chen', '+15550001002',
   '{Lily}',
   'Retired mailman, walks every morning. Proud of Lily''s soccer season.');

-- who tracks whom; exactly one primary per senior (primary gets the WhatsApp)
insert into care_relationships (senior_id, caregiver_id, relationship, is_primary) values
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'grandson', true),
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000002', 'son', false),
  ('a0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000002', 'family', true);

insert into medications (id, senior_id, name, dosage, instructions) values
  ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001',
   'Lisinopril', '10mg', 'once daily, morning'),
  ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001',
   'Metformin', '500mg', 'twice daily, with food'),
  ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000002',
   'Atorvastatin', '20mg', 'once daily, evening');

insert into schedules (medication_id, call_time, active) values
  ('b0000000-0000-0000-0000-000000000001', '09:00', true),
  ('b0000000-0000-0000-0000-000000000002', '18:00', true),
  ('b0000000-0000-0000-0000-000000000003', '19:00', true);
