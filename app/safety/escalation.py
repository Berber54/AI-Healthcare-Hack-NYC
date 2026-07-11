"""T5 — emergency escalation path. Invariants 2, 3, 4, 7.

Once app/safety/red_flags.check_red_flag flags a turn, this module is the only
thing allowed to respond — the LLM gets no discretion (Invariant 2). Scripted
messages are fixed strings, not model output.
"""

from __future__ import annotations

from app.safety import tools
from app.safety.contract import (
    CallContext,
    EscalationOutcome,
    RedFlagCategory,
    RedFlagResult,
    ToolCallRecord,
)
from app.safety.logging_hook import log_event

SCRIPT_NON_DENTAL_911 = (
    "This sounds like it could be a medical emergency, not a dental one. "
    "Please hang up and call 911, or go to the nearest emergency room right now. "
    "I'm not able to book an appointment for this — your safety comes first."
)

SCRIPT_DENTAL_EMERGENCY = (
    "This sounds like a dental emergency. I'm booking you the next available "
    "emergency slot right now and connecting you with our on-call team."
)


def enforce_tool_before_hangup(outcome: EscalationOutcome) -> None:
    """Invariant 7 guard: never let a call-ending outcome carry zero tool calls."""
    if outcome.call_may_end and not outcome.tool_calls:
        raise RuntimeError(
            "Invariant 7 violated: escalation outcome allows the call to end "
            "with no tool call fired"
        )


def _handle_non_dental(result: RedFlagResult, call_context: CallContext) -> EscalationOutcome:
    reason = f"non_dental_red_flag:{','.join(result.matched_keywords)}"
    tool_calls: list[ToolCallRecord] = [
        tools.escalate_to_oncall(reason=reason, patient_info=call_context.patient_info)
    ]
    return EscalationOutcome(
        category=result.category,
        message=SCRIPT_NON_DENTAL_911,
        tool_calls=tool_calls,
        allow_booking=False,
        call_may_end=True,
    )


def _handle_dental_emergency(result: RedFlagResult, call_context: CallContext) -> EscalationOutcome:
    reason = f"dental_emergency:{','.join(result.matched_keywords)}"
    booking = tools.book_urgent_slot(reason=reason, patient_info=call_context.patient_info)

    if call_context.transfer_available:
        second_call = tools.transfer_call(
            call_sid=call_context.call_sid, to_number=call_context.oncall_number
        )
    else:
        second_call = tools.escalate_to_oncall(
            reason=reason, patient_info=call_context.patient_info, urgent=True
        )

    return EscalationOutcome(
        category=result.category,
        message=SCRIPT_DENTAL_EMERGENCY,
        tool_calls=[booking, second_call],
        allow_booking=True,
        call_may_end=True,
    )


def handle_red_flag_turn(result: RedFlagResult, call_context: CallContext) -> EscalationOutcome:
    if not result.is_red_flag:
        raise ValueError("handle_red_flag_turn called on a non-red-flag RedFlagResult")

    log_event(
        {
            "event": "red_flag_escalation",
            "call_sid": call_context.call_sid,
            "category": result.category.value,
            "matched_keywords": result.matched_keywords,
        }
    )

    if result.category is RedFlagCategory.NON_DENTAL_EMERGENCY:
        outcome = _handle_non_dental(result, call_context)
    else:
        outcome = _handle_dental_emergency(result, call_context)

    enforce_tool_before_hangup(outcome)

    log_event(
        {
            "event": "escalation_tool_calls",
            "call_sid": call_context.call_sid,
            "tool_calls": [
                {"name": tc.name, "status": tc.status} for tc in outcome.tool_calls
            ],
        }
    )

    return outcome
