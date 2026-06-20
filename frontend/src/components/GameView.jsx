import React, { useState, useRef, useEffect, useCallback } from "react";
import NarrativeFeed from "./NarrativeFeed";
import StatsPanel from "./StatsPanel";
import CausalGraph from "./CausalGraph";
import { streamAction } from "../api";

// ── Act metadata ─────────────────────────────────────────────────────────────
const ACT_TITLES = {
  1: "Survive the Ambush",
  2: "Expose the Traitor",
  3: "Protect the King",
  4: "Forge the Alliance",
  5: "The Final Thread",
};

// ── Game-over styles ──────────────────────────────────────────────────────────
const ENDGAME = {
  story_victory: {
    label:   "✦",
    heading: "VICTORY",
    sub:     "The realm endures. Your deeds will be sung for a generation.",
    color:   "var(--gold-text)",
    glow:    "rgba(196,144,48,0.35)",
    border:  "var(--border-gold)",
  },
  story_failure: {
    label:   "☩",
    heading: "RUIN",
    sub:     "The realm burns. Your name becomes a warning whispered in the dark.",
    color:   "var(--failure-text)",
    glow:    "rgba(154,24,24,0.35)",
    border:  "var(--failure-border)",
  },
  story_neutral: {
    label:   "⁂",
    heading: "THE BALANCE HOLDS",
    sub:     "Neither triumph nor catastrophe. The world endures, scarred and unresolved.",
    color:   "var(--parchment-mid)",
    glow:    "rgba(168,153,122,0.2)",
    border:  "var(--border)",
  },
};

// ── Helpers ───────────────────────────────────────────────────────────────────

// Strip TITLE:/PARA1:/PARA2: labels from streaming text for clean display
function stripStructure(text) {
  return text
    .replace(/^TITLE:\s*.+\n?/m, "")
    .replace(/^PARA\d+:\s*/gm, "")
    .trim();
}

function storageKey(sessionId) { return `tf_entries_${sessionId}`; }

function saveEntries(sessionId, entries) {
  try { localStorage.setItem(storageKey(sessionId), JSON.stringify(entries)); }
  catch { /* storage full — silently ignore */ }
}

function loadEntries(sessionId) {
  try {
    const raw = localStorage.getItem(storageKey(sessionId));
    return raw ? JSON.parse(raw) : [];
  } catch { return []; }
}

// ─────────────────────────────────────────────────────────────────────────────

