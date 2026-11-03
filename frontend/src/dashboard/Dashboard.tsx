import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { ArrowRight, BarChart3, Blocks, Cable, ShieldCheck } from "lucide-react";
import { api } from "../services/api";
import type { User } from "../store/session";

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
          <h1>Good to see you, {user.name.split(" ")[0]} <span className="wave">↗</span></h1>
          <p>A clear view of your trading workspace.</p>
        </div>
        <Link className="button" to="/user/broker-and-exchanges">Connect a broker <ArrowRight size={17} /></Link>
      </div>
      <div className="stats">
        {[
          ["Connected brokers", summary ? String(count) : "—", count > 0 ? "Individual credentials verified" : "Connect your own account", Cable],
          ["Portfolio value", "—", "No broker data available", BarChart3],
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
