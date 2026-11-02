import { useEffect, useState } from "react";
import { api } from "../services/api";
type Field = { name: string; label: string; secret: boolean };
type Broker = {
  id: string;
  name: string;
  individual_available: boolean;
  auth_available: boolean;
  connection_blocker: string | null;
  fields: Field[];
  steps: string[];
  docs_url: string | null;
  portal_url: string | null;
};
export function Brokers({ notify }: { notify: (s: string) => void }) {
  const [items, setItems] = useState<Broker[]>([]),
    [accounts, setAccounts] = useState<any[]>([]),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<Broker | null>(null),
    [busy, setBusy] = useState(false);
  async function reload() {
    const [catalog, connections] = await Promise.all([
      api("/brokers"),
      api("/brokers/connections"),
    ]);
    setItems(catalog);
    setAccounts(connections);
  }
  useEffect(() => {
    reload().catch((e) => notify(e.message));
    const result = new URLSearchParams(window.location.search).get("result");
    if (result === "connected") notify("Broker authorization completed.");
    if (result === "failed")
      notify("Broker authorization failed. Please reconnect.");
  }, []);
  const count = accounts.filter((a) => a.status === "connected").length;
  return (
    <>
      <p className="eyebrow">CONNECT YOUR OWN BROKER ACCOUNT</p>
      <div className="page-heading">
        <div>
          <h1>Brokers & exchanges</h1>
          <p>
            Use your individual broker API credentials. Every account is
            isolated and encrypted.
          </p>
        </div>
        <span className="tag">{count} CONNECTED</span>
      </div>
      <div className="notice">
        <p>
          Account connection validates your broker identity. Order execution is
          a separate permission and remains disabled in this release.
        </p>
      </div>
      <article className="panel">
        <div className="panel-title">
          <h3>Your connection status</h3>
          <button
            className="button ghost"
            onClick={() => reload().catch((e) => notify(e.message))}
          >
            Refresh
          </button>
        </div>
        {accounts.length === 0 ? (
          <p>
            No broker accounts connected yet. Choose a broker below and enter
            your own API session credentials.
          </p>
        ) : (
          accounts.map((a) => (
            <div className="market" key={a.id} style={{ flexWrap: "wrap" }}>
              <b>
                {a.broker} · {a.account_identifier || "Pending identity"}
              </b>
              <span>{a.status}</span>
              <small>
                {a.verified_at
                  ? "Last verified " + new Date(a.verified_at).toLocaleString()
                  : ""}
                {a.expires_at
                  ? " · Session deadline " +
                    new Date(a.expires_at).toLocaleString()
                  : ""}
              </small>
              <button
                className="button ghost"
                onClick={() =>
                  setSelected(items.find((b) => b.id === a.broker) || null)
                }
              >
                Reconnect / replace session
              </button>
              {a.status !== "disconnected" && (
                <button
                  className="danger"
                  onClick={async () => {
                    try {
                      notify(
                        (
                          await api(
                            `/brokers/${a.broker}/${a.id}/disconnect`,
                            "POST",
                          )
                        ).message,
                      );
                      await reload();
                    } catch (e) {
                      notify((e as Error).message);
                    }
                  }}
                >
                  Disconnect locally
                </button>
              )}
            </div>
          ))
        )}
      </article>
      <div className="section-heading">
        <h3>Choose your broker</h3>
        <input
          aria-label="Search brokers"
          style={{ maxWidth: 280 }}
          placeholder="Search brokers…"
          value={search}
          onChange={(e) => setSearch(e.target.value)}
        />
      </div>
      <div className="broker-grid">
        {items
          .filter((b) => b.name.toLowerCase().includes(search.toLowerCase()))
          .map((b, i) => {
            const linked = accounts.some(
              (a) => a.broker === b.id && a.status === "connected",
            );
            return (
              <article className="broker-card" key={b.id}>
                <div className="broker-card-top">
                  <span className={"broker-logo color" + (i % 5)}>
                    {b.name[0]}
                  </span>
                  <span
                    className="pending"
                    style={
                      linked ? { background: "#153b32", color: "#65dfc5" } : {}
                    }
                  >
                    {linked
                      ? "Account connected"
                      : b.individual_available
                        ? "Individual setup available"
                        : b.fields.length
                          ? "Server setup required"
                          : "Integration planned"}
                  </span>
                </div>
                <h3>{b.name}</h3>
                <p>
                  {b.individual_available
                    ? "Validate your own API session"
                    : "View broker-specific setup requirements"}
                </p>
                <div className="broker-divider" />
                <button
                  className="button ghost wide"
                  onClick={() => setSelected(b)}
                >
                  {b.individual_available
                    ? "Connect your account"
                    : "Setup instructions"}
                </button>
              </article>
            );
          })}
      </div>
      {selected && (
        <div className="modal-backdrop">
          <div
            role="dialog"
            aria-modal="true"
            aria-label={selected.name + " individual broker setup"}
            className="modal"
            style={{ maxHeight: "90vh", overflowY: "auto", maxWidth: 640 }}
          >
            <button
              className="close"
              aria-label="Close"
              onClick={() => setSelected(null)}
            >
              ×
            </button>
            <p className="eyebrow">YOUR INDIVIDUAL API CREDENTIALS</p>
            <h2>Connect {selected.name}</h2>
            <ol style={{ paddingLeft: 20, lineHeight: 1.8, color: "#9daec4" }}>
              {selected.steps.map((step) => (
                <li key={step}>{step}</li>
              ))}
            </ol>
            <div style={{ display: "flex", gap: 20, marginBottom: 15 }}>
              {selected.portal_url && (
                <a
                  className="text-link"
                  href={selected.portal_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  Official broker portal ↗
                </a>
              )}
              {selected.docs_url && (
                <a
                  className="text-link"
                  href={selected.docs_url}
                  target="_blank"
                  rel="noopener noreferrer"
                >
                  API setup documentation ↗
                </a>
              )}
            </div>
            {selected.connection_blocker && (
              <div className="notice">
                <p>{selected.connection_blocker}</p>
              </div>
            )}
            {selected.individual_available && (
              <form
                key={selected.id}
                onSubmit={async (e) => {
                  e.preventDefault();
                  setBusy(true);
                  const form = e.currentTarget;
                  const f = new FormData(form);
                  const credentials = Object.fromEntries(
                    selected.fields.map((field) => [
                      field.name,
                      f.get(field.name),
                    ]),
                  );
                  try {
                    const result = await api(
                      `/brokers/${selected.id}/individual`,
                      "POST",
                      {
                        credentials,
                        owns_account: f.get("owns_account") === "on",
                        terms_accepted: f.get("terms_accepted") === "on",
                      },
                    );
                    form.reset();
                    setSelected(null);
                    await reload();
                    notify(result.message);
                  } catch (err) {
                    notify((err as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <p>
                  Enter API credentials only. Never enter a broker login
                  password, PIN, OTP or authenticator seed.
                </p>
                {selected.fields.map((field) => (
                  <label key={field.name}>
                    {field.label}
                    <input
                      name={field.name}
                      type={field.secret ? "password" : "text"}
                      required
                      autoComplete="off"
                      maxLength={16384}
                      spellCheck={false}
                    />
                  </label>
                ))}
                <label className="checkbox">
                  <input type="checkbox" name="owns_account" required />I own
                  this broker account and am authorized to connect its API
                  session.
                </label>
                <label className="checkbox">
                  <input type="checkbox" name="terms_accepted" required />I have
                  reviewed the broker's individual-app terms and permit
                  encrypted storage of my API session for this account.
                </label>
                <button className="button wide" disabled={busy}>
                  {busy
                    ? "Verifying with broker…"
                    : "Verify identity & save connection"}
                </button>
              </form>
            )}
            <p style={{ fontSize: 11 }}>
              No test orders are placed. This verifies your current account
              session, not ongoing market access or trading approval. For a
              broker login that needs an application callback, register{" "}
              <code style={{ wordBreak: "break-all" }}>
                https://api.gnkalgo.com/api/v1/brokers/{selected.id}/callback
              </code>{" "}
              only when that broker's setup supports it; a manual API-session
              check does not implement every broker's automatic OAuth flow.
            </p>
          </div>
        </div>
      )}
    </>
  );
}
