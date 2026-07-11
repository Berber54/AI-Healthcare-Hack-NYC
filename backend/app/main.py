import logging
import os
from dataclasses import asdict

import httpx
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import Connect, VoiceResponse

from app.logger import end_call, get_call_log, mark_sms_sent
from app.sms import compose_post_call_sms, send_post_call_sms

load_dotenv()

AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]
ELEVENLABS_API_KEY = os.environ.get("ELEVENLABS_API_KEY")
ELEVENLABS_AGENT_ID = os.environ.get("ELEVENLABS_AGENT_ID")

app = FastAPI()
validator = RequestValidator(AUTH_TOKEN)
logger = logging.getLogger(__name__)

FALLBACK_GREETING = (
    "Thanks for calling the dental office. We're having trouble connecting "
    "you to the assistant right now. Please call back in a few minutes. Goodbye."
)


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


async def _get_elevenlabs_stream_url() -> str | None:
    """Signed WebSocket URL for the configured ElevenLabs Conversational AI
    agent. Returns None if unconfigured or the handshake fails, so /voice can
    fall back to a scripted response (Invariant 12) instead of a dead call."""
    if not ELEVENLABS_AGENT_ID or not ELEVENLABS_API_KEY:
        return None
    try:
        async with httpx.AsyncClient(timeout=5.0) as client:
            resp = await client.get(
                "https://api.elevenlabs.io/v1/convai/conversation/get_signed_url",
                params={"agent_id": ELEVENLABS_AGENT_ID},
                headers={"xi-api-key": ELEVENLABS_API_KEY},
            )
            resp.raise_for_status()
            return resp.json()["signed_url"]
    except (httpx.HTTPError, KeyError):
        return None


@app.post("/voice")
async def voice(request: Request):
    await verify_twilio_request(request)

    response = VoiceResponse()
    stream_url = await _get_elevenlabs_stream_url()
    if stream_url:
        connect = Connect()
        connect.stream(url=stream_url)
        response.append(connect)
    else:
        response.say(FALLBACK_GREETING)
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
