// frontend/src/utils/api.js
const BASE = import.meta.env.VITE_API_URL || "http://localhost:8000";

async function get(path) {
  const res = await fetch(`${BASE}${path}`);
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

async function post(path, body) {
  const res = await fetch(`${BASE}${path}`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    body: JSON.stringify(body),
  });
  if (!res.ok) throw new Error(`API error ${res.status}: ${path}`);
  return res.json();
}

export const api = {
  getStatus:        () => get("/api/status"),
  getProbabilities: () => get("/api/pipeline/"),
  getPipelineMeta:  () => get("/api/pipeline/meta"),
  getGroups:        () => get("/api/groups/"),
  getBracket:       () => get("/api/bracket/"),
  getMatches:       () => get("/api/matches/"),
  postResult:       (data) => post("/api/result", data),
  getMatchProbabilities: () => get("/api/match-probabilities/"),

};