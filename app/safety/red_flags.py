"""T4 — deterministic red-flag detector. Invariants 1, 2.

Pure keyword/regex matching, no LLM call, no network call — this must be safe
to run on every user turn before the LLM sees the text, and must stay testable
without any of the other services (Twilio/ElevenLabs/Claude/Supabase) running.

Category boundaries reviewed with a practicing dentist (2026-07-11):
- Airway/systemic compromise routes to 911/ER even when the cause is dental —
  a Ludwig's-angina-type presentation (floor-of-mouth swelling, can't swallow,
  muffled voice, swelling tracking to the neck) starts in the mouth but is not
  a "book an emergency slot" problem, it's a "hang up and call 911" problem.
- Same-day dental urgencies (pulpitis, pericoronitis, localized abscess,
  isolated severe pain, fracture with pulp exposure but no major trauma) are
  deliberately NOT red-flagged here. They fall through to NONE and are
  triaged by the LLM as "urgent-non-emergency" (Person C's T3 territory,
  urgent-non-emergency bucket) — this module only owns the two red-flag
  buckets that override LLM discretion (Invariants 3 and 4).

Non-dental patterns take priority over dental ones when both match in the same
turn: life-safety escalation (Invariant 3) outranks a dental-only emergency.
"""

from __future__ import annotations

import re

from app.safety.contract import RedFlagCategory, RedFlagResult

_NON_DENTAL_PATTERNS: dict[str, re.Pattern] = {
    "chest_pain": re.compile(r"\bchest\s+(pain|pressure|tightness|hurts?)\b"),
    "breathing_trouble": re.compile(
        r"\b(can'?t breathe|cannot breathe|difficulty breathing|trouble breathing|"
        r"shortness of breath|struggling to breathe|throat.*closing|stridor|"
        r"high[- ]pitched (sound|noise).{0,15}breath)\b"
    ),
    # Ludwig's-angina-type airway risk: dental origin, non-dental disposition.
    "dysphagia_or_drooling": re.compile(
        r"\b(can'?t|cannot|unable to|trouble|difficulty) swallow\w*\b|"
        r"\bnew drooling\b|\bdrooling.{0,15}(can'?t|won'?t) stop\b"
    ),
    "muffled_voice": re.compile(
        r"\bmuffled voice\b|\bhot potato voice\b|\bvoice sounds (muffled|weird|strange)\b"
    ),
    "floor_of_mouth_or_neck_swelling": re.compile(
        r"\b(floor of (my |the )?mouth|under (my )?tongue).{0,20}(swoll?en|swelling|firm)\b|"
        r"\btongue.{0,15}(raised|elevated|pushed up)\b|"
        r"\bswelling.{0,20}(spreading|going|moving) (to|toward) (my )?neck\b|"
        r"\b(neck|under (my )?jaw|submandibular).{0,15}(swoll?en|swelling|firm|hard)\b"
    ),
    "stroke_signs": re.compile(
        r"\bface\b.{0,20}droop\w*|droop\w*.{0,20}\bface\b|"
        r"\bslurr\w*.{0,15}speech\b|\bspeech\b.{0,15}slurr\w*|"
        r"\bcan'?t speak right\b|\bsuddenly confused\b|\bsudden confusion\b|"
        r"\bone side.{0,20}(numb|weak)\b|\barm (is )?weak\b"
    ),
    "anaphylaxis": re.compile(
        r"\b(anaphyla\w*|severe allergic reaction)\b|"
        r"\b(lips?|tongue|throat).{0,20}(swell\w*|swoll?en).{0,30}(breath|hoarse|wheez)\w*\b"
    ),
    "seizure_or_unconscious": re.compile(
        r"\b(seizure|convulsing|convulsion|unconscious|unresponsive|won'?t wake up|"
        r"passed out|fainted|losing consciousness|collapsed)\b"
    ),
    "rapid_deterioration": re.compile(
        r"\b(getting worse (fast|quickly|rapidly)|rapidly (deteriorating|getting worse)|"
        r"can'?t stay awake)\b"
    ),
    "craniofacial_trauma_with_neuro_signs": re.compile(
        r"\bhit (my |his |her )?head\b.{0,40}(confus\w*|vomit\w*|dizzy|pass(ed)? out)\b|"
        r"\bhead injury\b.{0,40}(confus\w*|vomit\w*)\b"
    ),
    # Distinct from dental "uncontrolled_bleeding": this requires shock-type signs,
    # not just "won't stop" — that alone is a dental-emergency booking, not 911.
    "massive_hemorrhage": re.compile(
        r"\bbleeding.{0,25}(a lot|heavily|won'?t stop).{0,25}"
        r"(dizzy|light[- ]?headed|faint|weak|pale)\b|"
        r"\b(dizzy|light[- ]?headed|faint|weak|pale).{0,25}bleeding\b"
    ),
    "cardiac_event": re.compile(r"\bheart attack\b"),
}

