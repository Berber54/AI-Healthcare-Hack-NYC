## §G Goal
Voice agent triage+book dental call, hello to done, Twilio required, guardrail hardcoded not LLM-judged.

## §C Constraints
- Build window 3-4hr, single day, live demo required (Healthcare Hack NYC + Twilio Searchlight).
- Twilio telephony mandatory for prize eligibility.
- Scope locked 5 triage buckets, no expansion mid-build: routine / urgent-non-emergency / true-emergency / non-dental-red-flag / insurance-cost.
- Red-flag escalation must be deterministic (regex/keyword layer), independent of LLM output — LLM cannot be argued out of escalating.
- No real patient data, no real clinical claims — mock EHR only.
- Reuse voice-assistant repo plumbing where possible (agent_turn webhook pattern, live tool-call pattern, ElevenLabs+Twilio provisioning, post-call SMS) — port pattern, not literal shared code (separate repo).

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

## §V Invariants
V1|red-flag detector runs every user turn, keyword/regex-based, not model-dependent|I.claude
V2|red-flag fire ! interrupt LLM flow, force scripted escalation, no LLM discretion|V1
V3|non-dental red flag (chest pain, breathing trouble, stroke signs) ! instruct 911/ER, never attempt booking|V1
V4|true dental emergency (avulsed tooth, uncontrolled bleeding, jaw trauma, swelling+fever) ! force emergency slot booking same call + live transfer or urgent SMS, before call ends|I.tools
V5|caller phone number lookup personalizes greeting when patient record match found|I.data
V6|every call outcome logged: transcript, classification, tool calls, escalation decisions|I.data
V7|every live tool call fires before call ends — never "someone will call you back" as terminal state|I.tools

## §T Tasks
id|status|desc|cites
T1|.|Twilio number + webhook reachable, scripted greeting smoke test|I.twilio
T2|.|mock data: 3-5 patients, appointment slots, one insurance plan|I.data
T3|.|triage prompt + 4 non-emergency buckets (routine/urgent/insurance/booking) end to end|V5,I.claude
T4|.|red-flag detector built + tested in isolation before wiring into main flow|V1,V2
T5|.|emergency escalation path wired into call flow (dental emergency + non-dental red flag)|V3,V4
T6|.|post-call SMS + call logging|V6,I.sms
T7|.|end-to-end test calls: routine call + emergency call, fix rough edges|T1,T3,T4,T5
T8|.|demo script rehearsal (2 calls) + Devpost writeup|T7

## §B Bugs
id|date|cause|fix
