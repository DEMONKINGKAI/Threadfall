"""
Character Randomizer — generates a believable D&D character via the LLM.

Falls back to a curated local pool if the LLM is unavailable.
"""

from __future__ import annotations

import random
import re

from huggingface_hub import InferenceClient

from backend.llm.narrator import _HF_TOKEN, _MODELS

# ── Canonical lists ──────────────────────────────────────────────────────────

CLASSES = [
    "Fighter","Rogue","Wizard","Cleric","Ranger","Paladin",
    "Bard","Druid","Barbarian","Monk","Sorcerer","Warlock",
]
RACES = [
    "Human","Elf","Dwarf","Halfling","Tiefling","Half-Orc","Gnome","Dragonborn",
]
CLASS_SKILLS: dict[str, list[str]] = {
    "Fighter":   ["Athletics","Intimidation"],
    "Rogue":     ["Stealth","Deception"],
    "Wizard":    ["Arcana","History"],
    "Cleric":    ["Religion","Medicine"],
    "Ranger":    ["Survival","Perception"],
    "Paladin":   ["Persuasion","Athletics"],
    "Bard":      ["Performance","Persuasion"],
    "Druid":     ["Nature","Animal Handling"],
    "Barbarian": ["Athletics","Survival"],
    "Monk":      ["Acrobatics","Insight"],
    "Sorcerer":  ["Arcana","Persuasion"],
    "Warlock":   ["Arcana","Deception"],
}
_FALLBACK_NAMES = [
    "Mira","Edric","Vael","Corvyn","Serath","Theron",
    "Lysa","Torn","Aelric","Dusk","Brynn","Varek","Kessa","Oryn",
]
_FALLBACK_BACKSTORIES = [
    "Stripped of rank and title after questioning the wrong lord, you wander with nothing but a blade and a bitter memory.",
    "Your village was the first to burn when the pact shattered. You are the only one who remembers its name.",
    "Once a spy for the council, you defected when you learned who gave the orders. Now both sides want you dead.",
    "You were born in the borderlands, where every child learns to read the wind before they learn to read words.",
    "The scar on your palm is a brand — a reminder of the oath you swore and the price you paid for breaking it.",
    "Three commanders have given you orders. You watched all three fall. Now you take orders from no one.",
]

# ── LLM prompt ───────────────────────────────────────────────────────────────

_SYSTEM = (
    "You generate D&D 5e characters for a dark gothic campaign called 'The Shattered Pact'. "
    "Each character should feel morally complex, weathered, and fit for a world on the edge of war. "
    "Respond in EXACTLY this format and nothing else:\n"
    "NAME: <a medieval fantasy name, 1-2 words>\n"
    "CLASS: <one of: Fighter Rogue Wizard Cleric Ranger Paladin Bard Druid Barbarian Monk Sorcerer Warlock>\n"
    "RACE: <one of: Human Elf Dwarf Halfling Tiefling Half-Orc Gnome Dragonborn>\n"
    "LEVEL: <integer 2-5>\n"
    "STR: <integer 8-18>\n"
    "DEX: <integer 8-18>\n"
    "CON: <integer 8-18>\n"
    "INT: <integer 8-18>\n"
    "WIS: <integer 8-18>\n"
    "CHA: <integer 8-18>\n"
    "BACKSTORY: <exactly 2 sentences, dark and specific, second-person or third-person>"
)
_USER = "Generate a single unique D&D character now. Make them feel like someone who has survived real hardship."


# ── Parser ───────────────────────────────────────────────────────────────────

def _parse(text: str, rng: random.Random) -> dict:
    def field(key: str) -> str | None:
        m = re.search(rf"^{key}:\s*(.+)", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else None

    def stat(key: str, lo: int = 8, hi: int = 18) -> int:
        raw = field(key)
        try:
            return max(lo, min(hi, int(raw)))  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return rng.randint(lo, hi)

    char_class_raw = field("CLASS") or rng.choice(CLASSES)
    char_class = next(
        (c for c in CLASSES if c.lower() == char_class_raw.lower()),
        char_class_raw,
    )

    return {
        "name":    field("NAME") or rng.choice(_FALLBACK_NAMES),
        "class":   char_class,
        "race":    field("RACE") or rng.choice(RACES),
        "level":   stat("LEVEL", 2, 5),
        "stats": {
            "strength":     stat("STR"),
            "dexterity":    stat("DEX"),
            "constitution": stat("CON"),
            "intelligence": stat("INT"),
            "wisdom":       stat("WIS"),
            "charisma":     stat("CHA"),
        },
        "backstory": field("BACKSTORY") or rng.choice(_FALLBACK_BACKSTORIES),
        "skills":    CLASS_SKILLS.get(char_class, ["Perception", "Athletics"]),
    }


# ── Public API ────────────────────────────────────────────────────────────────

def randomize_character() -> dict:
    """Return a random D&D character dict, using the LLM when available."""
    rng = random.Random()
    raw: str | None = None

    if _HF_TOKEN:
        for model in _MODELS:
            try:
                client = InferenceClient(model=model, token=_HF_TOKEN, timeout=30)
                response = client.chat_completion(
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user",   "content": _USER},
                    ],
                    max_tokens=250,
                    temperature=1.0,
                )
                text = response.choices[0].message.content.strip()
                if text:
                    raw = text
                    print(f"[randomizer] success with {model}")
                    break
            except Exception as e:
                print(f"[randomizer] {model} failed: {e}")

    if raw:
        return _parse(raw, rng)

    # Pure local fallback
    char_class = rng.choice(CLASSES)
    stats = {s: rng.randint(8, 18) for s in
             ["strength", "dexterity", "constitution", "intelligence", "wisdom", "charisma"]}
    return {
        "name":      rng.choice(_FALLBACK_NAMES),
        "class":     char_class,
        "race":      rng.choice(RACES),
        "level":     rng.randint(2, 5),
        "stats":     stats,
        "backstory": rng.choice(_FALLBACK_BACKSTORIES),
        "skills":    CLASS_SKILLS.get(char_class, ["Perception", "Athletics"]),
    }
