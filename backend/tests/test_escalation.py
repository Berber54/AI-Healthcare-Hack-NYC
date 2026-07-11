"""T5 isolation tests — Twilio calls are monkeypatched, never hit the network."""

import pytest

from app.safety import escalation
from app.safety.contract import CallContext, RedFlagCategory, RedFlagResult, ToolCallRecord
from app.safety.logging_hook import get_logged_events


def _fake_tool_call(name):
    def _call(*args, **kwargs):
        return ToolCallRecord(name=name, args=kwargs, status="ok")

    return _call


@pytest.fixture(autouse=True)
def stub_tools(monkeypatch):
    monkeypatch.setattr(escalation.tools, "transfer_call", _fake_tool_call("transfer_call"))
    monkeypatch.setattr(
        escalation.tools, "escalate_to_oncall", _fake_tool_call("escalate_to_oncall")
    )
    monkeypatch.setattr(
        escalation.tools, "book_urgent_slot", _fake_tool_call("book_urgent_slot")
    )


def _call_context(**overrides):
    defaults = dict(
        call_sid="CA123",
        patient_info={"name": "Jane Doe"},
        transfer_available=True,
        oncall_number="+15550001111",
    )
    defaults.update(overrides)
    return CallContext(**defaults)


def test_non_dental_red_flag_never_books_and_never_transfers():
    result = RedFlagResult(RedFlagCategory.NON_DENTAL_EMERGENCY, ["chest_pain"], "chest pain")
    outcome = escalation.handle_red_flag_turn(result, _call_context())

    names = [tc.name for tc in outcome.tool_calls]
    assert "book_urgent_slot" not in names
    assert "transfer_call" not in names
    assert "escalate_to_oncall" in names
    assert outcome.allow_booking is False
    assert "911" in outcome.message


def test_dental_emergency_books_and_transfers_when_transfer_available():
    result = RedFlagResult(RedFlagCategory.DENTAL_EMERGENCY, ["avulsed_tooth"], "tooth knocked out")
    outcome = escalation.handle_red_flag_turn(result, _call_context(transfer_available=True))

    names = [tc.name for tc in outcome.tool_calls]
    assert names == ["book_urgent_slot", "transfer_call"]
    assert outcome.allow_booking is True


def test_dental_emergency_falls_back_to_urgent_sms_when_transfer_unavailable():
    result = RedFlagResult(RedFlagCategory.DENTAL_EMERGENCY, ["avulsed_tooth"], "tooth knocked out")
    outcome = escalation.handle_red_flag_turn(result, _call_context(transfer_available=False))

    names = [tc.name for tc in outcome.tool_calls]
    assert names == ["book_urgent_slot", "escalate_to_oncall"]


def test_handle_red_flag_turn_rejects_non_red_flag_result():
    result = RedFlagResult(RedFlagCategory.NONE, [], "routine cleaning please")
    with pytest.raises(ValueError):
        escalation.handle_red_flag_turn(result, _call_context())


def test_every_escalation_logs_an_event():
    before = len(get_logged_events())
    result = RedFlagResult(RedFlagCategory.NON_DENTAL_EMERGENCY, ["chest_pain"], "chest pain")
    escalation.handle_red_flag_turn(result, _call_context())
    after = get_logged_events()
    assert len(after) > before
    assert after[-1]["event"] == "escalation_tool_calls"


def test_invariant_7_guard_raises_on_call_ending_outcome_with_no_tool_calls():
    bad_outcome = escalation.EscalationOutcome(
        category=RedFlagCategory.DENTAL_EMERGENCY,
        message="bye",
        tool_calls=[],
        allow_booking=False,
        call_may_end=True,
    )
    with pytest.raises(RuntimeError):
        escalation.enforce_tool_before_hangup(bad_outcome)


def test_invariant_7_guard_allows_non_terminal_outcome_with_no_tool_calls():
    ok_outcome = escalation.EscalationOutcome(
        category=RedFlagCategory.DENTAL_EMERGENCY,
        message="still talking",
        tool_calls=[],
        allow_booking=False,
        call_may_end=False,
    )
    escalation.enforce_tool_before_hangup(ok_outcome)