export default function GameView({ gameState, onStateUpdate, dagMeta, onRestart }) {
  const [input,          setInput]          = useState("");
  const [isLoading,      setIsLoading]      = useState(false);
  const [error,          setError]          = useState(null);
  const [entries,        setEntries]        = useState(() => loadEntries(gameState.sessionId));
  const [streamingEntry, setStreamingEntry] = useState(null);   // in-progress SSE entry
  const [actTransition,  setActTransition]  = useState(null);   // { act, title } while overlay shows
  const inputRef  = useRef(null);
  const prevActRef = useRef(gameState.currentAct);

  const { sessionId, character, worldState, beliefs, currentAct, totalActs, sceneText, gameOver, finalOutcome } = gameState;

  // Task 6 — persist entries to localStorage
  useEffect(() => {
    if (entries.length > 0) saveEntries(sessionId, entries);
  }, [entries, sessionId]);

  // Task 8 — act transition overlay
  useEffect(() => {
    if (currentAct !== prevActRef.current && prevActRef.current !== null) {
      setActTransition({ act: currentAct, title: ACT_TITLES[currentAct] ?? `Act ${currentAct}` });
      const t = setTimeout(() => setActTransition(null), 2800);
      prevActRef.current = currentAct;
      return () => clearTimeout(t);
    }
    prevActRef.current = currentAct;
  }, [currentAct]);

  // Task 5 — streaming submit
  const handleSubmit = useCallback(async (e) => {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading || gameOver) return;

    setInput("");
    setIsLoading(true);
    setError(null);
    setStreamingEntry(null);

    // Hold engine data so onDone can build the complete committed entry
    let engineData = null;
    let playerInput = trimmed;

    await streamAction(sessionId, trimmed, {
      onEngine: (data) => {
        engineData = data;
        // Show outcome badge + downstream chips immediately while tokens load
        setStreamingEntry({
          player_input:       playerInput,
          action_type:        data.action_type,
          outcome:            data.outcome,
          probability:        data.probability,
          relevant_stat:      data.relevant_stat,
          downstream_changes: data.downstream_changes,
          current_act:        data.current_act,
          narrative:          "",
          isStreaming:        true,
        });
        onStateUpdate(data);
      },

      onToken: (text) => {
        setStreamingEntry(prev =>
          prev ? { ...prev, narrative: prev.narrative + text } : prev
        );
      },

      onDone: (data) => {
        // Commit final parsed entry (clean prose, correct title)
        const finalEntry = {
          player_input:       playerInput,
          action_type:        engineData?.action_type,
          outcome:            engineData?.outcome,
          probability:        engineData?.probability,
          relevant_stat:      engineData?.relevant_stat,
          downstream_changes: engineData?.downstream_changes ?? {},
          current_act:        engineData?.current_act,
          narrative:          data.narrative,
          scene_text:         data.scene_text,
        };
        setEntries(prev => {
          const updated = [...prev, finalEntry];
          saveEntries(sessionId, updated);
          return updated;
        });
        setStreamingEntry(null);

        // Update game state with final game_over / final_outcome from done event
        if (data.game_over && engineData) {
          onStateUpdate({ ...engineData, ...data });
        }
      },

      onError: (msg) => {
        setStreamingEntry(null);
        setError(msg || "Something went wrong.");
      },
    });

    setIsLoading(false);
    inputRef.current?.focus();
  }, [input, isLoading, gameOver, sessionId, onStateUpdate]);

  const endgame = ENDGAME[finalOutcome] ?? ENDGAME.story_neutral;

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{
        background: "var(--void)",
        backgroundImage: "radial-gradient(ellipse at 15% 50%, rgba(90,10,10,0.04) 0%, transparent 50%)",
        position: "relative",
      }}
    >

      {/* ── Task 8: Act transition overlay ─────────────────────────────────── */}
      {actTransition && (
        <div
          className="act-transition fixed inset-0 z-50 flex flex-col items-center justify-center"
          style={{ background: "rgba(3,3,5,0.94)", pointerEvents: "none" }}
        >
          <div
            className="text-xs uppercase tracking-[0.6em] mb-4"
            style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.6rem" }}
          >
            ✦ &nbsp; The Chronicle Advances &nbsp; ✦
          </div>
          <div
            className="tracking-[0.3em] mb-3"
            style={{
              fontFamily: "'Cinzel Decorative', Cinzel, serif",
              fontSize: "clamp(2rem,5vw,3.5rem)",
              fontWeight: 700,
              color: "var(--gold-text)",
              textShadow: "0 0 50px rgba(196,144,48,0.4)",
            }}
          >
            ACT {actTransition.act}
          </div>
          <div
            className="uppercase tracking-[0.25em] text-sm"
            style={{ fontFamily: "Cinzel, serif", color: "var(--blood-bright)" }}
          >
            {actTransition.title}
          </div>
          <div
            style={{ height: 1, width: 240, background: "linear-gradient(to right, transparent, var(--blood-mid), transparent)", marginTop: "1.5rem" }}
          />
        </div>
      )}

      {/* ── Left: Causal Graph ─────────────────────────────────────────────── */}
      <div
        className="flex flex-col flex-shrink-0"
        style={{ width: 260, borderRight: "1px solid var(--border)", background: "var(--ink-raised)" }}
      >
        <div className="px-4 py-3 flex-shrink-0" style={{ borderBottom: "1px solid var(--border)" }}>
          <div
            className="uppercase tracking-[0.3em] mb-0.5"
            style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}
          >
            Causal Web
          </div>
          <div className="text-xs italic" style={{ color: "var(--mist)", fontFamily: "'IM Fell English', serif" }}>
            Act {currentAct} of {totalActs}
          </div>
        </div>
        <div className="flex-1 overflow-hidden">
          <CausalGraph worldState={worldState} beliefs={beliefs} dagMeta={dagMeta} />
        </div>
        <div className="px-3 py-2 flex flex-wrap gap-x-3 gap-y-1" style={{ borderTop: "1px solid var(--border)" }}>
          {[["Action","#6b0f0f"],["State","#122640"],["Milestone","#2a1040"],["Outcome","#3a2e00"]].map(([label, color]) => (
            <span key={label} className="flex items-center gap-1.5"
              style={{ fontSize: "0.6rem", color: "var(--parchment-dim)", fontFamily: "Cinzel, serif" }}>
              <span className="inline-block w-2 h-2" style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* ── Centre: Narrative ──────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* Scene banner */}
        <div
          className="flex-shrink-0 px-7 py-3"
          style={{ borderBottom: "1px solid var(--border-warm)", background: "linear-gradient(to bottom, var(--ink-raised), var(--ink))" }}
        >
          <p
            className="uppercase tracking-[0.2em] leading-relaxed"
            style={{ fontFamily: "Cinzel, serif", color: "var(--parchment-mid)", fontSize: "0.7rem" }}
          >
            {sceneText}
          </p>
        </div>

        {/* Feed */}
        <NarrativeFeed entries={entries} streamingEntry={streamingEntry} isLoading={isLoading && !streamingEntry} />

        {/* Input / game-over bar */}
        <div
          className="flex-shrink-0 px-6 py-4"
          style={{ borderTop: "1px solid var(--border-warm)", background: "linear-gradient(to top, var(--ink-raised), var(--ink))" }}
        >
          {gameOver ? (
            /* Task 9 — differentiated game-over ─────────────────────────── */
            <div className="text-center py-5">
              <div
                className="text-xs uppercase tracking-[0.5em] mb-3"
                style={{ fontFamily: "Cinzel, serif", color: endgame.color, fontSize: "0.55rem", opacity: 0.7 }}
              >
                {endgame.label} &nbsp; Finis &nbsp; {endgame.label}
              </div>
              <div
                className="tracking-widest font-bold mb-3"
                style={{
                  fontFamily: "'Cinzel Decorative', Cinzel, serif",
                  fontSize: "clamp(1.5rem,3vw,2.4rem)",
                  color: endgame.color,
                  textShadow: `0 0 40px ${endgame.glow}`,
                }}
              >
                {endgame.heading}
              </div>
              <p
                className="text-sm italic mb-5 mx-auto"
                style={{ color: "var(--parchment-dim)", fontFamily: "'IM Fell English', Georgia, serif", maxWidth: 360 }}
              >
                {endgame.sub}
              </p>
              {/* Task 7 — restart button */}
              <button
                onClick={onRestart}
                className="px-8 py-2.5 uppercase tracking-[0.3em] text-xs transition-all"
                style={{
                  fontFamily: "Cinzel, serif",
                  background: "var(--stone)",
                  color: "var(--parchment-mid)",
                  border: `1px solid ${endgame.border}`,
                  borderRadius: 0,
                  cursor: "pointer",
                }}
                onMouseEnter={e => e.currentTarget.style.color = "var(--parchment)"}
                onMouseLeave={e => e.currentTarget.style.color = "var(--parchment-mid)"}
              >
                ✦ &nbsp; Begin a New Chronicle
              </button>
            </div>
          ) : (
            <form onSubmit={handleSubmit} className="flex gap-3">
              <input
                ref={inputRef}
                type="text"
                value={input}
                onChange={e => setInput(e.target.value)}
                placeholder="What do you do?"
                disabled={isLoading}
                maxLength={400}
                className="flex-1 disabled:opacity-40"
                style={{
                  background: "var(--stone)",
                  border: "1px solid var(--border-warm)",
                  borderRadius: 0,
                  color: "var(--parchment)",
                  fontFamily: "'IM Fell English', Georgia, serif",
                  fontSize: "1.05rem",
                  padding: "0.6rem 1rem",
                  outline: "none",
                }}
                onFocus={e => e.target.style.borderColor = "var(--gold-dim)"}
                onBlur={e => e.target.style.borderColor = "var(--border-warm)"}
              />
              <button
                type="submit"
                disabled={isLoading || !input.trim()}
                className="px-6 uppercase tracking-[0.25em] text-xs transition-all disabled:opacity-40"
                style={{
                  fontFamily: "Cinzel, serif",
                  background: "var(--blood-mid)",
                  color: "var(--parchment)",
                  border: "1px solid var(--border-bright)",
                  borderRadius: 0,
                  cursor: (isLoading || !input.trim()) ? "not-allowed" : "pointer",
                }}
                onMouseEnter={e => !e.currentTarget.disabled && (e.currentTarget.style.background = "var(--blood-bright)")}
                onMouseLeave={e => e.currentTarget.style.background = "var(--blood-mid)"}
              >
                {isLoading ? "…" : "Act"}
              </button>
            </form>
          )}
          {error && <p className="text-xs mt-2 italic" style={{ color: "var(--failure-text)" }}>{error}</p>}
        </div>
      </div>

      {/* ── Right: Stats + World + Milestones ─────────────────────────────── */}
      <div
        className="flex-shrink-0 overflow-y-auto"
        style={{ width: 230, borderLeft: "1px solid var(--border)", background: "var(--ink-raised)" }}
      >
        {/* Task 7 — restart button in header (available mid-game too) */}
        <div
          className="flex items-center justify-between px-4 py-2.5"
          style={{ borderBottom: "1px solid var(--border)" }}
        >
          <span className="uppercase tracking-[0.3em]"
            style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}>
            Chronicle
          </span>
          <button
            onClick={onRestart}
            title="Start a new chronicle"
            style={{
              background: "none",
              border: "none",
              color: "var(--mist)",
              cursor: "pointer",
              fontFamily: "Cinzel, serif",
              fontSize: "0.55rem",
              letterSpacing: "0.15em",
              padding: "2px 4px",
            }}
            onMouseEnter={e => e.currentTarget.style.color = "var(--blood-bright)"}
            onMouseLeave={e => e.currentTarget.style.color = "var(--mist)"}
          >
            ↺ restart
          </button>
        </div>

        {/* Character stats */}
        <div style={{ borderBottom: "1px solid var(--border)", padding: "0.75rem 1rem 1rem" }}>
          <StatsPanel character={character} />
        </div>

        {/* World State */}
        <div style={{ borderBottom: "1px solid var(--border)", padding: "0.75rem 1rem 1rem" }}>
          <div className="uppercase tracking-[0.3em] mb-2"
            style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}>
            World State
          </div>
          <div>
            {Object.entries(worldState || {})
              .filter(([k]) => !k.includes("action") && !k.includes("milestone") && k !== "final_outcome")
              .map(([node, state]) => (
                <div key={node} className="flex justify-between items-baseline py-1.5 text-xs"
                  style={{ borderBottom: "1px solid var(--border-dim)" }}>
                  <span className="capitalize" style={{ color: "var(--parchment-dim)" }}>
                    {node.replace(/_/g, " ")}
                  </span>
                  <span className="ml-2 text-right"
                    style={{ color: "var(--gold-text)", fontFamily: "Cinzel, serif", fontSize: "0.6rem" }}>
                    {state}
                  </span>
                </div>
              ))}
          </div>
        </div>

        {/* Milestones */}
        <div style={{ padding: "0.75rem 1rem 1rem" }}>
          <div className="uppercase tracking-[0.3em] mb-3"
            style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}>
            Milestones
          </div>
          <div className="space-y-2">
            {Object.entries(worldState || {})
              .filter(([k]) => k.includes("milestone"))
              .map(([node, state]) => {
                const done    = state === "complete";
                const partial = state === "partial";
                const dotColor = done ? "var(--success-text)" : partial ? "var(--partial-text)" : state === "incomplete" ? "var(--failure-text)" : "var(--stone-light)";
                const textColor = done ? "var(--success-text)" : partial ? "var(--partial-text)" : "var(--mist)";
                const label = node.replace("_milestone", "").replace("act", "Act ");
                return (
                  <div key={node} className="flex items-center gap-2.5">
                    <span className="flex-shrink-0 w-2 h-2 rounded-full"
                      style={{ background: dotColor, boxShadow: done ? `0 0 6px ${dotColor}` : "none" }} />
                    <span className="text-xs capitalize"
                      style={{ color: textColor, fontFamily: "Cinzel, serif", fontSize: "0.65rem" }}>
                      {label}
                    </span>
                    {state && (
                      <span className="text-xs ml-auto capitalize"
                        style={{ color: "var(--parchment-dim)", fontSize: "0.55rem" }}>
                        {state}
                      </span>
                    )}
                  </div>
                );
              })}
          </div>
        </div>
      </div>
    </div>
  );
}
