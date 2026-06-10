// frontend/src/pages/Matches.jsx
import { useState, useCallback } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../utils/api.js";
import { TeamFlag } from "../components/TeamFlag.jsx";

// ── Helpers ───────────────────────────────────────────────────────────────────

function pct(v) {
  if (v === null || v === undefined || Number.isNaN(v)) return "–";
  return `${Number(v).toFixed(1)}%`;
}

const STAGES = [
  "All",
  "Group Stage",
  "Round of 32",
  "Round of 16",
  "Quarter-Final",
  "Semi-Final",
  "Final",
];

// ── Match card ────────────────────────────────────────────────────────────────

function MatchCard({ match }) {
  const isKnockout = match.stage !== "Group Stage";
  const home       = match.team1;
  const away       = match.team2;
  const hasProbs   = match.p_home_win !== null;
  const isFinished = match.status === "FINISHED";

  return (
    <div style={{
      background: "rgba(255,255,255,0.04)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: "12px",
      padding: "14px 16px",
    }}>
      {/* Header */}
      <div style={{
        display: "flex", justifyContent: "space-between",
        alignItems: "center", marginBottom: "12px",
      }}>
        <div>
          <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.35)" }}>
            {match.stage}
          </span>
          <span style={{
            fontSize: "11px", color: "rgba(255,255,255,0.2)",
            marginLeft: "8px",
          }}>
            {match.date} · {match.time} UTC
          </span>
        </div>
        <div style={{ display: "flex", gap: "6px", alignItems: "center" }}>
          {match.group && (
            <span style={{
              fontSize: "11px", color: "#e8b84b",
              border: "1px solid rgba(232,184,75,0.25)",
              padding: "2px 8px", borderRadius: "999px",
            }}>
              Group {match.group}
            </span>
          )}
          {isFinished && (
            <span style={{
              fontSize: "11px", color: "#4caf50",
              border: "1px solid rgba(76,175,80,0.3)",
              padding: "2px 8px", borderRadius: "999px",
            }}>
              FT
            </span>
          )}
          {match.status === "IN_PLAY" && (
            <span style={{
              fontSize: "11px", color: "#ff9800",
              border: "1px solid rgba(255,152,0,0.3)",
              padding: "2px 8px", borderRadius: "999px",
            }}>
              🔴 LIVE
            </span>
          )}
        </div>
      </div>

      {/* Teams + probabilities */}
      {home === "TBD" ? (
        <div style={{ color: "rgba(255,255,255,0.3)", fontSize: "13px", textAlign: "center", padding: "8px 0" }}>
          Teams TBD
        </div>
      ) : (
        <div style={{ display: "grid", gap: "8px" }}>
          <TeamRow
            team={home}
            prob={match.p_home_win}
            championProb={match.home_champion}
            label={isKnockout ? "Advance" : "Win"}
            isWinner={isFinished && match.winner === home}
            isLoser={isFinished && match.winner && match.winner !== home}
          />
          {!isKnockout && (
            <DrawRow prob={match.p_draw} />
          )}
          <TeamRow
            team={away}
            prob={match.p_away_win}
            championProb={match.away_champion}
            label={isKnockout ? "Advance" : "Win"}
            isWinner={isFinished && match.winner === away}
            isLoser={isFinished && match.winner && match.winner !== away}
          />
        </div>
      )}

      {!hasProbs && home !== "TBD" && (
        <div style={{ fontSize: "11px", color: "rgba(255,255,255,0.2)", marginTop: "8px" }}>
          Prediction unavailable
        </div>
      )}
    </div>
  );
}

function TeamRow({ team, prob, championProb, label, isWinner, isLoser }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "1fr auto auto",
      gap: "12px", alignItems: "center",
      opacity: isLoser ? 0.4 : 1,
    }}>
      <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
        <TeamFlag team={team} size={18} />
        <span style={{
          fontSize: "13px", color: "#fff",
          fontWeight: isWinner ? 600 : 400,
        }}>
          {team}
        </span>
        {isWinner && (
          <span style={{ fontSize: "11px", color: "#4caf50" }}>✓</span>
        )}
      </div>
      {championProb !== null && championProb !== undefined && (
        <span style={{ fontSize: "11px", color: "rgba(255,255,255,0.3)" }}>
          🏆 {pct(championProb)}
        </span>
      )}
      <span style={{
        fontSize: "13px", color: "#e8b84b",
        fontVariantNumeric: "tabular-nums",
        minWidth: "44px", textAlign: "right",
      }}>
        {pct(prob)}
      </span>
    </div>
  );
}

