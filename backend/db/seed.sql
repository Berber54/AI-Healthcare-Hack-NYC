-- T2 mock EHR seed data (I.data). Run after schema.sql. Purely fabricated — no real
-- patients, no real clinical claims. Fixed UUIDs so phone numbers/slots are known
-- values to test against.

insert into insurance_plans (id, name, covered_procedures) values (
    '11111111-1111-1111-1111-111111111111',
    'Delta Dental PPO Mock',
    '{
        "cleaning": {"covered": true, "copay": 0},
        "filling": {"covered": true, "copay": 50},
        "extraction": {"covered": true, "copay": 150},
        "root_canal": {"covered": true, "copay": 400},
        "crown": {"covered": false, "copay": null}
    }'::jsonb
);

insert into patients (id, phone_number, name, last_visit_date, insurance_plan_id) values
    ('21111111-1111-1111-1111-111111111111', '+15550100001', 'Jane Doe',          '2026-03-15', '11111111-1111-1111-1111-111111111111'),
    ('21111111-1111-1111-1111-111111111112', '+15550100002', 'Miguel Alvarez',    '2025-11-02', '11111111-1111-1111-1111-111111111111'),
    ('21111111-1111-1111-1111-111111111113', '+15550100003', 'Priya Natarajan',   '2026-01-20', '11111111-1111-1111-1111-111111111111'),
    ('21111111-1111-1111-1111-111111111114', '+15550100004', 'Wei Chen',          '2025-08-09', null),
    ('21111111-1111-1111-1111-111111111115', '+15550100005', 'Sofia Russo',       '2026-05-30', '11111111-1111-1111-1111-111111111111');

insert into appointment_slots (start_time, slot_type) values
    ('2026-07-14 09:00:00-04', 'routine'),
    ('2026-07-14 11:00:00-04', 'routine'),
    ('2026-07-15 09:00:00-04', 'routine'),
    ('2026-07-15 14:00:00-04', 'routine'),
    ('2026-07-16 10:00:00-04', 'routine'),
    ('2026-07-16 15:00:00-04', 'routine'),
    ('2026-07-11 16:00:00-04', 'urgent'),
    ('2026-07-12 10:00:00-04', 'urgent'),
    ('2026-07-11 13:00:00-04', 'emergency'),
    ('2026-07-11 17:00:00-04', 'emergency');
