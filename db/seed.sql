-- Demo seed data — Grandma's Pill Buddy
-- IMPORTANT: replace the phone numbers below with your team's real cell numbers
-- before the demo so calls/SMS actually reach the people on stage.
--   +15550001001 → the "grandma" phone (whoever plays the senior)
--   +15550002001 → the "caregiver" phone (judge or teammate who gets the SMS)

insert into caregivers (id, name, phone) values
  ('c0000000-0000-0000-0000-000000000001', 'Priya (daughter)',  '+15550002001'),
  ('c0000000-0000-0000-0000-000000000002', 'Marcus (son)',      '+15550002002');

insert into seniors (id, name, phone, grandkid_names, notes, caregiver_id) values
  ('a0000000-0000-0000-0000-000000000001', 'Rose Thompson', '+15550001001',
   '{Maya,Jaden}',
   'Loves her garden (tomatoes this summer). Knee has been bothering her. Watches Jeopardy every night.',
   'c0000000-0000-0000-0000-000000000001'),
  ('a0000000-0000-0000-0000-000000000002', 'Harold Chen', '+15550001002',
   '{Lily}',
   'Retired mailman, walks every morning. Proud of Lily''s soccer season.',
   'c0000000-0000-0000-0000-000000000002');

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
