import os
from pathlib import Path

from fastapi import APIRouter

from agent import session_store
from agent.triage_prompt import build_greeting_context

# app/safety/ (T4/T5, Person D) is a separate top-level "app" package that
# lives at the repo root, deliberately kept out of backend/app/ (CLAUDE.md).
# Both packages are named "app" and backend/app has no __init__.py, so it's
# a namespace package — extending its __path__ to also cover the repo root's
# app/ dir lets `from app.safety import ...` below resolve without touching
# either package's internals. See SPEC.md Bug B6.
import app  # noqa: E402  (backend/app namespace package, not app/safety)

_repo_root_app = Path(__file__).resolve().parents[2] / "app"
if str(_repo_root_app) not in app.__path__:
    app.__path__.append(str(_repo_root_app))

from app.safety import tools as safety_tools  # noqa: E402
from app.safety.contract import CallContext  # noqa: E402
from app.safety.escalation import handle_red_flag_turn  # noqa: E402
from app.safety.red_flags import check_red_flag  # noqa: E402

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


def _call_context(call_sid: str) -> CallContext:
    phone = session_store.get_phone(call_sid)
    patient = _lookup_patient(phone) if phone else None
    return CallContext(
        call_sid=call_sid,
        patient_info=patient or {},
        transfer_available=bool(os.environ.get("ONCALL_PHONE_NUMBER")),
        oncall_number=os.environ.get("ONCALL_PHONE_NUMBER", ""),
    )


def _check_red_flag(params: dict) -> dict:
    """Invariants 1/2/3/4/7: deterministic safety net, not LLM-decided.

    The triage prompt instructs the agent to call this first, every turn,
    with the caller's literal words. If check_red_flag fires, this function
    — not the LLM — decides the outcome and fires the real escalation tool
    calls (booking/transfer/SMS) before returning a fixed script the agent
    must speak verbatim and then end the call. See SPEC.md's Invariant 1/2
    note: calling this tool is still an LLM-initiated action (ElevenLabs
    gives us no true pre-turn hook), so this is the strongest determinism
    available at this integration point, not a 100% LLM-independent guarantee.
    """
    result = check_red_flag(params["text"])
    if not result.is_red_flag:
        return {"red_flag": False}

    outcome = handle_red_flag_turn(result, _call_context(params["call_sid"]))
    return {
        "red_flag": True,
        "category": outcome.category.value,
        "say_verbatim": outcome.message,
        "allow_booking": outcome.allow_booking,
        "end_call": outcome.call_may_end,
        "tool_calls": [{"name": tc.name, "status": tc.status} for tc in outcome.tool_calls],
    }


def _escalate_to_oncall(params: dict) -> dict:
    record = safety_tools.escalate_to_oncall(
        reason=params["reason"],
        patient_info=params.get("patient_info", {}),
        urgent=params.get("urgent", False),
    )
    return {"status": record.status}


def _transfer_call(params: dict) -> dict:
    record = safety_tools.transfer_call(
        call_sid=params["call_sid"],
        to_number=params.get("to_number") or os.environ.get("ONCALL_PHONE_NUMBER", ""),
    )
    return {"status": record.status}


TOOL_HANDLERS = {
    "book_appointment": _book_appointment,
    "book_urgent_slot": _book_urgent_slot,
    "check_insurance": _check_insurance,
    "get_web_input": _get_web_input,
    "check_red_flag": _check_red_flag,
    "escalate_to_oncall": _escalate_to_oncall,
    "transfer_call": _transfer_call,
}


@router.post("/tools/{tool_name}")
async def call_tool(tool_name: str, body: dict):
    handler = TOOL_HANDLERS.get(tool_name)
    if handler is None:
        return {"error": f"unknown tool {tool_name}"}
    return {"result": handler(body["parameters"])}
