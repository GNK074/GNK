import { SignOutDialog } from "../components/SignOutDialog";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { QRCodeSVG } from "qrcode.react";
import { api } from "../services/api";
export function MfaEnrollment() {
  const [secret, setSecret] = useState(""),
    [uri, setUri] = useState(""),
    [code, setCode] = useState(""),
    [message, setMessage] = useState(""),
    [enabled, setEnabled] = useState<boolean | null>(null),
    [busy, setBusy] = useState(false),
    [recoveryCodes, setRecoveryCodes] = useState<string[]>([]),
    [saved, setSaved] = useState(false);
  const submitting = useRef(false);
  const [signOutOpen,setSignOutOpen]=useState(false);
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
    <div className="auth-wrap mfa-card">
      {signOutOpen && <SignOutDialog onClose={()=>setSignOutOpen(false)} onSignedOut={()=>window.location.replace("/login")} onError={setMessage}/>}
      <button type="button" className="text-link" onClick={()=>setSignOutOpen(true)}>Sign out</button>
      <h1>
        {recoveryCodes.length
          ? "Save your recovery codes"
          : enabled
            ? "Authenticator protection is enabled"
            : "Secure your account"}
      </h1>
      <p>
        {recoveryCodes.length
          ? "Store these single-use codes in a safe place. You will need one if you lose your authenticator. They are shown only once."
          : enabled
            ? "Use the GNK ALGO authenticator entry when signing in."
            : "Enroll an authenticator before accessing your workspace. Keep the setup key private."}
      </p>
      {message && <p role="alert">{message}</p>}
      {recoveryCodes.length > 0 ? (
        <>
          <div className="recovery-code-grid">
            {recoveryCodes.map((value) => (
              <code key={value}>{value}</code>
            ))}
          </div>
          <button
            className="subtle-button"
            onClick={async () => {
              try {
                await navigator.clipboard.writeText(recoveryCodes.join("\n"));
                setMessage("Recovery codes copied. Store them privately.");
              } catch {
                setMessage("Select and copy the codes manually.");
              }
            }}
          >
            Copy recovery codes
          </button>
          <label className="mfa-checkbox">
            <input
              type="checkbox"
              checked={saved}
              onChange={(e) => setSaved(e.target.checked)}
            />
            I have saved my recovery codes securely.
          </label>
          <button
            className="button"
            disabled={!saved}
            onClick={() => window.location.assign("/user/dashboard")}
          >
            Continue to dashboard
          </button>
        </>
      ) : enabled ? (
        <>
          <Link className="button" to="/user/settings">
            Return to account settings
          </Link>
          <Link className="text-link" to="/forgot-mfa">
            Forgot MFA?
          </Link>
        </>
      ) : (
        <>
          <button
            disabled={busy || enabled === null}
            className="button"
            onClick={() =>
              action(async () => {
                const d = await api("/auth/mfa/setup", "POST");
                setSecret(d.secret);
                setUri(d.provisioning_uri);
              })
            }
          >
            {busy
              ? "Please wait…"
              : secret
                ? "Show existing setup"
                : "Generate setup QR code"}
          </button>
          {secret && (
            <form
              onSubmit={(e) => {
                e.preventDefault();
                action(async () => {
                  const d = await api("/auth/mfa/confirm", "POST", { code });
                  setSecret("");
                  setUri("");
                  setCode("");
                  setEnabled(true);
                  setRecoveryCodes(d.recovery_codes);
                });
              }}
            >
              <div
                className="mfa-qr"
                role="img"
                aria-label="Scan this private QR code with your authenticator app"
              >
                <QRCodeSVG value={uri} size={224} marginSize={4} level="M" />
              </div>
              <p>
                Scan with Google Authenticator, Microsoft Authenticator or
                another TOTP app. The QR code is generated on your device.
              </p>
              <details>
                <summary>Enter the setup key manually</summary>
                <p>Use time-based SHA-1, 6 digits and a 30-second interval.</p>
                <code className="mfa-secret">{secret}</code>
              </details>
              <label>
                Authenticator code
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
                />
              </label>
              <p>Keep automatic date and time enabled on your phone.</p>
              <button disabled={busy} className="button">
                {busy ? "Verifying…" : "Confirm enrollment"}
              </button>
            </form>
          )}
          {enabled === null && message && (
            <Link className="text-link" to="/login">
              Back to sign in
            </Link>
          )}
        </>
      )}
    </div>
  );
}
