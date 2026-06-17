"""
Action Classifier — maps free-text player input to a canonical action type.

Uses verb-first keyword matching. The player's primary verb determines the
action type — nouns like "enemy" or "soldiers" don't override an "ask" or "tell".
"""

from __future__ import annotations

import re

ACTION_TYPES = [
    "combat_outcome",
    "npc_interaction",
    "resource_use",
    "espionage_action",
    "political_action",
]

# Each entry is (action_type, weight, [keywords]).
# Keywords are matched as whole words. Higher weight = stronger signal.
# Ordered so that verb patterns are checked before noun patterns.
_RULES: list[tuple[str, float, list[str]]] = [
    # ── Espionage — sneak/spy verbs are unambiguous ──────────────────────────
    ("espionage_action", 2.0, [
        "sneak", "slip", "creep", "tiptoe", "hide", "conceal", "shadow",
        "tail", "follow secretly", "eavesdrop", "listen at", "peek",
        "spy", "surveil", "infiltrate", "disguise", "forge", "pickpocket",
        "steal", "pilfer", "pick the lock", "pick a lock", "decode", "decipher",
        "intercept", "scout ahead", "gather intelligence",
    ]),

    # ── Political — formal action verbs ──────────────────────────────────────
    ("political_action", 2.0, [
        "declare", "proclaim", "invoke", "vote", "propose", "motion",
        "endorse", "denounce", "petition", "address the council",
        "call a meeting", "issue an edict", "forge an alliance",
        "negotiate a treaty", "rally the faction", "make a speech",
    ]),
    ("political_action", 1.0, [
        "alliance", "treaty", "council", "diplomat", "parliament",
        "faction", "throne", "edict", "embassy", "pact",
    ]),

    # ── NPC interaction — social verbs are the primary signal ─────────────────
    ("npc_interaction", 2.0, [
        "ask", "tell", "say", "speak", "talk", "call out", "shout to",
        "warn", "plead", "beg", "urge", "convince", "persuade", "argue",
        "negotiate", "reason with", "introduce", "greet", "approach",
        "converse", "question", "interrogate", "befriend", "compliment",
        "insult", "threaten", "charm", "flatter", "deceive", "lie to",
        "reassure", "comfort", "appeal", "confess",
    ]),
    ("npc_interaction", 1.0, [
        "npc", "merchant", "guard", "soldier", "villager", "innkeeper",
        "noble", "king", "queen", "lord", "commander",
    ]),

    # ── Resource use — transaction/item verbs ────────────────────────────────
    ("resource_use", 2.0, [
        "buy", "sell", "purchase", "trade", "spend", "pay", "hire",
        "rent", "equip", "use item", "use potion", "drink potion",
        "eat", "consume", "craft", "repair", "loot", "search for supplies",
        "restock", "open chest", "check inventory",
    ]),
    ("resource_use", 1.0, [
        "gold", "coin", "potion", "item", "supply", "ration", "equipment",
        "inventory", "chest", "market", "shop",
    ]),

    # ── Combat — physical violence verbs (checked last so social verbs win) ──
    ("combat_outcome", 2.0, [
        "attack", "strike", "stab", "slash", "shoot", "fire at", "charge",
        "block", "parry", "dodge", "deflect", "evade the", "duck",
        "swing", "thrust", "punch", "kick", "wrestle", "grapple",
        "draw my sword", "draw my weapon", "engage", "fight", "duel",
        "slay", "kill", "cast a spell", "cast spell",
    ]),
    ("combat_outcome", 1.0, [
        "sword", "arrow", "bow", "blade", "dagger", "shield", "axe",
        "spear", "crossbow", "ambush", "battle", "combat",
    ]),
]


def classify_action(
    player_input: str,
    *,
    scene_text: str = "",
    current_act: int = 1,
    total_acts: int = 5,
) -> tuple[str, float]:
    """
    Classify free-text input into one of the five canonical action types.
    Returns (action_type, confidence).

    Verb matches score 2× noun matches so that "ask the soldiers" beats
    "enemies" appearing later in the same sentence.
    """
    text = player_input.lower()

    scores: dict[str, float] = {a: 0.0 for a in ACTION_TYPES}

    for action_type, weight, keywords in _RULES:
        for kw in keywords:
            # Use word-boundary match for single words, substring for phrases
            if " " in kw:
                if kw in text:
                    scores[action_type] += weight
            else:
                if re.search(r"\b" + re.escape(kw) + r"\b", text):
                    scores[action_type] += weight

    best = max(scores, key=scores.get)
    best_score = scores[best]

    if best_score == 0.0:
        return "npc_interaction", 0.5

    total = sum(scores.values())
    confidence = round(min(best_score / total, 0.99), 3)
    return best, confidence
