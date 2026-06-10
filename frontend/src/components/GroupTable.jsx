// frontend/src/components/GroupTable.jsx
import { TeamFlag } from "./TeamFlag.jsx";

export function GroupTable({ group, standings }) {
  return (
    <div style={{
      background: "rgba(255,255,255,0.04)",
      border: "1px solid rgba(255,255,255,0.08)",
      borderRadius: "12px", overflow: "hidden",
    }}>
      <div style={{
        padding: "10px 16px",
        background: "rgba(232,184,75,0.12)",
        borderBottom: "1px solid rgba(255,255,255,0.06)",
        display: "flex", alignItems: "center", gap: "8px",
      }}>
        <span style={{
          fontFamily: "'Bebas Neue', sans-serif",
          fontSize: "18px", letterSpacing: "2px", color: "#e8b84b",
        }}>
          GROUP {group}
        </span>
      </div>

      <table className="group-table" style={{ width: "100%", borderCollapse: "collapse", fontSize: "13px" }}>
        <thead>
          <tr style={{ color: "rgba(255,255,255,0.35)", borderBottom: "1px solid rgba(255,255,255,0.06)" }}>
            {["Team", "P", "W", "D", "L", "GD", "Pts"].map(h => (
              <th key={h} style={{
                padding: "6px 8px", textAlign: h === "Team" ? "left" : "center",
                fontWeight: 500, fontSize: "11px", letterSpacing: "0.5px",
              }}>{h}</th>
            ))}
          </tr>
        </thead>
        <tbody>
          {standings.map((s, i) => (
            <tr key={s.team} style={{
              borderBottom: i < standings.length - 1 ? "1px solid rgba(255,255,255,0.04)" : "none",
              background: i < 2 ? "rgba(232,184,75,0.04)" : "transparent",
            }}>
              <td style={{ padding: "8px", display: "flex", alignItems: "center", gap: "8px" }}>
                <TeamFlag team={s.team} size={16} />
                <span style={{ color: i < 2 ? "#fff" : "rgba(255,255,255,0.6)" }}>
                  {s.team}
                </span>
                {i < 2 && (
                  <span style={{
                    fontSize: "9px", padding: "1px 5px",
                    background: "rgba(232,184,75,0.2)", color: "#e8b84b",
                    borderRadius: "3px", letterSpacing: "0.5px",
                  }}>Q</span>
                )}
              </td>
              {[s.played, s.won, s.drawn, s.lost, s.gd >= 0 ? `+${s.gd}` : s.gd, s.points].map((v, j) => (
                <td key={j} style={{
                  padding: "8px", textAlign: "center",
                  color: j === 5 ? "#e8b84b" : "rgba(255,255,255,0.7)",
                  fontWeight: j === 5 ? 600 : 400,
                  fontVariantNumeric: "tabular-nums",
                }}>{v}</td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}