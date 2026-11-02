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
import { Logo } from "../components/Logo";

export function Landing() {
  return (
    <div className="landing">
      <div className="topnav">
        <Logo />
        <div>
          <a href="#features">Features</a>
          <a href="#about">About</a>
          <a href="mailto:gnkalgo@gmail.com">Contact</a>
          <Link to="/login">Sign in</Link>
          <Link className="button" to="/register">
            Get started <ArrowUpRight size={16} />
          </Link>
        </div>
      </div>
      <section className="hero">
        <div className="pill">
          <span className="status-dot" /> THE NEXT CHAPTER OF YOUR TRADING
        </div>
        <h1>
          Intelligence behind
          <br />
          every <em>trade.</em>
        </h1>
        <p>
          Build with clarity. Automate with confidence.
          <br />A thoughtfully engineered workspace for your trading journey.
        </p>
        <div className="hero-actions">
          <Link className="button" to="/register">
            Create your workspace <ArrowRight size={18} />
          </Link>
          <a className="button ghost" href="#features">
            Explore the platform
          </a>
        </div>
        <div className="hero-facts">
          <span>
            <ShieldCheck size={17} /> Secure by design
          </span>
          <span>
            <Cable size={17} /> Broker-ready architecture
          </span>
          <span>
            <LockKeyhole size={17} /> Your account. Your control.
          </span>
        </div>
      </section>
      <div className="preview">
        <div className="preview-top">
          <Activity /> GNK ALGO <span>WORKSPACE PREVIEW · NO LIVE DATA</span>
        </div>
        <div className="preview-grid">
          <div>
            <p>YOUR TRADING, CONNECTED.</p>
            <h2>
              One workspace.
              <br />A clearer perspective.
            </h2>
            <p>
              Monitor connections, manage risk,
              <br />
              and prepare your next strategy.
            </p>
            <Link to="/register" className="text-link">
              Start your journey <ArrowUpRight size={17} />
            </Link>
          </div>
          <div className="signal-art">
            <div className="orbit o1" />
            <div className="orbit o2" />
            <div className="orbit o3" />
            <Activity size={72} />
            <span className="float f1">
              <ShieldCheck size={16} /> Risk controls
            </span>
            <span className="float f2">
              <Cable size={16} /> Broker connections
            </span>
            <span className="float f3">
              <Blocks size={16} /> Strategy workspace
            </span>
          </div>
        </div>
      </div>
      <section id="features">
        <p className="eyebrow">ENGINEERED FOR CONFIDENCE</p>
        <h2>A strong foundation for smarter decisions.</h2>
        <div className="three">
          {[
            [
              ShieldCheck,
              "Security at the core",
              "Email verification, protected sessions, and access controls keep your workspace secure.",
            ],
            [
              Cable,
              "Your broker, connected",
              "A dedicated onboarding experience with clear integration and approval status.",
            ],
            [
              Gauge,
              "Control comes first",
              "Trading remains disabled until integrations and required risk controls are approved.",
            ],
          ].map(([Icon, title, desc]: any) => (
            <article key={title}>
              <Icon />
              <h3>{title}</h3>
              <p>{desc}</p>
            </article>
          ))}
        </div>
      </section>
      <section id="about" className="about">
        <h2>Built for the way you think.</h2>
        <p>
          GNK ALGO brings account security, broker onboarding, and trading
          oversight together. Live broker connectivity and strategy execution
          are pending integration and review.
        </p>
        <Link to="/register" className="button">
          Get started <ArrowRight size={16} />
        </Link>
      </section>
      <footer>
        GNK ALGO · Intelligence Behind Every Trade.
        <span>Trading involves market risk. No guaranteed returns.</span>
        <a href="mailto:gnkalgo@gmail.com">Contact support</a>
      </footer>
    </div>
  );
}
