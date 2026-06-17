# ✦ THREADFALL ✦
### *A Causal Narrative Chronicle*

> *An ancient pact between kingdoms shatters. One hero must navigate politics, war, and betrayal — or watch the realm burn.*

**Threadfall** is a solo narrative RPG in which story outcomes are governed not by dice — but by cause and effect. Built as a portfolio piece demonstrating the application of **Judea Pearl's causal hierarchy** to interactive fiction, every consequence you experience flows from a transparent, auditable causal graph. The LLM never decides what happens; it only narrates what the engine has already determined.

---

## ❖ The Core Philosophy

> *"The difference between seeing and doing."* — Judea Pearl, *The Book of Why*

Most AI games hand the language model the wheel. Threadfall inverts this: the causal engine is the author; the LLM is the voice. This separation guarantees that outcomes are **reproducible**, **interpretable**, and **mathematically grounded** — not hallucinated.

```
Player Input
    │
    ▼
┌─────────────────┐    ┌────────────────────┐    ┌──────────────┐
│   Classifier    │───▶│  Character Sheet   │───▶│  Causal DAG  │
│ (intent → type) │    │ (stats → outcome)  │    │  do() op.    │
└─────────────────┘    └────────────────────┘    └──────┬───────┘
                                                         │
                                              ┌──────────▼───────────┐
                                              │  Bayesian Network    │
                                              │  (belief update)     │
                                              └──────────┬───────────┘
                                                         │
                                              ┌──────────▼───────────┐
                                              │  LLM Narrator        │
                                              │  (prose only)        │
                                              └──────────────────────┘
```

---

## ⚔ Pearl's Causal Hierarchy

The engine implements all three rungs of Pearl's *Ladder of Causation*:

| Rung | Operation | Question | Example |
|------|-----------|----------|---------|
| **1 — Association** | `P(Y \| X)` | *What is?* | What is the current state of faction loyalty? |
| **2 — Intervention** | `P(Y \| do(X))` | *What if I do?* | What happens if I attack the convoy? |
| **3 — Counterfactual** | `P(Y_x \| X', Y')` | *What if I had?* | Would the pact have held if I had spoken first? |

### The `do()` Operator

When a player acts, the engine performs a **graph surgery**: it cuts all incoming edges to the intervened node and forces it to the determined value, then propagates causally downstream.

```python
# dag.py — structural intervention
def do(self, node_id: str, outcome: str) -> InterventionLog:
    # 1. Set the action node to the observed outcome
    # 2. Walk topological order, propagate each affected child
    # 3. Gate milestones behind score thresholds
    # 4. Gate the final outcome behind all milestone resolution
```

Propagation uses a **weighted sigmoid** to compute a push score:

```
push_score = Σ (parent_state_index / (n_states - 1)) × edge_weight
           ÷ Σ edge_weight

sigmoid(x) = 1 / (1 + e^(−k × (x − 0.5)))   where k = 6

target_state_index = round(sigmoid(push_score) × (n_states − 1))
```

This maps the weighted average of causal pressure onto the target node's discrete state space, producing non-linear but auditable state transitions.

---

## 🗺 Causal DAG — *The Shattered Pact*

The campaign encodes **20 nodes** and **26 edges** across 5 acts:

```
ACTION NODES (player choice)
  combat_outcome · npc_interaction · resource_use
  espionage_action · political_action

STATE NODES (world conditions)
  player_health · enemy_defeated · npc_trust
  town_reputation · gold_remaining · item_inventory
  faction_loyalty · secret_knowledge · conflict_status · pact_integrity

MILESTONE NODES (act gates)
  act1_milestone → act2_milestone → act3_milestone → act4_milestone

OUTCOME NODE
  final_outcome  (story_failure | story_neutral | story_victory)
```

### Act Gating

Milestones are protected by a **three-layer progression system** so story acts cannot be rushed:

1. **Score threshold** — the push score must reach ≥ 0.65 to move from `null → incomplete`, ≥ 0.88 for `→ complete`
2. **One-step enforcement** — a milestone advances at most one state per action (no skipping from null to complete)
3. **Sequential act lock** — `actN_milestone` is blocked until `act(N-1)_milestone` is at least `partial`

The final outcome is additionally gated: it cannot resolve until **all four act milestones** are past `incomplete`.

---

## 🎲 Character & Probability

### Ability Modifiers (D&D 5e)

```
modifier(score) = ⌊(score − 10) / 2⌋
```

Modifiers update live in the character creation UI as you type. Each ability score maps to a colour-coded modifier: positive in gold, negative in crimson, zero in parchment.

Each action type draws on specific ability scores:

