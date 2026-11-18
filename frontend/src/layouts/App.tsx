import "./workspace.css";
import { Notifications } from "../components/Notifications";
import { SettingsPage } from "../pages/SettingsPage";
import { MfaRecoveryPage } from "../pages/MfaRecoveryPage";
import { MfaRecoveryReview } from "../admin/MfaRecoveryReview";
import { ContactUsPage } from "../pages/ContactUsPage";
import { DisclosureGate } from "../compliance/DisclosureGate";
import { SignOutDialog } from "../components/SignOutDialog";
import { applyTheme } from "../services/theme";
import { MfaEnrollment } from "../pages/MfaEnrollment";
import { useEffect, useLayoutEffect, useRef, useState } from "react";
import { Navigate, Link, useLocation, useNavigate } from "react-router-dom";
import {
  ArrowRight,
  ChevronRight,
  CircleHelp,
  Palette,
  Menu,
  Check,
  Gauge,
  LayoutDashboard,
  ShieldCheck,
  Activity,
  BriefcaseBusiness,
} from "lucide-react";
import { api, SESSION_ENDED_KEY } from "../services/api";
import type { Theme, User } from "../store/session";
import { Logo } from "../components/Logo";
import { Landing } from "../pages/Landing";
import { Auth } from "../pages/Auth";
import { NativePortfolio } from "../portfolio/NativePortfolio";
import { LiveTrading, tradingModules } from "../strategies/LiveTrading";
import { Dashboard } from "../dashboard/Dashboard";
import { Admin } from "../admin/Admin";

