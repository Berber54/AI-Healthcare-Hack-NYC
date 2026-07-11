import pytest

from app.data import (
    SlotAlreadyBookedError,
    book_slot,
    get_available_slots,
    get_insurance_plan,
    get_patient_by_phone,
)

pytestmark = pytest.mark.requires_supabase

SEEDED_PHONE = "+15550100001"
SEEDED_NAME = "Jane Doe"


def test_get_patient_by_phone_known_number():
    patient = get_patient_by_phone(SEEDED_PHONE)
    assert patient is not None
    assert patient.name == SEEDED_NAME


def test_get_patient_by_phone_unknown_number():
    assert get_patient_by_phone("+19995550000") is None


def test_get_available_slots_filters_by_type_and_booked():
    routine_slots = get_available_slots("routine")
    assert routine_slots
    assert all(slot.slot_type == "routine" for slot in routine_slots)
    assert all(not slot.is_booked for slot in routine_slots)


def test_book_slot_marks_booked_and_sets_reason(supabase_client):
    patient = get_patient_by_phone(SEEDED_PHONE)
    inserted = (
        supabase_client.table("appointment_slots")
        .insert({"start_time": "2026-09-01T09:00:00-04:00", "slot_type": "routine"})
        .execute()
    )
    slot_id = inserted.data[0]["id"]

    try:
        booked = book_slot(slot_id, patient.id, reason="throwaway test booking")
        assert booked.is_booked is True
        assert booked.patient_id == patient.id
        assert booked.booking_reason == "throwaway test booking"
    finally:
        supabase_client.table("appointment_slots").delete().eq("id", slot_id).execute()


def test_book_slot_rejects_double_booking(supabase_client):
    patient = get_patient_by_phone(SEEDED_PHONE)
    inserted = (
        supabase_client.table("appointment_slots")
        .insert({"start_time": "2026-09-02T09:00:00-04:00", "slot_type": "routine"})
        .execute()
    )
    slot_id = inserted.data[0]["id"]

    try:
        book_slot(slot_id, patient.id)
        with pytest.raises(SlotAlreadyBookedError):
            book_slot(slot_id, patient.id)
    finally:
        supabase_client.table("appointment_slots").delete().eq("id", slot_id).execute()


def test_get_insurance_plan_has_expected_procedures():
    plan = get_insurance_plan()
    assert "cleaning" in plan.covered_procedures
    assert "filling" in plan.covered_procedures
