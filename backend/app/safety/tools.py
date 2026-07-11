"""I.tools implementations used by the escalation path (T5).

Real Twilio calls, not mocks — the demo needs the live transfer and the SMS to
actually fire (per the escalation-fidelity call: real transfer + real SMS).
book_urgent_slot is a temporary in-memory stub: the real appointment-slot data
lives in feat/data-knowledge's I.data (Supabase) and isn't merged yet. Swap the
body of book_urgent_slot for a real Supabase call once that lands — the
function signature and ToolCallRecord return shape are the contract, keep them
stable so app/safety/escalation.py doesn't need to change.

No adapter/base-class split here on purpose (explicit SPEC.md non-goal) — a
single retry on the Twilio call is the only resilience layer, matching the
build-window budget.
"""

from __future__ import annotations

import os

from twilio.base.exceptions import TwilioRestException
from twilio.rest import Client
from twilio.twiml.voice_response import Dial, VoiceResponse

from app.safety.contract import ToolCallRecord

_client: Client | None = None

# Tiny in-memory stand-in for the real urgent-slot table (feat/data-knowledge).
_URGENT_SLOTS: list[dict] = [
    {"slot_id": "urgent-1", "time": "today +1h"},
    {"slot_id": "urgent-2", "time": "today +2h"},
]


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    return _client


def _with_one_retry(action):
    try:
        return action()
    except TwilioRestException:
        return action()


def transfer_call(call_sid: str, to_number: str) -> ToolCallRecord:
    """Live-transfer an in-progress Twilio call via a REST update (Invariant 4/7).

    Built with Twilio's TwiML response builder rather than string formatting so
    to_number is always emitted as escaped element text, never raw markup —
    matters once CallContext.oncall_number can be sourced from non-static config.
    """
    response = VoiceResponse()
    response.append(Dial(to_number))
    twiml = str(response)
    args = {"call_sid": call_sid, "to": to_number}
    try:
        call = _with_one_retry(lambda: _get_client().calls(call_sid).update(twiml=twiml))
        return ToolCallRecord(name="transfer_call", args=args, status=call.status)
    except TwilioRestException as exc:
        return ToolCallRecord(name="transfer_call", args=args, status=f"failed: {exc}")


def escalate_to_oncall(reason: str, patient_info: dict, urgent: bool = False) -> ToolCallRecord:
    """Send the on-call staff an SMS (Invariant 3/4/7)."""
    prefix = "URGENT" if urgent else "ESCALATION"
    name = patient_info.get("name", "unknown caller")
    body = f"{prefix}: {reason}. Patient: {name}."
    args = {"reason": reason, "patient_info": patient_info, "urgent": urgent}
    try:
        message = _with_one_retry(
            lambda: _get_client().messages.create(
                to=os.environ["ONCALL_PHONE_NUMBER"],
                from_=os.environ["TWILIO_FROM_NUMBER"],
                body=body,
            )
        )
        return ToolCallRecord(name="escalate_to_oncall", args=args, status=message.status)
    except TwilioRestException as exc:
        return ToolCallRecord(name="escalate_to_oncall", args=args, status=f"failed: {exc}")


def book_urgent_slot(reason: str, patient_info: dict | None = None) -> ToolCallRecord:
    """Stub emergency-slot allocator — replace with the real I.data call once merged."""
    args = {"reason": reason, "patient_info": patient_info or {}}
    if not _URGENT_SLOTS:
        return ToolCallRecord(name="book_urgent_slot", args=args, status="no_urgent_slot_available")
    slot = _URGENT_SLOTS.pop(0)
    return ToolCallRecord(name="book_urgent_slot", args={**args, "slot": slot}, status="booked")
