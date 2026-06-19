# ✦ Threadfall — Changelog

All notable changes to this project are documented here.
Format follows [Keep a Changelog](https://keepachangelog.com/en/1.1.0/).

---

## [Unreleased]

> Changes planned but not yet implemented — see shortcomings list.

- Streaming LLM narrator (token-by-token via SSE)
- Narrative history restored on page refresh via `/session/{id}`
- "New Chronicle" restart button in GameView
- Act transition animated title card
- Differentiated game-over screen (crimson / gold / silver per outcome)
- `llm/randomizer.py` module (decouple randomizer from `main.py`)
- Input length cap (400 chars) with frontend character counter
- 30-second timeout on all LLM calls
- Auto-generate `dagMeta.json` from `long.json` at startup
- Unit tests for DAG propagation, probability math, and classifier
- Second campaign

---

## [0.3.0] — 2026-06-19

### Added
- **Gothic frontend redesign** — full dark aesthetic across all components
  - New CSS variable palette: `--void`, `--ink-raised`, `--stone`, `--border-warm`, `--border-gold`, `--blood-mid/bright`, `--gold-dim/mid/text/bright`, `--parchment-mid`, `--mist`
  - `Cinzel Decorative` added alongside `Cinzel`, `IM Fell English`, `Crimson Text`
  - Vignette overlay, ornamental dividers (`.divider`), panel border utilities (`.panel-border-warm`)
  - Body-level `background-image` radial gradients for subtle warm atmosphere
- **Character Randomizer** — `⚄ Randomize` button on creation screen
  - `GET /randomize_character` backend endpoint
  - LLM-generated name, class, race, level, 6 stats, backstory via structured prompt
  - Regex parser with clamped stat validation; curated local fallback if LLM unavailable
- **Live ability score modifiers** — modifiers now update in real time as scores are typed
  - Separate `rawStats` state (strings) tracks the input field value
  - Modifier colour-coded: gold (positive), crimson (negative), parchment (zero)
  - On blur: value clamped to `[1, 20]`, preventing invalid state
- **README.md** — full rewrite with gothic aesthetic
  - `docs/banner.svg` — 900×240 dark SVG banner with glow filter, gold title, blood-red subtitle
  - `docs/divider.svg` — ornamental section separator with flanking rules
  - Full coverage of Pearl's causal hierarchy, DAG math, sigmoid formula, BN CPT generation, classifier design
- **Narrator double-call bug fixed** — `narrator.py` previously called the LLM twice per action (into `prose` then `raw`); only one call is now made

### Changed
- `App.jsx` — Character creation form redesigned as gothic tome; all inputs use `borderRadius: 0`
- `GameView.jsx` — All panel headers use Cinzel micro-label style; scene banner in uppercase Cinzel tracking; Act button sharp-cornered blood red
- `NarrativeFeed.jsx` — Blood-red square entry markers, `❧` separators in outcome badge, `›` arrow for player echo, IM Fell English at 1.05rem / 1.85 line-height
- `StatsPanel.jsx` — Stat blocks with warm top border, proficiency tags in dark blood-red border
- `CausalGraph.jsx` — Darker node colors to match new palette (`#6b0f0f`, `#122640`, `#2a1040`, `#3a2e00`)
- `index.css` — `@import` moved above Tailwind directives to avoid PostCSS ordering warning

---

## [0.2.0] — 2026-06-18

### Added
- **Conflict status rename** — `war_status` renamed to `conflict_status` throughout `long.json`, `dagMeta.json`, and all references
- **Verb-first action classifier** — social verbs (`ask`, `tell`, `urge`) score 2.0× vs. combat nouns 1.0×; prevents "ask the soldiers" classifying as combat
- **Structured LLM narrator output** — `TITLE / PARA1 / PARA2` format enforced in system prompt; regex parser extracts fields; title used as scene banner (no longer pulled from prose)
- **Scene banner from LLM** — banner is now the `TITLE` field from the narrator, not a predefined scene string
- **Milestone pacing — three-layer system**:
  - Score threshold: ≥ 0.65 to reach `incomplete`, ≥ 0.88 for `complete`
  - One-step enforcement: milestone advances at most one state per action
  - Sequential act lock: `actN_milestone` blocked until `act(N-1)_milestone` ≥ `partial`
- **Outcome node gate** — `final_outcome` cannot resolve until all four act milestones are past `incomplete`
- **HuggingFace InferenceClient narrator** — `Qwen/Qwen2.5-7B-Instruct` via featherless-ai provider (no explicit `provider=` arg); fallback chain: Qwen2.5-3B → Llama-3.2-3B → Phi-3.5-mini
- **Fallback narration** — tone-matched local prose when HF token absent or all models fail; no longer echoes player input

### Fixed
- `pgmpy` `BayesianNetwork` renamed to `DiscreteBayesianNetwork` — import with try/except fallback for compatibility
- DAG `_propagate()` returning `states[0]` (= `"incomplete"`) when score < 0.65, incorrectly advancing milestones from `None` — now returns `node.current_state` (which stays `None`)
- `do()` skips `None` returns from `_propagate()` so blocked nodes don't change state
- Fallback narration no longer starts with `"You act: {action}."` echo

---

## [0.1.0] — 2026-06-17

### Added
- **Core causal engine** — `CausalDAG` with topological propagation, weighted sigmoid push score, `do()` operator (Pearl graph surgery)
- **Bayesian Network world state** — `WorldState` with auto-generated CPTs from DAG edge weights; Variable Elimination inference via `pgmpy`
- **Character sheet** — D&D 5e ability modifiers, `success_probability()` via sigmoid, `sample_outcome()` with seeded RNG
- **Campaign: The Shattered Pact** — `long.json`, 20 nodes, 26 edges, 5 acts, predefined scene texts per act
- **FastAPI backend** — `/new_game`, `/action`, `/session/{id}`, `DELETE /session/{id}`; in-memory session store; seeded RNG per session
- **Full action pipeline** — classify → sample → DAG intervention → BN update → advance act → narrate → check game over
- **React frontend** — character creation form, three-panel game view (Causal Graph | Narrative | Stats + World State + Milestones)
- **Cytoscape.js DAG visualisation** — node types colour-coded; breadthfirst layout; opacity encodes determined vs. undetermined state
- **`requirements.txt`** — core dependencies pinned with `>=` lower bounds

---

## Fix Reference — Known Issues Resolved Per Version

| Issue | Fixed In |
|-------|----------|
| `war_status` → `conflict_status` rename | 0.2.0 |
| Story ending after first action (no milestone gates) | 0.2.0 |
| Narrator echoing player input | 0.2.0 |
| Banner pulled from prose (often player text) | 0.2.0 |
| `DiscreteBayesianNetwork` import error | 0.2.0 |
| Milestone advancing from `None` → `incomplete` on score < 0.65 | 0.2.0 |
| Ability score modifiers static (not live-updating) | 0.3.0 |
| Narrator double-calling LLM per action | 0.3.0 |
| `@import` ordering warning in PostCSS | 0.3.0 |
| `/randomize_character` not proxied in Vite | 0.3.1 |
| Dead code block in `character.py:sample_outcome()` | 0.3.1 |
| `CausalGraph.jsx` top-level `await import()` breaking Vite bundling | 0.3.1 |
| BN inference failure silently swallowed | 0.3.1 |
