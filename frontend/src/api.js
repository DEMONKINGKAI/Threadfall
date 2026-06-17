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
