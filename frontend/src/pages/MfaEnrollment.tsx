import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
export function MfaEnrollment() {
  const [secret, setSecret] = useState(""),
    [code, setCode] = useState(""),
    [message, setMessage] = useState(""),
    [enabled, setEnabled] = useState<boolean | null>(null),
    [busy, setBusy] = useState(false);
  const submitting = useRef(false);
  useEffect(() => {
    let live = true;
    api("/auth/mfa/status")
      .then((d) => live && setEnabled(d.enabled))
      .catch((e) => live && setMessage(e.message));
    return () => {
      live = false;
    };
  }, []);
  async function action(task: () => Promise<void>) {
    if (submitting.current) return;
    submitting.current = true;
    setBusy(true);
    setMessage("");
    try {
      await task();
    } catch (e) {
      setCode("");
      setMessage((e as Error).message);
    } finally {
      submitting.current = false;
      setBusy(false);
    }
  }
  return (
    <div className="auth-wrap">
      <h1>
        {enabled
          ? "Authenticator protection is enabled"
          : "Secure your account"}
      </h1>
      <p>
        {enabled
          ? "Use the GNK ALGO entry in your authenticator when signing in. Each accepted code can be used only once."
          : "Enroll an authenticator before accessing your workspace. Keep the setup key private."}
      </p>
      {message && <p role="alert">{message}</p>}
      {enabled ? (
        <Link className="button" to="/user/settings">
          Return to account settings
        </Link>
      ) : (
        <>
          <button
            disabled={busy || enabled === null}
            className="button"
            onClick={() =>
              action(async () => {
                const d = await api("/auth/mfa/setup", "POST");
                setSecret(d.secret);
              })
            }
          >
            {busy
              ? "Please wait…"
              : secret
                ? "Show existing setup key"
                : "Generate authenticator setup key"}
          </button>
          {secret && (
            <form
              style={{ maxWidth: 450, margin: "30px auto" }}
              onSubmit={(e) => {
                e.preventDefault();
                action(async () => {
                  await api("/auth/mfa/confirm", "POST", { code });
                  window.location.assign("/user/dashboard");
                });
              }}
            >
              <p>
                Add an account named GNK ALGO in your authenticator, using this
                key:
              </p>
              <code style={{ wordBreak: "break-all" }}>{secret}</code>
              <label>
                Confirmation code
                <input
                  required
                  pattern="[0-9]{6}"
                  maxLength={6}
                  autoComplete="one-time-code"
                  inputMode="numeric"
                  value={code}
                  disabled={busy}
                  onChange={(e) =>
                    setCode(e.target.value.replace(/[^0-9]/g, "").slice(0, 6))
                  }
                  onPaste={(e) => {
                    e.preventDefault();
                    setCode(
                      e.clipboardData
                        .getData("text")
                        .replace(/[^0-9]/g, "")
                        .slice(0, 6),
                    );
                  }}
                />
              </label>
              <p>
                Keep automatic date and time enabled on your phone. After
                confirmation, continue to the dashboard; a new sign-in requires
                a fresh code.
              </p>
              <button disabled={busy} className="button">
                {busy ? "Verifying…" : "Confirm enrollment"}
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
