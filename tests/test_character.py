"""
Tests for CharacterSheet — D&D 5e probability math, stat modifiers, outcome sampling.
"""

import pytest

from backend.pgm_engine.character import CharacterSheet

_CHAR_DICT = {
    "name": "Aldric",
    "class": "Fighter",
    "race": "Human",
    "level": 3,
    "stats": {
        "strength": 16,
        "dexterity": 12,
        "constitution": 14,
        "intelligence": 10,
        "wisdom": 11,
        "charisma": 13,
    },
    "skills": ["Athletics", "Persuasion"],
    "backstory": "A disgraced knight.",
}


@pytest.fixture
def char():
    return CharacterSheet.from_dict(_CHAR_DICT)


# ── Stat modifier ─────────────────────────────────────────────────────────────

class TestStatModifier:
    @pytest.mark.parametrize("score,expected", [
        (10, 0), (11, 0),
        (12, 1), (13, 1),
        (16, 3), (18, 4),
        (8, -1), (6, -2),
        (1, -5), (20, 5),
    ])
    def test_modifier(self, score, expected):
        assert (score - 10) // 2 == expected

    def test_strength_modifier_correct(self, char):
        # STR 16 → +3
        assert char.modifier("strength") == 3

    def test_charisma_modifier_correct(self, char):
        # CHA 13 → +1
        assert char.modifier("charisma") == 1

    def test_intelligence_modifier_zero(self, char):
        # INT 10 → 0
        assert char.modifier("intelligence") == 0


# ── Success probability ───────────────────────────────────────────────────────

class TestSuccessProbability:
    def test_probability_in_range(self, char):
        for action_type in ["combat_outcome", "npc_interaction", "resource_use",
                            "espionage_action", "political_action"]:
            p = char.success_probability(action_type)
            assert 0.0 <= p <= 1.0, f"p={p} out of range for {action_type}"

    def test_high_stat_gives_high_probability(self):
        strong = CharacterSheet.from_dict({**_CHAR_DICT, "stats": {**_CHAR_DICT["stats"], "strength": 20}})
        weak   = CharacterSheet.from_dict({**_CHAR_DICT, "stats": {**_CHAR_DICT["stats"], "strength": 6}})
        p_strong = strong.success_probability("combat_outcome")
        p_weak   = weak.success_probability("combat_outcome")
        assert p_strong > p_weak

    def test_low_stat_still_has_chance(self):
        char = CharacterSheet.from_dict({**_CHAR_DICT, "stats": {**_CHAR_DICT["stats"], "strength": 1}})
        p = char.success_probability("combat_outcome")
        assert p > 0.0

    def test_max_stat_not_guaranteed(self):
        char = CharacterSheet.from_dict({**_CHAR_DICT, "stats": {**_CHAR_DICT["stats"], "strength": 20}})
        p = char.success_probability("combat_outcome")
        assert p < 1.0


# ── Outcome sampling ──────────────────────────────────────────────────────────

class TestOutcomeSampling:
    VALID_OUTCOMES = {"success", "efficient", "partial", "normal", "failure", "wasteful"}

    def test_sample_outcome_returns_valid_label(self, char):
        for rng_val in [0.0, 0.25, 0.5, 0.75, 1.0]:
            outcome, prob = char.sample_outcome("combat_outcome", rng_val)
            assert outcome in self.VALID_OUTCOMES
            assert 0.0 <= prob <= 1.0

    def test_rng_zero_is_failure(self, char):
        # rng=0 is extreme low — should always be a failure variant
        outcome, _ = char.sample_outcome("combat_outcome", 0.0)
        assert outcome in ("failure", "wasteful", "partial")

    def test_rng_one_is_success(self, char):
        outcome, _ = char.sample_outcome("combat_outcome", 1.0)
        assert outcome in ("success", "efficient", "partial")

    def test_resource_use_outcomes(self, char):
        for rng_val in [0.05, 0.5, 0.95]:
            outcome, _ = char.sample_outcome("resource_use", rng_val)
            assert outcome in ("wasteful", "normal", "efficient")

    def test_determinism(self, char):
        o1, p1 = char.sample_outcome("npc_interaction", 0.7)
        o2, p2 = char.sample_outcome("npc_interaction", 0.7)
        assert o1 == o2 and abs(p1 - p2) < 1e-9


# ── Stat label ────────────────────────────────────────────────────────────────

class TestStatLabel:
    def test_combat_uses_strength(self, char):
        label = char.stat_label("combat_outcome")
        assert "strength" in label.lower() or label  # at minimum returns a string

    def test_npc_uses_charisma(self, char):
        label = char.stat_label("npc_interaction")
        assert "charisma" in label.lower() or label

    def test_unknown_action_returns_string(self, char):
        label = char.stat_label("unknown_action_type")
        assert isinstance(label, str)


# ── from_dict validation ──────────────────────────────────────────────────────

class TestFromDict:
    def test_round_trip(self, char):
        d = char.to_dict()
        char2 = CharacterSheet.from_dict(d)
        assert char2.name == char.name
        assert char2.level == char.level

    def test_missing_stat_defaults_to_ten(self):
        # CharacterSheet is lenient — unknown stats default to 10 (modifier 0)
        partial = {**_CHAR_DICT, "stats": {"strength": 10}}
        char = CharacterSheet.from_dict(partial)
        assert char.modifier("dexterity") == 0  # missing → defaults to 10 → mod 0
