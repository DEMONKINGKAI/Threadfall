"""
Threadfall FastAPI backend.

Full pipeline per action:
  1. Classifier → canonical action type
  2. CharacterSheet.sample_outcome() → success_level, probability
  3. DAG.do() → downstream structural changes
  4. WorldState.apply_intervention() → BN belief update
  5. Narrator → vivid prose from pre-determined facts
"""

from __future__ import annotations

import json
import random
import uuid
from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from backend.causal_engine.dag import CausalDAG, NodeType
from backend.llm.classifier import classify_action
from backend.llm.narrator import narrate, _HF_TOKEN, _MODELS, InferenceClient
from backend.models.schemas import (
    ActionRequest,
    ActionResponse,
    ErrorResponse,
    NewGameRequest,
    NewGameResponse,
    NodeBelief,
    SessionState,
)
from backend.pgm_engine.character import CharacterSheet
from backend.pgm_engine.world_state import WorldState

# ── Paths ────────────────────────────────────────────────────────────────────

_CAMPAIGNS_DIR = Path(__file__).parent / "causal_engine" / "campaigns"
_CAMPAIGN_FILES = {"long": _CAMPAIGNS_DIR / "long.json"}


# ── In-memory session store ──────────────────────────────────────────────────
# Maps session_id → { dag, world_state, character, campaign_meta, act, rng }

_SESSIONS: dict[str, dict[str, Any]] = {}


# ── App ───────────────────────────────────────────────────────────────────────

