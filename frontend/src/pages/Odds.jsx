// frontend/src/pages/Odds.jsx
import { useCallback } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../utils/api.js";
import { ProbabilityBar } from "../components/ProbabilityBar.jsx";
import { TeamFlag } from "../components/TeamFlag.jsx";

const ROUNDS = [
  { key: "round_of_32",   label: "R32" },
  { key: "round_of_16",   label: "R16" },
  { key: "quarter_final", label: "QF" },
  { key: "semi_final",    label: "SF" },
  { key: "final",         label: "Final" },
  { key: "champion",      label: "🏆" },
];

const medalColor = (i) => {
  if (i === 0) return "#FFD700";
  if (i === 1) return "#C0C0C0";
  if (i === 2) return "#CD7F32";
  return "rgba(255,255,255,0.3)";
};

export function Odds() {
  const fetcher = useCallback(() => api.getProbabilities(), []);
  const { data, loading, error, lastUpdated } = usePolling(fetcher, 60_000);

  if (loading) return <LoadingState />;
  if (error)   return <ErrorState msg={error} />;

  const top5  = data.slice(0, 5);
  const rest  = data.slice(5);

  return (
    <div>
      {/* Hero — top 5 */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(160px, 1fr))",
        gap: "12px", marginBottom: "32px",
      }}>
        {top5.map((t, i) => (
          <div key={t.team} style={{
            background: "rgba(255,255,255,0.04)",
            border: `1px solid ${i === 0 ? "rgba(255,215,0,0.3)" : "rgba(255,255,255,0.08)"}`,
            borderRadius: "12px", padding: "16px",
            position: "relative", overflow: "hidden",
          }}>
            {i === 0 && (
              <div style={{
                position: "absolute", top: 0, left: 0, right: 0, height: "2px",
                background: "linear-gradient(90deg, #FFD700, #e8b84b)",
              }} />
            )}
            <div style={{ fontSize: "28px", marginBottom: "4px" }}>
              <TeamFlag team={t.team} size={28} />
            </div>
            <div style={{
              fontSize: "13px", fontWeight: 600, color: "#fff",
              marginBottom: "4px", lineHeight: 1.2,
            }}>{t.team}</div>
            <div style={{
              fontFamily: "'Bebas Neue', sans-serif",
              fontSize: "28px", color: medalColor(i), letterSpacing: "1px",
            }}>{t.champion.toFixed(1)}%</div>
            <div style={{ fontSize: "10px", color: "rgba(255,255,255,0.35)" }}>
              champion probability
            </div>
          </div>
        ))}
      </div>

      {/* Full table */}
      <div style={{
        background: "rgba(255,255,255,0.03)",
        border: "1px solid rgba(255,255,255,0.07)",
        borderRadius: "12px", overflow: "hidden",
      }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: "28px 1fr 60px repeat(5, 80px) 100px",
          padding: "8px 16px",
          borderBottom: "1px solid rgba(255,255,255,0.07)",
          fontSize: "11px", color: "rgba(255,255,255,0.35)",
          letterSpacing: "0.5px",
        }}>
          <span>#</span>
          <span>Team</span>
          <span style={{ textAlign: "center" }}>Elo</span>
          {ROUNDS.slice(0, -1).map(r => (
            <span key={r.key} style={{ textAlign: "center" }}>{r.label}</span>
          ))}
          <span style={{ textAlign: "center" }}>🏆 Champion</span>
        </div>

        {data.map((t, i) => (
          <div key={t.team} style={{
            display: "grid",
            gridTemplateColumns: "28px 1fr 60px repeat(5, 80px) 100px",
            padding: "10px 16px",
            borderBottom: i < data.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
            alignItems: "center",
            background: i < 3 ? "rgba(232,184,75,0.03)" : "transparent",
          }}>
            <span style={{ fontSize: "12px", color: medalColor(i), fontWeight: 600 }}>
              {i + 1}
            </span>
            <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
              <TeamFlag team={t.team} size={16} />
              <div>
                <div style={{ fontSize: "13px", color: "#fff" }}>{t.team}</div>
                <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)" }}>
                  Group {t.group}
                </div>
              </div>
            </div>
            <span style={{
              textAlign: "center", fontSize: "12px",
              color: "rgba(255,255,255,0.4)", fontVariantNumeric: "tabular-nums",
            }}>{Math.round(t.elo)}</span>
            {ROUNDS.slice(0, -1).map(r => (
              <span key={r.key} style={{
                textAlign: "center", fontSize: "12px",
                color: "rgba(255,255,255,0.6)",
                fontVariantNumeric: "tabular-nums",
              }}>{t[r.key].toFixed(1)}%</span>
            ))}
            <div style={{ padding: "0 8px" }}>
              <ProbabilityBar value={t.champion} max={data[0].champion} color="#e8b84b" />
            </div>
          </div>
        ))}
      </div>

      {lastUpdated && (
        <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.25)", marginTop: "12px", textAlign: "right" }}>
          Last updated: {lastUpdated.toLocaleTimeString()} · auto-refresh 60s
        </p>
      )}
    </div>
  );
}

function LoadingState() {
  return (
    <div style={{ textAlign: "center", padding: "80px 0", color: "rgba(255,255,255,0.3)" }}>
      <div style={{ fontSize: "32px", marginBottom: "12px" }}>⚽</div>
      <div>Running simulations...</div>
    </div>
  );
}

function ErrorState({ msg }) {
  return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "#f44336" }}>
      <div style={{ marginBottom: "8px" }}>Failed to load data</div>
      <div style={{ fontSize: "12px", opacity: 0.6 }}>{msg}</div>
    </div>
  );
}