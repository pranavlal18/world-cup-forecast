// frontend/src/components/ProbabilityBar.jsx
export function ProbabilityBar({ value, max = 100, color = "#e8b84b" }) {
  const pct = Math.min((value / max) * 100, 100);
  return (
    <div style={{ display: "flex", alignItems: "center", gap: "8px" }}>
      <div style={{
        flex: 1, height: "6px", background: "rgba(255,255,255,0.08)",
        borderRadius: "3px", overflow: "hidden",
      }}>
        <div style={{
          width: `${pct}%`, height: "100%",
          background: color, borderRadius: "3px",
          transition: "width 0.6s ease",
        }} />
      </div>
      <span style={{
        minWidth: "42px", textAlign: "right",
        fontSize: "12px", color: "rgba(255,255,255,0.6)",
        fontVariantNumeric: "tabular-nums",
      }}>
        {value.toFixed(1)}%
      </span>
    </div>
  );
}