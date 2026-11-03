import { useRef, useState } from "react";
import { Link, useLocation, useNavigate } from "react-router-dom";
import { api } from "../services/api";
export function MfaRecoveryPage() {
  const location = useLocation(),
    navigate = useNavigate(),
    confirm = location.pathname === "/mfa-recovery";
  const [busy, setBusy] = useState(false),
    [message, setMessage] = useState(""),
    [done, setDone] = useState(false);
  const pending = useRef(false);
  return (
    <div className="auth-wrap mfa-card">
      <h1>{confirm ? "Confirm MFA recovery" : "Forgot MFA?"}</h1>
      <p>
        {confirm
          ? "Confirm only if you requested authenticator recovery. Opening this page alone makes no account changes."
          : "Use your password and a saved recovery code to receive an email confirmation link. If no recovery code is available, email verification and independent super-administrator approval are required."}
      </p>
      {message && <p role="status">{message}</p>}
      {!done && (
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            if (pending.current) return;
            pending.current = true;
            setBusy(true);
            setMessage("");
            const form = e.currentTarget;
            try {
              if (confirm) {
                const token = new URLSearchParams(location.search).get("token");
                if (!token)
                  throw Error(
                    "Recovery link is missing its token. Request a new link.",
                  );
                const d = await api("/auth/mfa/recovery/confirm", "POST", {
                  token,
                });
                form.reset();
                setDone(true);
                navigate(location.pathname, { replace: true });
                if (d.completed)
                  window.location.replace("/login?mfa=recovered");
                else setMessage(d.message);
              } else {
                const f = Object.fromEntries(new FormData(form));
                const d = await api("/auth/mfa/recovery/request", "POST", {
                  ...f,
                  recovery_code: f.recovery_code || null,
                });
                form.reset();
                setMessage(d.message);
                setDone(true);
              }
            } catch (error) {
              setMessage((error as Error).message);
            } finally {
              pending.current = false;
              setBusy(false);
            }
          }}
        >
          {!confirm && (
            <>
              <label>
                Email address
                <input
                  name="email"
                  type="email"
                  required
                  autoComplete="email"
                />
              </label>
              <label>
                Password
                <input
                  name="password"
                  type="password"
                  required
                  maxLength={128}
                  autoComplete="current-password"
                />
              </label>
              <label>
                Saved recovery code (if available)
                <input
                  name="recovery_code"
                  autoComplete="off"
                  maxLength={40}
                  placeholder="xxxxxxxxxx-xxxxxxxxxx"
                />
              </label>
            </>
          )}
          <button className="button" disabled={busy}>
            {busy
              ? "Please wait…"
              : confirm
                ? "Confirm recovery"
                : "Request recovery link"}
          </button>
        </form>
      )}
      <p>
        Approval is not automatic when all recovery codes are lost. Never share
        an authenticator setup key or recovery code with support.
      </p>
      <Link className="text-link" to="/login">
        Back to sign in
      </Link>
    </div>
  );
}
