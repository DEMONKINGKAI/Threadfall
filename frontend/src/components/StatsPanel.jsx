import React from "react";

const STAT_ABBR = {
  strength: "STR", dexterity: "DEX", constitution: "CON",
  intelligence: "INT", wisdom: "WIS", charisma: "CHA",
};

function mod(score) { return Math.floor((score - 10) / 2); }
function modLabel(score) { const m = mod(score); return m >= 0 ? `+${m}` : `${m}`; }

export default function StatsPanel({ character }) {
  if (!character) return null;
  return (
    <div>
      {/* Name + identity */}
      <div className="mb-3">
        <div
          className="font-bold tracking-wider text-base leading-tight"
          style={{ fontFamily: "Cinzel, serif", color: "var(--gold-text)" }}
        >
          {character.name}
        </div>
        <div className="text-xs mt-0.5 italic" style={{ color: "var(--parchment-dim)", fontFamily: "'IM Fell English', Georgia, serif" }}>
          {character.race} {character.class} &middot; Lv {character.level}
        </div>
      </div>

      <div style={{ height: 1, background: "linear-gradient(to right, var(--blood-mid), transparent)", marginBottom: "0.75rem" }} />

      {/* Stat grid */}
      <div className="grid grid-cols-3 gap-1.5 mb-3">
        {Object.entries(character.stats || {}).map(([stat, score]) => (
          <div
            key={stat}
            className="flex flex-col items-center py-2"
            style={{
              background: "var(--stone)",
              border: "1px solid var(--border)",
              borderTop: "1px solid var(--border-warm)",
            }}
          >
            <span
              className="uppercase tracking-wider"
              style={{ fontFamily: "Cinzel, serif", color: "var(--mist)", fontSize: "0.5rem", letterSpacing: "0.1em" }}
            >
              {STAT_ABBR[stat] || stat.slice(0,3).toUpperCase()}
            </span>
            <span
              className="font-bold text-lg leading-none mt-1"
              style={{ color: "var(--parchment)" }}
            >
              {score}
            </span>
            <span className="text-xs mt-0.5" style={{ color: "var(--gold-text)", fontFamily: "Cinzel, serif", fontSize: "0.65rem" }}>
              {modLabel(score)}
            </span>
          </div>
        ))}
      </div>

      {/* Skills / proficiencies */}
      {character.skills?.length > 0 && (
        <div className="mb-3">
          <div className="uppercase tracking-widest mb-1.5"
            style={{ fontFamily: "Cinzel, serif", color: "var(--parchment-dim)", fontSize: "0.5rem", letterSpacing: "0.2em" }}>
            Proficiencies
          </div>
          <div className="flex flex-wrap gap-1">
            {character.skills.map(s => (
              <span
                key={s}
                className="text-xs px-1.5 py-0.5"
                style={{
                  background: "var(--stone)",
                  border: "1px solid var(--blood)",
                  color: "var(--parchment-dim)",
                  fontFamily: "Cinzel, serif",
                  fontSize: "0.55rem",
                  letterSpacing: "0.05em",
                }}
              >
                {s}
              </span>
            ))}
          </div>
        </div>
      )}

      {/* Backstory */}
      {character.backstory && (
        <p
          className="text-xs italic leading-relaxed pt-2"
          style={{
            color: "var(--mist)",
            borderTop: "1px solid var(--border-dim)",
            fontFamily: "'IM Fell English', Georgia, serif",
            fontSize: "0.8rem",
          }}
        >
          {character.backstory}
        </p>
      )}
    </div>
  );
}
