/**
 * LoadScreen — video-game "Load Chronicle" screen.
 *
 * Shows all saved sessions from the vector store. Each card displays:
 *   character name / class / level, campaign name, start date,
 *   status badge (IN PROGRESS or outcome label), and action buttons
 *   (Resume, Delete).
 *
 * Props:
 *   onResume(sessionId)  — called when the user clicks Resume
 *   onBack()             — return to character creation
 */

import { useEffect, useState } from "react";
import { listSessions, deleteSession } from "../api";

const OUTCOME_LABEL = {
  story_victory: { text: "VICTORY",      color: "var(--gold-text)" },
  story_failure: { text: "RUIN",         color: "var(--failure-text, #b04040)" },
  story_neutral: { text: "BALANCE HELD", color: "var(--parchment-mid)" },
};

function fmt(iso) {
  if (!iso) return "";
  const d = new Date(iso);
  return d.toLocaleDateString(undefined, { month: "short", day: "numeric", year: "numeric" });
}

export default function LoadScreen({ onResume, onBack }) {
  const [sessions, setSessions]     = useState(null);   // null = loading
  const [error, setError]           = useState(null);
  const [deleting, setDeleting]     = useState(null);   // session_id being deleted
  const [resuming, setResuming]     = useState(null);   // session_id being resumed

  useEffect(() => {
    listSessions()
      .then(setSessions)
      .catch(e => setError(e.message));
  }, []);

  async function handleDelete(sid) {
    if (!confirm("Delete this chronicle? This cannot be undone.")) return;
    setDeleting(sid);
    try {
      await deleteSession(sid);
      setSessions(prev => prev.filter(s => s.session_id !== sid));
    } catch (e) {
      alert("Failed to delete: " + e.message);
    } finally {
      setDeleting(null);
    }
  }

  async function handleResume(sid) {
    setResuming(sid);
    try {
      await onResume(sid);
    } finally {
      setResuming(null);
    }
  }

  return (
    <div style={{
      minHeight: "100vh",
      background: "var(--void)",
      display: "flex",
      flexDirection: "column",
      alignItems: "center",
      padding: "3rem 1rem 4rem",
      fontFamily: "'Crimson Text', serif",
    }}>
      {/* Header */}
      <div style={{ textAlign: "center", marginBottom: "2.5rem" }}>
        <h1 style={{
          fontFamily: "'Cinzel Decorative', serif",
          fontSize: "1.6rem",
          color: "var(--gold-text)",
          letterSpacing: "0.12em",
          paddingLeft: "0.12em",
          margin: 0,
        }}>
          ✦ Saved Chronicles ✦
        </h1>
        <p style={{ color: "var(--mist)", fontSize: "1rem", marginTop: "0.5rem" }}>
          Resume a previous session or begin anew
        </p>
      </div>

      {/* Loading / error states */}
      {sessions === null && !error && (
        <p style={{ color: "var(--mist)", fontStyle: "italic" }}>
          Consulting the archives…
        </p>
      )}
      {error && (
        <p style={{ color: "var(--failure-text, #b04040)" }}>
          Failed to load sessions: {error}
        </p>
      )}

      {/* Empty state */}
      {sessions !== null && sessions.length === 0 && (
        <p style={{ color: "var(--mist)", fontStyle: "italic", marginTop: "2rem" }}>
          No chronicles found. Begin a new game to start your legend.
        </p>
      )}

      {/* Session cards */}
      {sessions && sessions.length > 0 && (
        <div style={{
          width: "100%",
          maxWidth: "680px",
          display: "flex",
          flexDirection: "column",
          gap: "1rem",
        }}>
          {sessions.map(s => {
            const outcome = OUTCOME_LABEL[s.final_outcome];
            const isDeleting = deleting === s.session_id;
            const isResuming = resuming === s.session_id;

            return (
              <div key={s.session_id} style={{
                border: "1px solid var(--border-warm)",
                background: "var(--ink-raised)",
                padding: "1.25rem 1.5rem",
                position: "relative",
              }}>
                {/* Top row: character + status */}
                <div style={{ display: "flex", justifyContent: "space-between", alignItems: "flex-start" }}>
                  <div>
                    <span style={{
                      fontFamily: "'Cinzel', serif",
                      fontSize: "1.05rem",
                      color: "var(--parchment-mid)",
                      letterSpacing: "0.05em",
                    }}>
                      {s.character_name}
                    </span>
                    <span style={{ color: "var(--mist)", fontSize: "0.85rem", marginLeft: "0.6rem" }}>
                      {s.character_class} · Lvl {s.character_level}
                    </span>
                  </div>
                  <span style={{
                    fontSize: "0.72rem",
                    fontFamily: "'Cinzel', serif",
                    letterSpacing: "0.1em",
                    color: outcome ? outcome.color : "var(--mist)",
                    border: `1px solid ${outcome ? outcome.color : "var(--border-warm)"}`,
                    padding: "0.2rem 0.55rem",
                  }}>
                    {outcome ? outcome.text : "IN PROGRESS"}
                  </span>
                </div>

                {/* Campaign + date */}
                <div style={{ marginTop: "0.5rem", display: "flex", gap: "1.2rem" }}>
                  <span style={{ color: "var(--gold-dim)", fontSize: "0.9rem" }}>
                    {s.campaign_name}
                  </span>
                  <span style={{ color: "var(--mist)", fontSize: "0.85rem" }}>
                    Started {fmt(s.created_at)}
                  </span>
                </div>

                {/* Action buttons */}
                <div style={{ marginTop: "1rem", display: "flex", gap: "0.75rem" }}>
                  <button
                    onClick={() => handleResume(s.session_id)}
                    disabled={!!resuming || !!deleting}
                    style={{
                      background: "var(--blood-mid, #4a0f0f)",
                      color: "var(--gold-text)",
                      border: "1px solid var(--border-gold)",
                      padding: "0.45rem 1.1rem",
                      fontFamily: "'Cinzel', serif",
                      fontSize: "0.78rem",
                      letterSpacing: "0.08em",
                      cursor: resuming === s.session_id ? "wait" : "pointer",
                      opacity: resuming && resuming !== s.session_id ? 0.5 : 1,
                    }}
                  >
                    {isResuming ? "Restoring…" : "▶ Resume"}
                  </button>
                  <button
                    onClick={() => handleDelete(s.session_id)}
                    disabled={!!resuming || !!deleting}
                    style={{
                      background: "transparent",
                      color: "var(--mist)",
                      border: "1px solid var(--border-warm)",
                      padding: "0.45rem 0.9rem",
                      fontFamily: "'Cinzel', serif",
                      fontSize: "0.78rem",
                      letterSpacing: "0.08em",
                      cursor: isDeleting ? "wait" : "pointer",
                      opacity: isDeleting ? 0.5 : 1,
                    }}
                  >
                    {isDeleting ? "Deleting…" : "✕ Delete"}
                  </button>
                </div>
              </div>
            );
          })}
        </div>
      )}

      {/* Back button */}
      <button
        onClick={onBack}
        style={{
          marginTop: "2.5rem",
          background: "transparent",
          color: "var(--mist)",
          border: "1px solid var(--border-warm)",
          padding: "0.5rem 1.4rem",
          fontFamily: "'Cinzel', serif",
          fontSize: "0.78rem",
          letterSpacing: "0.1em",
          cursor: "pointer",
        }}
      >
        ← New Chronicle
      </button>
    </div>
  );
}