| Action Type | Primary Stat | Secondary |
|-------------|-------------|-----------|
| `combat_outcome` | Strength | Constitution |
| `npc_interaction` | Charisma | Wisdom |
| `resource_use` | Intelligence | — |
| `espionage_action` | Dexterity | Intelligence |
| `political_action` | Charisma | Intelligence |

### Success Probability

```
modifier_value = ability_score_modifier  (range: −5 to +5)
normalised_mod = (modifier_value + 5) / 10   (maps to [0, 1])
p              = sigmoid(normalised_mod)      using k = 8

p_success = p^1.5          (compresses extreme success)
p_failure = (1 − p)^1.5   (compresses extreme failure)
p_partial = 1 − p_success − p_failure
```

The exponentiation means that even with very high stats, failure remains possible. No roll is ever guaranteed.

---

## 🔮 Bayesian Network — World Beliefs

The engine maintains a **discrete Bayesian Network** (via `pgmpy`) alongside the structural DAG. While the DAG tracks *determined state*, the BN tracks *probabilistic belief* — expressing uncertainty about nodes not yet directly intervened on.

**Conditional Probability Tables (CPTs)** are auto-generated from DAG edge weights using Dirichlet-smoothed softmax:

```python
for each child node c with parents p1, p2, ..., pk:
    for each parent configuration:
        scores[state_i] = w_i × (state_i_idx / (n_states − 1))
        cpt[config]     = softmax(scores + α)   # α = 0.1 Dirichlet smoothing
```

After each `do()` intervention, `VariableElimination` recomputes the marginal distribution over all non-intervened nodes, producing the belief percentages visible in the Causal Web panel.

---

## 🗡 Action Classifier

The classifier maps free-text player input to one of five canonical action types using **verb-first weighted keyword matching** — no API call required.

**Why verb-first?** The primary verb signals intent more reliably than noun context. *"Ask the soldiers about the ambush"* classifies as `npc_interaction` — not `combat_outcome` — even though "soldiers" and "ambush" carry combat associations.

```python
_RULES = [
    ("espionage_action", 2.0, ["sneak","infiltrate","eavesdrop",...]),  # verbs: 2× weight
    ("political_action", 2.0, ["declare","proclaim","invoke",...]),
    ("npc_interaction",  2.0, ["ask","tell","persuade","warn",...]),    # social verbs win
    ("combat_outcome",   2.0, ["attack","strike","slash",...]),
    ...
    ("npc_interaction",  1.0, ["guard","soldier","noble",...]),         # nouns: 1× weight
    ("combat_outcome",   1.0, ["sword","blade","ambush",...]),
]

confidence = best_score / Σ all_scores
```

Espionage and political rules are checked first (highest specificity). Social verbs always override combat nouns when both appear in the same sentence.

---

## 📜 LLM Narrator

The narrator receives **pre-determined facts** and produces prose. It cannot change an outcome, invent a consequence, or contradict the causal graph.

**Model**: `Qwen/Qwen2.5-7B-Instruct` via HuggingFace InferenceClient (featherless-ai provider)
**Fallback models**: Qwen2.5-3B · Llama-3.2-3B · Phi-3.5-mini (tried in order)

**Structured output format** enforced by system prompt:

```
TITLE: <4–7 word dark chapter title, specific to this moment>
PARA1: <3–4 sentences — physical action and immediate sensory result>
PARA2: <Exactly 3 sentences — ONE concrete causal hint, not yet resolved>
```

The `TITLE` field becomes the scene banner in the UI. `PARA1 + PARA2` form the narrative prose. A regex parser extracts these fields; if the model ignores the format, raw output is used as prose and the act description becomes the title.

**Fallback narration** (no HF token): a tone-matched paragraph is generated locally from the outcome type and downstream effects — no LLM required.

---

## ⚄ Character Randomizer

The *⚄ Randomize* button in character creation calls `GET /randomize_character`. The backend queries the LLM with a structured prompt requesting a gothic, morally complex character in a fixed key-value format:

```
NAME: Serath
CLASS: Warlock
RACE: Tiefling
LEVEL: 3
STR: 10  DEX: 14  CON: 12  INT: 15  WIS: 9  CHA: 17
BACKSTORY: <2 sentences>
```

The response is parsed with regex, values are clamped to valid D&D ranges, and a pure local fallback fires if the LLM fails. The resulting character is loaded instantly into the creation form — all fields editable.

---

## 🏛 Architecture

