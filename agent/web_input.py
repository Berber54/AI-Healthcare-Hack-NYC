import io
import os

import pdfplumber
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import RedirectResponse

from agent import session_store

router = APIRouter()

# frontend/ (React, `npx getdesign@latest add elevenlabs` styling) is the real
# UI; this backend route just redirects the SMS link to it.
FRONTEND_BASE_URL = os.environ.get("FRONTEND_BASE_URL", "http://localhost:5173")


def _extract_pdf_text(raw: bytes) -> str | None:
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip() or None
    except Exception:
        return None


@router.get("/input/{call_sid}")
async def input_page(call_sid: str):
    return RedirectResponse(f"{FRONTEND_BASE_URL}/call/{call_sid}")


@router.post("/input/lookup")
async def lookup_by_phone(phone: str = Form(...)):
    """Fallback link path (I.web_input): caller who never got the SMS link
    types their phone number in to find their call_sid."""
    call_sid = session_store.resolve_call_sid(phone)
    if not call_sid:
        raise HTTPException(status_code=404, detail="No active call found for that number")
    return {"call_sid": call_sid}


@router.post("/input/{call_sid}")
async def submit_input(call_sid: str, text: str = Form(""), file: UploadFile | None = File(None)):
    if text.strip():
        session_store.add_text(call_sid, text.strip())

    if file is not None and file.filename:
        raw = await file.read()
        extracted = _extract_pdf_text(raw) if file.content_type == "application/pdf" else None
        session_store.add_file_note(call_sid, file.filename, extracted)

    return {"status": "received"}
