import React, { useEffect, useState } from "react";
import {
  BrowserRouter,
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  ArrowRight,
  BarChart3,
  Blocks,
  Cable,
  ChevronRight,
  CircleHelp,
  Command,
  Gauge,
  LayoutDashboard,
  LockKeyhole,
  Search,
  Settings,
  ShieldCheck,
  Square,
  Zap,
} from "lucide-react";
import { api } from "../services/api";
import type { User } from "../store/session";

export function Security({ notify }: { notify: (s: string) => void }) {
  const [sessions, setSessions] = useState<any[]>([]);
  useEffect(() => {
    api("/users/me/sessions")
      .then(setSessions)
      .catch((e) => notify(e.message));
  }, []);
  return (
    <>
      <p className="eyebrow">ACCOUNT PROTECTION</p>
      <h1>Risk & security</h1>
      <div className="notice">
        <ShieldCheck />
        <div>
          <b>Live trading is disabled</b>
          <p>
            Security controls and broker approval must be reviewed before live
            execution is introduced.
          </p>
        </div>
      </div>
      <article className="panel">
        <h3>Account sessions</h3>
        {sessions.map((x) => (
          <div className="session" key={x.id}>
            <LockKeyhole size={17} />
            <div>
              {x.agent}
              <small>
                {new Date(x.created).toLocaleString()} ·{" "}
                {x.revoked ? "Revoked" : "Active"}
              </small>
            </div>
          </div>
        ))}
      </article>
    </>
  );
}
