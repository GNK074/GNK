import { useState } from "react";
import { api } from "../services/api";
type Recovery = { id: string; email: string; created: string; expires: string };
export function MfaRecoveryReview() {
  const [rows, setRows] = useState<Recovery[]>([]),
    [selected, setSelected] = useState(""),
    [message, setMessage] = useState(""),
    [busy, setBusy] = useState(false);
  async function load() {
    setBusy(true);
    try {
      setRows(await api("/admin/mfa-recovery/requests"));
      setMessage("");
    } catch (e) {
      setMessage((e as Error).message);
    } finally {
      setBusy(false);
    }
  }
  return (
    <section className="panel">
      <h2>MFA recovery review</h2>
      <p>
        These requests have verified their email but have no recovery code.
        Independently verify account ownership before approving.
        Super-administrator recovery is handled outside this flow.
      </p>
      <button className="button ghost" disabled={busy} onClick={load}>
        Load recovery requests
      </button>
      {message && <p role="status">{message}</p>}
      {rows.map((r) => (
        <div key={r.id} className="setting-row">
          <div>
            <strong>{r.email}</strong>
            <p>Expires {new Date(r.expires).toLocaleString()}</p>
          </div>
          <button className="subtle-button" onClick={() => setSelected(r.id)}>
            Review
          </button>
        </div>
      ))}
      {selected && (
        <form
          className="settings-inline"
          onSubmit={async (e) => {
            e.preventDefault();
            if (busy) return;
            const form = e.currentTarget;
            const f = Object.fromEntries(new FormData(form));
            setBusy(true);
            try {
              await api(
                `/admin/mfa-recovery/requests/${selected}/approve`,
                "POST",
                {
                  current_password: f.current_password,
                  code: f.code,
                  identity_verified: f.identity_verified === "on",
                },
              );
              form.reset();
              setSelected("");
              setRows(rows.filter((r) => r.id !== selected));
              setMessage(
                "Recovery approved. User must enroll a new authenticator.",
              );
            } catch (error) {
              setMessage((error as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          <label>
            Your current password
            <input
              name="current_password"
              type="password"
              autoComplete="current-password"
              required
            />
          </label>
          <label>
            Your authenticator code
            <input
              name="code"
              pattern="[0-9]{6}"
              maxLength={6}
              inputMode="numeric"
              autoComplete="one-time-code"
              required
            />
          </label>
          <label className="mfa-checkbox">
            <input name="identity_verified" type="checkbox" required />I
            independently verified this user’s identity and account ownership.
          </label>
          <button className="settings-primary" disabled={busy}>
            Approve recovery and revoke sessions
          </button>
          <button
            type="button"
            className="subtle-button"
            onClick={() => setSelected("")}
          >
            Cancel
          </button>
        </form>
      )}
    </section>
  );
}
