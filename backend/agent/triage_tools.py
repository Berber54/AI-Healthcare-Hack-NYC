# check_red_flag is the deterministic safety layer (feat/safety-escalation,
# T4/T5, Invariants 1-4/7) — listed first and described as mandatory so the
# agent calls it before anything else, every turn. escalate_to_oncall and
# transfer_call are also exposed directly for I.tools contract fidelity, but
# check_red_flag already fires them itself once a red flag is detected — the
# agent should not need to call them separately in the escalation path.

TRIAGE_TOOLS = [
    {
        "name": "check_red_flag",
        "description": (
            "MANDATORY FIRST STEP, EVERY CALLER TURN. Pass the caller's exact words "
            "from this turn before deciding how to respond. If the result has "
            "red_flag: true, speak the returned say_verbatim message exactly as given "
            "— do not rephrase, add to, or reconsider it — and end the call if "
            "end_call is true. Do not call any other tool that turn. If red_flag is "
            "false, proceed with normal triage."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "text": {"type": "string", "description": "The caller's exact words this turn"},
                "call_sid": {"type": "string", "description": "{{call_sid}} from the conversation's dynamic variables"},
            },
            "required": ["text", "call_sid"],
        },
    },
    {
        "name": "book_appointment",
        "description": "Book a routine or caller-selected appointment slot.",
        "input_schema": {
            "type": "object",
            "properties": {
                "slot": {"type": "string", "description": "ISO 8601 datetime of the chosen slot"},
                "type": {"type": "string", "description": "Appointment type, e.g. cleaning, checkup"},
            },
            "required": ["slot", "type"],
        },
    },
    {
        "name": "book_urgent_slot",
        "description": "Find and book the soonest available slot for a non-emergency urgent issue.",
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string", "description": "Brief reason for urgency, e.g. lost filling"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "check_insurance",
        "description": "Look up coverage for a given plan and procedure.",
        "input_schema": {
            "type": "object",
            "properties": {
                "plan_id": {"type": "string"},
                "procedure": {"type": "string"},
            },
            "required": ["plan_id", "procedure"],
        },
    },
    {
        "name": "get_web_input",
        "description": (
            "Check what the caller has typed or uploaded (insurance ID, PDF, photo) via the "
            "web input link shared at the start of the call. Call this whenever the caller says "
            "they've sent, typed, or uploaded something, or before asking them to spell out "
            "something like an insurance number that's easier to read than to say."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "call_sid": {"type": "string", "description": "{{call_sid}} from the conversation's dynamic variables"},
            },
            "required": ["call_sid"],
        },
    },
    {
        "name": "escalate_to_oncall",
        "description": (
            "Send an SMS alert to the on-call staff. Normally fired automatically by "
            "check_red_flag — only call this directly if on-call staff need to be "
            "notified for a reason check_red_flag would not have caught."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "reason": {"type": "string"},
                "patient_info": {"type": "object"},
                "urgent": {"type": "boolean"},
            },
            "required": ["reason"],
        },
    },
    {
        "name": "transfer_call",
        "description": (
            "Live-transfer the in-progress call to the on-call number. Normally fired "
            "automatically by check_red_flag for a true dental emergency — only call "
            "this directly if the caller explicitly asks to be transferred."
        ),
        "input_schema": {
            "type": "object",
            "properties": {
                "call_sid": {"type": "string", "description": "{{call_sid}} from the conversation's dynamic variables"},
                "to_number": {"type": "string", "description": "Optional override; defaults to the configured on-call number"},
            },
            "required": ["call_sid"],
        },
    },
]
