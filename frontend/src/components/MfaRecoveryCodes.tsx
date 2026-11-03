import { useState } from "react";
import { api } from "../services/api";
export function MfaRecoveryCodes() {
  const [open, setOpen] = useState(false),
    [codes, setCodes] = useState<string[]>([]),
    [busy, setBusy] = useState(false),
    [message, setMessage] = useState("");
  return (
    <div className="mfa-backup">
      <button
        className="settings-text-button"
        onClick={() => {
          setOpen(!open);
          setCodes([]);
          setMessage("");
        }}
      >
        Manage MFA recovery codes
      </button>
      {open && (
        <>
          <p>
            Generate ten new single-use recovery codes. This invalidates
            previous codes and pending recovery requests.
          </p>
          {message && <p role="alert">{message}</p>}
          {codes.length ? (
            <>
              <div className="recovery-code-grid">
                {codes.map((c) => (
                  <code key={c}>{c}</code>
                ))}
              </div>
              <p>
                Save these codes privately. They will not be shown again after
                leaving this view.
              </p>
              <button
                className="subtle-button"
                onClick={() => {
                  setCodes([]);
                  setOpen(false);
                }}
              >
                I have saved my codes
              </button>
            </>
          ) : (
            <form
              className="settings-inline"
              onSubmit={async (e) => {
                e.preventDefault();
                if (busy) return;
                const form = e.currentTarget;
                const f = Object.fromEntries(new FormData(form));
                setBusy(true);
                setMessage("");
                try {
                  const d = await api("/auth/mfa/recovery/codes", "POST", f);
                  form.reset();
                  setCodes(d.recovery_codes);
                } catch (error) {
                  setMessage((error as Error).message);
                } finally {
                  setBusy(false);
                }
              }}
            >
              <label>
                Current password
                <input
                  name="current_password"
                  type="password"
                  autoComplete="current-password"
                  required
                />
              </label>
              <label>
                Authenticator code
                <input
                  name="code"
                  pattern="[0-9]{6}"
                  inputMode="numeric"
                  maxLength={6}
                  autoComplete="one-time-code"
                  required
                />
              </label>
              <button className="settings-primary" disabled={busy}>
                Generate new recovery codes
              </button>
            </form>
          )}
        </>
      )}
    </div>
  );
}
