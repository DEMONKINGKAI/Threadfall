const BASE = "";

export async function newGame(character, campaign = "long", seed = null) {
  const res = await fetch(`${BASE}/new_game`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ character, campaign, seed }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

export async function takeAction(sessionId, playerInput) {
  const res = await fetch(`${BASE}/action`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ session_id: sessionId, player_input: playerInput }),
  });
  if (!res.ok) throw new Error(await res.text());
  return res.json();
}

/**
 * Stream a player action via SSE.
 *
 * Callbacks:
 *   onEngine(data)  — fires once with engine result (outcome, world_state, etc.)
 *   onToken(text)   — fires per streamed LLM token
 *   onDone(data)    — fires once with { narrative, scene_text, game_over, final_outcome }
 *   onError(msg)    — fires on network or parse error
 */
export async function streamAction(sessionId, playerInput, { onEngine, onToken, onDone, onError }) {
  let res;
  try {
    res = await fetch(`${BASE}/stream_action`, {
      method: "POST",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ session_id: sessionId, player_input: playerInput }),
    });
  } catch (e) {
    onError(e.message);
    return;
  }

  if (!res.ok) {
    onError(await res.text());
    return;
  }

  const reader  = res.body.getReader();
  const decoder = new TextDecoder();
  let buffer    = "";

  try {
    while (true) {
      const { done, value } = await reader.read();
      if (done) break;

      buffer += decoder.decode(value, { stream: true });

      // SSE events are separated by "\n\n"
      const parts = buffer.split("\n\n");
      buffer = parts.pop(); // keep trailing incomplete chunk

      for (const part of parts) {
        const line = part.trim();
        if (!line.startsWith("data: ")) continue;
        try {
          const data = JSON.parse(line.slice(6));
          if      (data.type === "engine") onEngine(data);
          else if (data.type === "token")  onToken(data.text);
          else if (data.type === "done")   onDone(data);
        } catch {
          // ignore malformed chunk
        }
      }
    }
  } catch (e) {
    onError(e.message);
  }
}

export async function listSessions() {
  const res = await fetch(`${BASE}/sessions`);
  if (!res.ok) throw new Error(await res.text());
  return res.json(); // SessionSummary[]
}

export async function resumeSession(sessionId) {
  const res = await fetch(`${BASE}/resume_session/${sessionId}`, { method: "POST" });
  if (!res.ok) throw new Error(await res.text());
  return res.json(); // ResumeResponse
}

export async function deleteSession(sessionId) {
  await fetch(`${BASE}/session/${sessionId}`, { method: "DELETE" });
}
