# T7 — end-to-end test call script

Run after `ngrok http 8000` and the ElevenLabs agent's Twilio number both point
live (Invariant 8 note in CLAUDE.md: real calls go through ElevenLabs' native
Twilio integration, not our `/voice`, per B3).

## Pre-flight

- [ ] `uvicorn app.main:app --reload --port 8000` running, `curl localhost:8000/healthz` → `{"status":"ok"}`
- [ ] ElevenLabs dashboard: agent's custom LLM endpoint set to `{PUBLIC_BASE_URL}/elevenlabs/v1/chat/completions`
- [ ] ElevenLabs dashboard: personalization webhook set to `{PUBLIC_BASE_URL}/elevenlabs/personalize`
- [ ] Twilio number's voice webhook still fires `/call-status` on completion (for SMS/logging close-out)
- [ ] Note the test caller's phone number — is it one of the 5 seeded patients (personalization) or unseeded (fallback greeting)?

## Call 1 — routine (non-emergency)

1. Dial the number from a seeded-patient phone.
2. **Expect:** greeting uses caller's name + last-visit/insurance context (Invariant 9).
3. Say something in each bucket, one per call segment if time allows:
   - booking: "I'd like to book a cleaning" → agent should call `book_appointment`
   - urgent, non-emergency: "I lost a filling, can I get in soon" → `book_urgent_slot`
   - insurance: "Is a root canal covered under my plan" → `check_insurance`
4. Interrupt the agent mid-sentence — **expect** it stops talking (Invariant 10, native ElevenLabs barge-in). If it talks over you, note that: no custom barge-in build per SPEC.md non-goals, so this becomes a known limitation, not a bug to fix in-session.
5. Hang up normally.
6. **Verify:**
   - `GET /calls/{CallSid}` shows non-empty `transcript`, correct `classification`, and a `tool_calls` entry with the booking/check result.
   - Post-call SMS arrives, matches the booked slot/classification.

## Call 2 — emergency (must trigger live escalation, not be described)

1. Dial again.
2. Say a dental-emergency phrase, e.g. "I got hit in the mouth and my tooth is completely knocked out and bleeding a lot."
3. **Expect:** scripted `SCRIPT_DENTAL_EMERGENCY` message, an urgent slot booked, and either a live transfer or on-call escalation — before the call is allowed to end (Invariant 7).
4. On a separate attempt, say a non-dental red flag, e.g. "I'm having chest pain and trouble breathing."
5. **Expect:** scripted `SCRIPT_NON_DENTAL_911` message, no booking attempted, call ends after 911/ER routing.
6. **Verify:**
   - `GET /calls/{CallSid}` shows `escalations` populated (decision + matched keywords) and `tool_calls` containing the booking/transfer/on-call record — Invariant 7's "tool fires before hangup" is visible in the log, not just in code.

## What "rough edges" to fix, not defer

- Any turn missing from the transcript → check `call_sid` is actually reaching `webhook.py` (`_call_sid_from_request`) — depends on ElevenLabs sending `elevenlabs_extra_body.call_sid` or `user_id`.
- Wrong/missing `classification` → tool name not in `_TOOL_TO_BUCKET` (`backend/agent/webhook.py`).
- Escalation script plays but no tool_call in the log → `enforce_tool_before_hangup` should have raised; check server logs for a `RuntimeError` swallowed somewhere upstream.
