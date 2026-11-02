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
import { Landing } from "../pages/Landing";
import { Auth } from "../pages/Auth";
import { Dashboard } from "../dashboard/Dashboard";
import { Brokers } from "../brokers/Brokers";
import { SettingsPage } from "../pages/SettingsPage";
import { Security } from "../risk-management/Security";
import { Admin } from "../admin/Admin";

export function App() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [note, setNote] = useState("");
  const loc = useLocation(),
    nav = useNavigate();
  useEffect(() => {
    api("/users/me")
      .then((d) => setUser(d.user))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useEffect(() => {
    setNote("");
  }, [loc.pathname]);
  const notify = (s: string) => setNote(s);
  const isAuth = [
    "/login",
    "/register",
    "/forgot-password",
    "/reset",
    "/verify",
  ].includes(loc.pathname);
  if (loading)
    return <div className="loading">GNK ALGO · Loading workspace…</div>;
  return (
    <>
      {note && (
        <div role="status" className="toast" onClick={() => setNote("")}>
          {note}
          <span> ×</span>
        </div>
      )}
      {isAuth ? (
        <Auth
          onLogin={(u) => {
            setUser(u);
            nav("/user/broker-and-exchanges");
          }}
          notify={notify}
        />
      ) : loc.pathname === "/" ? (
        <Landing />
      ) : !user ? (
        <div className="auth-wrap">
          <Logo />
          <h1>Your workspace awaits.</h1>
          <p>Sign in to securely access your account.</p>
          <Link className="button" to="/login">
            Sign in <ArrowRight size={17} />
          </Link>
        </div>
      ) : (
        <div className="app">
          <aside>
            <Logo />
            <div className="workspace">
              <span className="avatar">G</span>
              <div>
                Personal workspace<small>Individual account</small>
              </div>
              <span className="tag">FREE</span>
            </div>
            <div className="nav-label">WORKSPACE</div>
            <nav>
              {[
                [LayoutDashboard, "Overview", "/user/dashboard"],
                [Cable, "Brokers & exchanges", "/user/broker-and-exchanges"],
                [Blocks, "Strategies", "/user/strategies"],
                [BarChart3, "Portfolio", "/user/portfolio"],
                [ShieldCheck, "Risk & security", "/user/security"],
                [Settings, "Account settings", "/user/settings"],
                ...(user.role !== "USER"
                  ? [[Gauge, "Administration", "/admin"]]
                  : []),
              ].map(([Icon, title, path]: any) => (
                <Link
                  className={loc.pathname === path ? "selected" : ""}
                  to={path}
                  key={path}
                >
                  <Icon size={19} />
                  {title}
                  {title === "Strategies" && <span className="new">SOON</span>}
                </Link>
              ))}
            </nav>
            <div className="sidebar-bottom">
              <div className="secure">
                <ShieldCheck size={18} />
                <div>
                  Built for peace of mind
                  <small>Secure, encrypted sessions</small>
                </div>
              </div>
              <button
                className="profile"
                onClick={async () => {
                  try {
                    await api("/auth/logout", "POST");
                    setUser(null);
                    nav("/login");
                  } catch (e) {
                    notify((e as Error).message);
                  }
                }}
              >
                <span className="avatar">{user.name[0]}</span>
                <div>
                  {user.name}
                  <small>Sign out of all devices ↗</small>
                </div>
              </button>
            </div>
          </aside>
          <main>
            <header>
              <span>
                Workspace <ChevronRight size={14} />{" "}
                <b>
                  {loc.pathname.includes("broker")
                    ? "Brokers & exchanges"
                    : "Overview"}
                </b>
              </span>
              <div>
                <span className="status-dot" />
                Trading disabled <span className="header-divider">│</span>
                <CircleHelp size={18} />
                <span className="avatar">{user.name[0]}</span>
              </div>
            </header>
            <div className="content">
              {loc.pathname.includes("broker") ? (
                <Brokers notify={notify} />
              ) : loc.pathname === "/user/settings" ? (
                <SettingsPage user={user} notify={notify} />
              ) : loc.pathname === "/user/security" ? (
                <Security notify={notify} />
              ) : loc.pathname === "/admin" ? (
                <Admin />
              ) : loc.pathname === "/user/strategies" ||
                loc.pathname === "/user/portfolio" ? (
                <>
                  <p className="eyebrow">YOUR WORKSPACE</p>
                  <h1>
                    {loc.pathname.includes("strategies")
                      ? "Strategy workspace"
                      : "Portfolio"}
                  </h1>
                  <div className="empty">
                    <Blocks size={35} />
                    <h2>
                      {loc.pathname.includes("strategies")
                        ? "Build on a secure foundation"
                        : "No portfolio connected"}
                    </h2>
                    <p>
                      {loc.pathname.includes("strategies")
                        ? "Strategy building and execution are scheduled for a future release."
                        : "Holdings and balances will appear after an approved broker integration is connected."}
                    </p>
                    <Link to="/user/broker-and-exchanges" className="button">
                      View broker integrations
                    </Link>
                  </div>
                </>
              ) : (
                <Dashboard user={user} notify={notify} />
              )}
            </div>
            <footer>
              © {new Date().getFullYear()} GNK ALGO{" "}
              <span>Intelligence Behind Every Trade.</span>
              <span>
                Trading involves market risk. AI signals do not guarantee
                returns.
              </span>
            </footer>
          </main>
        </div>
      )}
    </>
  );
}
