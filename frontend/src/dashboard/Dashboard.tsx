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

export function Dashboard({
  user,
  notify,
}: {
  user: User;
  notify: (s: string) => void;
}) {
  return (
    <>
      <div className="page-heading">
        <div>
          <p className="eyebrow">YOUR COMMAND CENTER</p>
          <h1>
            Good to see you, {user.name.split(" ")[0]}{" "}
            <span className="wave">↗</span>
          </h1>
          <p>A clear view of your trading workspace.</p>
        </div>
        <Link className="button" to="/user/broker-and-exchanges">
          Connect a broker <ArrowRight size={17} />
        </Link>
      </div>
      <div className="notice">
        <ShieldCheck />
        <div>
          <b>You're in control. Always.</b>
          <p>
            Your workspace is ready. Broker integrations are awaiting
            verification; live trading is disabled.
          </p>
        </div>
        <span className="tag">DISCONNECTED</span>
      </div>
      <div className="stats">
        {[
          ["Connected brokers", "0", "Connect your first account", Cable],
          ["Portfolio value", "—", "No broker data available", BarChart3],
          ["Active strategies", "0", "Strategy module coming soon", Blocks],
          ["Risk status", "Protected", "Live execution disabled", ShieldCheck],
        ].map(([label, value, sub, Icon]: any) => (
          <article key={label}>
            <div className="stat-label">
              {label}
              <Icon size={18} />
            </div>
            <h2 className={value === "Protected" ? "green" : ""}>{value}</h2>
            <small>{sub}</small>
          </article>
        ))}
      </div>
      <div className="dash-grid">
        <article className="panel">
          <div className="panel-title">
            <h3>Portfolio overview</h3>
            <span className="tag">NO DATA</span>
          </div>
          <div className="chart-empty">
            <div className="chart-lines" />
            <div>
              <BarChart3 size={32} />
              <h3>Your portfolio starts here</h3>
              <p>
                Connect an approved broker to view your holdings
                <br />
                and account performance.
              </p>
              <Link className="text-link" to="/user/broker-and-exchanges">
                Explore broker integrations <ArrowRight size={16} />
              </Link>
            </div>
          </div>
        </article>
        <article className="panel">
          <div className="panel-title">
            <h3>Getting started</h3>
            <span className="muted">1 of 3</span>
          </div>
          <div className="steps">
            <div>
              <span className="step done">✓</span>
              <section>
                <b>Secure your account</b>
                <p>Email verified. You're ready to go.</p>
              </section>
            </div>
            <Link to="/user/broker-and-exchanges">
              <span className="step">2</span>
              <section>
                <b>Explore broker connections</b>
                <p>Find your broker and check availability.</p>
              </section>
              <ChevronRight size={17} />
            </Link>
            <div>
              <span className="step">3</span>
              <section>
                <b>Prepare your workspace</b>
                <p>Review your security and account settings.</p>
              </section>
            </div>
          </div>
          <Link className="button ghost wide" to="/user/broker-and-exchanges">
            Continue setup <ArrowRight size={16} />
          </Link>
        </article>
      </div>
      <div className="dash-grid lower">
        <article className="panel">
          <div className="panel-title">
            <h3>Market overview</h3>
            <span className="muted">Feed not connected</span>
          </div>
          {["NIFTY 50", "NIFTY BANK", "SENSEX"].map((n, i) => (
            <div className="market" key={n}>
              <span className="market-icon">{["N", "B", "S"][i]}</span>
              <b>{n}</b>
              <span>—</span>
              <small>Awaiting market data</small>
            </div>
          ))}
        </article>
        <article className="panel safety">
          <ShieldCheck size={25} />
          <h3>Built around your safety</h3>
          <p>
            No orders can be placed in this release. Broker authorization alone
            will never enable automated trading.
          </p>
          <button
            className="danger"
            onClick={async () => {
              try {
                notify((await api("/emergency-stop", "POST")).message);
              } catch (e) {
                notify((e as Error).message);
              }
            }}
          >
            <Square size={14} /> Emergency stop
          </button>
        </article>
      </div>
    </>
  );
}
