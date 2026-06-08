// frontend/src/pages/Groups.jsx
import { useCallback } from "react";
import { usePolling } from "../hooks/usePolling.js";
import { api } from "../utils/api.js";
import { GroupTable } from "../components/GroupTable.jsx";

export function Groups() {
  const fetcher = useCallback(() => api.getGroups(), []);
  const { data, loading, error, lastUpdated } = usePolling(fetcher, 60_000);

  if (loading) return (
    <div style={{ textAlign: "center", padding: "60px 0", color: "rgba(255,255,255,0.3)" }}>
      Loading groups...
    </div>
  );
  if (error) return (
    <div style={{ color: "#f44336", padding: "40px 0" }}>{error}</div>
  );

  return (
    <div>
      <div style={{
        display: "grid",
        gridTemplateColumns: "repeat(auto-fill, minmax(280px, 1fr))",
        gap: "16px",
      }}>
        {data?.map(g => (
          <GroupTable key={g.group} group={g.group} standings={g.standings} />
        ))}
      </div>
      {lastUpdated && (
        <p style={{ fontSize: "11px", color: "rgba(255,255,255,0.25)", marginTop: "16px", textAlign: "right" }}>
          Last updated: {lastUpdated.toLocaleTimeString()} · auto-refresh 60s
        </p>
      )}
    </div>
  );
}