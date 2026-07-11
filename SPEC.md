## §G Goal
Voice agent triage+book dental call, hello to done, Twilio required, guardrail hardcoded not LLM-judged.

## §C Constraints
- Build window 3-4hr, single day, live demo required (Healthcare Hack NYC + Twilio Searchlight).
- Twilio telephony mandatory for prize eligibility.
- Scope locked 5 triage buckets, no expansion mid-build: routine / urgent-non-emergency / true-emergency / non-dental-red-flag / insurance-cost.
- Red-flag escalation must be deterministic (regex/keyword layer), independent of LLM output — LLM cannot be argued out of escalating.
- No real patient data, no real clinical claims — mock EHR only.
- Reuse VoiceAI_Scheduler repo plumbing where possible (github.com/Khushir474/VoiceAI_Scheduler) — agent_turn webhook pattern, live tool-call pattern, ElevenLabs+Twilio provisioning, post-call SMS — port pattern, not literal shared code (separate repo).
- Scale target MVP: single concurrent caller (1 user). Data layer + webhook handler kept stateless/swappable so future concurrency is config change not rewrite — no load testing or infra work this build window.
- Non-goals this build: barge-in custom implementation (only if ElevenLabs lacks native flag, see V10), FSM-based conversation state machine (VoiceAI_Scheduler's conversation_state_machine.py pattern — too heavy for 3-4hr window, LLM+deterministic-regex-layer sufficient), adapter-pattern abstraction (base+impl split adds cost MVP can't afford).

## §I Interfaces
- I.twilio — inbound call routing to webhook, live transfer capability.
- I.elevenlabs — STT/TTS conversational agent.
- I.claude — Anthropic API, turn-by-turn decision-maker.
- I.data — mock patient/appointment/insurance store (DynamoDB or JSON, pick fastest).
- I.sms — post-call SMS confirmation/instructions.
- I.tools — live tool calls mid-conversation:
  - book_appointment(slot, type)
  - book_urgent_slot(reason)
  - escalate_to_oncall(reason, patient_info)
  - transfer_call()
  - check_insurance(plan_id, procedure)
- I.logger — structured event log, run_id-keyed (port pattern from VoiceAI_Scheduler services/logger.py), backs V6/V11/V12.

## §V Invariants
V1|red-flag detector runs every user turn, keyword/regex-based, not model-dependent|I.claude
V2|red-flag fire ! interrupt LLM flow, force scripted escalation, no LLM discretion|V1
V3|non-dental red flag (chest pain, breathing trouble, stroke signs) ! instruct 911/ER, never attempt booking|V1
V4|true dental emergency (avulsed tooth, uncontrolled bleeding, jaw trauma, swelling+fever) ! force emergency slot booking same call + live transfer or urgent SMS, before call ends|I.tools
V5|caller phone number lookup personalizes greeting when patient record match found|I.data
V6|every call outcome logged: transcript, classification, tool calls, escalation decisions|I.data
V7|every live tool call fires before call ends — never "someone will call you back" as terminal state|I.tools
V8|Twilio webhook requests validated via Twilio RequestValidator (URL+params HMAC-SHA1, not raw-body SHA256 — differs from VoiceAI_Scheduler's Vapi pattern) before processing|I.twilio
V9|patient record match ! first turn pulls last visit/insurance context, not just name greeting|V5,I.data
V10|barge-in / mid-response interruption supported if ElevenLabs agent config exposes native flag — no custom build if absent|I.elevenlabs
V11|call transcript/log visibly viewable (plain JSON or simple view), not just stored|V6,I.data
V12|Claude/Twilio/ElevenLabs API failure ! graceful fallback (retry once, then scripted fallback response), never silent crash mid-call — port pattern from VoiceAI_Scheduler services/error_recovery.py|I.claude,I.twilio,I.elevenlabs

## §T Tasks
id|status|desc|cites
T1|.|Twilio number + webhook reachable, scripted greeting smoke test|I.twilio
T2|.|mock data: 3-5 patients, appointment slots, one insurance plan|I.data
T3|.|triage prompt + 4 non-emergency buckets (routine/urgent/insurance/booking) end to end|V5,I.claude
T4|.|red-flag detector built + tested in isolation before wiring into main flow|V1,V2
T5|.|emergency escalation path wired into call flow (dental emergency + non-dental red flag)|V3,V4
T6|.|post-call SMS + call logging|V6,I.sms
T7|.|end-to-end test calls: routine call + emergency call, fix rough edges|T1,T3,T4,T5
T8|.|demo script rehearsal (2 calls, emergency call must trigger live escalation on stage not just described) + Devpost writeup|T7,V3,V4

## §P Parallel Branches (4-person split)
Order: T1 solo first (~20-30min, blocking — webhook contract others depend on). Then 4 branches parallel. Merge into main before T7.

branch|owner-role|cites|desc
feat/telephony|Person A|T1,V8,I.twilio|Twilio number+webhook live, signature validation (RequestValidator), scripted greeting smoke test. Do this first, solo, before others branch.
feat/data-knowledge|Person B|T2,T6,V6,V11,I.data,I.logger|Mock EHR (3-5 patients, slots, insurance plan), structured logger (run_id-keyed), post-call SMS, visible transcript/log view.
feat/triage-conversation|Person C|T3,V5,V9,V10,I.claude|Triage prompt, 4 non-emergency buckets, personalization (caller lookup + last-visit/insurance context), barge-in check (native ElevenLabs flag only).
feat/safety-escalation|Person D|T4,T5,V1,V2,V3,V4,V7,I.tools|Red-flag detector (build+test isolated first), emergency escalation wiring (dental + non-dental), forced tool-call-before-hangup.

V12 (API failure fallback) is cross-cutting — each owner adds fallback for their own surface: A→Twilio, C→Claude+ElevenLabs, B→data/logger read failures.

Integration: T7 (e2e test calls) + T8 (demo rehearsal) run all-hands after branches merge to main.

## §B Bugs
id|date|cause|fix
