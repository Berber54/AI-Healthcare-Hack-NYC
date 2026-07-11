-- T2 mock EHR schema (I.data). Run once in the Supabase SQL editor before seed.sql.

create extension if not exists pgcrypto;

create table insurance_plans (
    id uuid primary key default gen_random_uuid(),
    name text not null,
    covered_procedures jsonb not null
);

create table patients (
    id uuid primary key default gen_random_uuid(),
    phone_number text not null unique,
    name text not null,
    last_visit_date date,
    insurance_plan_id uuid references insurance_plans(id)
);

create table appointment_slots (
    id uuid primary key default gen_random_uuid(),
    start_time timestamptz not null,
    slot_type text not null check (slot_type in ('routine', 'urgent', 'emergency')),
    is_booked boolean not null default false,
    patient_id uuid references patients(id),
    booking_reason text
);
