import pytest

pytestmark = pytest.mark.requires_supabase


def test_patient_count_between_3_and_5(supabase_client):
    result = supabase_client.table("patients").select("id").execute()
    assert 3 <= len(result.data) <= 5


def test_exactly_one_insurance_plan(supabase_client):
    result = supabase_client.table("insurance_plans").select("id").execute()
    assert len(result.data) == 1


def test_all_slot_types_seeded(supabase_client):
    for slot_type in ("routine", "urgent", "emergency"):
        result = (
            supabase_client.table("appointment_slots")
            .select("id")
            .eq("slot_type", slot_type)
            .execute()
        )
        assert len(result.data) >= 1, f"no seeded slot of type {slot_type}"
