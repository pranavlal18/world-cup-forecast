// frontend/src/pages/Groups.jsx
import { useCallback } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../utils/api.js";
import { GroupTable } from "../components/GroupTable.jsx";
import { ResultInput } from "../components/ResultInput.jsx";

export function Groups() {
  const fetcher = useCallback(() => api.getGroups(), []);
  const { data, loading, error, refresh } = usePolling(fetcher, 60_000);

  if (loading) return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "rgba(255,255,255,0.3)" }}>
      Loading groups...
    </div>
  );
  if (error) return (
    <div style={{ color: "#f44336", padding: "40px 0" }}>{error}</div>
  );

  return (
    <div style={{ display: "grid", gridTemplateColumns: "1fr 320px", gap: "24px", alignItems: "start" }}>
      {/* Group tables grid */}
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: "16px",
      }}>
        {data?.map(g => (
          <GroupTable key={g.group} group={g.group} standings={g.standings} />
        ))}
      </div>

      {/* Result input sidebar */}
      <div style={{ position: "sticky", top: "80px" }}>
        <ResultInput onSuccess={refresh} />
        <p style={{
          fontSize: "11px", color: "rgba(255,255,255,0.25)",
          marginTop: "10px", lineHeight: 1.6,
        }}>
          Submitting a result updates group standings and triggers a new Monte Carlo simulation (~60 seconds).
        </p>
      </div>
    </div>
  );
}