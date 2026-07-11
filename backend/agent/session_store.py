# In-memory web-input session store. Single-concurrent-caller MVP scale
# target (SPEC.md) — swap for Supabase/Redis later without touching callers.

_sessions: dict[str, dict] = {}
_phone_to_call_sid: dict[str, str] = {}


def link_call(call_sid: str, phone: str | None) -> None:
    _sessions.setdefault(call_sid, {"phone": phone, "entries": []})
    if phone:
        _phone_to_call_sid[phone] = call_sid


def resolve_call_sid(phone: str) -> str | None:
    return _phone_to_call_sid.get(phone)


def add_text(call_sid: str, text: str) -> None:
    session = _sessions.setdefault(call_sid, {"phone": None, "entries": []})
    session["entries"].append({"type": "text", "value": text})


def add_file_note(call_sid: str, filename: str, extracted_text: str | None) -> None:
    session = _sessions.setdefault(call_sid, {"phone": None, "entries": []})
    session["entries"].append({"type": "file", "filename": filename, "extracted_text": extracted_text})


def get_entries(call_sid: str) -> list[dict]:
    return _sessions.get(call_sid, {}).get("entries", [])
