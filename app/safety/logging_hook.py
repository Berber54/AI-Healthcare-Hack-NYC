"""Stub for Invariant 6 (call outcome logging).

feat/data-knowledge (Person B) owns I.logger — a structured, run_id-keyed
logger ported from VoiceAI_Scheduler's services/logger.py. Until that merges,
escalation decisions are appended to an in-memory list so T5 stays testable in
isolation. Swap log_event's body for the real logger call once I.logger lands;
callers (app/safety/escalation.py) don't need to change.
"""

from __future__ import annotations

_EVENTS: list[dict] = []


def log_event(event: dict) -> None:
    _EVENTS.append(event)


def get_logged_events() -> list[dict]:
    return list(_EVENTS)
