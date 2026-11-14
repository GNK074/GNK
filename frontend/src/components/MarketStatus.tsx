import { useEffect, useState } from "react";
import { api } from "../services/api";

export function MarketStatus() {
  const [status, setStatus] = useState<string>();
  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api("/marketdata/session-schedule");
        if (active) setStatus(result.status);
      } catch {
        if (active) setStatus(undefined);
      } finally {
        if (active) timer = setTimeout(refresh, 30000);
      }
    }
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, []);
  const label = status === "SCHEDULED_CLOSED" ? "Markets Closed" :
    status === "SCHEDULED_OPEN" ? "Markets Open" : "Market status unavailable";

  return <details className="profile-menu market-session-menu">
    <summary className="market-session-badge">
      <span aria-hidden="true" className={status === "SCHEDULED_OPEN" ? "market-session-open" : ""}>●</span>
      {label}
    </summary>
    <div className="profile-menu-links market-session-panel">
      <strong>{label}</strong>
      <span>Regular NSE Equity hours</span>
      <span>9:15 am to 3:30 pm IST</span>
      <small>Based on the configured schedule, including configured holidays and special sessions.</small>
    </div>
  </details>;
}
