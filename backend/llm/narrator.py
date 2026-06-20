"""
Narrator — produces vivid prose from engine-determined outcomes.

Uses HuggingFace Inference API via the huggingface_hub SDK.
Set HF_TOKEN environment variable to your HuggingFace access token.
"""

from __future__ import annotations

import os
from collections.abc import Generator

from huggingface_hub import InferenceClient

_HF_TOKEN = os.environ.get("HF_TOKEN")

# Models that work on the free featherless-ai provider via InferenceClient
_MODELS = [
    "Qwen/Qwen2.5-7B-Instruct",
    "Qwen/Qwen2.5-3B-Instruct",
    "meta-llama/Llama-3.2-3B-Instruct",
    "microsoft/Phi-3.5-mini-instruct",
]

_ACT_DESCRIPTIONS = {
    1: "Survive the ambush and reach the capital",
    2: "Expose the traitor within the council",
    3: "Prevent the assassination of the loyal king",
    4: "Forge a new alliance across enemy lines",
    5: "The threads converge — the realm's fate is decided",
}

_SYSTEM = (
    "You are a dungeon master narrator writing for a dark, gritty D&D campaign. "
    "You describe what happened in vivid, immersive second-person prose. "
    "You do NOT decide outcomes — all facts are given to you.\n\n"
    "Respond in this exact format and nothing else:\n"
    "TITLE: <a 4–7 word chapter title, dark and specific to this moment — "
    "like 'Blood on the Mountain Pass' or 'The Traitor Speaks at Last'>\n"
    "PARA1: <3–4 sentences. Second-person. Describe the physical action and its immediate "
    "sensory result — what you see, hear, feel. Be specific and visceral.>\n"
    "PARA2: <Exactly 3 sentences, no more, no fewer. Second-person. "
    "Describe ONE specific detail you notice that hints the causal effects are beginning — "
    "a face, a sound, a shift in someone's posture, a change in the air. "
    "Do NOT summarise or resolve the consequence. Do NOT start with 'The world', 'Around you', or 'A distant'. "
    "Ground it in what your character concretely perceives right now.>\n\n"
    "Tone: match outcome — bleak and tense on failure, uncertain on partial, hard-won on success. "
    "Never use generic filler. Every sentence must earn its place."
)

_USER_TEMPLATE = """\
ACT {current_act} OF {total_acts} — {act_description}

Recent events:
{history_lines}

Current world state:
{world_state_lines}

THIS MOMENT (do not alter these facts):
- Action taken: {action}
- Outcome: {success_level} ({probability:.0%} chance, driven by {relevant_stat})
- Causal effects that just occurred: {causal_consequences}

Character: {character_name}, {character_class} level {character_level}

Write the TITLE, PARA1, and PARA2 now."""


def _format_world_state(world_state: dict[str, str]) -> str:
    lines = [
        f"- {k.replace('_', ' ').title()}: {v}"
        for k, v in world_state.items()
        if not any(x in k for x in ("milestone", "outcome", "action"))
    ]
    return "\n".join(lines) if lines else "- (no prior state)"


def _format_consequences(downstream: dict[str, str]) -> str:
    if not downstream:
        return "no immediate effects"
    return "; ".join(f"{k.replace('_', ' ').title()} → {v}" for k, v in downstream.items())


def _format_history(history: list[dict]) -> str:
    if not history:
        return "- (first action)"
    return "\n".join(f"- {e['action']} → {e['outcome']}" for e in history[-3:])


def narrate(
    *,
    current_act: int,
    total_acts: int,
    action: str,
    success_level: str,
    probability: float,
    relevant_stat: str,
    downstream_changes: dict[str, str],
    world_state: dict[str, str],
    character_name: str,
    character_class: str,
    character_level: int,
    action_history: list[dict] | None = None,
) -> tuple[str, str]:
    """Returns (narrative_prose, scene_title) where scene_title is a short evocative phrase."""
    user_content = _USER_TEMPLATE.format(
        current_act=current_act,
        total_acts=total_acts,
        act_description=_ACT_DESCRIPTIONS.get(current_act, "The story continues"),
        history_lines=_format_history(action_history or []),
        world_state_lines=_format_world_state(world_state),
        action=action,
        success_level=success_level,
        probability=probability,
        relevant_stat=relevant_stat,
        causal_consequences=_format_consequences(downstream_changes),
        character_name=character_name,
        character_class=character_class,
        character_level=character_level,
    )

    raw = None

    if _HF_TOKEN:
        for model in _MODELS:
            try:
                client = InferenceClient(model=model, token=_HF_TOKEN)
                response = client.chat_completion(
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user", "content": user_content},
                    ],
                    max_tokens=600,
                    temperature=0.85,
                )
                text = response.choices[0].message.content.strip()
                if text:
                    raw = text
                    print(f"[narrator] success with {model}")
                    break
            except Exception as e:
                print(f"[narrator] {model} failed: {e}")
    else:
        print("[narrator] HF_TOKEN not set — using fallback")

    prose, title = _parse_response(raw, success_level, downstream_changes, current_act)
    return prose, title


