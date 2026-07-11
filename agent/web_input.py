import io

import pdfplumber
from fastapi import APIRouter, File, Form, HTTPException, UploadFile
from fastapi.responses import HTMLResponse

from agent import session_store

router = APIRouter()

INPUT_PAGE = """<!doctype html>
<html><head><title>Share info with your call</title></head>
<body style="font-family: sans-serif; max-width: 480px; margin: 40px auto;">
  <h2>Share info with the agent</h2>
  <p>Whatever you enter here, the agent on your call can read it live.</p>
  <form id="f" enctype="multipart/form-data">
    <textarea name="text" rows="4" style="width:100%" placeholder="e.g. insurance member ID"></textarea><br>
    <input type="file" name="file" accept=".pdf,.png,.jpg,.jpeg"><br><br>
    <button type="submit">Send to agent</button>
  </form>
  <p id="status"></p>
  <script>
    const callSid = {call_sid!r};
    document.getElementById('f').onsubmit = async (e) => {
      e.preventDefault();
      const res = await fetch(`/input/${callSid}`, { method: 'POST', body: new FormData(e.target) });
      document.getElementById('status').textContent = res.ok ? 'Sent.' : 'Failed, try again.';
      e.target.reset();
    };
  </script>
</body></html>"""


def _extract_pdf_text(raw: bytes) -> str | None:
    try:
        with pdfplumber.open(io.BytesIO(raw)) as pdf:
            return "\n".join(page.extract_text() or "" for page in pdf.pages).strip() or None
    except Exception:
        return None


@router.get("/input/{call_sid}", response_class=HTMLResponse)
async def input_page(call_sid: str):
    return INPUT_PAGE.replace("{call_sid!r}", repr(call_sid))


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
