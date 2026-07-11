-- Demo seed data — Grandma's Pill Buddy
-- IMPORTANT: replace the phone numbers below with your team's real cell numbers
-- before the demo so calls/WhatsApp actually reach the people on stage.

insert into caregivers (id, name, phone, email) values
  ('c0000000-0000-0000-0000-000000000001', 'Rishav', '+19176559764', 'grandson@demo.com'),
  ('c0000000-0000-0000-0000-000000000002', 'Marcus (son)', '+15550002002', null),
  ('c0000000-0000-0000-0000-000000000003', 'Shreya', '+15550002003', 'shreya@demo.com'),
  ('c0000000-0000-0000-0000-000000000004', 'Maya', '+15550002004', 'maya@demo.com');

insert into seniors (id, name, phone, grandkid_names, notes, date_of_birth, conditions, allergies, primary_doctor) values
  ('a0000000-0000-0000-0000-000000000001', 'Abhinav', '+19293312368',
   '{Rishav}',
   'Suffering from amnesia — often forgets whether she has taken her medication today. Be extra gentle and patient; confirm each medication clearly. Loves her garden and watches Jeopardy every night.',
   '1948-03-14',
   '{Hypertension,"Type 2 diabetes","Mild amnesia — memory lapses","Osteoarthritis (right knee)"}',
   '{Penicillin}',
   'Dr. Patel — Riverside Family Medicine'),
  ('a0000000-0000-0000-0000-000000000002', 'Harold Chen', '+15550001002',
   '{Lily}',
   'Retired mailman, walks every morning. Proud of Lily''s soccer season.',
   null, '{}', '{}', null);

-- who tracks whom; exactly one primary per senior (primary gets the WhatsApp)
insert into care_relationships (senior_id, caregiver_id, relationship, senior_label, is_primary) values
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000001', 'grandson', 'grandmother', true),
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000003', 'granddaughter', 'grandmother', false),
  ('a0000000-0000-0000-0000-000000000001', 'c0000000-0000-0000-0000-000000000004', 'nurse', 'patient', false),
  ('a0000000-0000-0000-0000-000000000002', 'c0000000-0000-0000-0000-000000000002', 'family', 'father', true);

insert into medications (id, senior_id, name, dosage, instructions) values
  ('b0000000-0000-0000-0000-000000000001', 'a0000000-0000-0000-0000-000000000001',
   'Lisinopril', '10mg', 'once daily, morning'),
  ('b0000000-0000-0000-0000-000000000002', 'a0000000-0000-0000-0000-000000000001',
   'Metformin', '500mg', 'twice daily, with food'),
  ('b0000000-0000-0000-0000-000000000003', 'a0000000-0000-0000-0000-000000000002',
   'Atorvastatin', '20mg', 'once daily, evening');

insert into schedules (senior_id, medication_id, label, call_time, active) values
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000001',
   'Medication reminder: Lisinopril 10mg', '09:00', true),
  ('a0000000-0000-0000-0000-000000000001', 'b0000000-0000-0000-0000-000000000002',
   'Medication reminder: Metformin 500mg', '18:00', true),
  ('a0000000-0000-0000-0000-000000000002', 'b0000000-0000-0000-0000-000000000003',
   'Medication reminder: Atorvastatin 20mg', '19:00', true);