def _parse_response(
    raw: str | None,
    success_level: str,
    downstream_changes: dict[str, str],
    current_act: int,
) -> tuple[str, str]:
    """Parse TITLE/PARA1/PARA2 structured output into (prose, title)."""
    default_title = _ACT_DESCRIPTIONS.get(current_act, "The story continues")

    if not raw:
        return _fallback_narration(success_level, downstream_changes), default_title

    import re
    title_match = re.search(r"TITLE:\s*(.+)", raw)
    para1_match = re.search(r"PARA1:\s*(.+?)(?=PARA2:|$)", raw, re.DOTALL)
    para2_match = re.search(r"PARA2:\s*(.+?)$", raw, re.DOTALL)

    title = title_match.group(1).strip() if title_match else default_title
    para1 = para1_match.group(1).strip() if para1_match else ""
    para2 = para2_match.group(1).strip() if para2_match else ""

    if para1 and para2:
        prose = para1 + "\n\n" + para2
    elif para1:
        prose = para1
    else:
        # LLM ignored the format — use raw text as prose, default title
        prose = raw.strip()
        title = default_title

    # Strip any leftover TITLE:/PARA: labels if the LLM bled them into prose
    prose = re.sub(r"\b(TITLE|PARA\d):\s*", "", prose).strip()
    title = re.sub(r'["""*_]', "", title).strip()

    return prose, title


def _fallback_narration(success_level: str, downstream_changes: dict[str, str]) -> str:
    effects = ", ".join(
        f"{k.replace('_', ' ')} becomes {v}" for k, v in downstream_changes.items()
    ) or "the world holds its breath"

    tone = {
        "success":   "Fortune favours the bold — the moment resolves in your favour.",
        "efficient": "Resources are spent wisely. Nothing is wasted.",
        "partial":   "The outcome is mixed — neither triumph nor defeat, but the world shifts.",
        "normal":    "Things proceed as expected.",
        "failure":   "The attempt falters. The consequences settle around you like dust.",
        "wasteful":  "The effort proves costly. More was spent than gained.",
    }.get(success_level, "The moment passes, leaving its mark.")

    return f"{tone}\n\nAs a result, {effects}."


def narrate_stream(
    *,
    current_act: int,
    total_acts: int,
    action: str,
    success_level: str,
    probability: float,
    relevant_stat: str,
    downstream_changes: dict[str, str],
    world_state: dict[str, str],
    character_name: str,
    character_class: str,
    character_level: int,
    action_history: list[dict] | None = None,
) -> Generator[dict, None, None]:
    """
    Streaming variant of narrate().

    Yields dicts:
      {"type": "token", "text": "<chunk>"}   — one per streamed token
      {"type": "done",  "prose": "<full>", "title": "<title>"}  — final event
    """
    user_content = _USER_TEMPLATE.format(
        current_act=current_act,
        total_acts=total_acts,
        act_description=_ACT_DESCRIPTIONS.get(current_act, "The story continues"),
        history_lines=_format_history(action_history or []),
        world_state_lines=_format_world_state(world_state),
        action=action,
        success_level=success_level,
        probability=probability,
        relevant_stat=relevant_stat,
        causal_consequences=_format_consequences(downstream_changes),
        character_name=character_name,
        character_class=character_class,
        character_level=character_level,
    )

    accumulated = ""

    if _HF_TOKEN:
        for model in _MODELS:
            try:
                client = InferenceClient(model=model, token=_HF_TOKEN)
                stream = client.chat_completion(
                    messages=[
                        {"role": "system", "content": _SYSTEM},
                        {"role": "user",   "content": user_content},
                    ],
                    max_tokens=600,
                    temperature=0.85,
                    stream=True,
                )
                for chunk in stream:
                    token = chunk.choices[0].delta.content or ""
                    if token:
                        accumulated += token
                        yield {"type": "token", "text": token}
                print(f"[narrator] streaming success with {model}")
                break
            except Exception as e:
                print(f"[narrator] {model} streaming failed: {e}")
                accumulated = ""  # reset on failure, try next model

    prose, title = _parse_response(
        accumulated if accumulated else None,
        success_level,
        downstream_changes,
        current_act,
    )
    yield {"type": "done", "prose": prose, "title": title}
