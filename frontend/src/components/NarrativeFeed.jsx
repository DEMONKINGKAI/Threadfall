import React, { useEffect, useRef } from "react";

const OUTCOME_MAP = {
  success:   { label: "Victory",    color: "var(--success-text)",  bg: "var(--success-bg)",  border: "var(--success-border)" },
  efficient: { label: "Efficient",  color: "var(--success-text)",  bg: "var(--success-bg)",  border: "var(--success-border)" },
  partial:   { label: "Partial",    color: "var(--partial-text)",  bg: "var(--partial-bg)",  border: "var(--partial-border)" },
  normal:    { label: "Normal",     color: "var(--partial-text)",  bg: "var(--partial-bg)",  border: "var(--partial-border)" },
  failure:   { label: "Failure",    color: "var(--failure-text)",  bg: "var(--failure-bg)",  border: "var(--failure-border)" },
  wasteful:  { label: "Wasteful",   color: "var(--failure-text)",  bg: "var(--failure-bg)",  border: "var(--failure-border)" },
};

function OutcomeBadge({ outcome, probability, stat, actionType }) {
  const s = OUTCOME_MAP[outcome] || { label: outcome, color: "var(--mist)", bg: "transparent", border: "var(--border)" };
  return (
    <div
      className="flex flex-wrap items-center gap-3 px-3 py-2 mb-4 text-xs"
      style={{
        background: s.bg,
        border: `1px solid ${s.border}`,
        borderRadius: 0,
      }}
    >
      <span className="uppercase tracking-[0.25em] font-bold" style={{ color: s.color, fontFamily: "Cinzel, serif", fontSize: "0.6rem" }}>
        {s.label}
      </span>
      <span style={{ color: "var(--border-warm)", fontSize: "0.7rem" }}>❧</span>
      <span style={{ color: "var(--parchment-dim)" }}>
        {(probability * 100).toFixed(0)}% &mdash; &thinsp;
        <span style={{ color: "var(--gold-text)" }} className="capitalize">{stat}</span>
      </span>
      <span style={{ color: "var(--border-warm)", fontSize: "0.7rem" }}>❧</span>
      <span className="capitalize" style={{ color: "var(--mist)" }}>
        {actionType?.replace(/_/g, " ")}
      </span>
    </div>
  );
}

function NarrativeEntry({ entry, index }) {
  return (
    <div
      className="mb-10"
      style={{
        borderLeft: "2px solid var(--border-warm)",
        paddingLeft: "1.5rem",
        position: "relative",
      }}
    >
      {/* Entry marker */}
      <div
        style={{
          position: "absolute",
          left: -5,
          top: 0,
          width: 8,
          height: 8,
          background: "var(--blood-mid)",
          border: "1px solid var(--blood-bright)",
        }}
      />

      {/* Act label */}
      <div className="flex items-center gap-2 mb-2">
        <span
          className="uppercase tracking-[0.35em]"
          style={{ fontFamily: "Cinzel, serif", color: "var(--gold-dim)", fontSize: "0.55rem" }}
        >
          Act {entry.current_act}
        </span>
        <div style={{ height: 1, flex: 1, background: "var(--border-dim)" }} />
      </div>

      {/* Player input */}
      <div
        className="text-xs italic mb-3 flex items-start gap-1.5"
        style={{ color: "var(--parchment-dim)", fontFamily: "'IM Fell English', Georgia, serif", fontSize: "0.85rem" }}
      >
        <span style={{ color: "var(--blood-bright)" }}>›</span>
        {entry.player_input}
      </div>

      {/* Outcome badge */}
      <OutcomeBadge
        outcome={entry.outcome}
        probability={entry.probability}
        stat={entry.relevant_stat}
        actionType={entry.action_type}
      />

      {/* Prose */}
      <div
        className="leading-[1.85] mb-4"
        style={{
          fontFamily: "'IM Fell English', Georgia, serif",
          fontSize: "1.05rem",
          color: "var(--parchment)",
          whiteSpace: "pre-wrap",
        }}
      >
        {entry.narrative}
      </div>

      {/* Downstream changes */}
      {Object.keys(entry.downstream_changes || {}).length > 0 && (
        <div className="flex flex-wrap gap-1.5 pt-2" style={{ borderTop: "1px solid var(--border-dim)" }}>
          {Object.entries(entry.downstream_changes).map(([node, state]) => (
            <span
              key={node}
              className="text-xs px-2 py-0.5"
              style={{
                background: "var(--stone)",
                border: "1px solid var(--border)",
                color: "var(--parchment-dim)",
                fontFamily: "Cinzel, serif",
                fontSize: "0.55rem",
                letterSpacing: "0.05em",
                textTransform: "capitalize",
              }}
            >
              {node.replace(/_/g, " ")}
              <span style={{ color: "var(--gold-text)" }}> → {state}</span>
            </span>
          ))}
        </div>
      )}
    </div>
  );
}

export default function NarrativeFeed({ entries, isLoading }) {
  const bottomRef = useRef(null);
  useEffect(() => { bottomRef.current?.scrollIntoView({ behavior: "smooth" }); }, [entries, isLoading]);

  return (
    <div className="flex-1 overflow-y-auto" style={{ padding: "2rem 2.5rem" }}>
      {entries.length === 0 && !isLoading && (
        <div className="flex flex-col items-center justify-center h-full" style={{ paddingTop: "4rem" }}>
          <p className="text-xs uppercase tracking-[0.4em] mb-3"
            style={{ fontFamily: "Cinzel, serif", color: "var(--mist)", fontSize: "0.55rem" }}>
            ✦ &nbsp; The realm holds its breath &nbsp; ✦
          </p>
          <p className="text-sm italic text-center" style={{ color: "var(--parchment-dim)", fontFamily: "'IM Fell English', Georgia, serif", maxWidth: 300 }}>
            Speak your first action. The threads of fate await your command.
          </p>
        </div>
      )}

      {entries.map((entry, i) => <NarrativeEntry key={i} entry={entry} index={i} />)}

      {isLoading && (
        <div className="mb-8" style={{ borderLeft: "2px solid var(--border)", paddingLeft: "1.5rem" }}>
          <p className="text-sm italic animate-pulse" style={{ color: "var(--mist)", fontFamily: "'IM Fell English', Georgia, serif" }}>
            The fates deliberate…
          </p>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
}
