import { LiveWorkspace } from "../strategies/LiveWorkspace";
import { LiveExecutionAdmin } from "../admin/LiveExecutionAdmin";
import { MarketDataAdmin } from "../admin/MarketDataAdmin";
import { MarketsPage } from "../markets/MarketsPage";
import { MfaRecoveryPage } from "../pages/MfaRecoveryPage";
import { MfaRecoveryReview } from "../admin/MfaRecoveryReview";
import { ContactUsPage } from "../pages/ContactUsPage";
import { DisclosureGate } from "../compliance/DisclosureGate";
import { SignOutDialog } from "../components/SignOutDialog";
import { applyTheme } from "../services/theme";
import { MfaEnrollment } from "../pages/MfaEnrollment";
import { PaperWorkspace } from "../strategies/PaperWorkspace";
import { useEffect, useLayoutEffect, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  BarChart3,
  Blocks,
  Cable,
  ChevronRight,
  CircleHelp,
  Gauge,
  LayoutDashboard,
  Settings,
  ShieldCheck,
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
  const [liveReady,setLiveReady] = useState(false);
  useEffect(()=>{if(user)api("/live/readiness").then(r=>setLiveReady(r.server_enabled&&r.broker_approved&&r.reconciliation_healthy&&r.accounts.some((a:any)=>a.armed&&a.live_authorized))).catch(()=>setLiveReady(false));},[user?.id,location.pathname]);
  const [signOutOpen, setSignOutOpen] = useState(false);
  function updateUser(u: User) {
    setUser(u);
    applyTheme(u.theme || "carbon_black");
  }
  const loc = useLocation(),
    nav = useNavigate();
  useEffect(() => {
    api("/users/me")
      .then((d) => updateUser(d.user))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useLayoutEffect(() => {
    document.documentElement.dataset.workspace = String(
      loc.pathname.startsWith("/user/") || loc.pathname.startsWith("/markets") || loc.pathname === "/admin",
    );
  }, [loc.pathname]);
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
    "/confirm-email-change",
  ].includes(loc.pathname);
  if (["/forgot-mfa", "/mfa-recovery"].includes(loc.pathname))
    return <MfaRecoveryPage />;
  if (loc.pathname === "/mfa") return <MfaEnrollment />;
  if (loading)
    return <div className="loading">GNK ALGO · Loading workspace…</div>;
  return (
    <>
      {signOutOpen && (
        <SignOutDialog
          onClose={() => setSignOutOpen(false)}
          onSignedOut={() => {
            setUser(null);
            setSignOutOpen(false);
            nav("/login");
          }}
          onError={notify}
        />
      )}
      {note && (
        <div role="status" className="toast" onClick={() => setNote("")}>
          {note}
          <span> ×</span>
        </div>
      )}
      {isAuth ? (
        <Auth
          onLogin={(u) => {
            updateUser(u);
            nav("/user/dashboard");
          }}
          notify={notify}
        />
      ) : ["/contact", "/contact-us", "/contact-us/"].includes(loc.pathname) ? (
        <ContactUsPage signedIn={!!user} />
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
                [BarChart3, "Markets", "/markets"],
                [Cable, "Brokers & exchanges", "/user/broker-and-exchanges"],
                [Blocks, "Strategies", "/user/strategies"],
                [BarChart3, "Live orders", "/user/live-orders"],
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
              <button className="profile" onClick={() => setSignOutOpen(true)}>
                <span className="avatar">
                  {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" />
                  ) : (
                    user.name[0]
                  )}
                </span>
                <div>
                  {user.name}
                  <small>Account & sign out ↗</small>
                </div>
              </button>
            </div>
          </aside>
          <main>
            <header>
              <span>
                Workspace <ChevronRight size={14} />{" "}
                <b>
                  {loc.pathname === "/user/live-orders"
                    ? "Live orders"
                    : loc.pathname.startsWith("/markets")
                    ? "Markets"
                    : loc.pathname.includes("broker")
                    ? "Brokers & exchanges"
                    : loc.pathname.includes("settings")
                      ? "Profile & settings"
                      : "Overview"}
                </b>
              </span>
              <div>
                <span className="status-dot" />
                {liveReady?"Live account armed":"Live placement locked"} <span className="header-divider">│</span>
                <CircleHelp size={18} />
                <span className="avatar">
                  {user.avatar_url ? (
                    <img src={user.avatar_url} alt="" />
                  ) : (
                    user.name[0]
                  )}
                </span>
              </div>
            </header>
            <div className="content">
              {loc.pathname === "/user/live-orders" ? (
                <DisclosureGate key={user.id}><LiveWorkspace /></DisclosureGate>
              ) : loc.pathname.startsWith("/markets") ? (
                <MarketsPage />
              ) : loc.pathname.includes("broker") ? (
                <Brokers notify={notify} />
              ) : loc.pathname === "/user/settings" ? (
                <SettingsPage
                  user={user}
                  notify={notify}
                  onUpdate={updateUser}
                  onSignOut={() => setSignOutOpen(true)}
                />
              ) : loc.pathname === "/user/security" ? (
                <Security notify={notify} />
              ) : loc.pathname === "/admin" ? (
                <>
                  <Admin />
                  {user.role === "SUPER_ADMIN" && <><MfaRecoveryReview /><MarketDataAdmin /><LiveExecutionAdmin /></>}
                </>
              ) : loc.pathname === "/user/strategies" ||
                loc.pathname === "/user/portfolio" ? (
                <DisclosureGate key={user.id}>
                  <PaperWorkspace notify={notify} />
                </DisclosureGate>
              ) : (
                <DisclosureGate key={user.id}>
                  <Dashboard user={user} notify={notify} />
                </DisclosureGate>
              )}
            </div>
            <footer>
              © {new Date().getFullYear()} GNK ALGO{" "}
              <span>Intelligence Behind Every Trade.</span>
              <Link to="/contact-us">Contact Us</Link>
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
