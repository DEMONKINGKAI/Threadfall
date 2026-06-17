"""
PGM World State — Bayesian Network over discrete story variables.

Uses pgmpy for Bayesian network structure and inference.
Receives evidence from the causal DAG (via InterventionLog) and updates
all node beliefs via Variable Elimination.

Separation of concerns:
- dag.py  : structural causal pushes (do-calculus)
- world_state.py : probabilistic belief over ALL story variables,
                   updated with soft evidence from the DAG
"""

from __future__ import annotations

from typing import Any

import numpy as np

try:
    try:
        from pgmpy.models import DiscreteBayesianNetwork as BayesianNetwork
    except ImportError:
        from pgmpy.models import BayesianNetwork
    from pgmpy.factors.discrete import TabularCPD
    from pgmpy.inference import VariableElimination
    PGMPY_AVAILABLE = True
except ImportError:
    PGMPY_AVAILABLE = False

from backend.causal_engine.dag import CausalDAG, InterventionLog, NodeType


# State ordering (worst → best) mirrors what's in the campaign JSON.
# Index 0 = worst state, index N-1 = best state.
# CPTs encode "given parent is in state X, what's the probability distribution
# over this node's states?"

_DEFAULT_CPT_BIAS = 0.6   # probability mass on the "causally expected" state
_NOISE = (1 - _DEFAULT_CPT_BIAS)  # spread across remaining states


def _uniform(n: int) -> list[float]:
    return [1.0 / n] * n


def _biased(n: int, peak_idx: int, bias: float = _DEFAULT_CPT_BIAS) -> list[float]:
    """Return a probability vector with most mass on peak_idx."""
    remainder = (1.0 - bias) / max(n - 1, 1)
    return [bias if i == peak_idx else remainder for i in range(n)]


def _build_cpt_from_parents(
    child_states: list[str],
    parent_states_list: list[list[str]],
    influence_weights: list[float] | None = None,
) -> np.ndarray:
    """
    Auto-generate a CPT for a child node given its parents.

    Logic: the expected child state index is the weighted average of parent
    state indices (normalized to [0,1]), then mapped back to the child's
    state space. A Dirichlet-ish distribution is centered on that index.

    Shape of returned array: (n_child_states, prod(n_parent_states_i))
    pgmpy expects columns ordered by the Cartesian product of parent states
    in the order parents are listed.
    """
    n_child = len(child_states)
    n_parents = len(parent_states_list)
    weights = influence_weights or [1.0] * n_parents
    total_weight = sum(weights)

    from itertools import product as iproduct

    parent_ranges = [range(len(ps)) for ps in parent_states_list]
    combos = list(iproduct(*parent_ranges))

    cpt_cols = []
    for combo in combos:
        score = 0.0
        for i, idx in enumerate(combo):
            n_p = len(parent_states_list[i])
            normalized = idx / max(n_p - 1, 1)
            score += normalized * (weights[i] / total_weight)
        child_idx = round(score * (n_child - 1))
        child_idx = max(0, min(child_idx, n_child - 1))
        col = _biased(n_child, child_idx)
        cpt_cols.append(col)

    # Shape: (n_child, n_combos)
    return np.array(cpt_cols).T


