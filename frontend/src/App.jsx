// frontend/src/App.jsx
import { useState, useCallback } from "react";
import { Analytics } from "@vercel/analytics/react";
import { SpeedInsights } from "@vercel/speed-insights/react";
import { Odds } from "./pages/Odds.jsx";
import { Groups } from "./pages/Groups.jsx";
import { Matches } from "./pages/Matches.jsx";
import { Bracket } from "./pages/Bracket.jsx";
import { usePolling } from "./hooks/usePolling.js";
import { api } from "./utils/api.js";

const NAV = [
  { id: "odds",    label: "🏆 Odds" },
  { id: "matches", label: "📅 Matches" },
  { id: "groups",  label: "⚽ Groups" },
  { id: "bracket", label: "🗓 Bracket" },
];

export default function App() {
  const [page, setPage] = useState("odds");
  const statusFetcher = useCallback(() => api.getStatus(), []);
  const { data: status } = usePolling(statusFetcher, 10_000);

  const getPageTitle = () => {
    switch (page) {
      case "odds": return "CHAMPIONSHIP ODDS";
      case "matches": return "MATCHES & FORECASTS";
      case "groups": return "STANDINGS & GROUPS";
      case "bracket": return "KNOCKOUT BRACKET";
      default: return "WORLD CUP FORECAST";
    }
  };

  const getPageSubtitle = () => {
    switch (page) {
      case "odds": return "Monte Carlo simulation · 10,000 runs · updates after every result";
      case "groups": return "Live standings · simulated team progression probabilities";
      case "matches": return "Match predictions · Live and upcoming fixture probabilities";
      case "bracket": return "Simulated knockout tree progression and match outcomes";
      default: return "";
    }
  };

  return (
    <div style={{ minHeight: "100vh" }}>
      {/* Header */}
      <header className="app-header">
        <div className="header-left">
          <div className="logo-text">
            WC 2026 FORECAST
          </div>

          <nav className="app-nav">
            {NAV.map(n => (
              <button
                key={n.id}
                onClick={() => setPage(n.id)}
                className={`nav-button ${page === n.id ? 'active' : ''}`}
              >
                {n.label}
              </button>
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
      <div className="page-header-container">
        <h1 className="page-title">
          {getPageTitle()}
        </h1>
        <p className="page-subtitle">
          {getPageSubtitle()}
        </p>
      </div>

      {/* Content */}
      <main className="app-main">
        {page === "odds"   && <Odds />}
        {page === "groups" && <Groups />}
        {page === "matches" && <Matches />}
        {page === "bracket" && <Bracket />}
      </main>

      {/* Footer */}
      <footer className="app-footer">
        <span>WC 2026 Forecast · LightGBM + Monte Carlo</span>
        <span>Probabilities update after each match result</span>
      </footer>

      <Analytics />
      <SpeedInsights />
    </div>
  );
}