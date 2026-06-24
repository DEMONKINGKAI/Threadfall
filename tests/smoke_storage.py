"""Quick round-trip smoke test for the storage module. Run directly: python tests/smoke_storage.py"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))

from backend.storage.vector_store import init_store
from backend.storage.session_store import (
    save_new_game, save_action_entry, load_session_history,
    list_all_sessions, purge_session,
)

store = init_store()
print(f"store: {type(store).__name__}")

sid = "test-smoke-001"

save_new_game(
    session_id=sid,
    campaign_key="long",
    campaign_name="The Shattered Pact",
    character={"name": "Aldric", "class": "Fighter", "level": 3},
    act_titles={"1": "Survive the Ambush"},
    dag_meta={"nodes": [], "edges": []},
)

save_action_entry(
    session_id=sid, entry_index=0,
    player_input="I attack", action_type="combat_outcome",
    outcome="success", probability=0.75, relevant_stat="strength",
    downstream_changes={"player_health": "full"}, narrative="You strike true.",
    scene_text="The Battle Begins", world_state={"player_health": "full"},
    current_act=1,
)

save_action_entry(
    session_id=sid, entry_index=1,
    player_input="I ask for help", action_type="npc_interaction",
    outcome="partial", probability=0.55, relevant_stat="charisma",
    downstream_changes={"npc_trust": "neutral"}, narrative="They hesitate.",
    scene_text="Uncertain Allies", world_state={"player_health": "full"},
    current_act=1,
)

history = load_session_history(sid)
assert history is not None, "load_session_history returned None"
assert len(history["entries"]) == 2, f"expected 2 entries, got {len(history['entries'])}"
assert history["entries"][0]["player_input"] == "I attack"
assert history["meta"]["campaign_name"] == "The Shattered Pact"
print(f"entries loaded: {len(history['entries'])}")

sessions = list_all_sessions()
assert any(s["session_id"] == sid for s in sessions)
print(f"sessions listed: {len(sessions)}, includes Aldric: {sessions[0]['character_name']}")

purge_session(sid)
assert load_session_history(sid) is None, "session should be gone after purge"
print("purge OK")

print("ALL SMOKE TESTS PASSED")
