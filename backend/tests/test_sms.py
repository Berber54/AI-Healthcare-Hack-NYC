from app.logger import CallLog
from app.sms import _GENERIC_FALLBACK, compose_post_call_sms

# Composition only - never send a real SMS from the automated suite.


def _call_log(classification):
    return CallLog(
        run_id="run",
        phone_number="+15550100001",
        patient_id=None,
        started_at="2026-07-11T00:00:00Z",
        ended_at=None,
        status="in_progress",
        transcript=[],
        classification=classification,
        tool_calls=[],
        escalations=[],
        sms_sent=False,
    )


def test_compose_post_call_sms_known_classification():
    body = compose_post_call_sms(_call_log("routine"))
    assert "routine" in body.lower()


def test_compose_post_call_sms_no_call_log_uses_fallback():
    assert compose_post_call_sms(None) == _GENERIC_FALLBACK


def test_compose_post_call_sms_no_classification_uses_fallback():
    assert compose_post_call_sms(_call_log(None)) == _GENERIC_FALLBACK


def test_compose_post_call_sms_unknown_classification_uses_fallback():
    assert compose_post_call_sms(_call_log("something_weird")) == _GENERIC_FALLBACK