app = FastAPI(title="Threadfall", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Helpers ──────────────────────────────────────────────────────────────────

def _beliefs_list(world_state: WorldState) -> list[NodeBelief]:
    beliefs = world_state.get_beliefs()
    return [
        NodeBelief(
            node_id=nid,
            states=dist,
            most_likely=max(dist, key=dist.get),
        )
        for nid, dist in beliefs.items()
    ]


def _current_scene(campaign_data: dict, act: int, scene_index: int = 0) -> str:
    act_key = f"act{act}"
    scenes = campaign_data.get("scenes", {}).get(act_key, [])
    if not scenes:
        return "The story continues."
    return scenes[min(scene_index, len(scenes) - 1)]


def _advance_act(session: dict) -> None:
    """Increment act counter when the current act's milestone is complete."""
    dag: CausalDAG = session["dag"]
    act = session["act"]
    total = session["campaign"]["acts"]
    if act >= total:
        return

    milestone_id = f"act{act}_milestone"
    if milestone_id not in dag.nodes():
        return
    state = dag.node(milestone_id).current_state
    if state == "complete":
        session["act"] = min(act + 1, total)


def _get_final_outcome(dag: CausalDAG) -> str | None:
    outcomes = dag.get_outcome_states()
    for _nid, state in outcomes.items():
        if state is not None:
            return state
    return None


# ── Endpoints ────────────────────────────────────────────────────────────────

@app.post("/new_game", response_model=NewGameResponse)
def new_game(req: NewGameRequest) -> NewGameResponse:
    """Start a new game session. Returns initial world state."""
    campaign_key = req.campaign.lower()
    if campaign_key not in _CAMPAIGN_FILES:
        raise HTTPException(status_code=400, detail=f"Unknown campaign: {req.campaign}")

    campaign_path = _CAMPAIGN_FILES[campaign_key]
    with open(campaign_path) as f:
        campaign_data = json.load(f)

    seed = req.seed if req.seed is not None else random.randint(0, 2**31)
    dag = CausalDAG.from_dict(campaign_data, seed=seed)
    world_state = WorldState(dag)

    try:
        character = CharacterSheet.from_dict(req.character)
    except (KeyError, TypeError) as e:
        raise HTTPException(status_code=422, detail=f"Invalid character sheet: {e}")

    session_id = str(uuid.uuid4())
    _SESSIONS[session_id] = {
        "dag": dag,
        "world_state": world_state,
        "character": character,
        "campaign": campaign_data["campaign"],
        "campaign_data": campaign_data,
        "act": 1,
        "scene_index": 0,
        "action_history": [],   # list of {action, outcome} for narrator context
        "rng": random.Random(seed),
    }

    return NewGameResponse(
        session_id=session_id,
        campaign_name=campaign_data["campaign"]["name"],
        world_state={k: v or "unknown" for k, v in dag.get_state_summary().items()},
        beliefs=_beliefs_list(world_state),
        current_act=1,
        total_acts=campaign_data["campaign"]["acts"],
        scene_text=_current_scene(campaign_data, 1),
        character=character.to_dict(),
    )


@app.post("/action", response_model=ActionResponse)
def take_action(req: ActionRequest) -> ActionResponse:
    """Process a player action through the full causal pipeline."""
    session = _SESSIONS.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    dag: CausalDAG = session["dag"]
    world_state: WorldState = session["world_state"]
    character: CharacterSheet = session["character"]
    campaign_data: dict = session["campaign_data"]
    act: int = session["act"]
    total_acts: int = session["campaign"]["acts"]
    rng: random.Random = session["rng"]
    scene_text = _current_scene(campaign_data, act, session["scene_index"])

    # ── Step 1: Classify action ───────────────────────────────────────────────
    action_type, confidence = classify_action(
        req.player_input,
        scene_text=scene_text,
        current_act=act,
        total_acts=total_acts,
    )

    # ── Step 2: Sample outcome from character stats ───────────────────────────
    rng_value = rng.random()
    outcome, probability = character.sample_outcome(action_type, rng_value)
    relevant_stat = character.stat_label(action_type)

    # ── Step 3: DAG intervention ──────────────────────────────────────────────
    intervention_log = dag.do(action_type, outcome)

    # ── Step 4: BN belief update ──────────────────────────────────────────────
    world_state.apply_intervention(intervention_log)

    # ── Step 5: Advance act if milestone complete; advance scene within act ──
    prev_act = session["act"]
    _advance_act(session)
    act = session["act"]

    if act != prev_act:
        session["scene_index"] = 0  # reset scene on act change
    else:
        act_key = f"act{act}"
        n_scenes = len(campaign_data.get("scenes", {}).get(act_key, []))
        session["scene_index"] = min(session["scene_index"] + 1, max(n_scenes - 1, 0))

    # ── Step 6: Narration ─────────────────────────────────────────────────────
    downstream = {
        k: v
        for k, v in intervention_log.downstream_changes.items()
        if k != action_type
    }

    narrative, scene_banner = narrate(
        current_act=act,
        total_acts=total_acts,
        action=req.player_input,
        success_level=outcome,
        probability=probability,
        relevant_stat=relevant_stat,
        downstream_changes=downstream,
        world_state=world_state.get_state_summary(),
        character_name=character.name,
        character_class=character.char_class,
        character_level=character.level,
        action_history=session["action_history"],
    )

    # Record this action for future narrator context
    session["action_history"].append({"action": req.player_input, "outcome": outcome})

    # ── Step 7: Check end condition ───────────────────────────────────────────
    game_over = dag.is_campaign_over()
    final_outcome = _get_final_outcome(dag) if game_over else None

    return ActionResponse(
        session_id=req.session_id,
        action_type=action_type,
        classifier_confidence=confidence,
        outcome=outcome,
        probability=probability,
        relevant_stat=relevant_stat,
        downstream_changes=downstream,
        narrative=narrative,
        world_state={k: v or "unknown" for k, v in world_state.get_state_summary().items()},
        beliefs=_beliefs_list(world_state),
        current_act=act,
        total_acts=total_acts,
        scene_text=scene_banner,
        game_over=game_over,
        final_outcome=final_outcome,
    )


@app.get("/session/{session_id}", response_model=SessionState)
def get_session(session_id: str) -> SessionState:
    """Return the current state of a session (for reconnection/refresh)."""
    session = _SESSIONS.get(session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    dag: CausalDAG = session["dag"]
    world_state: WorldState = session["world_state"]
    character: CharacterSheet = session["character"]
    act: int = session["act"]
    total_acts: int = session["campaign"]["acts"]
    campaign_data: dict = session["campaign_data"]

    game_over = dag.is_campaign_over()
    return SessionState(
        session_id=session_id,
        campaign_name=session["campaign"]["name"],
        world_state={k: v or "unknown" for k, v in world_state.get_state_summary().items()},
        beliefs=_beliefs_list(world_state),
        current_act=act,
        total_acts=total_acts,
        scene_text=_current_scene(campaign_data, act),
        character=character.to_dict(),
        game_over=game_over,
        final_outcome=_get_final_outcome(dag) if game_over else None,
    )


@app.delete("/session/{session_id}", status_code=204)
def delete_session(session_id: str) -> None:
    """Clean up a session."""
    _SESSIONS.pop(session_id, None)


# ── Randomizer ───────────────────────────────────────────────────────────────

_RANDOM_CLASSES = ["Fighter","Rogue","Wizard","Cleric","Ranger","Paladin","Bard","Druid","Barbarian","Monk","Sorcerer","Warlock"]
_RANDOM_RACES   = ["Human","Elf","Dwarf","Halfling","Tiefling","Half-Orc","Gnome","Dragonborn"]
_RANDOM_SKILLS  = {
    "Fighter":["Athletics","Intimidation"],"Rogue":["Stealth","Deception"],
    "Wizard":["Arcana","History"],"Cleric":["Religion","Medicine"],
    "Ranger":["Survival","Perception"],"Paladin":["Persuasion","Athletics"],
    "Bard":["Performance","Persuasion"],"Druid":["Nature","Animal Handling"],
    "Barbarian":["Athletics","Survival"],"Monk":["Acrobatics","Insight"],
    "Sorcerer":["Arcana","Persuasion"],"Warlock":["Arcana","Deception"],
}

_RANDOMIZE_SYSTEM = (
    "You generate D&D 5e characters for a dark gothic campaign called 'The Shattered Pact'. "
    "Each character should feel morally complex, weathered, and fit for a world on the edge of war. "
    "Respond in EXACTLY this format, nothing else:\n"
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

_RANDOMIZE_USER = "Generate a single unique D&D character now. Make them feel like someone who has survived real hardship."


def _parse_random_character(text: str, rng: random.Random) -> dict:
    import re

    def field(key):
        m = re.search(rf"^{key}:\s*(.+)", text, re.MULTILINE | re.IGNORECASE)
        return m.group(1).strip() if m else None

    char_class = field("CLASS") or rng.choice(_RANDOM_CLASSES)
    # Normalise class to match our list
    char_class = next((c for c in _RANDOM_CLASSES if c.lower() == char_class.lower()), char_class)

    def stat(key, lo=8, hi=18):
        raw = field(key)
        try:
            return max(lo, min(hi, int(raw)))
        except (TypeError, ValueError):
            return rng.randint(lo, hi)

    return {
        "name": field("NAME") or rng.choice(["Mira","Edric","Vael","Corvyn","Serath","Aldric","Lysa","Torn"]),
        "class": char_class,
        "race": field("RACE") or rng.choice(_RANDOM_RACES),
        "level": stat("LEVEL", 2, 5),
        "stats": {
            "strength":     stat("STR"),
            "dexterity":    stat("DEX"),
            "constitution": stat("CON"),
            "intelligence": stat("INT"),
            "wisdom":       stat("WIS"),
            "charisma":     stat("CHA"),
        },
        "backstory": field("BACKSTORY") or "A wanderer with no allegiance — only a debt unpaid and a name best forgotten.",
        "skills": _RANDOM_SKILLS.get(char_class, ["Perception","Athletics"]),
    }


@app.get("/randomize_character")
def randomize_character() -> dict:
    """Use the LLM to generate a random believable character. Falls back to local random on failure."""
    rng = random.Random()
    raw = None

    if _HF_TOKEN:
        for model in _MODELS:
            try:
                client = InferenceClient(model=model, token=_HF_TOKEN)
                response = client.chat_completion(
                    messages=[
                        {"role": "system", "content": _RANDOMIZE_SYSTEM},
                        {"role": "user",   "content": _RANDOMIZE_USER},
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
        return _parse_random_character(raw, rng)

    # Pure local fallback
    char_class = rng.choice(_RANDOM_CLASSES)
    race = rng.choice(_RANDOM_RACES)
    names = ["Mira","Edric","Vael","Corvyn","Serath","Theron","Lysa","Torn","Aelric","Dusk","Brynn","Varek"]
    backstories = [
        "Stripped of rank and title after questioning the wrong lord, you wander with nothing but a blade and a bitter memory.",
        "Your village was the first to burn when the pact shattered. You are the only one who remembers its name.",
        "Once a spy for the council, you defected when you learned who gave the orders. Now both sides want you dead.",
        "You were born in the borderlands, where every child learns to read the wind before they learn to read words.",
    ]
    stats = {s: rng.randint(8, 18) for s in ["strength","dexterity","constitution","intelligence","wisdom","charisma"]}
    return {
        "name": rng.choice(names),
        "class": char_class,
        "race": race,
        "level": rng.randint(2, 5),
        "stats": stats,
        "backstory": rng.choice(backstories),
        "skills": _RANDOM_SKILLS.get(char_class, ["Perception","Athletics"]),
    }
