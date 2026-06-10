// frontend/src/components/ResultInput.jsx
import { useState } from "react";
import { api } from "../utils/api.js";

const ALL_TEAMS = [
  "Mexico","South Africa","South Korea","Czechia",
  "Canada","Bosnia and Herzegovina","Qatar","Switzerland",
  "Brazil","Morocco","Haiti","Scotland",
  "United States","Paraguay","Australia","Turkey",
  "Germany","Curaçao","Ivory Coast","Ecuador",
  "Netherlands","Japan","Sweden","Tunisia",
  "Belgium","Egypt","Iran","New Zealand",
  "Spain","Cape Verde","Saudi Arabia","Uruguay",
  "France","Senegal","Iraq","Norway",
  "Argentina","Algeria","Austria","Jordan",
  "Portugal","DR Congo","Uzbekistan","Colombia",
  "England","Croatia","Ghana","Panama",
].sort();

const STAGES = [
  "Group Stage","Round of 32","Round of 16",
  "Quarter-Final","Semi-Final","Final",
];

const inp = {
  background: "rgba(255,255,255,0.06)",
  border: "1px solid rgba(255,255,255,0.12)",
  borderRadius: "8px", color: "#fff",
  padding: "8px 12px", fontSize: "14px",
  outline: "none", width: "100%",
};

export function ResultInput({ onSuccess }) {
  const [form, setForm] = useState({
    home_team: "", away_team: "",
    home_score: "", away_score: "",
    stage: "Group Stage",
  });
  const [status, setStatus] = useState(null);
  const [loading, setLoading] = useState(false);

  const set = (k, v) => setForm(f => ({ ...f, [k]: v }));

  const submit = async () => {
    if (!form.home_team || !form.away_team || form.home_score === "" || form.away_score === "") {
      setStatus({ ok: false, msg: "Please fill all fields." });
      return;
    }
    if (form.home_team === form.away_team) {
      setStatus({ ok: false, msg: "Teams must be different." });
      return;
    }
    setLoading(true);
    try {
      await api.postResult({
        ...form,
        home_score: parseInt(form.home_score),
        away_score: parseInt(form.away_score),
      });
      setStatus({ ok: true, msg: "Result submitted. Re-simulating..." });
      setForm({ home_team: "", away_team: "", home_score: "", away_score: "", stage: "Group Stage" });
      onSuccess?.();
    } catch (e) {
      setStatus({ ok: false, msg: e.message });
    } finally {
      setLoading(false);
    }
  };

  return (
    <div className="result-input-container">
      <h3 style={{
        margin: "0 0 16px", fontFamily: "'Bebas Neue', sans-serif",
        letterSpacing: "2px", color: "#e8b84b", fontSize: "16px",
      }}>POST RESULT</h3>

      <div className="result-input-grid">
        <div>
          <label style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)", display: "block", marginBottom: "4px" }}>HOME</label>
          <select style={inp} value={form.home_team} onChange={e => set("home_team", e.target.value)}>
            <option value="">Select...</option>
            {ALL_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
        <div style={{ textAlign: "center" }} className="result-input-score-col">
          <label style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)", display: "block", marginBottom: "4px" }}>SCORE</label>
          <div style={{ display: "flex", gap: "4px" }}>
            <input type="number" min="0" max="20" style={{ ...inp, textAlign: "center", padding: "8px 4px" }}
              value={form.home_score} onChange={e => set("home_score", e.target.value)} />
            <input type="number" min="0" max="20" style={{ ...inp, textAlign: "center", padding: "8px 4px" }}
              value={form.away_score} onChange={e => set("away_score", e.target.value)} />
          </div>
        </div>
        <div>
          <label style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)", display: "block", marginBottom: "4px" }}>AWAY</label>
          <select style={inp} value={form.away_team} onChange={e => set("away_team", e.target.value)}>
            <option value="">Select...</option>
            {ALL_TEAMS.map(t => <option key={t} value={t}>{t}</option>)}
          </select>
        </div>
      </div>

      <div style={{ marginBottom: "12px" }}>
        <label style={{ fontSize: "11px", color: "rgba(255,255,255,0.4)", display: "block", marginBottom: "4px" }}>STAGE</label>
        <select style={inp} value={form.stage} onChange={e => set("stage", e.target.value)}>
          {STAGES.map(s => <option key={s} value={s}>{s}</option>)}
        </select>
      </div>

      <button onClick={submit} disabled={loading} style={{
        width: "100%", padding: "10px",
        background: loading ? "rgba(232,184,75,0.3)" : "#e8b84b",
        color: loading ? "rgba(255,255,255,0.5)" : "#1a1208",
        border: "none", borderRadius: "8px",
        fontFamily: "'Bebas Neue', sans-serif", letterSpacing: "2px",
        fontSize: "15px", cursor: loading ? "not-allowed" : "pointer",
        transition: "all 0.2s",
      }}>
        {loading ? "SUBMITTING..." : "SUBMIT RESULT"}
      </button>

      {status && (
        <p style={{
          margin: "10px 0 0", fontSize: "13px",
          color: status.ok ? "#4caf50" : "#f44336",
        }}>{status.msg}</p>
      )}
    </div>
  );
}