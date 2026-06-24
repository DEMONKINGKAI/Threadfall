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
from fastapi.responses import StreamingResponse

from backend.causal_engine.dag import CausalDAG, NodeType
from backend.llm.classifier import classify_action
from backend.llm.narrator import narrate, narrate_stream
from backend.llm.randomizer import randomize_character as _randomize_character
from backend.models.schemas import (
    ActionRequest,
    ActionResponse,
    ErrorResponse,
    NewGameRequest,
    NewGameResponse,
    NodeBelief,
    ResumeResponse,
    SessionState,
    SessionSummary,
)
from backend.pgm_engine.character import CharacterSheet
from backend.pgm_engine.world_state import WorldState
from backend.storage.vector_store import init_store
from backend.storage.session_store import (
    save_new_game as _store_new_game,
    save_action_entry as _store_entry,
    update_final_outcome as _store_outcome,
    retrieve_rag_context,
)

# ── Paths ────────────────────────────────────────────────────────────────────

_CAMPAIGNS_DIR = Path(__file__).parent / "causal_engine" / "campaigns"
_CAMPAIGN_FILES = {
    "long":  _CAMPAIGNS_DIR / "long.json",
    "short": _CAMPAIGNS_DIR / "short.json",
}


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


@app.on_event("startup")
def startup() -> None:
    """Connect to the vector store on server start."""
    init_store()


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


def _dag_meta(campaign_data: dict) -> dict:
    """Extract graph-visualisation metadata from a loaded campaign dict."""
    nodes = [{"id": n["id"], "type": n["type"]} for n in campaign_data.get("nodes", [])]
    edges = [
        {"source": e["source"], "target": e["target"], "weight": e.get("weight", 1.0)}
        for e in campaign_data.get("edges", [])
    ]
    return {"nodes": nodes, "edges": edges}


