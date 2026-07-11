# Patient schema proposal (for Person B — feat/data-knowledge)

Contract Person C needs for personalization (Invariants 5, 9). Not authoritative — Person B owns final schema, this is the read shape triage-conversation code will call against.

## `patients` table

| column | type | notes |
|---|---|---|
| `phone_number` | text, PK | E.164 format, matches Twilio `From` |
| `name` | text | |
| `last_visit_date` | date, nullable | null = new patient, greeting skips "last visit" line |
| `last_visit_reason` | text, nullable | e.g. "routine cleaning" |
| `insurance_plan_id` | text, nullable, FK → `insurance_plans.plan_id` | |

## `insurance_plans` table

| column | type | notes |
|---|---|---|
| `plan_id` | text, PK | |
| `plan_name` | text | |
| `coverage_notes` | text | plain-language coverage summary for the LLM to quote |

## Lookup contract

Given inbound caller phone number, triage code needs one call returning: `patient | None`, with insurance joined in (not a second round trip mid-call — Invariant 9 requires last-visit + insurance in the *first* turn).

Suggest a single Supabase RPC or view (`patient_with_insurance`) joining both tables on `phone_number`, so the triage code does one lookup, not two.
