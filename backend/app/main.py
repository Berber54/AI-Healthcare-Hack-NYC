import os

from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import Response
from twilio.request_validator import RequestValidator
from twilio.twiml.voice_response import VoiceResponse

load_dotenv()

AUTH_TOKEN = os.environ["TWILIO_AUTH_TOKEN"]

app = FastAPI()
validator = RequestValidator(AUTH_TOKEN)


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
