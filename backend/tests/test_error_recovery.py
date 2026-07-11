from app.error_recovery import retry_once


def test_retry_once_returns_result_on_success():
    assert retry_once(lambda: 42) == 42


def test_retry_once_retries_then_succeeds():
    calls = {"n": 0}

    def flaky():
        calls["n"] += 1
        if calls["n"] < 2:
            raise RuntimeError("boom")
        return "ok"

    assert retry_once(flaky) == "ok"
    assert calls["n"] == 2


def test_retry_once_falls_back_after_two_failures():
    def always_fails():
        raise RuntimeError("boom")

    assert retry_once(always_fails, fallback="fallback-value") == "fallback-value"


def test_retry_once_default_fallback_is_none():
    def always_fails():
        raise RuntimeError("boom")

    assert retry_once(always_fails) is None
