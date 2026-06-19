"""
Character stat → action success probability mapper.

D&D 5e uses ability scores (3–20 typical range, 10 = human average).
We convert each stat to a modifier: modifier = (stat - 10) // 2
Then compute a sigmoid-based probability of success for each action type.

This is the ONLY place character stats affect outcomes — the LLM never sees
raw probabilities and cannot override them.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

# Action type → primary stat + optional secondary stat (half weight)
ACTION_STAT_MAP: dict[str, tuple[str, str | None]] = {
    "combat_outcome":   ("strength",     "constitution"),
    "npc_interaction":  ("charisma",     "wisdom"),
    "resource_use":     ("intelligence", None),
    "espionage_action": ("dexterity",    "intelligence"),
    "political_action": ("charisma",     "intelligence"),
}

# Outcome thresholds: prob < LOW → failure, LOW ≤ prob < HIGH → partial, ≥ HIGH → success
_FAILURE_THRESHOLD = 0.35
_SUCCESS_THRESHOLD = 0.65

OUTCOME_STATES = {
    "combat_outcome":   ["failure", "partial", "success"],
    "npc_interaction":  ["failure", "partial", "success"],
    "resource_use":     ["wasteful", "normal", "efficient"],
    "espionage_action": ["failure", "partial", "success"],
    "political_action": ["failure", "partial", "success"],
}


@dataclass
class CharacterSheet:
    name: str
    char_class: str
    race: str
    level: int
    stats: dict[str, int]
    skills: list[str]
    backstory: str = ""

    @classmethod
    def from_dict(cls, data: dict) -> "CharacterSheet":
        return cls(
            name=data["name"],
            char_class=data["class"],
            race=data["race"],
            level=data["level"],
            stats=data["stats"],
            skills=data.get("skills", []),
            backstory=data.get("backstory", ""),
        )

    def to_dict(self) -> dict:
        return {
            "name": self.name,
            "class": self.char_class,
            "race": self.race,
            "level": self.level,
            "stats": self.stats,
            "skills": self.skills,
            "backstory": self.backstory,
        }

    def modifier(self, stat: str) -> int:
        """Standard D&D 5e ability modifier."""
        score = self.stats.get(stat.lower(), 10)
        return (score - 10) // 2

    def skill_bonus(self, action_type: str) -> int:
        """Return +2 proficiency bonus if any of the character's skills apply."""
        skill_action_map = {
            "combat_outcome":   ["Athletics", "Acrobatics"],
            "npc_interaction":  ["Persuasion", "Deception", "Intimidation"],
            "resource_use":     ["Investigation", "Arcana"],
            "espionage_action": ["Stealth", "Perception", "Sleight of Hand"],
            "political_action": ["History", "Persuasion", "Insight"],
        }
        relevant = skill_action_map.get(action_type, [])
        if any(s in self.skills for s in relevant):
            return 2   # standard proficiency bonus
        return 0

    def success_probability(self, action_type: str) -> float:
        """
        Return p(success) ∈ [0,1] for a given action type.

        Formula:
          raw = primary_modifier + 0.5 * secondary_modifier + skill_bonus + level_factor
          p = sigmoid(raw / 2.5)

        Level factor gives slight edge to higher-level characters.
        """
        mapping = ACTION_STAT_MAP.get(action_type)
        if mapping is None:
            return 0.5  # unknown action → coin flip

        primary_stat, secondary_stat = mapping
        raw = float(self.modifier(primary_stat))
        if secondary_stat:
            raw += 0.5 * self.modifier(secondary_stat)
        raw += self.skill_bonus(action_type)
        raw += (self.level - 1) * 0.2   # +0.2 raw per level above 1

        # Sigmoid centred at 0 (average character → 50% success)
        p = 1.0 / (1.0 + math.exp(-raw / 2.5))
        return round(p, 4)

    def sample_outcome(self, action_type: str, rng_value: float) -> tuple[str, float]:
        """
        Given a pre-sampled uniform rng_value ∈ [0,1], return (outcome_state, p_success).

        rng_value is passed in (not sampled here) so the caller can seed it
        for reproducibility.
        """
        p = self.success_probability(action_type)
        states = OUTCOME_STATES.get(action_type, ["failure", "partial", "success"])

        # Partition [0,1]: failure gets (1-p)^1.5, success gets p^1.5,
        # partial fills the remainder — success more likely when p is high.
        p_fail = (1 - p) ** 1.5
        p_success = p ** 1.5
        p_partial = max(0.0, 1.0 - p_fail - p_success)

        if rng_value < p_fail:
            state = states[0]   # failure / wasteful
        elif rng_value < p_fail + p_partial:
            state = states[1]   # partial / normal
        else:
            state = states[2]   # success / efficient

        return state, p

    def stat_label(self, action_type: str) -> str:
        """Return the primary stat name for display in narration."""
        mapping = ACTION_STAT_MAP.get(action_type)
        if mapping:
            return mapping[0]
        return "ability"
