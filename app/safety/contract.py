"""Integration contract for the safety-escalation module (Person D: T4/T5).

feat/telephony (I.twilio) and feat/triage-conversation (I.claude) haven't merged
yet, so this module defines the shapes the turn loop will call into:

    from app.safety.red_flags import check_red_flag
    from app.safety.escalation import handle_red_flag_turn

    result = check_red_flag(user_turn_text)
    if result.is_red_flag:
        outcome = handle_red_flag_turn(result, call_context)
        # speak outcome.message, then the call may end — Invariant 2/7 already
        # enforced tool_calls fired before outcome.call_may_end is trusted.
    else:
        ...  # normal LLM-driven triage flow (Person C's territory)
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum


class RedFlagCategory(Enum):
    NONE = "none"
    NON_DENTAL_EMERGENCY = "non_dental_emergency"
    DENTAL_EMERGENCY = "dental_emergency"


@dataclass(frozen=True)
class RedFlagResult:
    category: RedFlagCategory
    matched_keywords: list[str]
    raw_turn_text: str

    @property
    def is_red_flag(self) -> bool:
        return self.category is not RedFlagCategory.NONE


@dataclass(frozen=True)
class CallContext:
    """Minimal fields the escalation path needs from the live call session.

    Populated by whoever owns the webhook (feat/telephony) once T1 lands.
    call_sid/transfer_available are real Twilio-call fields; patient_info
    comes from the I.data lookup (feat/data-knowledge), pass {} until wired.
    """

    call_sid: str
    patient_info: dict = field(default_factory=dict)
    transfer_available: bool = True
    oncall_number: str = ""


@dataclass(frozen=True)
class ToolCallRecord:
    name: str
    args: dict
    status: str


@dataclass(frozen=True)
class EscalationOutcome:
    category: RedFlagCategory
    message: str
    tool_calls: list[ToolCallRecord]
    allow_booking: bool
    call_may_end: bool
