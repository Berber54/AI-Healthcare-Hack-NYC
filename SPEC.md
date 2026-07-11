# SPEC — Dental Triage Voice Agent (Healthcare Hack NYC)

## Goal

Build a voice agent that triages and books a dental call, start to finish, in a single call. Twilio is required for telephony. Safety guardrails must be hardcoded and deterministic — never left to LLM judgment.

## Constraints

- **Build window:** 3–4 hours, single day, live demo required (Healthcare Hack NYC + Twilio Searchlight).
- **Telephony:** Twilio is mandatory for prize eligibility.
- **Scope is locked** to 5 triage buckets, with no expansion mid-build:
  1. Routine
  2. Urgent, non-emergency
  3. True emergency
  4. Non-dental red flag
  5. Insurance / cost questions
- **Red-flag escalation must be deterministic** — a regex/keyword layer, independent of LLM output. The LLM can never be argued out of escalating.
- **No real patient data and no real clinical claims.** Mock EHR only.
- **Reuse plumbing from the VoiceAI_Scheduler repo** where possible (github.com/Khushir474/VoiceAI_Scheduler): the agent-turn webhook pattern, the live tool-call pattern, ElevenLabs+Twilio provisioning, and post-call SMS. Port the *pattern*, not literal shared code — it's a separate repo.
- **Scale target for MVP is a single concurrent caller (1 user).** The data layer and webhook handler should be kept stateless/swappable so that supporting more concurrency later is a config change, not a rewrite. No load testing or infra work happens in this build window.
- **Explicit non-goals for this build:**
  - A custom barge-in implementation — only build one if ElevenLabs lacks a native flag (see Invariant 10).
  - An FSM-based conversation state machine (the pattern used in VoiceAI_Scheduler's `conversation_state_machine.py`) — too heavy for a 3–4 hour window; the LLM plus a deterministic regex layer is sufficient.
  - An adapter-pattern abstraction (base + implementation split) — adds cost the MVP can't afford.

## Techstack

- **Server:** Python + FastAPI — webhook handler for Twilio + ElevenLabs. Chosen to port `logger.py` and `error_recovery.py` from VoiceAI_Scheduler near-verbatim instead of translating to another language.
- **Data:** Supabase (Postgres) for the mock EHR (patients, appointment slots, insurance plan).
- **Hosting (build + demo):** ngrok tunnel to localhost. Start it well before stage time to derisk tunnel drop mid-demo.

## Interfaces

- **I.twilio** — inbound call routing to the webhook, with live transfer capability.
- **I.elevenlabs** — STT/TTS conversational agent.
- **I.claude** — Anthropic API, acting as the turn-by-turn decision-maker.
- **I.data** — mock patient/appointment/insurance store, backed by Supabase (Postgres).
- **I.sms** — post-call SMS confirmation and instructions.
- **I.tools** — live tool calls fired mid-conversation:
  - `book_appointment(slot, type)`
  - `book_urgent_slot(reason)`
  - `escalate_to_oncall(reason, patient_info)`
  - `transfer_call()`
  - `check_insurance(plan_id, procedure)`
- **I.logger** — structured, run_id-keyed event log (pattern ported from VoiceAI_Scheduler's `services/logger.py`). Backs Invariants 6, 11, and 12.

## Invariants

1. A red-flag detector runs on every user turn. It's keyword/regex-based, not model-dependent. *(depends on I.claude)*
2. When a red flag fires, it interrupts the LLM flow and forces a scripted escalation — the LLM has no discretion here. *(depends on Invariant 1)*
3. A non-dental red flag (chest pain, breathing trouble, stroke signs) instructs the caller to go to 911/ER, and the agent never attempts booking in that case. *(depends on Invariant 1)*
4. A true dental emergency (avulsed tooth, uncontrolled bleeding, jaw trauma, swelling with fever) forces an emergency slot booking in the same call, plus a live transfer or urgent SMS, before the call ends. *(depends on I.tools)*
5. When the caller's phone number matches a patient record, the greeting is personalized. *(depends on I.data)*
6. Every call outcome is logged: transcript, classification, tool calls, and escalation decisions. *(depends on I.data)*
7. Every live tool call fires before the call ends — "someone will call you back" is never an acceptable terminal state. *(depends on I.tools)*
8. Twilio webhook requests are validated via Twilio's `RequestValidator` (URL + params, HMAC-SHA1) before processing. Note this differs from VoiceAI_Scheduler's Vapi pattern, which validates the raw body with SHA256 — don't copy that scheme directly. *(depends on I.twilio)*
9. When a patient record matches, the first turn pulls in last-visit and insurance context — not just a name in the greeting. *(depends on Invariant 5 and I.data)*
10. Barge-in / mid-response interruption is supported if the ElevenLabs agent config exposes a native flag for it. No custom build if that flag is absent. *(depends on I.elevenlabs)*
11. The call transcript/log is visibly viewable (plain JSON or a simple view) — not just stored. *(depends on Invariant 6 and I.data)*
12. If Claude, Twilio, or ElevenLabs fails mid-call, the agent falls back gracefully — retry once, then a scripted fallback response. It never crashes silently mid-call. Pattern ported from VoiceAI_Scheduler's `services/error_recovery.py`. *(depends on I.claude, I.twilio, I.elevenlabs)*

## Tasks

| ID | Status | Description | Cites |
|----|--------|-------------|-------|
| T1 | In progress | Twilio number + webhook reachable, scripted greeting smoke test | I.twilio |
| T2 | Done | Mock data: 5 patients, 10 appointment slots (routine/urgent/emergency), one insurance plan — schema + seed in `backend/db/`, exposed via `backend/app/data.py`, verified by `backend/tests/` (12 passing against a live Supabase project) | I.data |
| T3 | Not started | Triage prompt + 4 non-emergency buckets (routine/urgent/insurance/booking) working end to end | Invariant 5, I.claude |
| T4 | Not started | Red-flag detector built and tested in isolation before wiring into the main flow | Invariants 1, 2 |
| T5 | Not started | Emergency escalation path wired into the call flow (dental emergency + non-dental red flag) | Invariants 3, 4 |
| T6 | Not started | Post-call SMS + call logging | Invariant 6, I.sms |
| T7 | Not started | End-to-end test calls: one routine call, one emergency call — fix rough edges | T1, T3, T4, T5 |
| T8 | Not started | Demo script rehearsal (2 calls; the emergency call must trigger live escalation on stage, not just be described) + Devpost writeup | T7, Invariants 3, 4 |

## Parallel Branches — 4-Person Split

**Order of operations:** T1 goes first, solo (~20–30 minutes) — it's blocking, since everyone else depends on the webhook contract it establishes. After that, the four branches below run in parallel and merge into `main` before T7 starts.

| Branch | Owner | Cites | Description |
|--------|-------|-------|-------------|
| `feat/telephony` | Person A | T1, Invariant 8, I.twilio | Get the Twilio number and webhook live, add signature validation (`RequestValidator`), run the scripted-greeting smoke test. Do this first, solo, before anyone else branches. |
| `feat/data-knowledge` | Person B | T2, T6, Invariants 6/11, I.data, I.logger | Build the mock EHR (3–5 patients, slots, one insurance plan), the structured run_id-keyed logger, post-call SMS, and the visible transcript/log view. |
| `feat/triage-conversation` | Person C | T3, Invariants 5/9/10, I.claude | Write the triage prompt and the 4 non-emergency buckets, add personalization (caller lookup plus last-visit/insurance context), and check for a native ElevenLabs barge-in flag. |
| `feat/safety-escalation` | Person D | T4, T5, Invariants 1/2/3/4/7, I.tools | Build and isolation-test the red-flag detector, wire the emergency escalation path (dental + non-dental), and enforce the "tool call fires before hangup" rule. |

**Invariant 12** (API failure fallback) is cross-cutting — each owner adds a fallback for their own surface: Person A covers Twilio, Person C covers Claude and ElevenLabs, Person B covers data/logger read failures.

**Integration:** T7 (end-to-end test calls) and T8 (demo rehearsal) run all-hands, after the branches merge into `main`.

## Bugs

| ID | Date | Cause | Fix |
|----|------|-------|-----|
| B1 | 2026-07-11 | `POST /voice` returned 500 — Starlette's `request.form()` needs the `python-multipart` package to parse Twilio's `application/x-www-form-urlencoded` body, which wasn't in `backend/requirements.txt` | Added `python-multipart==0.0.20` to `backend/requirements.txt` and reinstalled |
| B2 | 2026-07-11 | `backend/tests` errored instead of skipping when `SUPABASE_URL`/`SUPABASE_KEY` were unset — the session-scoped `supabase_client` fixture was instantiated before the function-scoped autouse skip check ran, so tests requesting it directly hit `SupabaseException` instead of a clean skip | Added the same env-var guard directly inside the `supabase_client` fixture in `backend/tests/conftest.py`, so it skips independently of fixture ordering |
