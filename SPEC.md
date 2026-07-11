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
  - `get_web_input(call_sid)`
- **I.logger** — structured, run_id-keyed event log (pattern ported from VoiceAI_Scheduler's `services/logger.py`). Backs Invariants 6, 11, and 12.
- **I.web_input** — `frontend/` React app (Vite, styled from `npx getdesign@latest add elevenlabs` tokens in `frontend/DESIGN.md`) at `/call/{call_sid}` the caller can open mid-call to type text or upload a PDF/image (insurance card, ID) that the agent reads via the `get_web_input` tool. Backend's `GET /input/{call_sid}` (`agent/web_input.py`) redirects to it — that's what an SMS link would point at once T6 lands. Linked by `call_sid`, captured from ElevenLabs' personalization webhook; the frontend's `/` phone-lookup page (calling `POST /input/lookup`) is the fallback if the caller never got a `call_sid` link. In-memory session store (`agent/session_store.py`) matches the single-concurrent-caller MVP scale target — swap for Supabase/Redis later without touching callers. PDF text is extracted with `pdfplumber`; images are stored with filename only, no OCR, to avoid a Tesseract system dependency on demo day. Backend allows all CORS origins for now (`backend/app/main.py`) since the frontend is a separate origin — tighten before this goes past the hackathon demo.

## Invariants

1. A red-flag detector runs on every user turn. It's keyword/regex-based, not model-dependent. *(depends on I.claude)*
2. When a red flag fires, it interrupts the LLM flow and forces a scripted escalation — the LLM has no discretion here. *(depends on Invariant 1)*
3. A non-dental red flag (chest pain, breathing trouble, stroke signs) instructs the caller to go to 911/ER, and the agent never attempts booking in that case. *(depends on Invariant 1)*
4. A true dental emergency (avulsed tooth, uncontrolled bleeding, jaw trauma, swelling with fever) forces an emergency slot booking in the same call, plus a live transfer or urgent SMS, before the call ends. *(depends on I.tools)*
5. When the caller's phone number matches a patient record, the greeting is personalized. *(depends on I.data)*
6. Every call outcome is logged: transcript, classification, tool calls, and escalation decisions. *(depends on I.data)*
7. Every live tool call fires before the call ends — "someone will call you back" is never an acceptable terminal state. *(depends on I.tools)*
8. Twilio webhook requests are validated via Twilio's `RequestValidator` (URL + params, HMAC-SHA1) before processing. Note this differs from VoiceAI_Scheduler's Vapi pattern, which validates the raw body with SHA256 — don't copy that scheme directly. *(depends on I.twilio)*
   - **⚠️ Needs team discussion:** the number is set up via ElevenLabs' native Twilio integration (imported into their dashboard, `voice_url` = `https://api.us.elevenlabs.io/twilio/inbound_call`) — Twilio calls ElevenLabs directly for the live voice path, never our own `/voice`. Our `RequestValidator` check exists and works (verified via simulated signed request) but currently sits on a webhook Twilio never hits for real calls. Need to decide: accept that ElevenLabs' side handles Twilio validation itself, or reroute voice through our webhook (loses ElevenLabs' native Media Streams handling — see B2 below). `agent/webhook.py`'s tool-call endpoint is unaffected either way; ElevenLabs calls that directly regardless of how the voice leg is routed.
9. When a patient record matches, the first turn pulls in last-visit and insurance context — not just a name in the greeting. *(depends on Invariant 5 and I.data)*
10. Barge-in / mid-response interruption is supported if the ElevenLabs agent config exposes a native flag for it. No custom build if that flag is absent. *(depends on I.elevenlabs)*
11. The call transcript/log is visibly viewable (plain JSON or a simple view) — not just stored. *(depends on Invariant 6 and I.data)*
12. If Claude, Twilio, or ElevenLabs fails mid-call, the agent falls back gracefully — retry once, then a scripted fallback response. It never crashes silently mid-call. Pattern ported from VoiceAI_Scheduler's `services/error_recovery.py`. *(depends on I.claude, I.twilio, I.elevenlabs)*

## Tasks

| ID | Status | Description | Cites |
|----|--------|-------------|-------|
| T1 | Verified via simulated signed request; pending real phone call confirmation | Twilio number + webhook reachable, scripted greeting smoke test | I.twilio |
| T2 | Done | Mock data: 5 patients, 10 appointment slots (routine/urgent/emergency), one insurance plan — schema + seed in `backend/db/`, exposed via `backend/app/data.py`, verified by `backend/tests/` (12 passing against a live Supabase project) | I.data |
| T3 | Prompt/tools/personalization wired to live Supabase data layer (`agent/webhook.py`); pending real-call verification and barge-in flag check (needs ElevenLabs dashboard/agent-config access, not available in this environment) | Triage prompt + 4 non-emergency buckets (routine/urgent/insurance/booking) working end to end | Invariant 5, I.claude |
| T4 | Done | Red-flag detector built and tested in isolation (`backend/app/safety/red_flags.py`, 27 tests passing, see B4/B5) before wiring into the main flow | Invariants 1, 2 |
| T5 | Wired into the live call flow — `agent/webhook.py`'s new `/elevenlabs/v1/chat/completions` custom-LLM endpoint runs `check_red_flag` on every turn before Claude sees it, routing red flags to `handle_red_flag_turn` instead (Invariant 2). Requires the ElevenLabs agent's dashboard config to be switched to point at this endpoint as a custom LLM (not done in this environment); pending real-call verification | Emergency escalation path wired into the call flow (dental emergency + non-dental red flag) | Invariants 3, 4 |
| T6 | Not started | Post-call SMS + call logging | Invariant 6, I.sms |
| T7 | Not started | End-to-end test calls: one routine call, one emergency call — fix rough edges | T1, T3, T4, T5 |
| T8 | Not started | Demo script rehearsal (2 calls; the emergency call must trigger live escalation on stage, not just be described) + Devpost writeup | T7, Invariants 3, 4 |
| T1b | Verified via simulated signed request; pending real phone call confirmation | `/voice` hands off to the ElevenLabs Conversational AI agent via `<Connect><Stream>` so `agent/webhook.py` tool calls get hit by real traffic; falls back to scripted `<Say>` per Invariant 12 if ElevenLabs is unconfigured/unreachable | T1, I.elevenlabs, `agent/webhook.py` |
| T9 | Built, verified end-to-end in browser (text submit + phone-lookup fallback) against the live backend; PDF upload path unit-tested, pending real-call verification | Web input bar: `frontend/` React app (`/call/{call_sid}` + `/` phone lookup) + `get_web_input` tool so the caller can type or upload (PDF/image) info mid-call for the agent to read | I.web_input |

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
| B3 | 2026-07-11 | Real call ended instantly, Twilio error 31921 (Stream WebSocket closed by remote). `/voice`'s `<Connect><Stream>` pointed at ElevenLabs' raw Conversational AI websocket (`/v1/convai/conversation`), which speaks ElevenLabs' client protocol, not Twilio's Media Streams protocol — no custom relay is a documented/supported path | The number was already imported into ElevenLabs' native Twilio integration and assigned to the agent (done via their dashboard, not by us); `voice_url` now correctly points at `https://api.us.elevenlabs.io/twilio/inbound_call`, bypassing our `/voice` entirely for the live call. See Invariant 8 note above — our `<Connect><Stream>` code in `/voice` is now unused for the real call path. |
| B4 | 2026-07-11 | Red-flag detector's `swelling_with_fever` combo matched on the literal substring "fever" even inside a negated phrase (e.g. "swollen but no fever"), misfiring `DENTAL_EMERGENCY` on a routine turn | Added a negation guard (`_present_and_not_negated`) that skips a symptom match if a negation word appears immediately before it |
| B5 | 2026-07-11 | Red-flag detector's `stroke_signs` pattern only matched literal phrases "face...droop" (trailing `\b` broke on "drooping") and "slurred speech" (failed on reversed word order "speech is slurred") — real caller phrasing was silently missed | Rewrote pattern to match either word order and verb inflection (`droop\w*`, `slurr\w*`) instead of one literal phrase |
| B6 | 2026-07-11 | Person D's `app/safety/` (red-flag detector + escalation, T4/T5) lived at repo root, while Person B/C's data layer lives at `backend/app/`. `backend/app/` has an `__init__.py` (regular package), so it can't namespace-merge with root `app/` — `app.safety.X` and `app.data` couldn't both import in the same process, blocking T5's wiring into the live call flow | Relocated `app/safety/` (and its tests) into `backend/app/safety/`, one `app` package for the whole backend — same fix pattern as commit 407f9de's `agent/` relocation |
| B7 | 2026-07-11 | After the B6 move, `backend/tests/test_red_flags.py`/`test_escalation.py` inherited `conftest.py`'s `autouse=True` Supabase-skip fixture and got force-skipped even though they never touch Supabase | Changed the fixture to only skip tests marked `@pytest.mark.requires_supabase`; applied that marker to the three data-layer test files (`test_data_access.py`, `test_schema.py`, `test_seed_data.py`) |
