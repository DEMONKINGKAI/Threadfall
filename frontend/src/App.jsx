import React, { useState } from "react";
import GameView from "./components/GameView";
import { newGame } from "./api";
import dagMeta from "./dagMeta.json";

const API = "http://localhost:8000";

const DEFAULT_CHARACTER = {
  name: "Aldric",
  class: "Fighter",
  race: "Human",
  level: 3,
  stats: { strength: 16, dexterity: 12, constitution: 14, intelligence: 10, wisdom: 11, charisma: 13 },
  skills: ["Athletics", "Persuasion"],
  backstory: "A disgraced knight seeking redemption in the ruins of a broken realm.",
};

const CLASSES = ["Fighter","Rogue","Wizard","Cleric","Bard","Ranger","Paladin","Druid","Barbarian","Monk","Sorcerer","Warlock"];
const RACES   = ["Human","Elf","Dwarf","Halfling","Tiefling","Half-Orc","Gnome","Dragonborn"];

const inputStyle = {
  background: "var(--stone)",
  border: "1px solid var(--border-warm)",
  color: "var(--parchment)",
  fontFamily: "'Crimson Text', Georgia, serif",
  fontSize: "1rem",
  borderRadius: 0,
  padding: "0.55rem 0.75rem",
  width: "100%",
  outline: "none",
};

function Label({ children }) {
  return (
    <label
      className="block mb-1.5 uppercase tracking-[0.25em] text-xs"
      style={{ fontFamily: "Cinzel, serif", color: "var(--parchment-dim)", fontSize: "0.6rem" }}
    >
      {children}
    </label>
  );
}

function GInput({ value, onChange, ...props }) {
  return (
    <input
      value={value} onChange={onChange}
      style={inputStyle}
      onFocus={e => e.target.style.borderColor = "var(--gold-dim)"}
      onBlur={e => e.target.style.borderColor = "var(--border-warm)"}
      {...props}
    />
  );
}

function GSelect({ value, onChange, options }) {
  return (
    <select value={value} onChange={onChange} style={inputStyle}>
      {options.map(o => <option key={o}>{o}</option>)}
    </select>
  );
}

function SectionHead({ children }) {
  return (
    <div className="flex items-center gap-3 mb-3">
      <div style={{ height: 1, flex: 1, background: "var(--border-warm)" }} />
      <span className="text-xs uppercase tracking-[0.25em]"
        style={{ fontFamily: "Cinzel, serif", color: "var(--blood-bright)", fontSize: "0.6rem" }}>
        {children}
      </span>
      <div style={{ height: 1, flex: 1, background: "var(--border-warm)" }} />
    </div>
  );
}

