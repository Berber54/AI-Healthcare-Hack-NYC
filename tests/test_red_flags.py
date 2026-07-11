"""T4 isolation tests — no network, no Twilio/Claude/ElevenLabs, pure function."""

from app.safety.contract import RedFlagCategory
from app.safety.red_flags import check_red_flag


NON_DENTAL_POSITIVES = [
    "I'm having really bad chest pain right now",
    "I can't breathe properly",
    "my face is drooping and my speech is slurred",
    "I think my dad just had a heart attack",
    "she just passed out and won't wake up",
]

DENTAL_EMERGENCY_POSITIVES = [
    "my son's tooth got knocked out playing soccer",
    "my tooth just fell out after I got hit",
    "the bleeding from my gums won't stop",
    "I hit my jaw and now it's dislocated",
    "my cheek is swollen and I have a fever of 102",
]

ROUTINE_NEGATIVES = [
    "I'd like to book a routine cleaning",
    "I have a small cavity that's been bothering me",
    "what's my insurance copay for a filling",
    "my gum is a little swollen but no fever",
    "I have a slight fever from a cold, unrelated to my teeth",
]


def test_non_dental_emergencies_detected():
    for text in NON_DENTAL_POSITIVES:
        result = check_red_flag(text)
        assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY, text
        assert result.is_red_flag
        assert result.matched_keywords


def test_dental_emergencies_detected():
    for text in DENTAL_EMERGENCY_POSITIVES:
        result = check_red_flag(text)
        assert result.category is RedFlagCategory.DENTAL_EMERGENCY, text
        assert result.is_red_flag
        assert result.matched_keywords


def test_routine_turns_are_not_flagged():
    for text in ROUTINE_NEGATIVES:
        result = check_red_flag(text)
        assert result.category is RedFlagCategory.NONE, text
        assert not result.is_red_flag


def test_swelling_alone_is_not_a_red_flag():
    result = check_red_flag("my jaw area is a bit swollen today")
    assert result.category is RedFlagCategory.NONE


def test_fever_alone_is_not_a_red_flag():
    result = check_red_flag("I have a fever but my teeth feel fine")
    assert result.category is RedFlagCategory.NONE


def test_swelling_and_fever_together_is_dental_emergency():
    result = check_red_flag("my face is swollen and I have a fever")
    assert result.category is RedFlagCategory.DENTAL_EMERGENCY
    assert "swelling_with_fever" in result.matched_keywords


def test_non_dental_takes_priority_over_dental_when_both_match():
    text = "my tooth got knocked out and now I also have chest pain"
    result = check_red_flag(text)
    assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY


def test_is_case_insensitive():
    result = check_red_flag("MY TOOTH GOT KNOCKED OUT")
    assert result.category is RedFlagCategory.DENTAL_EMERGENCY


def test_raw_turn_text_preserved():
    text = "I can't breathe"
    result = check_red_flag(text)
    assert result.raw_turn_text == text


# --- Clinical review (dentist, 2026-07-11): airway/systemic compromise routes
# to 911/ER even when the presentation starts as dental (Ludwig's-angina-type
# signs), not into the dental-emergency booking path. ---

AIRWAY_RISK_DENTAL_ORIGIN_POSITIVES = [
    "I have trouble swallowing my own saliva and I'm drooling",
    "the swelling under my tongue is spreading to my neck",
    "my voice sounds muffled and the swelling under my jaw is firm",
]


def test_airway_risk_swelling_of_dental_origin_routes_to_non_dental_911():
    for text in AIRWAY_RISK_DENTAL_ORIGIN_POSITIVES:
        result = check_red_flag(text)
        assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY, text


def test_anaphylaxis_after_medication_is_non_dental_911():
    text = "my lips and tongue are swelling and I can't breathe right after taking amoxicillin"
    result = check_red_flag(text)
    assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY
    assert "anaphylaxis" in result.matched_keywords


def test_massive_hemorrhage_with_shock_signs_is_non_dental_911():
    text = "bleeding won't stop and I feel really dizzy and pale"
    result = check_red_flag(text)
    assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY
    assert "massive_hemorrhage" in result.matched_keywords


def test_seizure_or_unconscious_is_non_dental_911():
    result = check_red_flag("he's having a seizure and is unresponsive")
    assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY


def test_severe_hypoglycemia_requires_altered_consciousness():
    # Bare mention of being diabetic must not trigger — only combined with
    # altered consciousness does this become a 911 case.
    assert check_red_flag("I'm diabetic and need to reschedule").category is RedFlagCategory.NONE
    result = check_red_flag("I'm diabetic, my blood sugar is low and I'm getting confused")
    assert result.category is RedFlagCategory.NON_DENTAL_EMERGENCY


# --- Dental-emergency bucket: structural/hemorrhage/trauma issues without
# airway compromise. Forces same-call booking + transfer/SMS (Invariant 4). ---


def test_persistent_post_extraction_bleeding_is_dental_emergency():
    text = "I'm bleeding a lot since my extraction and it won't stop"
    result = check_red_flag(text)
    assert result.category is RedFlagCategory.DENTAL_EMERGENCY
    assert "uncontrolled_bleeding" in result.matched_keywords


def test_dentoalveolar_trauma_beyond_jaw_wording_is_dental_emergency():
    # Broadened beyond the word "jaw" — a fall/accident affecting the tooth,
    # mouth, or bite is the same clinical category.
    text = "I fell and my tooth is loose and my bite feels off"
    result = check_red_flag(text)
    assert result.category is RedFlagCategory.DENTAL_EMERGENCY
    assert "dentoalveolar_trauma" in result.matched_keywords


# --- False-positive guards called out explicitly by clinical review: a body
# part + pain word alone should never be enough to fire an emergency. ---


def test_jaw_pain_without_trauma_context_is_not_flagged():
    result = check_red_flag("my jaw hurts when I chew")
    assert result.category is RedFlagCategory.NONE


def test_minor_gum_bleeding_is_not_flagged():
    result = check_red_flag("my gums bleed a little when I brush")
    assert result.category is RedFlagCategory.NONE


def test_negated_fever_does_not_combine_with_swelling():
    # Regression: "swollen but no fever" previously matched on the literal
    # substring "fever" inside the negated phrase and misfired as an emergency.
    result = check_red_flag("my gum is a little swollen but no fever")
    assert result.category is RedFlagCategory.NONE


def test_same_day_dental_urgencies_are_not_red_flagged():
    # Pulpitis, pericoronitis, localized abscess, isolated severe pain — these
    # are same-day urgencies triaged by the LLM (T3), not this module's job.
    same_day_urgent = [
        "I have a throbbing toothache that won't go away with painkillers",
        "the tooth in the back near my wisdom tooth is really painful and swollen right there",
        "I have a small abscess on one tooth, it's sore but I don't have a fever",
    ]
    for text in same_day_urgent:
        result = check_red_flag(text)
        assert result.category is RedFlagCategory.NONE, text
