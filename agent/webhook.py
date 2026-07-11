from fastapi import APIRouter

from agent import session_store
from agent.triage_prompt import build_greeting_context

router = APIRouter()

# TODO(T2): replace stub returns once Person B's Supabase mock EHR lands.


def _lookup_patient(caller_id: str) -> dict | None:
    return None  # TODO(T2): query Supabase patient_with_insurance view by caller_id


@router.post("/elevenlabs/personalize")
async def personalize(body: dict):
    # Invariants 5, 9: ElevenLabs calls this before the call connects (native
    # Twilio integration bypasses our /voice route — see SPEC.md Invariant 8 note).
    patient = _lookup_patient(body["caller_id"])

    # I.web_input: link call_sid <-> caller phone so the web input bar and the
    # get_web_input tool can find each other. TODO(T6, Person B): send the
    # /input/{call_sid} link via SMS once post-call SMS lands.
    call_sid = body.get("call_sid")
    if call_sid:
        session_store.link_call(call_sid, body.get("caller_id"))

    return {
        "type": "conversation_initiation_client_data",
        "dynamic_variables": {
            "greeting_context": build_greeting_context(patient),
            "call_sid": call_sid or "",
        },
    }


def _book_appointment(params: dict) -> dict:
    return {"status": "booked", "slot": params["slot"], "type": params["type"]}


def _book_urgent_slot(params: dict) -> dict:
    return {"status": "booked", "reason": params["reason"], "slot": "next available"}


def _check_insurance(params: dict) -> dict:
    return {"plan_id": params["plan_id"], "procedure": params["procedure"], "covered": "unknown — data layer pending"}


def _get_web_input(params: dict) -> dict:
    entries = session_store.get_entries(params["call_sid"])
    return {"entries": entries} if entries else {"entries": [], "note": "nothing submitted yet"}


TOOL_HANDLERS = {
    "book_appointment": _book_appointment,
    "book_urgent_slot": _book_urgent_slot,
    "check_insurance": _check_insurance,
    "get_web_input": _get_web_input,
}


@router.post("/tools/{tool_name}")
async def call_tool(tool_name: str, body: dict):
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"unknown tool {tool_name}"}
    return {"result": handler(body["parameters"])}
