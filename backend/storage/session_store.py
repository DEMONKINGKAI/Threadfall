"""
session_store.py — high-level helpers for main.py to call.

All functions are thin wrappers over VectorStore that deal in
Threadfall-specific concepts (sessions, entries, DAG replay).

Public API
──────────
save_new_game(session_id, ...)           persist session metadata on /new_game
save_action_entry(session_id, idx, ...) persist one action entry after /action
update_final_outcome(session_id, ...)   mark a session as finished
load_session_history(session_id)        reconstruct session from stored entries
list_all_sessions()                     summary list for the resume screen
purge_session(session_id)               hard delete from vector DB
retrieve_rag_context(session_id, ...)   k nearest past entries for narrator RAG
"""

from __future__ import annotations

import json
from typing import Any

from backend.storage.vector_store import get_store


# ── Write operations ──────────────────────────────────────────────────────────

def save_new_game(
    *,
    session_id: str,
    campaign_key: str,
    campaign_name: str,
    character: dict,
    act_titles: dict,
    dag_meta: dict,
) -> None:
    """Persist session metadata document immediately after /new_game."""
    try:
        get_store().save_session_meta(
            session_id=session_id,
            campaign_key=campaign_key,
            campaign_name=campaign_name,
            character=character,
            act_titles=act_titles,
            dag_meta=dag_meta,
        )
    except Exception as e:
        print(f"[session_store] save_new_game failed (non-fatal): {e}")


def save_action_entry(
    *,
    session_id: str,
    entry_index: int,
    player_input: str,
    action_type: str,
    outcome: str,
    probability: float,
    relevant_stat: str,
    downstream_changes: dict,
    narrative: str,
    scene_text: str,
    world_state: dict,
    current_act: int,
) -> None:
    """Persist one action entry after it has been fully resolved."""
    entry = {
        "player_input":       player_input,
        "action_type":        action_type,
        "outcome":            outcome,
        "probability":        probability,
        "relevant_stat":      relevant_stat,
        "downstream_changes": downstream_changes,
        "narrative":          narrative,
        "scene_text":         scene_text,
        "world_state":        world_state,
        "current_act":        current_act,
    }
    try:
        get_store().save_entry(session_id=session_id, entry_index=entry_index, entry=entry)
    except Exception as e:
        print(f"[session_store] save_action_entry failed (non-fatal): {e}")


def update_final_outcome(session_id: str, final_outcome: str) -> None:
    """Write the final outcome onto the session metadata document."""
    try:
        get_store().update_session_outcome(session_id, final_outcome)
    except Exception as e:
        print(f"[session_store] update_final_outcome failed (non-fatal): {e}")


# ── Read operations ───────────────────────────────────────────────────────────

def load_session_history(session_id: str) -> dict | None:
    """
    Reconstruct a session from the vector DB.

    Returns a dict with:
      meta    : session metadata (character, campaign_key, act_titles, dag_meta, final_outcome)
      entries : list of action entry dicts in chronological order

    Returns None if the session_id is not found.
    """
    store = get_store()
    try:
        meta = store.get_session_meta(session_id)
        if meta is None:
            return None
        entries = store.get_entries(session_id)
        return {"meta": meta, "entries": entries}
    except Exception as e:
        print(f"[session_store] load_session_history failed: {e}")
        return None


def list_all_sessions() -> list[dict]:
    """
    Return a summary list for the resume screen.

    Each item:
      session_id, campaign_key, campaign_name, character (name/class/level),
      created_at, final_outcome, entry_count (approximate from metadata)
    """
    try:
        metas = get_store().list_sessions()
    except Exception as e:
        print(f"[session_store] list_all_sessions failed: {e}")
        return []

    summaries = []
    for m in metas:
        char = m.get("character", {})
        summaries.append({
            "session_id":    m["session_id"],
            "campaign_key":  m["campaign_key"],
            "campaign_name": m["campaign_name"],
            "character_name":  char.get("name", "Unknown"),
            "character_class": char.get("class", ""),
            "character_level": char.get("level", 1),
            "created_at":    m["created_at"],
            "final_outcome": m.get("final_outcome"),
        })

    # Most recent first
    summaries.sort(key=lambda s: s["created_at"], reverse=True)
    return summaries


def purge_session(session_id: str) -> None:
    """Remove all documents for this session from the vector DB."""
    try:
        get_store().delete_session(session_id)
    except Exception as e:
        print(f"[session_store] purge_session failed (non-fatal): {e}")


# ── RAG helper ────────────────────────────────────────────────────────────────

def retrieve_rag_context(session_id: str, query: str, k: int = 3) -> list[dict]:
    """
    Return the k past narrative entries most semantically similar to `query`.

    Used by the narrator to inject relevant remembered moments into the prompt.
    Falls back to empty list on any error so the narrator always gets a response.
    """
    try:
        return get_store().search_similar(session_id=session_id, query=query, k=k)
    except Exception as e:
        print(f"[session_store] retrieve_rag_context failed (non-fatal): {e}")
        return []
