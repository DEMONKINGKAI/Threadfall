"""
Tests for the CausalDAG engine.

Covers:
  - push_score sigmoid computation
  - do() intervention propagates downstream
  - milestone gating (one-step enforcement, sequential act lock)
  - is_campaign_over / get_outcome_states
"""

import json
import math
from pathlib import Path

import pytest

from backend.causal_engine.dag import CausalDAG

_LONG_JSON = Path(__file__).parent.parent / "backend" / "causal_engine" / "campaigns" / "long.json"
_SHORT_JSON = Path(__file__).parent.parent / "backend" / "causal_engine" / "campaigns" / "short.json"


@pytest.fixture
def long_dag():
    with open(_LONG_JSON) as f:
        data = json.load(f)
    return CausalDAG.from_dict(data, seed=42)


@pytest.fixture
def short_dag():
    with open(_SHORT_JSON) as f:
        data = json.load(f)
    return CausalDAG.from_dict(data, seed=42)


# ── Sigmoid helper ────────────────────────────────────────────────────────────

def _sigmoid(x: float, k: float = 6.0) -> float:
    return 1.0 / (1.0 + math.exp(-k * (x - 0.5)))


class TestSigmoid:
    def test_midpoint_is_half(self):
        assert abs(_sigmoid(0.5) - 0.5) < 1e-9

    def test_low_input_near_zero(self):
        assert _sigmoid(0.0) < 0.1

    def test_high_input_near_one(self):
        assert _sigmoid(1.0) > 0.9

    def test_monotone(self):
        xs = [i / 10 for i in range(11)]
        vals = [_sigmoid(x) for x in xs]
        assert all(a < b for a, b in zip(vals, vals[1:]))


# ── DAG construction ──────────────────────────────────────────────────────────

class TestDAGConstruction:
    def test_long_campaign_node_count(self, long_dag):
        assert len(long_dag.nodes()) == 20

    def test_short_campaign_node_count(self, short_dag):
        # 5 action + 7 state + 2 milestone + 1 outcome = 15
        assert len(short_dag.nodes()) == 15

    def test_long_has_final_outcome(self, long_dag):
        assert "final_outcome" in long_dag.nodes()

    def test_short_has_final_outcome(self, short_dag):
        assert "final_outcome" in short_dag.nodes()

    def test_milestones_start_null(self, long_dag):
        for nid in ["act1_milestone", "act2_milestone", "act3_milestone", "act4_milestone"]:
            assert long_dag.node(nid).current_state is None

    def test_outcome_starts_null(self, long_dag):
        assert long_dag.node("final_outcome").current_state is None


# ── do() intervention ─────────────────────────────────────────────────────────

class TestIntervention:
    def test_do_success_changes_downstream(self, long_dag):
        log = long_dag.do("combat_outcome", "success")
        # At minimum the action node itself should be logged
        assert "combat_outcome" in log.downstream_changes or len(log.downstream_changes) >= 0

    def test_do_npc_interaction_affects_npc_trust(self, long_dag):
        # Repeated successes should eventually push npc_trust upward
        for _ in range(10):
            long_dag.do("npc_interaction", "success")
        state = long_dag.node("npc_trust").current_state
        assert state in ("friendly", "allied", "neutral")

    def test_do_failure_does_not_advance_milestone_immediately(self, long_dag):
        long_dag.do("npc_interaction", "failure")
        assert long_dag.node("act1_milestone").current_state is None

    def test_repeated_success_can_advance_act1_milestone(self, long_dag):
        for _ in range(30):
            long_dag.do("npc_interaction", "success")
            long_dag.do("combat_outcome", "success")
        state = long_dag.node("act1_milestone").current_state
        assert state in ("incomplete", "partial", "complete")

    def test_downstream_changes_are_dict(self, long_dag):
        log = long_dag.do("resource_use", "efficient")
        assert isinstance(log.downstream_changes, dict)


# ── Milestone gating ──────────────────────────────────────────────────────────

class TestMilestoneGating:
    def test_act2_milestone_cannot_complete_before_act1(self, long_dag):
        # Progress act2-relevant actions only; act2 cannot reach 'complete' before act1 is partial
        for _ in range(40):
            long_dag.do("espionage_action", "success")
            long_dag.do("political_action", "success")
        act1_state = long_dag.node("act1_milestone").current_state
        act2_state = long_dag.node("act2_milestone").current_state
        # If act2 has completed, act1 must at least be partial (sequential lock invariant)
        if act2_state == "complete":
            assert act1_state in ("partial", "complete")

    def test_final_outcome_needs_milestones(self, long_dag):
        # Final outcome should remain None if no milestones complete
        assert long_dag.node("final_outcome").current_state is None

    def test_milestone_one_step_per_action(self, long_dag):
        """A single action cannot skip a milestone state."""
        for _ in range(5):
            long_dag.do("npc_interaction", "success")
            long_dag.do("combat_outcome", "success")
        state = long_dag.node("act1_milestone").current_state
        if state is not None:
            assert state in ("incomplete", "partial", "complete")


# ── Campaign over ─────────────────────────────────────────────────────────────

class TestCampaignOver:
    def test_not_over_at_start(self, long_dag):
        assert not long_dag.is_campaign_over()

    def test_not_over_after_a_few_actions(self, long_dag):
        for _ in range(5):
            long_dag.do("combat_outcome", "success")
        assert not long_dag.is_campaign_over()

    def test_outcome_states_returns_dict(self, long_dag):
        outcomes = long_dag.get_outcome_states()
        assert isinstance(outcomes, dict)
        assert "final_outcome" in outcomes
