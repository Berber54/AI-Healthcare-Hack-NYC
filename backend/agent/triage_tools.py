# 3 non-emergency tools (I.tools). escalate_to_oncall/transfer_call belong
# to feat/safety-escalation. Not wired into the webhook loop yet — needs
# T1's payload contract first.

TRIAGE_TOOLS = [
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
]
