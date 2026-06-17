"""
Causal DAG engine for Threadfall.

Nodes represent world variables, actions, milestones, and outcomes.
Intervention logic follows Pearl's do-calculus: do(X=x) removes all incoming
edges to X and fixes its value, then propagates downstream via topological order.
"""

from __future__ import annotations

import json
import random
import re
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any


class NodeType(str, Enum):
    ACTION = "action"
    STATE = "state"
    MILESTONE = "milestone"
    OUTCOME = "outcome"


@dataclass
class Node:
    id: str
    type: NodeType
    states: list[str]          # ordered from worst to best
    current_state: str | None = None
    description: str = ""

    def state_index(self, state: str | None = None) -> int:
        s = state or self.current_state
        return self.states.index(s) if s in self.states else 0

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "type": self.type,
            "states": self.states,
            "current_state": self.current_state,
            "description": self.description,
        }


@dataclass
class Edge:
    source: str
    target: str
    weight: float = 1.0          # influence strength, used by downstream propagation


@dataclass
class InterventionLog:
    action_node: str
    forced_state: str
    downstream_changes: dict[str, str]   # node_id → new_state
    causal_chain: list[str]              # ordered list of nodes affected


class CausalDAG:
    """
    Directed acyclic graph encoding the story's causal structure.

    Supports:
    - do(node, state): Pearl-style intervention — fixes a node's value,
      removes its incoming edges for this step, propagates downstream.
    - get_ancestors / get_descendants: graph traversal utilities.
    - Serialization to/from JSON campaign files.
    """

    def __init__(self, seed: int = 42):
        self._nodes: dict[str, Node] = {}
        self._edges: list[Edge] = []
        self._adjacency: dict[str, list[str]] = {}   # parent → [children]
        self._parents: dict[str, list[str]] = {}     # child → [parents]
        self._rng = random.Random(seed)

    # ── Graph construction ──────────────────────────────────────────────────

    def add_node(self, node: Node) -> None:
        self._nodes[node.id] = node
        self._adjacency.setdefault(node.id, [])
        self._parents.setdefault(node.id, [])

    def add_edge(self, source: str, target: str, weight: float = 1.0) -> None:
        assert source in self._nodes, f"Unknown source node: {source}"
        assert target in self._nodes, f"Unknown target node: {target}"
        self._edges.append(Edge(source, target, weight))
        self._adjacency[source].append(target)
        self._parents[target].append(source)

    # ── Traversal ───────────────────────────────────────────────────────────

    def topological_order(self) -> list[str]:
        visited, order = set(), []

        def dfs(n: str) -> None:
            if n in visited:
                return
            visited.add(n)
            for child in self._adjacency[n]:
                dfs(child)
            order.append(n)

        for node_id in self._nodes:
            dfs(node_id)
        return list(reversed(order))

    def get_descendants(self, node_id: str) -> list[str]:
        """All nodes reachable from node_id (exclusive)."""
        visited, queue = set(), [node_id]
        while queue:
            n = queue.pop()
            for child in self._adjacency.get(n, []):
                if child not in visited:
                    visited.add(child)
                    queue.append(child)
        return list(visited)

    def get_ancestors(self, node_id: str) -> list[str]:
        visited, queue = set(), [node_id]
        while queue:
            n = queue.pop()
            for parent in self._parents.get(n, []):
                if parent not in visited:
                    visited.add(parent)
                    queue.append(parent)
        return list(visited)

    # ── Intervention (do-calculus) ──────────────────────────────────────────

    def do(self, node_id: str, state: str) -> InterventionLog:
        """
        Apply do(node_id = state).

        1. Force node_id to `state` (ignoring its parents for this step).
        2. Propagate the change downstream in topological order.
        3. Return a log of every node changed and the causal chain.
        """
        assert node_id in self._nodes, f"Unknown node: {node_id}"
        node = self._nodes[node_id]
        assert state in node.states, f"Invalid state '{state}' for node '{node_id}'"

        node.current_state = state
        downstream = self.get_descendants(node_id)

        # Topological pass over descendants only
        topo = [n for n in self.topological_order() if n in downstream]
        changes: dict[str, str] = {node_id: state}
        chain: list[str] = [node_id]

        for nid in topo:
            new_state = self._propagate(nid)
            if new_state is None:
                continue  # node blocked from updating (e.g. outcome gate not met)
            old_state = self._nodes[nid].current_state
            self._nodes[nid].current_state = new_state
            if new_state != old_state:
                changes[nid] = new_state
                chain.append(nid)

        return InterventionLog(
            action_node=node_id,
            forced_state=state,
            downstream_changes=changes,
            causal_chain=chain,
        )

    def _propagate(self, node_id: str) -> str | None:
        """
        Determine a node's new state from its parents' current states.
        Returns None if the node is gated and should not update this step.

        Strategy: weighted average of parent state indices → discretize back.
        This is intentionally simple; the PGM layer (world_state.py) handles
        full belief propagation. This gives a deterministic structural push.
        """
        node = self._nodes[node_id]
        parents = self._parents[node_id]

        if not parents:
            return node.current_state  # root node — leave as-is

        parent_edges = {e.source: e.weight for e in self._edges if e.target == node_id}

        # OUTCOME nodes only resolve once ALL milestone parents are past "incomplete".
        if node.type == NodeType.OUTCOME:
            for p in parents:
                pnode = self._nodes[p]
                if pnode.type == NodeType.MILESTONE and (
                    pnode.current_state is None or pnode.current_state == "incomplete"
                ):
                    return None  # blocked — don't touch the outcome node yet

        # Act-gating: actN_milestone can only advance if act(N-1)_milestone is
        # at least "partial". This enforces sequential act progression.
        if node.type == NodeType.MILESTONE:
            m = re.match(r"act(\d+)_milestone", node_id)
            if m:
                act_num = int(m.group(1))
                if act_num > 1:
                    prev_id = f"act{act_num - 1}_milestone"
                    prev = self._nodes.get(prev_id)
                    if prev is None or prev.current_state in (None, "incomplete"):
                        return None  # blocked — prior act not started yet

        # Count how many parents actually have a state set
        active_parents = [p for p in parents if self._nodes[p].current_state is not None]
        if not active_parents:
            return node.current_state or node.states[0]

        active_weight = sum(parent_edges.get(p, 1.0) for p in active_parents)

        score = 0.0
        for p in active_parents:
            pnode = self._nodes[p]
            idx = pnode.state_index()
            normalized = idx / max(len(pnode.states) - 1, 1)
            w = parent_edges.get(p, 1.0) / active_weight
            score += normalized * w

        # Map [0,1] score back to this node's state space
        target_idx = round(score * (len(node.states) - 1))
        target_idx = max(0, min(target_idx, len(node.states) - 1))

        # Milestones have stricter thresholds — a single good action is not enough.
        # Score must exceed 0.65 to reach "partial" and 0.88 to reach "complete".
        if node.type == NodeType.MILESTONE:
            n = len(node.states)  # incomplete(0), partial(1), complete(2)
            current_idx = node.state_index() if node.current_state else -1

            if score < 0.65:
                # Not enough momentum yet — leave the milestone untouched
                return node.current_state  # None stays None
            elif score < 0.88:
                target_idx = min(target_idx, n - 2)   # cap at partial

            # Enforce one-step-at-a-time
            target_idx = min(target_idx, current_idx + 1)

        return node.states[target_idx]

    # ── Queries ─────────────────────────────────────────────────────────────

    def get_state_summary(self) -> dict[str, str | None]:
        return {nid: n.current_state for nid, n in self._nodes.items()}

    def get_milestone_states(self) -> dict[str, str | None]:
        return {
            nid: n.current_state
            for nid, n in self._nodes.items()
            if n.type == NodeType.MILESTONE
        }

    def get_outcome_states(self) -> dict[str, str | None]:
        return {
            nid: n.current_state
            for nid, n in self._nodes.items()
            if n.type == NodeType.OUTCOME
        }

    def is_campaign_over(self) -> bool:
        # All milestones must be resolved (not None, not "incomplete") before
        # the campaign can end — prevents premature termination from early propagation.
        milestones = self.get_milestone_states()
        if not milestones:
            return False
        all_milestones_done = all(
            s is not None and s != "incomplete" for s in milestones.values()
        )
        if not all_milestones_done:
            return False
        outcomes = self.get_outcome_states()
        return any(s is not None for s in outcomes.values())

    def node(self, node_id: str) -> Node:
        return self._nodes[node_id]

    def nodes(self) -> dict[str, Node]:
        return dict(self._nodes)

    def edges(self) -> list[Edge]:
        return list(self._edges)

    # ── Serialization ────────────────────────────────────────────────────────

    def to_dict(self) -> dict:
        return {
            "nodes": [n.to_dict() for n in self._nodes.values()],
            "edges": [
                {"source": e.source, "target": e.target, "weight": e.weight}
                for e in self._edges
            ],
        }

    @classmethod
    def from_dict(cls, data: dict, seed: int = 42) -> "CausalDAG":
        dag = cls(seed=seed)
        for nd in data["nodes"]:
            dag.add_node(
                Node(
                    id=nd["id"],
                    type=NodeType(nd["type"]),
                    states=nd["states"],
                    current_state=nd.get("current_state"),
                    description=nd.get("description", ""),
                )
            )
        for ed in data["edges"]:
            dag.add_edge(ed["source"], ed["target"], ed.get("weight", 1.0))
        return dag

    @classmethod
    def from_campaign_file(cls, path: str | Path, seed: int = 42) -> "CausalDAG":
        with open(path) as f:
            return cls.from_dict(json.load(f), seed=seed)