function DrawRow({ prob }) {
  return (
    <div style={{
      display: "grid",
      gridTemplateColumns: "1fr auto",
      gap: "12px", alignItems: "center",
      opacity: 0.6,
    }}>
      <span style={{ fontSize: "12px", color: "rgba(255,255,255,0.4)", paddingLeft: "26px" }}>
        Draw
      </span>
      <span style={{
        fontSize: "13px", color: "#e8b84b",
        fontVariantNumeric: "tabular-nums",
        minWidth: "44px", textAlign: "right",
      }}>
        {pct(prob)}
      </span>
    </div>
  );
}

// ── Filter bar ────────────────────────────────────────────────────────────────

function FilterBar({ active, onChange }) {
  return (
    <div className="matches-filter-bar">
      {STAGES.map(s => (
        <button key={s} onClick={() => onChange(s)} className={`matches-filter-button ${active === s ? "active" : ""}`}>
          {s}
        </button>
      ))}
    </div>
  );
}

// ── Date group header ─────────────────────────────────────────────────────────

function DateHeader({ date }) {
  const d    = new Date(date + "T00:00:00Z");
  const today = new Date().toISOString().slice(0, 10);
  const label = date === today ? "Today" : d.toLocaleDateString("en-GB", {
    weekday: "short", day: "numeric", month: "short", timeZone: "UTC",
  });
  return (
    <div style={{
      fontSize: "12px", color: "rgba(255,255,255,0.35)",
      letterSpacing: "1px", textTransform: "uppercase",
      padding: "16px 0 8px",
      borderBottom: "1px solid rgba(255,255,255,0.06)",
      marginBottom: "12px",
    }}>
      {label}
    </div>
  );
}

// ── Main page ─────────────────────────────────────────────────────────────────

export function Matches() {
  const [stageFilter, setStageFilter] = useState("All");

  const fetcher = useCallback(() => api.getMatchProbabilities(), []);
  const { data, loading, error, lastUpdated } = usePolling(fetcher, 60_000);

  if (loading) return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "rgba(255,255,255,0.3)" }}>
      <div style={{ fontSize: "32px", marginBottom: "12px" }}>⚽</div>
      <div>Loading matches...</div>
    </div>
  );

  if (error) return (
    <div style={{ textAlign: "center", padding: "40px", color: "#f44336" }}>
      <div>Failed to load matches</div>
      <div style={{ fontSize: "12px", opacity: 0.6, marginTop: "4px" }}>{error}</div>
    </div>
  );

  // Filter by stage
  const filtered = stageFilter === "All"
    ? data
    : data.filter(m => m.stage === stageFilter);

  // Group by date
  const byDate = filtered.reduce((acc, m) => {
    if (!acc[m.date]) acc[m.date] = [];
    acc[m.date].push(m);
    return acc;
  }, {});

  const sortedDates = Object.keys(byDate).sort();

  return (
    <div>
      <FilterBar active={stageFilter} onChange={setStageFilter} />

      {sortedDates.length === 0 && (
        <div style={{ textAlign: "center", padding: "40px", color: "rgba(255,255,255,0.3)" }}>
          No matches found
        </div>
      )}

      {sortedDates.map(date => (
        <div key={date}>
          <DateHeader date={date} />
          <div style={{
            display: "grid",
            gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
            gap: "12px",
            marginBottom: "8px",
          }}>
            {byDate[date].map(match => (
              <MatchCard key={match.match_id} match={match} />
            ))}
          </div>
        </div>
      ))}

      {lastUpdated && (
        <p style={{
          fontSize: "11px", color: "rgba(255,255,255,0.2)",
          marginTop: "16px", textAlign: "right",
        }}>
          Last updated: {lastUpdated.toLocaleTimeString()} · auto-refresh 60s
        </p>
      )}
    </div>
  );
}