import React, { useState, useRef } from "react";
import NarrativeFeed from "./NarrativeFeed";
import StatsPanel from "./StatsPanel";
import CausalGraph from "./CausalGraph";
import { takeAction } from "../api";

function PanelHead({ children, accent }) {
  return (
    <div
      className="px-4 py-2.5 flex-shrink-0 flex items-center gap-2"
      style={{ borderBottom: `1px solid var(--border${accent ? "-warm" : ""})` }}
    >
      <span
        className="uppercase tracking-[0.3em]"
        style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem", letterSpacing: "0.3em" }}
      >
        {children}
      </span>
    </div>
  );
}

export default function GameView({ gameState, onStateUpdate, dagMeta }) {
  const [input, setInput] = useState("");
  const [isLoading, setIsLoading] = useState(false);
  const [error, setError] = useState(null);
  const [entries, setEntries] = useState([]);
  const inputRef = useRef(null);

  const { sessionId, character, worldState, beliefs, currentAct, totalActs, sceneText, gameOver, finalOutcome } = gameState;

  async function handleSubmit(e) {
    e.preventDefault();
    const trimmed = input.trim();
    if (!trimmed || isLoading || gameOver) return;
    setInput("");
    setIsLoading(true);
    setError(null);
    try {
      const result = await takeAction(sessionId, trimmed);
      setEntries(prev => [...prev, {
        player_input: trimmed,
        action_type: result.action_type,
        outcome: result.outcome,
        probability: result.probability,
        relevant_stat: result.relevant_stat,
        downstream_changes: result.downstream_changes,
        narrative: result.narrative,
        current_act: result.current_act,
        scene_text: result.scene_text,
      }]);
      onStateUpdate(result);
    } catch (err) {
      setError(err.message || "Something went wrong.");
    } finally {
      setIsLoading(false);
      inputRef.current?.focus();
    }
  }

  return (
    <div
      className="flex h-screen overflow-hidden"
      style={{
        background: "var(--void)",
        backgroundImage: "radial-gradient(ellipse at 15% 50%, rgba(90,10,10,0.04) 0%, transparent 50%)",
      }}
    >

      {/* ── Left: Causal Graph ─────────────────────────────────────────────── */}
      <div
        className="flex flex-col flex-shrink-0"
        style={{
          width: 260,
          borderRight: "1px solid var(--border)",
          background: "var(--ink-raised)",
        }}
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
        <div
          className="px-3 py-2 flex flex-wrap gap-x-3 gap-y-1"
          style={{ borderTop: "1px solid var(--border)" }}
        >
          {[["Action","#7a1515"],["State","#1a3a5c"],["Milestone","#3a1a5c"],["Outcome","#5c4a00"]].map(([label, color]) => (
            <span key={label} className="flex items-center gap-1.5" style={{ fontSize: "0.6rem", color: "var(--parchment-dim)", fontFamily: "Cinzel, serif" }}>
              <span className="inline-block w-2 h-2" style={{ background: color }} />
              {label}
            </span>
          ))}
        </div>
      </div>

      {/* ── Center: Narrative ──────────────────────────────────────────────── */}
      <div className="flex flex-col flex-1 min-w-0">

        {/* Scene banner */}
        <div
          className="flex-shrink-0 px-7 py-3"
          style={{
            borderBottom: "1px solid var(--border-warm)",
            background: "linear-gradient(to bottom, var(--ink-raised), var(--ink))",
          }}
        >
          <p
            className="uppercase tracking-[0.2em] leading-relaxed"
            style={{ fontFamily: "Cinzel, serif", color: "var(--parchment-mid)", fontSize: "0.7rem" }}
          >
            {sceneText}
          </p>
        </div>

        {/* Feed */}
        <NarrativeFeed entries={entries} isLoading={isLoading} />

        {/* Input bar */}
        <div
          className="flex-shrink-0 px-6 py-4"
          style={{
            borderTop: "1px solid var(--border-warm)",
            background: "linear-gradient(to top, var(--ink-raised), var(--ink))",
          }}
        >
          {gameOver ? (
            <div className="text-center py-4">
              <p className="text-xs uppercase tracking-[0.4em] mb-2"
                style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.6rem" }}>
                ✦ &nbsp; Finis &nbsp; ✦
              </p>
              <div className="text-3xl tracking-widest font-bold mb-2"
                style={{ fontFamily: "'Cinzel Decorative', Cinzel, serif", color: "var(--gold-text)", textShadow: "0 0 30px rgba(196,144,48,0.3)" }}>
                The Tale Is Told
              </div>
              <div className="text-sm italic capitalize" style={{ color: "var(--parchment-dim)", fontFamily: "'IM Fell English', Georgia, serif" }}>
                {finalOutcome?.replace(/_/g, " ")}
              </div>
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
                  letterSpacing: "0.25em",
                }}
                onMouseEnter={e => !e.currentTarget.disabled && (e.currentTarget.style.background = "var(--blood-bright)")}
                onMouseLeave={e => e.currentTarget.style.background = "var(--blood-mid)"}
              >
                {isLoading ? "…" : "Act"}
              </button>
            </form>
          )}
          {error && (
            <p className="text-xs mt-2 italic" style={{ color: "var(--failure-text)" }}>{error}</p>
          )}
        </div>
      </div>

      {/* ── Right: Stats + World + Milestones ─────────────────────────────── */}
      <div
        className="flex-shrink-0 overflow-y-auto"
        style={{
          width: 230,
          borderLeft: "1px solid var(--border)",
          background: "var(--ink-raised)",
        }}
      >

        {/* Character */}
        <div style={{ borderBottom: "1px solid var(--border)", padding: "0.75rem 1rem 1rem" }}>
          <div className="uppercase tracking-[0.3em] mb-3"
            style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}>
            Chronicle
          </div>
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
                <div
                  key={node}
                  className="flex justify-between items-baseline py-1.5 text-xs"
                  style={{ borderBottom: "1px solid var(--border-dim)" }}
                >
                  <span className="capitalize" style={{ color: "var(--parchment-dim)" }}>
                    {node.replace(/_/g, " ")}
                  </span>
                  <span className="ml-2 text-right" style={{ color: "var(--gold-text)", fontFamily: "Cinzel, serif", fontSize: "0.6rem" }}>
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
                const done = state === "complete";
                const partial = state === "partial";
                const incomplete = state === "incomplete";
                const unstarted = !state;
                const dotColor = done ? "var(--success-text)" : partial ? "var(--partial-text)" : incomplete ? "var(--failure-text)" : "var(--stone-light)";
                const textColor = done ? "var(--success-text)" : partial ? "var(--partial-text)" : "var(--mist)";
                const actNum = node.replace("act","").replace("_milestone","").replace("final","5");
                const label = node.includes("act") ? `Act ${actNum}` : "Final";
                return (
                  <div key={node} className="flex items-center gap-2.5">
                    <span className="flex-shrink-0 w-2 h-2 rounded-full" style={{ background: dotColor, boxShadow: done ? `0 0 6px ${dotColor}` : "none" }} />
                    <span className="text-xs capitalize" style={{ color: textColor, fontFamily: "Cinzel, serif", fontSize: "0.65rem" }}>
                      {label}
                    </span>
                    {state && (
                      <span className="text-xs ml-auto capitalize" style={{ color: "var(--parchment-dim)", fontSize: "0.55rem" }}>
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
