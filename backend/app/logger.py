"""I.logger - structured, run_id-keyed call log (pattern ported from
VoiceAI_Scheduler's services/logger.py). Backs Invariants 6, 11, 12.

Stateless like data.py: every log_* call reads the current row from
Supabase and writes it back, rather than accumulating in memory. That
keeps a call's log durable and visible even if the process crashes
mid-call, and matches the stateless/swappable data-layer constraint
in SPEC.md. run_id is the Twilio CallSid.
"""

import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Optional

from supabase import Client, create_client

from app.error_recovery import retry_once

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = create_client(os.environ["SUPABASE_URL"], os.environ["SUPABASE_KEY"])
    return _client


@dataclass
class CallLog:
    run_id: str
    phone_number: str
    patient_id: Optional[str]
    started_at: str
    ended_at: Optional[str]
    status: str
    transcript: list
    classification: Optional[str]
    tool_calls: list
    escalations: list
    sms_sent: bool


def start_call(run_id: str, phone_number: str, patient_id: Optional[str] = None) -> CallLog:
    result = (
        _get_client()
        .table("call_logs")
        .upsert(
            {
                "run_id": run_id,
                "phone_number": phone_number,
                "patient_id": patient_id,
                "status": "in_progress",
                "transcript": [],
                "tool_calls": [],
                "escalations": [],
                "sms_sent": False,
            }
        )
        .execute()
    )
    return _row_to_call_log(result.data[0])


def log_turn(run_id: str, speaker: str, text: str) -> CallLog:
    row = _get_row(run_id)
    transcript = row["transcript"] + [{"speaker": speaker, "text": text, "at": _now()}]
    return _update(run_id, {"transcript": transcript})


def log_classification(run_id: str, bucket: str) -> CallLog:
    return _update(run_id, {"classification": bucket})


def log_tool_call(run_id: str, name: str, args: dict, result: Any) -> CallLog:
    row = _get_row(run_id)
    tool_calls = row["tool_calls"] + [{"name": name, "args": args, "result": result, "at": _now()}]
    return _update(run_id, {"tool_calls": tool_calls})


def log_escalation(run_id: str, decision: str, reason: str) -> CallLog:
    row = _get_row(run_id)
    escalations = row["escalations"] + [{"decision": decision, "reason": reason, "at": _now()}]
    return _update(run_id, {"escalations": escalations})


def end_call(run_id: str) -> CallLog:
    return _update(run_id, {"status": "completed", "ended_at": _now()})


def mark_sms_sent(run_id: str) -> CallLog:
    return _update(run_id, {"sms_sent": True})


def get_call_log(run_id: str) -> Optional[CallLog]:
    def _read():
        result = _get_client().table("call_logs").select("*").eq("run_id", run_id).execute()
        return _row_to_call_log(result.data[0]) if result.data else None

    return retry_once(_read, fallback=None)


def _get_row(run_id: str) -> dict:
    result = _get_client().table("call_logs").select("*").eq("run_id", run_id).execute()
    if not result.data:
        raise ValueError(f"No call_log with run_id {run_id}; call start_call first")
    return result.data[0]


def _update(run_id: str, fields: dict) -> CallLog:
    result = _get_client().table("call_logs").update(fields).eq("run_id", run_id).execute()
    if not result.data:
        raise ValueError(f"No call_log with run_id {run_id}; call start_call first")
    return _row_to_call_log(result.data[0])


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _row_to_call_log(row: dict) -> CallLog:
    return CallLog(
        run_id=row["run_id"],
        phone_number=row["phone_number"],
        patient_id=row.get("patient_id"),
        started_at=row["started_at"],
        ended_at=row.get("ended_at"),
        status=row["status"],
        transcript=row["transcript"],
        classification=row.get("classification"),
        tool_calls=row["tool_calls"],
        escalations=row["escalations"],
        sms_sent=row["sms_sent"],
    )