_DENTAL_PATTERNS: dict[str, re.Pattern] = {
    "avulsed_tooth": re.compile(
        r"\b(tooth|teeth).{0,20}(knocked out|came out|fell out|got knocked)\b|"
        r"\bknocked out.{0,10}(my )?tooth\b|\bavulsed\b"
    ),
    "uncontrolled_bleeding": re.compile(
        r"\b(bleeding|blood).{0,25}(won'?t stop|not stopping|uncontrolled|"
        r"keeps? bleeding|soaking (through )?(the )?gauze)\b|"
        r"\bbleeding (a lot |heavily )?(since|after) (my |the )?extraction\b"
    ),
    "post_extraction_complication": re.compile(
        r"\b(dry socket|extraction site).{0,25}(bleeding|swelling|pain).{0,20}"
        r"(worse|worsening|won'?t stop|getting worse)\b"
    ),
}

# Dentoalveolar trauma needs a cause + a body part + an effect together, not just
# a body part mentioned near a pain word — otherwise "my jaw hurts" (TMJ, routine)
# reads the same as "I got hit and my jaw is dislocated" (true emergency).
_TRAUMA_CAUSE_RE = re.compile(
    r"\b(hit|got hit|fell|fall|accident|blow|collision|trauma|injury|knocked)\b"
)
_TRAUMA_EFFECT_RE = re.compile(
    r"\b(broken|dislocated|fractured|can'?t (close|open)|loose|wobbly|"
    r"deformed|moved|bite (feels|is) (off|different|wrong))\b"
)
_TRAUMA_BODY_PART_RE = re.compile(r"\b(jaw|tooth|teeth|mouth|face)\b")

# Same AND-not-sequence problem as trauma: "my blood sugar is low and I'm
# getting confused" doesn't fit a single ordered regex window, so these are
# checked independently and combined — requires altered consciousness, not
# just "I'm diabetic", to avoid over-triggering.
_HYPOGLYCEMIA_CAUSE_RE = re.compile(
    r"\b(low blood sugar|blood sugar.{0,10}low|hypoglycemi\w*|diabetic)\b"
)
_ALTERED_CONSCIOUSNESS_RE = re.compile(
    r"\b(confus\w*|passing out|passed out|unresponsive|shaking badly|can'?t think straight)\b"
)

_SWELLING_RE = re.compile(r"\bswoll?en|swelling\b")
_FEVER_RE = re.compile(r"\bfever|temperature|hot to the touch\b")
_NEGATION_RE = re.compile(r"\b(no|not|isn'?t|don'?t|doesn'?t|without|never)\b")


def _match_any(text: str, patterns: dict[str, re.Pattern]) -> list[str]:
    return [name for name, pattern in patterns.items() if pattern.search(text)]


def _is_dentoalveolar_trauma(text: str) -> bool:
    return bool(
        _TRAUMA_BODY_PART_RE.search(text)
        and _TRAUMA_CAUSE_RE.search(text)
        and _TRAUMA_EFFECT_RE.search(text)
    )


def _is_severe_hypoglycemia(text: str) -> bool:
    return bool(_HYPOGLYCEMIA_CAUSE_RE.search(text) and _ALTERED_CONSCIOUSNESS_RE.search(text))


def _present_and_not_negated(text: str, symptom_re: re.Pattern, window: int = 15) -> bool:
    """True if symptom_re matches somewhere not immediately preceded by a negation.

    Catches "swollen but no fever" — a plain substring match on "fever" would
    otherwise fire a red flag on a negated symptom.
    """
    for match in symptom_re.finditer(text):
        preceding = text[max(0, match.start() - window) : match.start()]
        if _NEGATION_RE.search(preceding):
            continue
        return True
    return False


def check_red_flag(turn_text: str) -> RedFlagResult:
    text = turn_text.lower()

    non_dental_matches = _match_any(text, _NON_DENTAL_PATTERNS)
    if _is_severe_hypoglycemia(text):
        non_dental_matches.append("severe_hypoglycemia")
    if non_dental_matches:
        return RedFlagResult(
            category=RedFlagCategory.NON_DENTAL_EMERGENCY,
            matched_keywords=non_dental_matches,
            raw_turn_text=turn_text,
        )

    dental_matches = _match_any(text, _DENTAL_PATTERNS)
    if _is_dentoalveolar_trauma(text):
        dental_matches.append("dentoalveolar_trauma")
    if _present_and_not_negated(text, _SWELLING_RE) and _present_and_not_negated(text, _FEVER_RE):
        dental_matches.append("swelling_with_fever")
    if dental_matches:
        return RedFlagResult(
            category=RedFlagCategory.DENTAL_EMERGENCY,
            matched_keywords=dental_matches,
            raw_turn_text=turn_text,
        )

    return RedFlagResult(
        category=RedFlagCategory.NONE,
        matched_keywords=[],
        raw_turn_text=turn_text,
    )
