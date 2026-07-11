import json
import os
import time

import anthropic
from fastapi import APIRouter
from fastapi.responses import StreamingResponse

from agent import session_store
from agent.triage_prompt import TRIAGE_SYSTEM_PROMPT, build_greeting_context
from agent.triage_tools import TRIAGE_TOOLS
from app import data
from app.logger import log_classification, log_escalation, log_tool_call, log_turn, start_call
from app.safety.contract import CallContext
from app.safety.escalation import handle_red_flag_turn
from app.safety.red_flags import check_red_flag

# Invariant 6: which tool a turn calls implies its triage bucket.
_TOOL_TO_BUCKET = {
    "book_appointment": "booking",
    "book_urgent_slot": "urgent",
    "check_insurance": "insurance",
}

router = APIRouter()

_anthropic_client: anthropic.Anthropic | None = None


def _get_anthropic_client() -> anthropic.Anthropic:
    global _anthropic_client
    if _anthropic_client is None:
        _anthropic_client = anthropic.Anthropic(api_key=os.environ["ANTHROPIC_API_KEY"])
    return _anthropic_client


def _greeting_context_from_patient(patient: data.Patient | None) -> dict | None:
    # Invariants 5, 9: greeting context needs name + last-visit + insurance,
    # not just a patient match.
    if patient is None:
        return None

    result = {
        "name": patient.name,
        "last_visit_date": patient.last_visit_date,
        "insurance_plan_id": patient.insurance_plan_id,
    }
    if patient.insurance_plan_id:
        try:
            plan = data.get_insurance_plan()
            result["plan_name"] = plan.name
        except LookupError:
            pass
    return result


@router.post("/elevenlabs/personalize")
async def personalize(body: dict):
    # Invariants 5, 9: ElevenLabs calls this before the call connects (native
    # Twilio integration bypasses our /voice route — see SPEC.md Invariant 8 note).
    raw_patient = data.get_patient_by_phone(body["caller_id"]) if body.get("caller_id") else None
    patient = _greeting_context_from_patient(raw_patient)

    # I.web_input: link call_sid <-> caller phone so the web input bar and the
    # get_web_input tool can find each other. TODO(T6, Person B): send the
    # /input/{call_sid} link via SMS once post-call SMS lands.
    call_sid = body.get("call_sid")
    if call_sid:
        session_store.link_call(call_sid, body.get("caller_id"))
        # Invariants 6, 11: the call log starts here so a transcript exists
        # even if the caller hangs up before any tool call fires.
        start_call(
            run_id=call_sid,
            phone_number=body.get("caller_id") or "",
            patient_id=raw_patient.id if raw_patient else None,
        )

    return {
        "type": "conversation_initiation_client_data",
        "dynamic_variables": {
            "greeting_context": build_greeting_context(patient),
            "call_sid": call_sid or "",
        },
    }


def _sse_chunk(content: str = "", tool_calls: list[dict] | None = None, finish_reason: str | None = None) -> str:
    delta: dict = {}
    if content:
        delta["content"] = content
    if tool_calls:
        delta["tool_calls"] = tool_calls
    chunk = {
        "id": "chatcmpl-arya",
        "object": "chat.completion.chunk",
        "created": int(time.time()),
        "choices": [{"index": 0, "delta": delta, "finish_reason": finish_reason}],
    }
    return f"data: {json.dumps(chunk)}\n\n"


def _last_user_text(messages: list[dict]) -> str:
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content")
            return content if isinstance(content, str) else str(content)
    return ""


def _call_sid_from_request(body: dict) -> str:
    extra = body.get("elevenlabs_extra_body") or {}
    return extra.get("call_sid") or body.get("user_id") or "unknown"


def _call_context_from_request(body: dict, call_sid: str) -> CallContext:
    phone = session_store.get_phone(call_sid)
    patient = data.get_patient_by_phone(phone) if phone else None
    return CallContext(
        call_sid=call_sid,
        patient_info={"name": patient.name} if patient else {},
        transfer_available=True,
        oncall_number=os.environ.get("ONCALL_PHONE_NUMBER", ""),
    )


