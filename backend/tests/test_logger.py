from app.logger import (
    end_call,
    get_call_log,
    log_classification,
    log_escalation,
    log_tool_call,
    log_turn,
    mark_sms_sent,
    start_call,
)

RUN_ID = "TEST-CALL-SID-0001"


def test_call_log_round_trip(supabase_client):
    try:
        start_call(RUN_ID, "+15550199999")
        log_turn(RUN_ID, "caller", "My tooth hurts")
        log_turn(RUN_ID, "agent", "Can you describe the pain?")
        log_classification(RUN_ID, "urgent")
        log_tool_call(RUN_ID, "book_urgent_slot", {"reason": "toothache"}, {"slot_id": "abc"})
        log_escalation(RUN_ID, "none", "not a red flag")
        mark_sms_sent(RUN_ID)
        ended = end_call(RUN_ID)

        assert ended.status == "completed"
        assert ended.ended_at is not None

        fetched = get_call_log(RUN_ID)
        assert fetched is not None
        assert len(fetched.transcript) == 2
        assert fetched.transcript[0]["speaker"] == "caller"
        assert fetched.classification == "urgent"
        assert len(fetched.tool_calls) == 1
        assert fetched.tool_calls[0]["name"] == "book_urgent_slot"
        assert len(fetched.escalations) == 1
        assert fetched.escalations[0]["decision"] == "none"
        assert fetched.sms_sent is True
    finally:
        supabase_client.table("call_logs").delete().eq("run_id", RUN_ID).execute()


def test_get_call_log_missing_returns_none():
    assert get_call_log("NONEXISTENT-RUN-ID") is None