export function App() {
  const [user, setUser] = useState<User | null>(null),
    [loading, setLoading] = useState(true),
    [note, setNote] = useState("");

  const [navigationOpen, setNavigationOpen] = useState(false);
  const [savingTheme, setSavingTheme] = useState(false);
  const profileMenu = useRef<HTMLDetailsElement>(null);
  const [signOutOpen, setSignOutOpen] = useState(false);
  useEffect(()=>{
    const ended=(event:StorageEvent)=>{
      if(event.key===SESSION_ENDED_KEY && event.newValue)window.location.replace("/login");
    };
    window.addEventListener("storage",ended);
    return()=>window.removeEventListener("storage",ended);
  },[]);
  function updateUser(u: User) {
    setUser(u);
    applyTheme(u.theme || "carbon_black");
  }
  const loc = useLocation(),
    nav = useNavigate();
  const portfolio = loc.pathname === "/user/portfolio";
  const tradingRoot = loc.pathname === "/user/trading";
  const tradingModule = tradingRoot
    ? tradingModules[0]
    : tradingModules.find(module => module.path === loc.pathname);

  useEffect(() => {
    if (!user || loc.pathname !== "/user/dashboard") return;
    const previousTitle = document.title;
    document.title = "Dashboard | GNK ALGO";
    return () => {
      document.title = previousTitle;
    };
  }, [user, loc.pathname]);
  useEffect(()=>{
    if(!user)return;
    let active=true,inFlight=false;
    async function checkSession(){
      if(inFlight||document.visibilityState!=="visible")return;
      inFlight=true;
      try{
        const response=await fetch("/api/v1/auth/session",{credentials:"include",cache:"no-store"});
        if(active&&response.status===401){
          setUser(null);setSignOutOpen(false);
          nav("/login",{replace:true});
        }
      }catch{/* A temporary network failure does not prove session revocation. */}
      finally{inFlight=false;}
    }
    const timer=window.setInterval(checkSession,30000);
    window.addEventListener("focus",checkSession);
    document.addEventListener("visibilitychange",checkSession);
    return()=>{active=false;clearInterval(timer);window.removeEventListener("focus",checkSession);document.removeEventListener("visibilitychange",checkSession);};
  },[user?.id,nav]);
  useEffect(() => {
    api("/users/me")
      .then((d) => updateUser(d.user))
      .catch(() => {})
      .finally(() => setLoading(false));
  }, []);
  useLayoutEffect(() => {
    document.documentElement.dataset.workspace = String(
      loc.pathname.startsWith("/user/") || loc.pathname.startsWith("/markets") || loc.pathname.startsWith("/tradedetails/") || ["/admin", "/notification"].includes(loc.pathname),
    );
  }, [loc.pathname]);
  useEffect(() => {
    setNote("");
    setNavigationOpen(false);
    if (profileMenu.current) profileMenu.current.open = false;
  }, [loc.pathname]);
  const notify = (s: string) => setNote(s);
  async function saveTheme(theme: Theme) {
    if (!user || savingTheme || theme === (user.theme || "carbon_black")) return;
    setSavingTheme(true);
    applyTheme(theme);
    try {
      const result = await api("/users/me/preferences", "PUT", { theme });
      updateUser(result.user);
    } catch (error) {
      applyTheme(user.theme || "carbon_black");
      notify((error as Error).message);
    } finally {
      setSavingTheme(false);
    }
  }

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
  if (/^\/markets(?:\/|$)/.test(loc.pathname) ||
      /^\/user\/(broker-and-exchanges|brokers|dhan|strategies|security|settings|live-orders)(?:\/|$)/.test(loc.pathname) ||
      loc.pathname.startsWith("/tradedetails/")) {
    return <Navigate to={user ? "/user/dashboard" : "/login"} replace />;
  }
  return (
    <>
      {signOutOpen && (
        <SignOutDialog
          onClose={() => setSignOutOpen(false)}
          onSignedOut={() => {
            setUser(null);
            setSignOutOpen(false);
            nav("/login", {replace:true});
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
        user ? <Navigate to="/user/dashboard" replace /> : <Landing />
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
        <div className="app workspace-shell">
          <aside id="workspace-navigation" className={navigationOpen ? "workspace-navigation-open" : ""}>
            <Logo signedIn />
            <div className="workspace">
              <span className="avatar">G</span>
              <div>
                Personal workspace<small>Individual account</small>
              </div>
              <span className="tag">FREE</span>
            </div>
            <div className="nav-label">WORKSPACE</div>
            <nav aria-label="Workspace">
              <Link to="/user/dashboard"
                className={loc.pathname === "/user/dashboard" ? "selected" : ""}
                aria-current={loc.pathname === "/user/dashboard" ? "page" : undefined}>
                <LayoutDashboard size={19} aria-hidden="true" /> Dashboard
              </Link>
              <Link to="/user/trading" className={tradingModule ? "trading-parent is-active" : "trading-parent"}>
                <Activity size={19} aria-hidden="true" /> Trading
              </Link>
              <div className="gnk-trading-subnav" role="group" aria-label="Trading modules">
                {tradingModules.map(module => {
                  const Icon = module.icon;
                  const active = tradingModule === module;
                  return <Link to={module.path} key={module.path} data-tone={module.tone}
                    className={active ? "selected" : undefined} aria-current={active ? "page" : undefined}>
                    <Icon size={17} aria-hidden="true" /> {module.title}
                  </Link>;
                })}
              </div>
              <Link to="/user/portfolio" className={portfolio ? "selected" : undefined}
                aria-current={portfolio ? "page" : undefined}>
                <BriefcaseBusiness size={19} aria-hidden="true" /> Portfolio
              </Link>
              {user.role !== "USER" && <Link to="/admin"
                className={loc.pathname === "/admin" ? "selected" : ""}
                aria-current={loc.pathname === "/admin" ? "page" : undefined}>
                <Gauge size={19} aria-hidden="true" /> Administration
              </Link>}
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
                <button className="workspace-menu" type="button" aria-label="Toggle workspace navigation" aria-controls="workspace-navigation" aria-expanded={navigationOpen} onClick={() => setNavigationOpen(open => !open)}><Menu size={18} /></button>
                Workspace <ChevronRight size={14} />{" "}
                <b>
                  {loc.pathname === "/notification" ? "Notifications"
                    : loc.pathname === "/user/profile" ? "Profile"
                    : portfolio ? "Portfolio"
                    : tradingModule ? "Trading / " + tradingModule.title
                    : loc.pathname === "/admin" ? "Administration" : loc.pathname === "/user/dashboard" ? "Dashboard" : "Overview"}
                  {loc.pathname === "/user/dashboard" && <span className="workspace-spark workspace-spark-delayed" aria-hidden="true"> ✳</span>}
                </b>
              </span>
              <div>
                <details className="profile-menu appearance-menu">
                  <summary aria-label="Notifications" title="Notifications">
                    <span aria-hidden="true">🔔</span>
                  </summary>
                  <div className="profile-menu-links">
                    <strong>Notifications <span className="workspace-spark" aria-hidden="true">✳</span></strong>
                    {note && <span>{note}</span>}
                    <Link to="/notification">Open notification inbox</Link>
                  </div>
                </details>
                <CircleHelp size={18} />
                <details className="profile-menu appearance-menu"
                  onBlur={event => {
                    if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false;
                  }}
                  onKeyDown={event => {
                    if (event.key === "Escape" && event.currentTarget.open) {
                      event.currentTarget.open = false;
                      event.currentTarget.querySelector("summary")?.focus();
                    }
                  }}>
                  <summary aria-label="Choose appearance" title="Appearance"><Palette size={18} /></summary>
                  <div className="profile-menu-links" role="group" aria-label="Workspace theme">
                    {([["light", "Light"], ["carbon_black", "Carbon Black"], ["royal_blue", "Royal Blue"]] as const)
                      .map(([value, label]) => {
                        const selected = (user.theme || "carbon_black") === value;
                        return <button key={value} type="button" aria-pressed={selected} aria-disabled={savingTheme}
                          onClick={() => void saveTheme(value)}>{label}{selected && <Check size={14} aria-hidden="true" />}</button>;
                      })}
                  </div>
                </details>
                <details className="profile-menu" ref={profileMenu}
                  onBlur={event => {
                    if (!event.currentTarget.contains(event.relatedTarget)) event.currentTarget.open = false;
                  }}
                  onKeyDown={event => {
                    if (event.key === "Escape" && event.currentTarget.open) {
                      event.currentTarget.open = false;
                      event.currentTarget.querySelector("summary")?.focus();
                    }
                  }}>
                  <summary className="avatar" aria-label="My profile">
                    {user.avatar_url ? <img src={user.avatar_url} alt="" /> : user.name[0]}
                  </summary>
                  <div className="profile-menu-links">
                    <Link to="/user/profile" onClick={() => { if (profileMenu.current) profileMenu.current.open = false; }}>Profile</Link>
                    <button type="button" onClick={() => {
                      if (profileMenu.current) profileMenu.current.open = false;
                      setSignOutOpen(true);
                    }}>Sign out</button>
                  </div>
                </details>
              </div>
            </header>
            <div className="content">
              {loc.pathname === "/notification" ? (
                <Notifications />
              ) : loc.pathname === "/user/profile" ? (
                <SettingsPage user={user} notify={notify} onUpdate={updateUser} onSignOut={() => setSignOutOpen(true)} />
              ) : loc.pathname === "/admin" ? (
                <>
                  <Admin />
                  {user.role === "SUPER_ADMIN" && <MfaRecoveryReview />}
                </>
              ) : (
                <DisclosureGate key={user.id}>
                  {portfolio ? <NativePortfolio /> : tradingModule ? <LiveTrading module={tradingModule} /> : <Dashboard user={user} notify={notify} />}
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
