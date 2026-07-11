"""T5 integration test: does the webhook's tool-call loop actually reach the
red-flag detector and escalation orchestrator, not just the isolated module
tested in repo-root tests/test_escalation.py.

Doesn't need Supabase, so this overrides conftest's autouse skip fixture.
"""

import os

import pytest


@pytest.fixture(autouse=True)
def _skip_without_supabase():
    """Override conftest's data-layer guard - this suite doesn't touch Supabase."""
    return


@pytest.fixture(autouse=True)
def _twilio_env(monkeypatch):
    monkeypatch.setenv("TWILIO_ACCOUNT_SID", "ACtest")
    monkeypatch.setenv("TWILIO_AUTH_TOKEN", "test_token")
    monkeypatch.setenv("TWILIO_PHONE_NUMBER", "+15550000000")
    monkeypatch.setenv("ONCALL_PHONE_NUMBER", "+15559999999")


@pytest.fixture
def webhook(monkeypatch):
    from agent import webhook as webhook_module

    def _fake(name):
        def _call(*args, **kwargs):
            from app.safety.contract import ToolCallRecord

            return ToolCallRecord(name=name, args=kwargs, status="ok")

        return _call

    monkeypatch.setattr(webhook_module.safety_tools, "transfer_call", _fake("transfer_call"))
    monkeypatch.setattr(webhook_module.safety_tools, "escalate_to_oncall", _fake("escalate_to_oncall"))
    monkeypatch.setattr(webhook_module.safety_tools, "book_urgent_slot", _fake("book_urgent_slot"))
    return webhook_module


def test_app_safety_resolves_from_backend_process():
    """Guards against the app/app namespace collision (SPEC.md Bug B6): both
    backend/app/main.py and app/safety/* must be importable in one process."""
    from agent import webhook as webhook_module
    from app.main import app as fastapi_app

    assert webhook_module.check_red_flag is not None
    assert fastapi_app is not None


def test_check_red_flag_clears_routine_turn(webhook):
    result = webhook.TOOL_HANDLERS["check_red_flag"](
        {"text": "I'd like to book a cleaning next week", "call_sid": "CA1"}
    )
    assert result == {"red_flag": False}


def test_check_red_flag_escalates_non_dental_emergency(webhook):
    result = webhook.TOOL_HANDLERS["check_red_flag"](
        {"text": "I have crushing chest pain and can't breathe", "call_sid": "CA2"}
    )
    assert result["red_flag"] is True
    assert result["category"] == "non_dental_emergency"
    assert "911" in result["say_verbatim"]
    assert result["allow_booking"] is False
    assert result["end_call"] is True
    assert [tc["name"] for tc in result["tool_calls"]] == ["escalate_to_oncall"]


def test_check_red_flag_escalates_dental_emergency_and_books_plus_transfers(webhook):
    result = webhook.TOOL_HANDLERS["check_red_flag"](
        {"text": "my tooth got knocked out and won't stop bleeding", "call_sid": "CA3"}
    )
    assert result["red_flag"] is True
    assert result["category"] == "dental_emergency"
    assert result["allow_booking"] is True
    names = [tc["name"] for tc in result["tool_calls"]]
    assert names == ["book_urgent_slot", "transfer_call"]


def test_escalate_to_oncall_tool_delegates_to_safety_tools(webhook):
    result = webhook.TOOL_HANDLERS["escalate_to_oncall"](
        {"reason": "manual escalation", "patient_info": {"name": "Jane"}}
    )
    assert result == {"status": "ok"}


def test_transfer_call_tool_delegates_to_safety_tools(webhook):
    result = webhook.TOOL_HANDLERS["transfer_call"]({"call_sid": "CA4"})
    assert result == {"status": "ok"}


def test_invariant_7_never_ends_call_with_zero_tool_calls(webhook):
    """Invariant 7 guard inside escalation.py must still be reachable through
    the webhook path - a red flag can never resolve with no tool call fired."""
    result = webhook.TOOL_HANDLERS["check_red_flag"](
        {"text": "chest pain, can't breathe", "call_sid": "CA5"}
    )
    if result["end_call"]:
        assert len(result["tool_calls"]) > 0
