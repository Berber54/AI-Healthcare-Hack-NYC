"""Tool schemas for the 3 non-emergency tools this branch owns (I.tools).

`escalate_to_oncall` and `transfer_call` belong to feat/safety-escalation
(Person D) — not defined here.

NOT YET WIRED into the webhook turn loop: that needs the payload/response
contract from T1 (feat/telephony), which hasn't landed yet. This is the
Claude tool-use schema only, ready to plug in once the webhook contract
exists.
"""

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
