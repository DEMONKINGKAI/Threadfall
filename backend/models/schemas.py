"""
Pydantic schemas for the Threadfall API.

All request/response types live here so FastAPI can auto-generate docs
and the frontend has a single source of truth for payload shapes.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


# ── Request ──────────────────────────────────────────────────────────────────

class ActionRequest(BaseModel):
    player_input: str = Field(..., description="Free-text action from the player")
    session_id: str = Field(..., description="Unique session identifier")


class NewGameRequest(BaseModel):
    campaign: str = Field("long", description="Campaign mode: 'long'")
    character: dict[str, Any] = Field(
        ...,
        description="Character sheet: name, class, race, level, stats, skills, backstory",
        examples=[{
            "name": "Aldric",
            "class": "Fighter",
            "race": "Human",
            "level": 3,
            "stats": {
                "strength": 16, "dexterity": 12, "constitution": 14,
                "intelligence": 10, "wisdom": 11, "charisma": 13,
            },
            "skills": ["Athletics", "Persuasion"],
            "backstory": "A disgraced knight seeking redemption.",
        }],
    )
    seed: int | None = Field(None, description="Optional RNG seed for reproducibility")


# ── Response ─────────────────────────────────────────────────────────────────

class NodeBelief(BaseModel):
    node_id: str
    states: dict[str, float]      # state_label → probability
    most_likely: str


class ActionResponse(BaseModel):
    session_id: str
    action_type: str              # canonical action type
    classifier_confidence: float
    outcome: str                  # e.g. "success", "partial", "failure"
    probability: float            # p(success) from character sheet
    relevant_stat: str            # primary stat used
    downstream_changes: dict[str, str]   # node_id → new state
    narrative: str                # LLM-generated prose
    world_state: dict[str, str]   # current MAP state of all nodes
    beliefs: list[NodeBelief]     # full BN beliefs for the graph panel
    current_act: int
    total_acts: int
    scene_text: str
    game_over: bool
    final_outcome: str | None     # only set when game_over is True


class NewGameResponse(BaseModel):
    session_id: str
    campaign_name: str
    world_state: dict[str, str]
    beliefs: list[NodeBelief]
    current_act: int
    total_acts: int
    scene_text: str
    character: dict[str, Any]


class SessionState(BaseModel):
    session_id: str
    campaign_name: str
    world_state: dict[str, str]
    beliefs: list[NodeBelief]
    current_act: int
    total_acts: int
    scene_text: str
    character: dict[str, Any]
    game_over: bool
    final_outcome: str | None


class ErrorResponse(BaseModel):
    detail: str
