// frontend/src/pages/Bracket.jsx
import { useCallback } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../utils/api.js";
import { TeamFlag } from "../components/TeamFlag.jsx";

const STAGES = ["Round of 32", "Round of 16", "Quarter-final", "Semi-final", "Final"];

function MatchCard({ match }) {
  const finished = match.winner != null;
  return (
    <div style={{
      background: "rgba(255,255,255,0.04)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: "8px", padding: "10px 12px",
      marginBottom: "8px", minWidth: "200px",
    }}>
      {[
        { team: match.team1, score: match.score1 },
        { team: match.team2, score: match.score2 },
      ].map(({ team, score }, i) => (
        <div key={i} style={{
          display: "flex", alignItems: "center",
          justifyContent: "space-between",
          padding: "4px 0",
          opacity: finished && match.winner !== team ? 0.4 : 1,
          fontWeight: match.winner === team ? 600 : 400,
        }}>
          <div style={{ display: "flex", alignItems: "center", gap: "6px" }}>
            <TeamFlag team={team} size={14} />
            <span style={{ fontSize: "13px", color: "#fff" }}>
              {team === "TBD" ? "TBD" : team}
            </span>
          </div>
          <span style={{
            fontSize: "13px", color: "#e8b84b",
            fontVariantNumeric: "tabular-nums",
          }}>
            {score ?? "-"}
          </span>
        </div>
      ))}
      <div style={{
        fontSize: "10px", color: "rgba(255,255,255,0.25)",
        marginTop: "6px",
      }}>
        {match.date} {match.time} UTC
      </div>
    </div>
  );
}

export function Bracket() {
  const fetcher = useCallback(() => api.getBracket(), []);
  const { data, loading, error } = usePolling(fetcher, 60_000);

  if (loading) return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "rgba(255,255,255,0.3)" }}>
      Loading bracket...
    </div>
  );
  if (error) return (
    <div style={{ color: "#f44336", padding: "40px" }}>{error}</div>
  );

  return (
    <div className="scroll-container-wrapper">
      <div className="mobile-scroll-helper">
        <span>↔️ Swipe horizontally to view full knockout bracket stages</span>
      </div>
      <div className="scroll-container" style={{ paddingBottom: "12px" }}>
        <div style={{
          display: "grid",
          gridTemplateColumns: `repeat(${STAGES.length}, 1fr)`,
          gap: "16px",
          minWidth: "1100px",
        }}>
          {STAGES.map(stage => (
            <div key={stage}>
              <div style={{
                fontFamily: "'Bebas Neue', sans-serif",
                fontSize: "14px", letterSpacing: "2px",
                color: "#e8b84b", marginBottom: "12px",
                textAlign: "center",
              }}>
                {stage.toUpperCase()}
              </div>
              {(data[stage] || []).map(match => (
                <MatchCard key={match.match_id} match={match} />
              ))}
            </div>
          ))}
        </div>
      </div>
    </div>
  );
}