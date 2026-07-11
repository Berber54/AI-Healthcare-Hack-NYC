# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project state

This repository currently contains only [SPEC.md](SPEC.md) — no source code, build tooling, or tests exist yet. Implementation is happening in parallel across team-owned branches (e.g. `feat/safety-escalation`). Read SPEC.md in full before writing code; it is the single source of truth for scope, and its structure (sections `§G/§C/§I/§V/§T/§B`) is referenced by task IDs elsewhere (standups, branch names, commit messages).

Since there is no established stack yet, check for a branch/commit that has already made a stack decision (Node/TS vs Python) before introducing a new one, and prefer reusing the pattern from the team's prior `voice-assistant` repo referenced in §C ("port pattern, not literal shared code") — the webhook-per-turn shape, live tool-call dispatch, and ElevenLabs+Twilio provisioning approach.

## The build: dental triage voice agent

Voice agent that triages an inbound call and books a dental appointment, live over Twilio telephony, in a single hackathon build window (Healthcare Hack NYC + Twilio Searchlight prize). No LLM-judged guardrails — the safety-critical path must be deterministic.

Scope is locked to 5 triage buckets — do not add more mid-build:
- routine
- urgent-non-emergency
- true-emergency (dental)
- non-dental-red-flag
- insurance-cost

### Architecture (per §I)

- **I.twilio** — inbound call routing to a webhook; must support live call transfer.
- **I.elevenlabs** — STT/TTS for the conversational turn.
- **I.claude** — Anthropic API as the turn-by-turn decision-maker (triage classification, response generation). This is *not* where safety-critical branching lives — see Invariants below.
- **I.data** — mock patient/appointment/insurance store (DynamoDB or JSON — pick whichever is fastest to stand up). No real patient data, no real clinical claims.
- **I.sms** — post-call SMS confirmation/instructions.
- **I.tools** — live tool calls fired mid-conversation, not deferred to after the call:
  - `book_appointment(slot, type)`
  - `book_urgent_slot(reason)`
  - `escalate_to_oncall(reason, patient_info)`
  - `transfer_call()`
  - `check_insurance(plan_id, procedure)`

### Safety invariants (§V) — the load-bearing part of this codebase

The core architectural rule: **red-flag detection is a deterministic keyword/regex layer that runs independently of the LLM, on every user turn, and can override the LLM's discretion.** The LLM decides triage/booking flow for the 4 non-emergency buckets, but it cannot argue its way out of an escalation once the red-flag layer fires.

- V1 — red-flag detector runs every user turn; keyword/regex-based, not model-dependent.
- V2 — a red-flag firing interrupts the LLM flow and forces a scripted escalation with no LLM discretion.
- V3 — non-dental red flags (chest pain, breathing trouble, stroke signs) → instruct 911/ER, never attempt booking.
- V4 — true dental emergencies (avulsed tooth, uncontrolled bleeding, jaw trauma, swelling+fever) → force an emergency slot booking in the same call, plus live transfer or urgent SMS, before the call ends.
- V5 — caller phone number lookup personalizes the greeting when a patient record matches.
- V6 — every call outcome is logged: transcript, classification, tool calls, escalation decisions.
- V7 — every live tool call fires *before* the call ends — "someone will call you back" is never a terminal state without a tool call having fired.

When implementing anything touching triage or escalation, treat V1–V4 and V7 as hard constraints, not defaults to be relaxed for convenience.

### Task graph (§T)

Tasks cite the invariants/interfaces they satisfy — use that mapping to know what "done" means for a task (e.g. T4 cites V1/V2, so a red-flag detector isn't done until it's model-independent and runs every turn). T4 (red-flag detector) is built and isolation-tested *before* T5 wires it into the main call flow — don't skip straight to integration.

### Bugs log (§B)

SPEC.md has a `§B Bugs` table (id/date/cause/fix) — check it for known issues before debugging something that's already been diagnosed, and append to it (don't just fix silently) when you resolve a non-obvious bug during the hackathon build.
