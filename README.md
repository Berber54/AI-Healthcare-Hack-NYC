# Dental Triage Voice Agent

A phone call answers itself: a caller with a dental problem dials a real number, talks to an AI agent in natural voice, gets triaged, and — if it's an emergency — gets booked into an emergency slot and connected to a human, all inside a single call. No app, no hold music, no "someone will call you back."

Built in a single ~4-hour hackathon window for **Healthcare Hack NYC** (Twilio Searchlight track).

## Why this exists

Dental offices triage by phone, staffed by a receptionist who has to catch true emergencies (avulsed tooth, uncontrolled bleeding, jaw trauma) versus things that can wait, while also booking routine cleanings and answering "is this covered by my insurance." That triage judgment is exactly the kind of task an LLM is good at — except when it's wrong, the cost is a missed medical emergency. So the core design bet of this project is:

**Let the LLM handle the conversation. Never let it own the safety-critical decision.**

## What it does

- **Answers a real inbound phone call** over Twilio and holds a natural voice conversation (ElevenLabs Conversational AI for STT/TTS, Claude as the turn-by-turn decision-maker).
- **Classifies every caller into one of 5 buckets**: routine, urgent-non-emergency, true dental emergency, non-dental red flag, or insurance/cost question — and acts on it live, mid-call, via tool calls (not "we'll follow up").
- **Runs a deterministic safety layer independent of the LLM**, on every single turn, that can override the model outright. If a caller says something matching a true emergency, the LLM doesn't get a vote — a scripted, hardcoded escalation takes over immediately.
- **Personalizes the greeting** when the caller's phone number matches a patient record — pulls in their name, last visit, and insurance context, not just "hi again."
- **Lets a caller share things speech can't easily convey** — an insurance card photo, a PDF, a typed detail — via a live web link opened mid-call, which the agent can read back to itself with a tool call.
- **Falls back gracefully** if Claude, Twilio, or ElevenLabs hiccups mid-call — retries once, then a scripted response. Never a silent crash on a live call.
- **Logs every call outcome** — transcript, classification, every tool call, every escalation decision — viewable, not just written to a database no one opens.

## The safety architecture (the part that actually matters)

This is the load-bearing design decision of the whole project, so it gets its own section.

```
caller turn (speech-to-text)
        │
        ▼
deterministic regex/keyword red-flag layer  ── runs on every single turn
        │
        ├── no red flag ──▶ Claude: triage + conversation + booking
        │                   (routine / urgent-non-emergency / insurance / booking)
        │
        └── red flag fires ──▶ scripted escalation, zero LLM discretion
                                │
                                ├── non-dental (chest pain, can't breathe, stroke
                                │   signs, anaphylaxis, seizure, ...)
                                │   → 911/ER instruction, booking never attempted
                                │
                                └── dental emergency (avulsed tooth, uncontrolled
                                    bleeding, major trauma, swelling+fever)
                                    → emergency slot booked + live transfer/SMS,
                                      in this same call
```

- The red-flag detector is **pure keyword/regex matching** — no model call, no network call, testable in complete isolation from Twilio/ElevenLabs/Claude/Supabase.
- It was reviewed against real clinical criteria with a practicing dentist to get the boundaries right: airway/systemic-risk presentations (e.g. Ludwig's-angina-type signs — can't swallow, floor-of-mouth swelling, muffled voice) route to **911/ER even when the cause is dental**, because that's a "hang up and call emergency services" problem, not a "book an appointment" problem. Same-day dental urgencies (pulpitis, a localized abscess, isolated severe pain) are deliberately *not* red-flagged — those stay the LLM's job.
- **Every live tool call fires before the call can end.** "Someone will call you back" is never an acceptable terminal state for an emergency — the code enforces this as an invariant, not a convention (`enforce_tool_before_hangup` raises if a call-ending outcome carries zero tool calls).
- Inbound Twilio requests are signature-validated (`RequestValidator`, HMAC-SHA1) before anything is processed.

