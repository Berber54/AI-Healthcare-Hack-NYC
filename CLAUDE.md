# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A voice agent that triages and books a dental call in a single phone call, built in a 3-4 hour hackathon window (Healthcare Hack NYC + Twilio Searchlight). **`SPEC.md` is the source of truth** — read it before making non-trivial changes. It defines the goal, constraints, interfaces (I.twilio, I.elevenlabs, I.claude, I.data, I.sms, I.tools, I.logger), 12 numbered invariants, the task list, the 4-person parallel branch split, and a running bugs log.

Do not treat SPEC.md as documentation to skim once — it is the plan of record. If a change contradicts an invariant or constraint in SPEC.md, stop and flag it rather than silently deviating. If you fix a bug, add an entry to the Bugs table in SPEC.md (ID, date, cause, fix) following the existing B1 pattern.

## Commands

```bash
# Install deps (from backend/)
pip install -r requirements.txt

# Run the webhook server (from backend/)
uvicorn app.main:app --reload --port 8000

# Health check
curl http://localhost:8000/healthz

# Expose locally for Twilio during dev/demo
ngrok http 8000

# Run the data-layer test suite (from backend/)
pytest tests -v
```

Config lives in `.env` (copy from `.env.template`, gitignored). Required: `TWILIO_ACCOUNT_SID`, `TWILIO_AUTH_TOKEN`, `TWILIO_PHONE_NUMBER`, `SUPABASE_URL`, `SUPABASE_KEY` (the `service_role` key — this app has no user auth layer, and RLS is enabled with no policies so only `service_role` can reach the data), plus `NGROK_AUTHTOKEN`/`PUBLIC_BASE_URL` for tunneling.

`backend/tests` is a real integration suite against the live Supabase project (no mocking the DB) — every test skips cleanly, not fails, when `SUPABASE_URL`/`SUPABASE_KEY` are unset. No linter is configured yet.

To (re)provision the Supabase schema/seed data: run `backend/db/schema.sql` then `backend/db/seed.sql` in the Supabase SQL editor, then enable RLS on all four tables (`patients`, `appointment_slots`, `insurance_plans`, `call_logs`) with `alter table <name> enable row level security;` (no policies needed). `call_logs` has no seed data — it's written at runtime. After creating a new table, run `notify pgrst, 'reload schema';` (or click "Reload schema" in the dashboard) so PostgREST's cache picks it up; otherwise the REST client raises `PGRST205: Could not find the table ... in the schema cache`.

## Architecture

- **Single FastAPI app** at `backend/app/main.py` — the `/voice` webhook, `/healthz`, the `/call-status` Twilio status-callback (fires post-call SMS + closes the call log), and `GET /calls/{run_id}` (the Invariant 11 plain-JSON log view). This will grow into the full Twilio + ElevenLabs webhook handler.
- **Twilio signature validation is mandatory on every webhook request** (Invariant 8): `verify_twilio_request()` reconstructs the exact request URL (honoring `X-Forwarded-Proto`/`X-Forwarded-Host` since ngrok sits in front) and validates it against `X-Twilio-Signature` via Twilio's `RequestValidator` (HMAC-SHA1 over URL + form params) before any other processing. This is a different scheme from the VoiceAI_Scheduler reference repo's Vapi pattern (raw-body SHA256) — do not port that scheme here.
- **Safety escalation is deterministic, not LLM-driven** (Invariants 1-4): a regex/keyword red-flag detector must run on every user turn, independent of and able to override the LLM. Non-dental red flags (chest pain, breathing trouble, stroke signs) route to 911/ER with no booking attempt. True dental emergencies force an emergency slot booking plus live transfer/urgent SMS before the call ends. Never implement escalation logic as something the LLM can be argued out of.
- **Every live tool call must fire before the call ends** (Invariant 7) — "someone will call you back" is never an acceptable terminal state.
- **Mock EHR only** — Supabase (Postgres) backing `patients`, `appointment_slots`, and `insurance_plans` (schema/seed in `backend/db/`). No real patient data, no real clinical claims. `backend/app/data.py` is the I.data access layer (`get_patient_by_phone`, `get_available_slots`, `book_slot`, `get_insurance_plan`) — other branches should import this rather than querying Supabase directly. `book_slot` guards against double-booking; it raises `SlotAlreadyBookedError` rather than silently overwriting.
- **Call logging (I.logger, Invariants 6/11)** — `backend/app/logger.py` is a stateless, `run_id`-keyed logger over the `call_logs` table (`run_id` = Twilio CallSid). `start_call` then per-event `log_turn`/`log_classification`/`log_tool_call`/`log_escalation`, `end_call` to close out, `get_call_log` to read. Each write is read-modify-write against Supabase (no in-memory buffer), so a call's log survives a mid-call crash and is queryable live. The conversation/escalation branches call these to record their turns, tool calls, and escalation decisions.
- **Post-call SMS (I.sms)** — `backend/app/sms.py`: `compose_post_call_sms(call_log)` maps the triage classification to a message (generic fallback when there's no log or no classification), `send_post_call_sms(to, body)` sends via Twilio's REST `Client`. Triggered by the `/call-status` webhook on `CallStatus=completed`, decoupled from the LLM flow. Tests only exercise composition — the suite never sends a real SMS.
- **Graceful read fallback (Invariant 12)** — `backend/app/error_recovery.py` `retry_once(fn, ..., fallback=...)` retries a read once then returns the fallback instead of raising. `data.py`'s reads and `logger.get_call_log` are wrapped in it, so a Supabase blip degrades (empty/None) rather than crashing the webhook mid-call. This is Person B's slice of the cross-cutting Invariant 12.
- **Reference repo for porting patterns**: github.com/Khushir474/VoiceAI_Scheduler. Port the *pattern* (agent-turn webhook shape, live tool-call pattern, ElevenLabs+Twilio provisioning, post-call SMS, `logger.py`, `error_recovery.py`), not literal code — it's a separate repo.

## Explicit non-goals (do not build these)

- Custom barge-in implementation — only if ElevenLabs' agent config lacks a native flag for it (Invariant 10).
- An FSM-based conversation state machine (like VoiceAI_Scheduler's `conversation_state_machine.py`) — the LLM plus the deterministic regex layer is considered sufficient for this build.
- An adapter-pattern (base + implementation split) abstraction layer.
- Load testing or scaling beyond a single concurrent caller — keep the data layer/webhook handler stateless/swappable so scaling later is a config change, not a rewrite, but don't build the scaling itself now.

## Branch structure

Four parallel feature branches split by owner, merging into `main` before end-to-end testing (T7): `feat/telephony`, `feat/data-knowledge`, `feat/triage-conversation`, `feat/safety-escalation`. See SPEC.md's "Parallel Branches" table for exactly which invariants/tasks each branch owns before touching cross-branch concerns.