@router.post("/elevenlabs/v1/chat/completions")
async def chat_completions(body: dict):
    call_sid = _call_sid_from_request(body)
    user_text = _last_user_text(body.get("messages", []))
    if call_sid != "unknown":
        log_turn(call_sid, "caller", user_text)

    # Invariants 1, 2: the red-flag check runs on every turn before Claude
    # ever sees it — the LLM gets no discretion over escalation (I.claude).
    result = check_red_flag(user_text)

    if result.is_red_flag:
        outcome = handle_red_flag_turn(result, _call_context_from_request(body, call_sid))
        if call_sid != "unknown":
            log_escalation(call_sid, outcome.category.value, ",".join(result.matched_keywords))
            log_turn(call_sid, "agent", outcome.message)

        async def escalation_stream():
            yield _sse_chunk(content=outcome.message)
            yield _sse_chunk(finish_reason="stop")
            yield "data: [DONE]\n\n"

        return StreamingResponse(escalation_stream(), media_type="text/event-stream")

    system_prompt = next(
        (m["content"] for m in body.get("messages", []) if m.get("role") == "system"),
        TRIAGE_SYSTEM_PROMPT,
    )
    claude_messages = [m for m in body.get("messages", []) if m.get("role") != "system"]

    def _call_claude():
        return _get_anthropic_client().messages.create(
            model="claude-sonnet-5",
            max_tokens=1024,
            system=system_prompt,
            messages=claude_messages,
            tools=TRIAGE_TOOLS,
        )

    # Invariant 12: retry once, then a scripted fallback — never crash silently.
    try:
        response = _call_claude()
    except anthropic.APIError:
        try:
            response = _call_claude()
        except anthropic.APIError:

            async def fallback_stream():
                yield _sse_chunk(
                    content="Sorry, I'm having trouble connecting right now. "
                    "Please hold, or call back in a few minutes."
                )
                yield _sse_chunk(finish_reason="stop")
                yield "data: [DONE]\n\n"

            return StreamingResponse(fallback_stream(), media_type="text/event-stream")

    if call_sid != "unknown":
        for block in response.content:
            if block.type == "text" and block.text:
                log_turn(call_sid, "agent", block.text)
            elif block.type == "tool_use" and block.name in _TOOL_TO_BUCKET:
                log_classification(call_sid, _TOOL_TO_BUCKET[block.name])

    async def claude_stream():
        for block in response.content:
            if block.type == "text":
                yield _sse_chunk(content=block.text)
            elif block.type == "tool_use":
                yield _sse_chunk(
                    tool_calls=[
                        {
                            "index": 0,
                            "id": block.id,
                            "type": "function",
                            "function": {"name": block.name, "arguments": json.dumps(block.input)},
                        }
                    ]
                )
        yield _sse_chunk(finish_reason="stop")
        yield "data: [DONE]\n\n"

    return StreamingResponse(claude_stream(), media_type="text/event-stream")


def _book_appointment(params: dict, body: dict) -> dict:
    slots = {s.start_time.isoformat(): s for s in data.get_available_slots()}
    slot = slots.get(params["slot"])
    if slot is None:
        return {"status": "error", "message": f"no open slot at {params['slot']}"}
    try:
        booked = data.book_slot(slot.id, patient_id=None, reason=params.get("type"))
    except data.SlotAlreadyBookedError:
        return {"status": "error", "message": "slot was just booked by someone else"}
    return {"status": "booked", "slot": booked.start_time.isoformat(), "type": params["type"]}


def _book_urgent_slot(params: dict, body: dict) -> dict:
    slots = data.get_available_slots(slot_type="urgent")
    if not slots:
        return {"status": "error", "message": "no urgent slots available"}
    soonest = slots[0]
    try:
        booked = data.book_slot(soonest.id, patient_id=None, reason=params["reason"])
    except data.SlotAlreadyBookedError:
        return {"status": "error", "message": "slot was just booked by someone else"}
    return {"status": "booked", "reason": params["reason"], "slot": booked.start_time.isoformat()}


def _check_insurance(params: dict, body: dict) -> dict:
    plan = data.get_insurance_plan()
    if plan.id != params.get("plan_id"):
        return {"plan_id": params["plan_id"], "procedure": params["procedure"], "covered": "unknown — no matching plan on file"}
    coverage = plan.covered_procedures.get(params["procedure"])
    if coverage is None:
        return {"plan_id": params["plan_id"], "procedure": params["procedure"], "covered": "unknown — procedure not on file"}
    return {"plan_id": params["plan_id"], "procedure": params["procedure"], **coverage}


def _get_web_input(params: dict, body: dict) -> dict:
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
    result = handler(body["parameters"], body)

    # Invariant 6: every live tool call is recorded against the run's log.
    call_sid = body["parameters"].get("call_sid") or _call_sid_from_request(body)
    if call_sid != "unknown":
        log_tool_call(call_sid, tool_name, body["parameters"], result)

    return {"result": result}