def _act_titles(campaign_data: dict) -> dict[str, str]:
    """Return act titles keyed by string act number.

    Prefers the optional 'act_titles' dict in the campaign JSON.
    Falls back to parsing milestone node descriptions ("Act N: …").
    """
    if "act_titles" in campaign_data:
        return {str(k): v for k, v in campaign_data["act_titles"].items()}

    titles: dict[str, str] = {}
    for node in campaign_data.get("nodes", []):
        if node.get("type") == "milestone":
            desc = node.get("description", "")
            # "Act 1: Survive the ambush…" → {"1": "Survive the ambush…"}
            import re
            m = re.match(r"Act\s+(\d+):\s*(.+)", desc)
            if m:
                titles[m.group(1)] = m.group(2).strip()
    return titles


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
    meta_dag   = _dag_meta(campaign_data)
    meta_acts  = _act_titles(campaign_data)

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
        "entry_count": 0,       # tracks how many entries have been stored
        "campaign_key": campaign_key,
    }

    _store_new_game(
        session_id=session_id,
        campaign_key=campaign_key,
        campaign_name=campaign_data["campaign"]["name"],
        character=character.to_dict(),
        act_titles=meta_acts,
        dag_meta=meta_dag,
    )

    return NewGameResponse(
        session_id=session_id,
        campaign_name=campaign_data["campaign"]["name"],
        campaign_description=campaign_data["campaign"].get("description", ""),
        world_state={k: v or "unknown" for k, v in dag.get_state_summary().items()},
        beliefs=_beliefs_list(world_state),
        current_act=1,
        total_acts=campaign_data["campaign"]["acts"],
        scene_text=_current_scene(campaign_data, 1),
        character=character.to_dict(),
        dag_meta=_dag_meta(campaign_data),
        act_titles=_act_titles(campaign_data),
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

    # ── Step 8: Persist to vector store ──────────────────────────────────────
    world_snapshot = {k: v or "unknown" for k, v in world_state.get_state_summary().items()}
    entry_idx = session["entry_count"]
    _store_entry(
        session_id=req.session_id,
        entry_index=entry_idx,
        player_input=req.player_input,
        action_type=action_type,
        outcome=outcome,
        probability=probability,
        relevant_stat=relevant_stat,
        downstream_changes=downstream,
        narrative=narrative,
        scene_text=scene_banner,
        world_state=world_snapshot,
        current_act=act,
    )
    session["entry_count"] = entry_idx + 1
    if final_outcome:
        _store_outcome(req.session_id, final_outcome)

    return ActionResponse(
        session_id=req.session_id,
        action_type=action_type,
        classifier_confidence=confidence,
        outcome=outcome,
        probability=probability,
        relevant_stat=relevant_stat,
        downstream_changes=downstream,
        narrative=narrative,
        world_state=world_snapshot,
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
    """Clean up a session from memory and the vector store."""
    _SESSIONS.pop(session_id, None)
    from backend.storage.session_store import purge_session
    purge_session(session_id)


@app.get("/sessions", response_model=list[SessionSummary])
def list_sessions() -> list[SessionSummary]:
    """Return all saved sessions for the load-game screen."""
    from backend.storage.session_store import list_all_sessions
    rows = list_all_sessions()
    return [SessionSummary(**r) for r in rows]


@app.post("/resume_session/{session_id}", response_model=ResumeResponse)
def resume_session(session_id: str) -> ResumeResponse:
    """
    Restore a saved session from the vector store into memory and return
    enough state for the frontend to hydrate exactly as after /new_game.
    """
    from backend.storage.session_store import load_session_history
    history = load_session_history(session_id)
    if history is None:
        raise HTTPException(status_code=404, detail="Session not found in store")

    meta    = history["meta"]
    entries = history["entries"]

    # If already in memory (e.g. same server restart hasn't cleared it), skip rebuild
    if session_id not in _SESSIONS:
        campaign_key  = meta["campaign_key"]
        campaign_path = _CAMPAIGN_FILES.get(campaign_key)
        if campaign_path is None:
            raise HTTPException(status_code=422, detail=f"Unknown campaign key: {campaign_key!r}")

        with open(campaign_path) as _f:
            campaign_data = json.load(_f)
        dag           = CausalDAG.from_dict(campaign_data)
        world_state   = WorldState(dag)
        character     = CharacterSheet.from_dict(meta["character"])

        _SESSIONS[session_id] = {
            "dag":            dag,
            "world_state":    world_state,
            "character":      character,
            "campaign":       campaign_data["campaign"],
            "campaign_data":  campaign_data,
            "act":            max((e.get("current_act", 1) for e in entries), default=1),
            "scene_index":    0,
            "action_history": [
                {"action": e["player_input"], "outcome": e["outcome"]} for e in entries
            ],
            "rng":            random.Random(),
            "entry_count":    len(entries),
            "campaign_key":   campaign_key,
        }

    session       = _SESSIONS[session_id]
    dag           = session["dag"]
    world_state   = session["world_state"]
    character     = session["character"]
    campaign_data = session["campaign_data"]
    act           = session["act"]
    total_acts    = session["campaign"]["acts"]

    return ResumeResponse(
        session_id=session_id,
        campaign_name=meta["campaign_name"],
        campaign_description=campaign_data["campaign"].get("description", ""),
        world_state={k: v or "unknown" for k, v in world_state.get_state_summary().items()},
        beliefs=_beliefs_list(world_state),
        current_act=act,
        total_acts=total_acts,
        scene_text=_current_scene(campaign_data, act),
        character=character.to_dict(),
        dag_meta=meta["dag_meta"],
        act_titles=meta["act_titles"],
        entries=entries,
    )


@app.get("/randomize_character")
def randomize_character_endpoint() -> dict:
    """LLM-generated random D&D character, with local fallback."""
    return _randomize_character()


# ── Streaming action ─────────────────────────────────────────────────────────

@app.post("/stream_action")
def stream_action(req: ActionRequest) -> StreamingResponse:
    """
    Process a player action through the full causal pipeline, then stream the
    LLM narration token-by-token via Server-Sent Events.

    SSE event types:
      {"type": "engine", ...ActionResponse fields except narrative/scene_text}
      {"type": "token",  "text": "<chunk>"}
      {"type": "done",   "narrative": "<prose>", "scene_text": "<title>",
                         "game_over": bool, "final_outcome": str|null}
    """
    session = _SESSIONS.get(req.session_id)
    if session is None:
        raise HTTPException(status_code=404, detail="Session not found")

    dag: CausalDAG        = session["dag"]
    world_state: WorldState = session["world_state"]
    character: CharacterSheet = session["character"]
    campaign_data: dict   = session["campaign_data"]
    act: int              = session["act"]
    total_acts: int       = session["campaign"]["acts"]
    rng: random.Random    = session["rng"]
    scene_text_current    = _current_scene(campaign_data, act, session["scene_index"])

    # ── Pipeline (sync, runs before streaming begins) ─────────────────────────
    action_type, confidence = classify_action(
        req.player_input,
        scene_text=scene_text_current,
        current_act=act,
        total_acts=total_acts,
    )
    rng_value = rng.random()
    outcome, probability = character.sample_outcome(action_type, rng_value)
    relevant_stat        = character.stat_label(action_type)
    intervention_log     = dag.do(action_type, outcome)
    world_state.apply_intervention(intervention_log)

    prev_act = session["act"]
    _advance_act(session)
    act = session["act"]

    if act != prev_act:
        session["scene_index"] = 0
    else:
        act_key  = f"act{act}"
        n_scenes = len(campaign_data.get("scenes", {}).get(act_key, []))
        session["scene_index"] = min(session["scene_index"] + 1, max(n_scenes - 1, 0))

    downstream = {
        k: v for k, v in intervention_log.downstream_changes.items() if k != action_type
    }

    game_over      = dag.is_campaign_over()
    final_outcome  = _get_final_outcome(dag) if game_over else None
    world_snapshot = {k: v or "unknown" for k, v in world_state.get_state_summary().items()}
    beliefs_list   = _beliefs_list(world_state)

    engine_event = {
        "type":                 "engine",
        "session_id":           req.session_id,
        "action_type":          action_type,
        "classifier_confidence":confidence,
        "outcome":              outcome,
        "probability":          probability,
        "relevant_stat":        relevant_stat,
        "downstream_changes":   downstream,
        "world_state":          world_snapshot,
        "beliefs":              [b.model_dump() for b in beliefs_list],
        "current_act":          act,
        "total_acts":           total_acts,
        "game_over":            game_over,
        "final_outcome":        final_outcome,
    }

    # Record action for narrator context BEFORE streaming
    session["action_history"].append({"action": req.player_input, "outcome": outcome})

    narrate_kwargs = dict(
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

    entry_idx = session["entry_count"]

    def generate():
        yield f"data: {json.dumps(engine_event)}\n\n"
        for event in narrate_stream(**narrate_kwargs):
            if event["type"] == "token":
                yield f"data: {json.dumps({'type': 'token', 'text': event['text']})}\n\n"
            elif event["type"] == "done":
                prose      = event["prose"]
                scene_text = event["title"]

                # Persist the completed entry now that we have the final narrative
                _store_entry(
                    session_id=req.session_id,
                    entry_index=entry_idx,
                    player_input=req.player_input,
                    action_type=action_type,
                    outcome=outcome,
                    probability=probability,
                    relevant_stat=relevant_stat,
                    downstream_changes=downstream,
                    narrative=prose,
                    scene_text=scene_text,
                    world_state=world_snapshot,
                    current_act=act,
                )
                session["entry_count"] = entry_idx + 1
                if final_outcome:
                    _store_outcome(req.session_id, final_outcome)

                done_event = {
                    "type":          "done",
                    "narrative":     prose,
                    "scene_text":    scene_text,
                    "game_over":     game_over,
                    "final_outcome": final_outcome,
                }
                yield f"data: {json.dumps(done_event)}\n\n"

    return StreamingResponse(
        generate(),
        media_type="text/event-stream",
        headers={
            "Cache-Control":    "no-cache",
            "X-Accel-Buffering":"no",
        },
    )