```
Threadfall/
├── backend/
│   ├── main.py                      FastAPI app, all endpoints
│   ├── causal_engine/
│   │   ├── dag.py                   CausalDAG, do() operator, topological propagation
│   │   └── campaigns/
│   │       └── long.json            "The Shattered Pact" — 20 nodes, 26 edges, 5 acts
│   ├── pgm_engine/
│   │   ├── world_state.py           Bayesian Network, CPT generation, belief update
│   │   └── character.py             CharacterSheet, ability score → probability mapping
│   ├── llm/
│   │   ├── narrator.py              HuggingFace InferenceClient, structured prose
│   │   └── classifier.py           Verb-first keyword classifier, 5 action types
│   └── models/
│       └── schemas.py               Pydantic request/response schemas
└── frontend/
    ├── src/
    │   ├── App.jsx                  Character creation, live modifiers, randomizer
    │   ├── components/
    │   │   ├── GameView.jsx         Three-panel layout (Graph | Narrative | Stats)
    │   │   ├── NarrativeFeed.jsx    Scrolling log — outcome badges, causal chips
    │   │   ├── StatsPanel.jsx       D&D stat block with live modifiers
    │   │   └── CausalGraph.jsx      Cytoscape.js DAG visualisation
    │   ├── api.js                   fetch wrappers for backend endpoints
    │   ├── dagMeta.json             Static graph structure for Cytoscape rendering
    │   └── index.css               Gothic CSS palette, Cinzel + IM Fell English
    └── tailwind.config.js
```

---

## ⚙ Setup

### Prerequisites

```
Python 3.11+    Node.js 18+    npm or pnpm
```

### Backend

```bash
cd Threadfall
pip install -r requirements.txt
uvicorn backend.main:app --reload --port 8000
```

Set your HuggingFace token for LLM narration (optional — fallback prose works without it):

```bash
# Windows PowerShell
$env:HF_TOKEN = "hf_your_token_here"

# bash / macOS / Linux
export HF_TOKEN=hf_your_token_here
```

### Frontend

```bash
cd frontend
npm install
npm run dev
# Open http://localhost:5173
```

---

## 🔗 API Reference

| Method | Path | Description |
|--------|------|-------------|
| `POST` | `/new_game` | Start a session — returns initial world state |
| `POST` | `/action` | Process player input through the full causal pipeline |
| `GET` | `/session/{id}` | Fetch current session state (reconnect / refresh) |
| `DELETE` | `/session/{id}` | Clean up a session |
| `GET` | `/randomize_character` | LLM-generated believable D&D character |

### `/action` Pipeline (per request)

```
1. Classify player text → canonical action type + confidence score
2. Map action type → relevant ability stat
3. Compute p_success, p_partial, p_failure from stat modifier via sigmoid
4. Sample outcome against seeded session RNG
5. DAG.do() — graph surgery + topological state propagation
6. BN belief update via VariableElimination
7. Advance act if milestone complete; advance scene index within act
8. Narrate with pre-determined facts — LLM has no decision authority
9. Check campaign-over condition (all milestones resolved)
```

---

## 🎓 Concepts & References

| Concept | Source |
|---------|--------|
| Pearl's Causal Hierarchy | *The Book of Why* — Judea Pearl & Dana Mackenzie (2018) |
| do-Calculus & Graph Surgery | *Causality* — Judea Pearl (2000) |
| Backdoor / Frontdoor Criterion | Pearl (1995) |
| D&D 5e Ability Modifier Formula | *Player's Handbook* — Wizards of the Coast (2014) |
| Discrete Bayesian Networks & CPTs | `pgmpy` — Ankan & Panda (2015) |
| Variable Elimination Inference | Russell & Norvig, *AIMA* Chapter 13 |
| Verb-first Intent Classification | Fillmore Frame Semantics; Linguistic priority heuristics |
| Structured LLM Output Parsing | TITLE / PARA1 / PARA2 format with regex extraction |

---

## ✦ Design Principles

**The Engine Decides. The LLM Narrates.**
The model is a voice actor, not a playwright. It receives a packet of pre-determined facts — outcome, probability, causal consequences — and writes prose around them. It cannot change a result.

**Transparency is the Feature.**
Every outcome badge shows the action type, the ability stat used, and the exact probability. Every downstream causal effect is displayed as a chip. The full DAG is visible at all times in the Causal Web panel.

**Pacing is a First-Class Constraint.**
Acts cannot be rushed. Three layers of gating — score thresholds, one-step advancement, sequential act locks — ensure the story breathes at a human pace.

**Reproducibility.**
Each session is seeded. Given the same seed and the same sequence of player inputs, the same outcomes occur every time. The game is deterministic beneath its gothic surface.

---

<p align="center">
  <em>Built with Pearl's causal hierarchy · pgmpy · FastAPI · React · Tailwind · HuggingFace Inference API</em><br/>
  <em>A portfolio project by Kai — MSc ML/AI, TU Darmstadt</em>
</p>
