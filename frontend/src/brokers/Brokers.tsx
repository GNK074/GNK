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

export function Brokers({ notify }: { notify: (s: string) => void }) {
  const [items, setItems] = useState<any[]>([]),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<any>(null);
  useEffect(() => {
    api("/brokers")
      .then(setItems)
      .catch((e) => notify(e.message));
  }, []);
  return (
    <>
      <p className="eyebrow">CONNECT YOUR ECOSYSTEM</p>
      <div className="page-heading">
        <div>
          <h1>Brokers & exchanges</h1>
          <p>Your trading accounts, together in one secure workspace.</p>
        </div>
        <span className="tag">0 CONNECTED</span>
      </div>
      <div className="notice">
        <Cable />
        <div>
          <b>A thoughtful connection starts with verification.</b>
          <p>
            All broker integrations are pending official API access and
            compliance verification.
          </p>
        </div>
      </div>
      <div className="section-heading">
        <h3>
          Available integration candidates{" "}
          <span className="muted">{items.length}</span>
        </h3>
        <div className="search">
          <Search size={17} />
          <input
            aria-label="Search brokers"
            placeholder="Search brokers…"
            value={search}
            onChange={(e) => setSearch(e.target.value)}
          />
        </div>
      </div>
      <div className="broker-grid">
        {items
          .filter((b) => b.name.toLowerCase().includes(search.toLowerCase()))
          .map((b, i) => (
            <article className="broker-card" key={b.id}>
              <div className="broker-card-top">
                <span className={"broker-logo color" + (i % 5)}>
                  {b.name.slice(0, 1)}
                </span>
                <span className="pending">Pending verification</span>
              </div>
              <h3>{b.name}</h3>
              <p>Indian stock broker integration</p>
              <div className="broker-divider" />
              <button
                className="button ghost wide"
                onClick={() => setSelected(b)}
              >
                View setup status <ArrowUpRight size={16} />
              </button>
            </article>
          ))}
      </div>
      {items.length > 0 &&
        !items.some((b) =>
          b.name.toLowerCase().includes(search.toLowerCase()),
        ) && <div className="empty">No brokers match your search.</div>}
      <div className="broker-note">
        <LockKeyhole size={16} /> Never share your broker password, PIN or OTP.
        GNK ALGO will only use verified official authentication flows.
      </div>
      <Link className="text-link" to="/user/dashboard">
        Continue without a broker <ArrowRight size={16} />
      </Link>
      {selected && (
        <div className="modal-backdrop">
          <div
            className="modal"
            role="dialog"
            aria-modal="true"
            aria-label="Broker setup status"
          >
            <button
              className="close"
              aria-label="Close"
              onClick={() => setSelected(null)}
            >
              ×
            </button>
            <span className="eyebrow">BROKER ONBOARDING · STEP 1 OF 2</span>
            <h2>{selected.name}</h2>
            <p>
              Configuration is unavailable until this broker's integration has
              been approved.
            </p>
            {[
              "Official API and authentication review",
              "API access and commercial approval",
              "Exchange and segment validation",
              "Compliance and security review",
            ].map((x) => (
              <div className="check-row" key={x}>
                <span>○</span>
                {x}
                <small>Pending</small>
              </div>
            ))}
            <div className="notice">
              <ShieldCheck size={20} />
              <p>No credentials are collected and no orders are placed.</p>
            </div>
            <button className="button wide" onClick={() => setSelected(null)}>
              Return to brokers
            </button>
          </div>
        </div>
      )}
    </>
  );
}
