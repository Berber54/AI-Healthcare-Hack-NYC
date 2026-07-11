import pytest


def test_tables_are_queryable(supabase_client):
    assert supabase_client.table("patients").select("*").limit(0).execute() is not None
    assert supabase_client.table("appointment_slots").select("*").limit(0).execute() is not None
    assert supabase_client.table("insurance_plans").select("*").limit(0).execute() is not None


def test_invalid_slot_type_is_rejected(supabase_client):
    with pytest.raises(Exception):
        supabase_client.table("appointment_slots").insert(
            {"start_time": "2026-08-01T09:00:00-04:00", "slot_type": "bogus"}
        ).execute()

    leftover = (
        supabase_client.table("appointment_slots").select("*").eq("slot_type", "bogus").execute()
    )
    assert leftover.data == []


def test_duplicate_phone_number_is_rejected(supabase_client):
    existing = supabase_client.table("patients").select("phone_number").limit(1).execute()
    assert existing.data, "seed.sql must be loaded before running tests"
    phone = existing.data[0]["phone_number"]

    with pytest.raises(Exception):
        supabase_client.table("patients").insert(
            {"phone_number": phone, "name": "Duplicate Test Patient"}
        ).execute()

    dupes = supabase_client.table("patients").select("*").eq("phone_number", phone).execute()
    assert len(dupes.data) == 1
