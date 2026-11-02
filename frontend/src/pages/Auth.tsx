import React, { useState } from "react";
import { Link, useLocation } from "react-router-dom";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { api } from "../services/api";
import type { User } from "../store/session";
import { PasswordStrength } from "../components/PasswordStrength";
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
  const [busy, setBusy] = useState(false),
    [password, setPassword] = useState("");
  const titles: Record<string, string> = {
    "/login": "Welcome back.",
    "/register": "Your next chapter starts here.",
    "/forgot-password": "Reset your password.",
    "/reset": "Set a new password.",
    "/verify": "Verify your email.",
    "/confirm-email-change": "Confirm your new email.",
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
            : path === "/confirm-email-change"
              ? "confirm-email-change"
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
      if (path === "/login" && d.mfa_required) {
        window.location.assign("/mfa");
        return;
      }
      if (path === "/login") onLogin(d.user);
      else notify(d.message);
    } catch (e) {
      notify((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <div className="auth-layout gnk-auth">
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
          <img
            className="auth-brand-art"
            src="/brand/gnkalgo-brand.jpg"
            alt="GNK ALGO bull and bear brand artwork"
          />
        </div>
        <small>
          Trading involves market risk. Returns are never guaranteed.
        </small>
      </div>
      <div className="auth-form">
        <div className="auth-mobile-brand">
          <Logo />
        </div>
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
          {path === "/register" && (
            <div className="registration-fields">
              <label>
                Gender
                <select
                  aria-label="Gender"
                  name="gender"
                  required
                  defaultValue=""
                >
                  <option value="" disabled>
                    Select gender
                  </option>
                  <option value="female">Female</option>
                  <option value="male">Male</option>
                  <option value="non_binary">Non-binary</option>
                  <option value="prefer_not_to_say">Prefer not to say</option>
                </select>
              </label>
              <label>
                Date of birth
                <input
                  name="date_of_birth"
                  type="date"
                  required
                  min="1900-01-01"
                  max={new Date().toISOString().slice(0, 10)}
                  autoComplete="bday"
                />
              </label>
              <label className="field-wide">
                Mobile number
                <input
                  name="mobile"
                  type="tel"
                  required
                  pattern="\+[1-9][0-9]{7,14}"
                  placeholder="+919876543210"
                  title="International format, for example +919876543210"
                  autoComplete="tel"
                />
              </label>
            </div>
          )}
          {!["/reset", "/verify", "/confirm-email-change"].includes(path) && (
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
                onChange={(e) => setPassword(e.target.value)}
                name="password"
                required
                minLength={path === "/login" ? 1 : 12}
                maxLength={128}
                autoComplete={
                  path === "/login" ? "current-password" : "new-password"
                }
                placeholder="Enter your password"
              />
            </label>
          )}
          {["/register", "/reset"].includes(path) && (
            <PasswordStrength value={password} />
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
          {path === "/login" && (
            <label>
              Authenticator code (if enrolled)
              <input
                name="totp_code"
                inputMode="numeric"
                autoComplete="one-time-code"
                pattern="[0-9]{6}"
                maxLength={6}
                placeholder="6-digit code"
              />
            </label>
          )}
          <button disabled={busy} className="button" type="submit">
            {busy
              ? "Please wait…"
              : path === "/login"
                ? "Sign in"
                : path === "/register"
                  ? "Create account"
                  : path === "/confirm-email-change"
                    ? "Confirm email change"
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
