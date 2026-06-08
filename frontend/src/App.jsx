// frontend/src/App.jsx
import { useState, useCallback } from "react";
import { Odds } from "./pages/Odds.jsx";
import { Groups } from "./pages/Groups.jsx";
import { usePolling } from "./hooks/usePolling.js";
import { api } from "./utils/api.js";

const NAV = [
  { id: "odds",    label: "🏆 Odds" },
  { id: "groups",  label: "⚽ Groups",  hideAfter: "2026-06-28" },
  { id: "bracket", label: "🗓 Bracket", showAfter: "2026-06-28" },
];

export default function App() {
  const [page, setPage] = useState("odds");
  const statusFetcher = useCallback(() => api.getStatus(), []);
  const { data: status } = usePolling(statusFetcher, 10_000);

  return (
    <div style={{
      minHeight: "100vh",
      background: "#0d1117",
      color: "#fff",
      fontFamily: "'DM Sans', sans-serif",
    }}>
      {/* Header */}
      <header style={{
        borderBottom: "1px solid rgba(255,255,255,0.07)",
        padding: "0 24px",
        display: "flex", alignItems: "center",
        justifyContent: "space-between",
        height: "60px",
        position: "sticky", top: 0,
        background: "rgba(13,17,23,0.95)",
        backdropFilter: "blur(12px)",
        zIndex: 100,
      }}>
        <div style={{ display: "flex", alignItems: "center", gap: "16px" }}>
          <div style={{
            fontFamily: "'Bebas Neue', sans-serif",
            fontSize: "22px", letterSpacing: "3px",
            color: "#e8b84b",
          }}>
            WC 2026 FORECAST
          </div>

          <nav style={{ display: "flex", gap: "4px" }}>
            {NAV.map(n => (
              <button key={n.id} onClick={() => setPage(n.id)} style={{
                background: page === n.id ? "rgba(232,184,75,0.15)" : "transparent",
                border: page === n.id ? "1px solid rgba(232,184,75,0.3)" : "1px solid transparent",
                borderRadius: "6px", padding: "6px 14px",
                color: page === n.id ? "#e8b84b" : "rgba(255,255,255,0.5)",
                fontSize: "13px", cursor: "pointer",
                transition: "all 0.15s",
              }}>{n.label}</button>
            ))}
          </nav>
        </div>

        {/* Status indicator */}
        <div style={{ display: "flex", alignItems: "center", gap: "8px", fontSize: "12px" }}>
          <div style={{
            width: "6px", height: "6px", borderRadius: "50%",
            background: status?.is_running ? "#e8b84b"
              : status?.results_available ? "#4caf50" : "#666",
            boxShadow: status?.is_running ? "0 0 6px #e8b84b" : "none",
          }} />
          <span style={{ color: "rgba(255,255,255,0.4)" }}>
            {status?.is_running ? "Simulating..."
              : status?.results_available ? `${(status.simulations / 1000).toFixed(0)}k sims`
              : "Loading"}
          </span>
        </div>
      </header>

      {/* Page title */}
      <div style={{
        padding: "28px 24px 12px",
        borderBottom: "1px solid rgba(255,255,255,0.04)",
      }}>
        <h1 style={{
          margin: 0,
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: "32px", letterSpacing: "3px",
          color: "#fff",
        }}>
          {page === "odds" ? "CHAMPIONSHIP ODDS" : "GROUP STAGE"}
        </h1>
        <p style={{ margin: "4px 0 0", fontSize: "13px", color: "rgba(255,255,255,0.35)" }}>
          {page === "odds"
            ? "Monte Carlo simulation · 10,000 runs · updates after every result"
            : "Live standings · submit results to update probabilities"}
        </p>
      </div>

      {/* Content */}
      <main style={{ padding: "24px" }}>
        {page === "odds"   && <Odds />}
        {page === "groups" && <Groups />}
      </main>

      {/* Footer */}
      <footer style={{
        borderTop: "1px solid rgba(255,255,255,0.05)",
        padding: "16px 24px",
        fontSize: "11px", color: "rgba(255,255,255,0.2)",
        display: "flex", justifyContent: "space-between",
      }}>
        <span>WC 2026 Forecast · LightGBM + Monte Carlo</span>
        <span>Probabilities update after each match result</span>
      </footer>
    </div>
  );
}