class WorldState:
    """
    Maintains a Bayesian Network over all story state variables.

    Only STATE, MILESTONE, and OUTCOME nodes are tracked here —
    ACTION nodes are ephemeral interventions that drive evidence.

    After each DAG intervention, call `apply_intervention(log)` to
    update the BN with hard evidence and re-run inference.
    """

    def __init__(self, dag: CausalDAG):
        self._dag = dag
        self._beliefs: dict[str, dict[str, float]] = {}
        self._evidence: dict[str, int] = {}   # node_id → state index

        # Track which nodes belong in the BN
        self._bn_nodes = {
            nid: n
            for nid, n in dag.nodes().items()
            if n.type in (NodeType.STATE, NodeType.MILESTONE, NodeType.OUTCOME)
        }

        self._bn: "BayesianNetwork | None" = None
        self._inference: VariableElimination | None = None

        if PGMPY_AVAILABLE:
            self._build_bn()
        else:
            # Fallback: track beliefs as uniform distributions,
            # update deterministically from DAG propagation.
            self._init_fallback_beliefs()

    # ── BN Construction ─────────────────────────────────────────────────────

    def _build_bn(self) -> None:
        edges_in_bn = []
        for e in self._dag.edges():
            src_node = self._dag.node(e.source)
            tgt_node = self._dag.node(e.target)
            # Include edge only if both endpoints are BN nodes
            if (
                e.source in self._bn_nodes
                and e.target in self._bn_nodes
            ):
                edges_in_bn.append((e.source, e.target))
            # If source is an ACTION node, its effect is injected as evidence;
            # we do NOT add action nodes to the BN directly.

        self._bn = BayesianNetwork(edges_in_bn)
        for nid in self._bn_nodes:
            if nid not in self._bn.nodes():
                self._bn.add_node(nid)

        self._attach_cpds()
        self._bn.check_model()
        self._inference = VariableElimination(self._bn)
        self._refresh_beliefs()

    def _attach_cpds(self) -> None:
        all_edges = self._dag.edges()
        edge_weights = {(e.source, e.target): e.weight for e in all_edges}

        for nid, node in self._bn_nodes.items():
            parent_ids = [
                e[0]
                for e in self._bn.edges()
                if e[1] == nid and e[0] in self._bn_nodes
            ]
            n_states = len(node.states)

            if not parent_ids:
                # Root node — use uniform prior
                cpd = TabularCPD(
                    variable=nid,
                    variable_card=n_states,
                    values=[[1.0 / n_states]] * n_states,
                    state_names={nid: node.states},
                )
            else:
                parent_nodes = [self._bn_nodes[pid] for pid in parent_ids]
                parent_cards = [len(pn.states) for pn in parent_nodes]
                weights = [edge_weights.get((pid, nid), 1.0) for pid in parent_ids]
                cpt_matrix = _build_cpt_from_parents(
                    node.states,
                    [pn.states for pn in parent_nodes],
                    weights,
                )
                cpd = TabularCPD(
                    variable=nid,
                    variable_card=n_states,
                    values=cpt_matrix,
                    evidence=parent_ids,
                    evidence_card=parent_cards,
                    state_names={nid: node.states, **{pid: self._bn_nodes[pid].states for pid in parent_ids}},
                )
            self._bn.add_cpds(cpd)

    # ── Fallback (no pgmpy) ──────────────────────────────────────────────────

    def _init_fallback_beliefs(self) -> None:
        for nid, node in self._bn_nodes.items():
            n = len(node.states)
            self._beliefs[nid] = {s: 1.0 / n for s in node.states}

    # ── Inference ────────────────────────────────────────────────────────────

    def _refresh_beliefs(self) -> None:
        if not PGMPY_AVAILABLE or self._inference is None:
            return
        try:
            query_vars = list(self._bn_nodes.keys())
            evidence = {k: v for k, v in self._evidence.items() if k in self._bn_nodes}

            # Query one variable at a time to avoid large joint queries
            for var in query_vars:
                if var in evidence:
                    # Hard evidence: spike distribution
                    node = self._bn_nodes[var]
                    idx = evidence[var]
                    self._beliefs[var] = {
                        s: (1.0 if i == idx else 0.0)
                        for i, s in enumerate(node.states)
                    }
                else:
                    result = self._inference.query(
                        variables=[var],
                        evidence=evidence,
                        show_progress=False,
                    )
                    node = self._bn_nodes[var]
                    self._beliefs[var] = {
                        s: float(result.values[i])
                        for i, s in enumerate(node.states)
                    }
        except Exception:
            # Inference can fail if evidence is inconsistent; keep old beliefs
            pass

    # ── Public API ───────────────────────────────────────────────────────────

    def apply_intervention(self, log: InterventionLog) -> None:
        """
        Update BN evidence from a DAG intervention result.
        Hard evidence is set for every node whose state was determined.
        """
        for nid, state in log.downstream_changes.items():
            if nid not in self._bn_nodes:
                continue
            node = self._bn_nodes[nid]
            if state in node.states:
                self._evidence[nid] = node.states.index(state)

        if PGMPY_AVAILABLE:
            self._refresh_beliefs()
        else:
            # Fallback: set belief to spike on observed state
            for nid, state in log.downstream_changes.items():
                if nid not in self._bn_nodes:
                    continue
                node = self._bn_nodes[nid]
                self._beliefs[nid] = {
                    s: (1.0 if s == state else 0.0) for s in node.states
                }

    def get_beliefs(self) -> dict[str, dict[str, float]]:
        """Return full belief distributions for all BN nodes."""
        return dict(self._beliefs)

    def get_most_likely_states(self) -> dict[str, str]:
        """Return the MAP state for each BN node."""
        result = {}
        for nid, dist in self._beliefs.items():
            if dist:
                result[nid] = max(dist, key=dist.get)
        return result

    def get_state_summary(self) -> dict[str, Any]:
        """Human-readable summary for the LLM narrator prompt."""
        likely = self.get_most_likely_states()
        dag_states = self._dag.get_state_summary()

        # Merge: DAG hard state wins where available, BN MAP fills gaps
        summary = {}
        for nid in self._bn_nodes:
            dag_val = dag_states.get(nid)
            summary[nid] = dag_val if dag_val is not None else likely.get(nid, "unknown")
        return summary

    def reset(self) -> None:
        self._evidence.clear()
        self._beliefs.clear()
        if PGMPY_AVAILABLE:
            self._refresh_beliefs()
        else:
            self._init_fallback_beliefs()
