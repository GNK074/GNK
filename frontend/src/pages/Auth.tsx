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

export function Auth({
  onLogin,
  notify,
}: {
  onLogin: (u: User) => void;
  notify: (s: string) => void;
}) {
  const loc = useLocation(),
    path = loc.pathname;
  const [busy, setBusy] = useState(false);
  const titles: Record<string, string> = {
    "/login": "Welcome back.",
    "/register": "Your next chapter starts here.",
    "/forgot-password": "Reset your password.",
    "/reset": "Set a new password.",
    "/verify": "Verify your email.",
  };
  async function submit(e: React.FormEvent<HTMLFormElement>) {
    e.preventDefault();
    setBusy(true);
    const f = new FormData(e.currentTarget),
      data = Object.fromEntries(f);
    try {
      if (path === "/register" && data.password !== data.confirm)
        throw Error("Passwords do not match");
      const route =
        path === "/login"
          ? "login"
          : path === "/register"
            ? "register"
            : path === "/verify"
              ? "verify-email"
              : path === "/reset"
                ? "reset-password"
                : "forgot-password";
      const body =
        path === "/register"
          ? { ...data, terms: !!data.terms, privacy: !!data.privacy }
          : { ...data, token: new URLSearchParams(loc.search).get("token") };
      const d = await api("/auth/" + route, "POST", body);
      if (path === "/login") onLogin(d.user);
      else notify(d.message);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout">
      <div className="auth-art">
        <Logo />
        <div>
          <div className="pill">INTELLIGENCE BEHIND EVERY TRADE</div>
          <h1>
            A clearer view.
            <br />A smarter beginning.
          </h1>
          <p>
            Your strategies. Your decisions.
            <br />
            One secure workspace.
          </p>
          <Activity size={100} />
        </div>
        <small>
          Trading involves market risk. Returns are never guaranteed.
        </small>
      </div>
      <div className="auth-form">
        <Link className="back" to="/">
          ← Back to home
        </Link>
        <p className="eyebrow">WELCOME TO GNK ALGO</p>
        <h1>{titles[path]}</h1>
        <p>
          {path === "/register"
            ? "Create your secure trading workspace."
            : "Secure access to your GNK ALGO account."}
        </p>
        <form onSubmit={submit}>
          {path === "/register" && (
            <label>
              Full name
              <input
                name="name"
                required
                minLength={2}
                maxLength={100}
                autoComplete="name"
                placeholder="Your full name"
              />
            </label>
          )}
          {!["/reset", "/verify"].includes(path) && (
            <label>
              Email address
              <input
                type="email"
                name="email"
                required
                autoComplete="email"
                placeholder="you@example.com"
              />
            </label>
          )}
          {["/login", "/register", "/reset"].includes(path) && (
            <label>
              Password
              <input
                type="password"
                name="password"
                required
                minLength={path === "/login" ? 1 : 12}
                maxLength={128}
                autoComplete={
                  path === "/login" ? "current-password" : "new-password"
                }
                placeholder="Enter your password"
              />
              {path !== "/login" && (
                <small>
                  12+ characters, uppercase, lowercase, number and symbol.
                </small>
              )}
            </label>
          )}
          {path === "/register" && (
            <>
              <label>
                Confirm password
                <input
                  name="confirm"
                  type="password"
                  required
                  autoComplete="new-password"
                />
              </label>
              <label className="checkbox">
                <input type="checkbox" name="terms" required />I accept the
                terms: technical services only, no investment advice or
                guaranteed returns.
              </label>
              <label className="checkbox">
                <input type="checkbox" name="privacy" required />I consent to
                storing my account information to provide this service.
              </label>
            </>
          )}
          {path === "/login" && (
            <Link className="text-link" to="/forgot-password">
              Forgot password?
            </Link>
          )}
          <button disabled={busy} className="button" type="submit">
            {busy
              ? "Please wait…"
              : path === "/login"
                ? "Sign in"
                : path === "/register"
                  ? "Create account"
                  : path === "/verify"
                    ? "Verify email"
                    : "Continue"}
            <ArrowRight size={17} />
          </button>
        </form>
        <p>
          {path === "/login" ? (
            <>
              New to GNK ALGO? <Link to="/register">Create account</Link>
            </>
          ) : (
            <Link to="/login">Back to sign in</Link>
          )}
        </p>
        <div className="auth-secure">
          <LockKeyhole size={15} /> Your session is secured with encrypted
          cookies.
        </div>
      </div>
    </div>
  );
}
