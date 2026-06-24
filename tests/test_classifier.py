"""
Tests for the verb-first action classifier.

Key design: social verbs (ask, tell, urge, convince) score 2× vs combat nouns (sword, attack);
so "ask the soldiers" should NOT classify as combat_outcome.
"""

import pytest

from backend.llm.classifier import classify_action


# ── Sanity: returns a known action type ──────────────────────────────────────

VALID_TYPES = {
    "combat_outcome",
    "npc_interaction",
    "resource_use",
    "espionage_action",
    "political_action",
}


def _classify(text):
    action_type, confidence = classify_action(text, scene_text="", current_act=1, total_acts=5)
    return action_type, confidence


class TestReturnShape:
    def test_returns_tuple(self):
        result = classify_action("I attack the guard", scene_text="", current_act=1, total_acts=5)
        assert len(result) == 2

    def test_action_type_is_valid(self):
        action_type, _ = _classify("I swing my sword at the enemy")
        assert action_type in VALID_TYPES

    def test_confidence_in_range(self):
        _, confidence = _classify("I look around the room")
        assert 0.0 <= confidence <= 1.0


# ── Combat classification ─────────────────────────────────────────────────────

class TestCombatClassification:
    def test_attack_verb_is_combat(self):
        action, _ = _classify("I attack the soldier with my sword")
        assert action == "combat_outcome"

    def test_fight_is_combat(self):
        action, _ = _classify("I fight my way through the guards")
        assert action == "combat_outcome"

    def test_shoot_arrow_is_combat(self):
        action, _ = _classify("I shoot an arrow at the enemy")
        assert action == "combat_outcome"


# ── Social / NPC classification ───────────────────────────────────────────────

class TestNPCClassification:
    def test_persuade_is_npc(self):
        action, _ = _classify("I try to persuade the innkeeper")
        assert action == "npc_interaction"

    def test_ask_is_npc(self):
        action, _ = _classify("I ask the guard what happened")
        assert action == "npc_interaction"

    def test_convince_is_npc(self):
        action, _ = _classify("I convince the merchant to help us")
        assert action == "npc_interaction"

    def test_social_verb_beats_combat_noun(self):
        # "ask the soldiers" — verb 'ask' (social) should win over noun 'soldiers'
        action, _ = _classify("I ask the soldiers why they are here")
        assert action == "npc_interaction"


# ── Resource use ──────────────────────────────────────────────────────────────

class TestResourceClassification:
    def test_buy_supplies_is_resource(self):
        action, _ = _classify("I buy supplies at the market")
        assert action == "resource_use"

    def test_spend_gold_is_resource(self):
        action, _ = _classify("I spend my gold on a horse")
        assert action == "resource_use"


# ── Espionage ─────────────────────────────────────────────────────────────────

class TestEspionageClassification:
    def test_sneak_is_espionage(self):
        action, _ = _classify("I sneak into the enemy camp")
        assert action == "espionage_action"

    def test_spy_is_espionage(self):
        action, _ = _classify("I spy on the council meeting")
        assert action == "espionage_action"


# ── Political ─────────────────────────────────────────────────────────────────

class TestPoliticalClassification:
    def test_formal_decree_is_political(self):
        # "formal decree" / "make a speech" / "rally the faction" → political
        action, _ = _classify("I make a formal speech before the council")
        assert action == "political_action"

    def test_alliance_is_political(self):
        action, _ = _classify("I propose an alliance with the northern faction")
        assert action == "political_action"
