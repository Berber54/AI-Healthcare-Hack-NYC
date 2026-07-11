import logging
import os
from dataclasses import asdict

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

from app.logger import end_call, get_call_log, mark_sms_sent
from app.sms import compose_post_call_sms, send_post_call_sms

load_dotenv()

AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]

app = FastAPI()
validator = RequestValidator(AUTH_TOKEN)
logger = logging.getLogger(__name__)


async def verify_twilio_request(request: Request) -> dict:
    """Invariant 8: reject any /voice request whose X-Twilio-Signature doesn't
    match what RequestValidator computes for this exact URL + form body."""
    form = await request.form()
    params = dict(form)

    proto = request.headers.get("x-forwarded-proto", request.url.scheme)
    host = request.headers.get("x-forwarded-host", request.headers.get("host", request.url.netloc))
    url = f"{proto}://{host}{request.url.path}"

    signature = request.headers.get("x-twilio-signature", "")
    if not validator.validate(url, params, signature):
        raise HTTPException(status_code=403, detail="Invalid Twilio signature")

    return params


@app.get("/healthz")
def healthz():
    return {"status": "ok"}


@app.post("/voice")
async def voice(request: Request):
    await verify_twilio_request(request)

    response = VoiceResponse()
    response.say(
        "Thanks for calling the dental office. This is a test greeting for "
        "the telephony smoke test. Goodbye.",
    )
    return Response(content=str(response), media_type="application/xml")


@app.post("/call-status")
async def call_status(request: Request):
    """Twilio call-status callback (I.sms). Fires the post-call SMS and closes
    out the call log when Twilio reports the call as completed, independent of
    whatever conversation flow ran the call."""
    params = await verify_twilio_request(request)
    run_id = params.get("CallSid")

    if params.get("CallStatus") == "completed" and run_id:
        call_log = get_call_log(run_id)
        to_number = call_log.phone_number if call_log else params.get("From")
        if to_number:
            try:
                send_post_call_sms(to_number, compose_post_call_sms(call_log))
                if call_log:
                    mark_sms_sent(run_id)
            except Exception:
                # Invariant 12: never crash the webhook on an SMS failure - log
                # and move on, don't take down call-status handling with it.
                logger.error("post-call SMS failed for run_id=%s", run_id, exc_info=True)
        if call_log:
            end_call(run_id)

    return Response(status_code=204)


@app.get("/calls/{run_id}")
def get_call(run_id: str):
    """Invariant 11: the call log is visibly viewable as plain JSON."""
    call_log = get_call_log(run_id)
    if call_log is None:
        raise HTTPException(status_code=404, detail=f"No call log for run_id {run_id}")
    return asdict(call_log)
