import { BrokerApprovals } from "./BrokerApprovals";
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

export function Admin() {
  const [users, setUsers] = useState<any[]>([]),
    [error, setError] = useState("");
  useEffect(() => {
    api("/admin/users")
      .then(setUsers)
      .catch((e) => setError(e.message));
  }, []);
  return (
    <>
      <h1>Administration</h1>
      <p>{error || `${users.length} registered accounts`}</p>
      <article className="panel">
        {users.map((u) => (
          <div className="market" key={u.id}>
            <b>{u.name}</b>
            <span>{u.email}</span>
            <small>
              {u.role} · {u.verified ? "Verified" : "Pending"}
            </small>
          </div>
        ))}
      </article>
      <BrokerApprovals />
    </>
  );
}