## Architecture

```
Caller ──dial──▶ Twilio number ──▶ ElevenLabs Conversational AI (STT/TTS)
                                          │
                                          ├─▶ Claude (turn-by-turn triage + response)
                                          │        │
                                          │        ▼
                                          │   red-flag layer (deterministic, every turn)
                                          │        │
                                          │        ├─ no flag → 4 non-emergency buckets
                                          │        └─ flag → scripted escalation (no LLM say)
                                          │
                                          ├─▶ live tool calls ──▶ Supabase (mock EHR:
                                          │                        patients, slots, insurance)
                                          │
                                          ├─▶ Twilio REST (live call transfer, on-call SMS)
                                          │
                                          └─▶ web input bar (frontend/, opened mid-call) for
                                               anything easier to type/photograph than say
```

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Telephony | Twilio | Required for hackathon prize eligibility; live call transfer support |
| Voice (STT/TTS) | ElevenLabs Conversational AI | Native Twilio integration, native barge-in support, no custom media-stream relay needed |
| Decision-maker | Anthropic Claude | Turn-by-turn triage/response — deliberately *not* the safety-critical path |
| Backend | Python + FastAPI | Webhook handlers for Twilio + ElevenLabs + tool calls |
| Data | Supabase (Postgres) | Mock EHR — patients, appointment slots, one insurance plan. No real patient data. |
| Web input | React + Vite | Side-channel for anything easier to type/upload than say aloud (insurance card, ID) |
| Hosting (demo) | ngrok | Local tunnel, started well ahead of stage time |

## Repo layout

```
app/safety/          deterministic red-flag detector + emergency escalation (T4/T5)
backend/agent/        triage prompt, tool definitions, webhook handlers, web-input session store
backend/app/          FastAPI app entrypoint, Supabase data access layer
backend/db/           schema + seed SQL for the mock EHR
frontend/             React web-input bar (mid-call text/file upload, phone-lookup fallback)
tests/, backend/tests/ isolation tests for the safety layer + integration tests against Supabase
docs/                 barge-in config notes, patient schema proposal
SPEC.md               source of truth: goal, constraints, invariants, task graph, bugs log
```

## Running it locally

```bash
# Backend
cd backend
pip install -r requirements.txt
cp ../.env.template ../.env   # fill in Twilio / Supabase / ElevenLabs keys
uvicorn app.main:app --reload --port 8000

# Frontend (web input bar)
cd frontend
npm install
npm run dev

# Expose the backend to Twilio/ElevenLabs
ngrok http 8000
```

Health check: `curl http://localhost:8000/healthz`

### Tests

```bash
# Safety layer (no network, no external services needed)
pytest tests -v

# Data layer (needs a live Supabase project — skips cleanly if unset)
cd backend && pytest tests -v
```

## What's deliberately out of scope

Called out explicitly so it reads as a decision, not an oversight, given the build window:

- No FSM-based conversation state machine — the LLM plus the deterministic regex layer is sufficient at this scale.
- No custom barge-in build — ElevenLabs exposes a native interruption flag, so that's what's used.
- No adapter/base-class abstraction layer — not worth the cost for an MVP.
- Scale target is a single concurrent caller; the data and webhook layers are kept stateless/swappable so scaling later is a config change, not a rewrite.
- Mock EHR only — no real patient data, no real clinical claims.

## Team

Built by a 4-person team in parallel branches, one owner per surface:

| Branch | Scope |
|---|---|
| `feat/telephony` | Twilio number, webhook, signature validation |
| `feat/data-knowledge` | Mock EHR, structured logging, post-call SMS |
| `feat/triage-conversation` | Triage prompt, 4 non-emergency buckets, personalization, barge-in |
| `feat/safety-escalation` | Red-flag detector, emergency escalation, tool-before-hangup enforcement |

Full detail — every constraint, invariant, task, and bug fixed along the way — lives in [SPEC.md](SPEC.md).
