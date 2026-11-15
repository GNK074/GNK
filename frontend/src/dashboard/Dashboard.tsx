import { useEffect, useState } from "react";
import { BarChart3, Blocks, Cable, ShieldCheck } from "lucide-react";
import { api } from "../services/api";
import type { User } from "../store/session";

const currency = new Intl.NumberFormat("en-IN", { style: "currency", currency: "INR" });

function positionMetric(metric?: { value: string | number | null; complete: boolean }) {
  return metric?.value != null && metric.complete ? currency.format(Number(metric.value)) : "—";
}

export function Dashboard({ user, notify }: { user: User; notify: (message: string) => void }) {
  const [summary, setSummary] = useState<any>(null);
  useEffect(() => {
    api("/dashboard").then(setSummary).catch((error) => notify(error.message));
  }, []);
  const count = summary?.connections ?? 0;
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR COMMAND CENTER</p>
          <h1>Dashboard</h1>
          <p>Good to see you, {user.name.split(" ")[0]} <span className="wave">↗</span></p>
          <p>A clear view of your trading workspace.</p>
        </div>
      </div>
      <div className="stats">
        {[
          ["Connected brokers", summary ? String(count) : "—", count > 0 ? "Individual credentials verified" : "Connect your own account", Cable],
          ["Holdings value", summary?.portfolio?.holdings_current?.value != null ? new Intl.NumberFormat("en-IN",{style:"currency",currency:"INR"}).format(Number(summary.portfolio.holdings_current.value)) : "—", summary?.portfolio?.holdings_current?.complete ? "Latest complete broker snapshots" : "Missing or stale broker valuation", BarChart3],
          ["Realized P&L", positionMetric(summary?.portfolio?.positions_realized), "Broker position snapshots", BarChart3],
          ["Unrealized P&L", positionMetric(summary?.portfolio?.positions_unrealized), "Broker position snapshots", BarChart3],
          ["Research strategies", summary ? String(summary.strategies.length) : "—", "Saved paper research strategies", Blocks],
          ["Execution controls", summary ? (summary.live_trading ? "Configured" : "Locked") : "—", "Account and risk checks apply", ShieldCheck],
        ].map(([label, value, sub, Icon]: any) => (
          <article key={label}>
            <div className="stat-label">{label}<Icon size={18} /></div>
            <h2>{value}</h2>
            <small>{sub}</small>
          </article>
        ))}
      </div>
    </>
  );
}