function CharacterForm({ onStart }) {
  const [char, setChar] = useState(DEFAULT_CHARACTER);
  // Raw string values for each stat input, so intermediate typing doesn't reset to 10
  const [rawStats, setRawStats] = useState(
    () => Object.fromEntries(Object.entries(DEFAULT_CHARACTER.stats).map(([k, v]) => [k, String(v)]))
  );
  const [isLoading, setIsLoading] = useState(false);
  const [isRandomizing, setIsRandomizing] = useState(false);
  const [error, setError] = useState(null);

  function handleStatInput(stat, raw) {
    setRawStats(prev => ({ ...prev, [stat]: raw }));
    const parsed = parseInt(raw, 10);
    if (!isNaN(parsed) && parsed >= 1 && parsed <= 20) {
      setChar(c => ({ ...c, stats: { ...c.stats, [stat]: parsed } }));
    }
  }

  function handleStatBlur(stat) {
    // On blur: clamp whatever is in raw to valid range
    const parsed = parseInt(rawStats[stat], 10);
    const clamped = isNaN(parsed) ? 10 : Math.max(1, Math.min(20, parsed));
    setRawStats(prev => ({ ...prev, [stat]: String(clamped) }));
    setChar(c => ({ ...c, stats: { ...c.stats, [stat]: clamped } }));
  }

  async function handleRandomize() {
    setIsRandomizing(true); setError(null);
    try {
      const res = await fetch(`${API}/randomize_character`);
      if (!res.ok) throw new Error(await res.text());
      const data = await res.json();
      const newChar = {
        name: data.name,
        class: data.class,
        race: data.race,
        level: data.level,
        stats: data.stats,
        skills: data.skills || [],
        backstory: data.backstory,
      };
      setChar(newChar);
      setRawStats(Object.fromEntries(Object.entries(data.stats).map(([k, v]) => [k, String(v)])));
    } catch (e) {
      setError("The fates refused to speak. Try again.");
    } finally {
      setIsRandomizing(false);
    }
  }

  async function handleStart(e) {
    e.preventDefault();
    setIsLoading(true); setError(null);
    try {
      const result = await newGame(char, "long");
      onStart(result, char);
    } catch (err) {
      setError(err.message || "Could not reach the server.");
    } finally {
      setIsLoading(false);
    }
  }

  return (
    <div
      className="min-h-screen flex items-center justify-center p-8"
      style={{
        background: "var(--void)",
        backgroundImage: "radial-gradient(ellipse at 30% 40%, rgba(90,10,10,0.05) 0%, transparent 55%), radial-gradient(ellipse at 70% 70%, rgba(20,10,50,0.06) 0%, transparent 50%)",
      }}
    >
      <div className="w-full max-w-lg">

        {/* ── Title ── */}
        <div className="text-center mb-10">
          <p className="text-xs tracking-[0.5em] uppercase mb-4"
            style={{ fontFamily: "Cinzel, serif", color: "var(--parchment-dim)", fontSize: "0.6rem" }}>
            ✦ &nbsp; A Causal Narrative Chronicle &nbsp; ✦
          </p>
          <h1
            className="tracking-[0.35em] mb-4"
            style={{
              fontFamily: "'Cinzel Decorative', Cinzel, serif",
              fontSize: "clamp(2.5rem,6vw,3.8rem)",
              fontWeight: 700,
              color: "var(--gold-text)",
              textShadow: "0 0 60px rgba(196,144,48,0.18), 0 2px 4px rgba(0,0,0,0.8)",
              letterSpacing: "0.4em",
            }}
          >
            THREADFALL
          </h1>
          <div className="flex items-center justify-center gap-3 mb-4">
            <div style={{ height: 1, width: 80, background: "linear-gradient(to right, transparent, var(--blood-mid))" }} />
            <span className="text-xs tracking-[0.3em]"
              style={{ fontFamily: "Cinzel, serif", color: "var(--blood-bright)", fontSize: "0.6rem" }}>
              THE SHATTERED PACT
            </span>
            <div style={{ height: 1, width: 80, background: "linear-gradient(to left, transparent, var(--blood-mid))" }} />
          </div>
          <p className="text-sm italic leading-relaxed mx-auto" style={{ color: "var(--parchment-dim)", fontFamily: "'IM Fell English', Georgia, serif", maxWidth: 380 }}>
            An ancient pact between kingdoms shatters. One hero must navigate politics,
            war, and betrayal — or watch the realm burn.
          </p>
        </div>

        {/* ── Form ── */}
        <form
          onSubmit={handleStart}
          style={{
            background: "var(--ink-raised)",
            border: "1px solid var(--border-warm)",
            padding: "2rem 2rem",
            boxShadow: "0 0 0 1px var(--border-dim), inset 0 1px 0 rgba(255,255,255,0.02)",
          }}
        >
          {/* Identity header + randomizer */}
          <div className="flex items-center gap-3 mb-3">
            <div style={{ height: 1, flex: 1, background: "var(--border-warm)" }} />
            <span className="text-xs uppercase tracking-[0.25em]"
              style={{ fontFamily: "Cinzel, serif", color: "var(--blood-bright)", fontSize: "0.6rem" }}>
              Identity
            </span>
            <div style={{ height: 1, flex: 1, background: "var(--border-warm)" }} />
            <button
              type="button"
              onClick={handleRandomize}
              disabled={isRandomizing}
              title="Summon a hero from the void"
              style={{
                background: "var(--stone)",
                border: "1px solid var(--border-warm)",
                color: isRandomizing ? "var(--mist)" : "var(--gold-dim)",
                fontFamily: "Cinzel, serif",
                fontSize: "0.6rem",
                letterSpacing: "0.2em",
                padding: "0.3rem 0.7rem",
                borderRadius: 0,
                cursor: isRandomizing ? "not-allowed" : "pointer",
                textTransform: "uppercase",
                whiteSpace: "nowrap",
                transition: "border-color 0.15s, color 0.15s",
              }}
              onMouseEnter={e => !e.currentTarget.disabled && (e.currentTarget.style.borderColor = "var(--gold-dim)")}
              onMouseLeave={e => e.currentTarget.style.borderColor = "var(--border-warm)"}
            >
              {isRandomizing ? "✦ Consulting…" : "⚄ Randomize"}
            </button>
          </div>

          <div className="grid grid-cols-2 gap-4 mb-5">
            <div><Label>Name</Label><GInput value={char.name} onChange={e => setChar(c => ({...c, name: e.target.value}))} /></div>
            <div><Label>Class</Label><GSelect value={char.class} onChange={e => setChar(c => ({...c, class: e.target.value}))} options={CLASSES} /></div>
            <div><Label>Race</Label><GSelect value={char.race} onChange={e => setChar(c => ({...c, race: e.target.value}))} options={RACES} /></div>
            <div>
              <Label>Level</Label>
              <GInput type="number" min={1} max={20} value={char.level} onChange={e => setChar(c => ({...c, level: parseInt(e.target.value)||1}))} />
            </div>
          </div>

          <SectionHead>Ability Scores</SectionHead>
          <div className="grid grid-cols-6 gap-2 mb-5">
            {Object.entries(char.stats).map(([stat, score]) => {
              const rawVal = rawStats[stat] ?? String(score);
              const parsed = parseInt(rawVal, 10);
              const validScore = !isNaN(parsed) && parsed >= 1 && parsed <= 20 ? parsed : score;
              const m = Math.floor((validScore - 10) / 2);
              const modStr = m >= 0 ? `+${m}` : String(m);
              return (
                <div key={stat} className="flex flex-col items-center gap-1">
                  <span className="uppercase text-xs" style={{ fontFamily: "Cinzel, serif", color: "var(--parchment-dim)", fontSize: "0.55rem", letterSpacing: "0.1em" }}>
                    {stat.slice(0,3)}
                  </span>
                  <input
                    type="number" min={1} max={20}
                    value={rawVal}
                    onChange={e => handleStatInput(stat, e.target.value)}
                    onBlur={() => handleStatBlur(stat)}
                    className="text-center text-sm font-bold"
                    style={{ ...inputStyle, padding: "0.4rem 0.25rem" }}
                    onFocus={e => e.target.style.borderColor = "var(--gold-dim)"}
                  />
                  <span
                    className="text-xs font-bold"
                    style={{
                      color: m > 0 ? "var(--gold-text)" : m < 0 ? "var(--failure-text)" : "var(--parchment-mid)",
                      fontFamily: "Cinzel, serif",
                      fontSize: "0.7rem",
                      minWidth: "2rem",
                      textAlign: "center",
                      transition: "color 0.15s",
                    }}
                  >
                    {modStr}
                  </span>
                </div>
              );
            })}
          </div>

          <SectionHead>Backstory</SectionHead>
          <div className="mb-6">
            <textarea
              value={char.backstory}
              onChange={e => setChar(c => ({...c, backstory: e.target.value}))}
              rows={3}
              style={{
                ...inputStyle,
                resize: "none",
                fontFamily: "'IM Fell English', Georgia, serif",
                fontSize: "0.95rem",
                lineHeight: 1.6,
              }}
              onFocus={e => e.target.style.borderColor = "var(--gold-dim)"}
              onBlur={e => e.target.style.borderColor = "var(--border-warm)"}
            />
          </div>

          {error && (
            <p className="text-xs italic mb-4 text-center" style={{ color: "var(--failure-text)" }}>{error}</p>
          )}

          <button
            type="submit"
            disabled={isLoading}
            className="w-full py-3 uppercase tracking-[0.3em] text-sm transition-all disabled:opacity-40"
            style={{
              fontFamily: "Cinzel, serif",
              background: "var(--blood-mid)",
              color: "var(--parchment)",
              border: "1px solid var(--border-bright)",
              borderRadius: 0,
              cursor: isLoading ? "not-allowed" : "pointer",
              letterSpacing: "0.3em",
            }}
            onMouseEnter={e => !e.currentTarget.disabled && (e.currentTarget.style.background = "var(--blood-bright)")}
            onMouseLeave={e => e.currentTarget.style.background = "var(--blood-mid)"}
          >
            {isLoading ? "✦  The realm stirs…  ✦" : "✦  Begin the Chronicle  ✦"}
          </button>
        </form>

        <p className="text-center mt-5 uppercase tracking-[0.25em]"
          style={{ fontFamily: "Cinzel, serif", color: "var(--mist)", fontSize: "0.5rem" }}>
          Outcomes governed by Pearl's Causal Hierarchy &nbsp;·&nbsp; LLM narrates only
        </p>
      </div>
    </div>
  );
}

export default function App() {
  const [gameState, setGameState] = useState(null);

  function handleStart(result, character) {
    setGameState({
      sessionId: result.session_id,
      character,
      worldState: result.world_state,
      beliefs: result.beliefs,
      currentAct: result.current_act,
      totalActs: result.total_acts,
      sceneText: result.scene_text,
      gameOver: false,
      finalOutcome: null,
    });
  }

  function handleStateUpdate(result) {
    setGameState(prev => ({
      ...prev,
      worldState: result.world_state,
      beliefs: result.beliefs,
      currentAct: result.current_act,
      sceneText: result.scene_text,
      gameOver: result.game_over,
      finalOutcome: result.final_outcome,
    }));
  }

  function handleRestart() {
    setGameState(null);
  }

  if (!gameState) return <CharacterForm onStart={handleStart} />;
  return <GameView gameState={gameState} onStateUpdate={handleStateUpdate} dagMeta={dagMeta} onRestart={handleRestart} />;
}
