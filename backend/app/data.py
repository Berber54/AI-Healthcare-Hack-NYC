"""I.data access layer over the mock EHR (backend/db/schema.sql + seed.sql).

Sync supabase client is a deliberate choice: MVP scale target is a single
concurrent caller, so calling it from FastAPI's async handlers is fine.
"""

import os
from dataclasses import dataclass
from datetime import date, datetime
from typing import Optional

from supabase import Client, create_client

from app.error_recovery import retry_once

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


class SlotAlreadyBookedError(Exception):
    pass


@dataclass
class InsurancePlan:
    id: str
    name: str
    covered_procedures: dict


@dataclass
class Patient:
    id: str
    phone_number: str
    name: str
    last_visit_date: Optional[date]
    insurance_plan_id: Optional[str]


@dataclass
class Slot:
    id: str
    start_time: datetime
    slot_type: str
    is_booked: bool
    patient_id: Optional[str]
    booking_reason: Optional[str]


def get_patient_by_phone(phone: str) -> Optional[Patient]:
    def _read():
        result = _get_client().table("patients").select("*").eq("phone_number", phone).execute()
        return _row_to_patient(result.data[0]) if result.data else None

    return retry_once(_read, fallback=None)


def get_available_slots(slot_type: Optional[str] = None) -> list[Slot]:
    def _read():
        query = _get_client().table("appointment_slots").select("*").eq("is_booked", False)
        if slot_type is not None:
            query = query.eq("slot_type", slot_type)
        result = query.order("start_time").execute()
        return [_row_to_slot(row) for row in result.data]

    return retry_once(_read, fallback=[])


def book_slot(slot_id: str, patient_id: str, reason: Optional[str] = None) -> Slot:
    client = _get_client()

    current = client.table("appointment_slots").select("*").eq("id", slot_id).execute()
    if not current.data:
        raise ValueError(f"No slot with id {slot_id}")
    if current.data[0]["is_booked"]:
        raise SlotAlreadyBookedError(f"Slot {slot_id} is already booked")

    # .eq("is_booked", False) on the update makes this the atomic guard against
    # a concurrent booking racing the check above; the check just gives a
    # clearer error message in the common (non-racing) case.
    result = (
        client.table("appointment_slots")
        .update({"is_booked": True, "patient_id": patient_id, "booking_reason": reason})
        .eq("id", slot_id)
        .eq("is_booked", False)
        .execute()
    )
    if not result.data:
        raise SlotAlreadyBookedError(f"Slot {slot_id} is already booked")
    return _row_to_slot(result.data[0])


def get_insurance_plan() -> Optional[InsurancePlan]:
    def _read():
        result = _get_client().table("insurance_plans").select("*").limit(1).execute()
        if not result.data:
            raise LookupError("No insurance plan seeded")
        return _row_to_plan(result.data[0])

    return retry_once(_read, fallback=None)


def _row_to_patient(row: dict) -> Patient:
    return Patient(
        id=row["id"],
        phone_number=row["phone_number"],
        name=row["name"],
        last_visit_date=row.get("last_visit_date"),
        insurance_plan_id=row.get("insurance_plan_id"),
    )


def _row_to_slot(row: dict) -> Slot:
    return Slot(
        id=row["id"],
        start_time=row["start_time"],
        slot_type=row["slot_type"],
        is_booked=row["is_booked"],
        patient_id=row.get("patient_id"),
        booking_reason=row.get("booking_reason"),
    )


def _row_to_plan(row: dict) -> InsurancePlan:
    return InsurancePlan(
        id=row["id"],
        name=row["name"],
        covered_procedures=row["covered_procedures"],
    )
