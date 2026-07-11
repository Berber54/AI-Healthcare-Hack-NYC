"""I.sms - post-call SMS confirmation and instructions."""

import os
from typing import Optional

from twilio.rest import Client

from app.logger import CallLog

_client: Optional[Client] = None


def _get_client() -> Client:
    global _client
    if _client is None:
        _client = Client(os.environ["TWILIO_ACCOUNT_SID"], os.environ["TWILIO_AUTH_TOKEN"])
    return _client


_MESSAGES = {
    "routine": "Thanks for calling! We've noted your routine appointment request and will follow up to confirm your time.",
    "urgent": "Thanks for calling. We've noted your urgent appointment request - our office has your details and will prioritize you.",
    "emergency": "Following up on your emergency call: please keep your booked emergency slot, and go to the nearest ER if symptoms worsen before then.",
    "non_dental_red_flag": "Following up on your call: please seek immediate medical attention at your nearest ER or call 911 if you haven't already.",
    "insurance": "Thanks for calling about your insurance and cost questions. Reach out if anything else comes up.",
}

# Invariant 12 fallback: if we have no classification (or no log at all) to
# tailor the message, send this instead of failing to send anything.
_GENERIC_FALLBACK = "Thanks for calling our dental office. If you need anything else, please call us back."


def compose_post_call_sms(call_log: Optional[CallLog]) -> str:
    if call_log is None or not call_log.classification:
        return _GENERIC_FALLBACK
    return _MESSAGES.get(call_log.classification, _GENERIC_FALLBACK)


def send_post_call_sms(to_number: str, body: str) -> str:
    message = _get_client().messages.create(
        to=to_number,
        from_=os.environ["TWILIO_PHONE_NUMBER"],
        body=body,
    )
    return message.sid
