import { useEffect, useState } from "react";
import { api } from "../services/api";
export function Brokers({ notify }: { notify: (s: string) => void }) {
  const [items, setItems] = useState<any[]>([]),
    [connections, setConnections] = useState<any[]>([]),
    [search, setSearch] = useState(""),
    [selected, setSelected] = useState<any>(null),
    [busy, setBusy] = useState(false);
  async function reload() {
    const [catalog, accounts] = await Promise.all([
      api("/brokers"),
      api("/brokers/connections"),
    ]);
    setItems(catalog);
    setConnections(accounts);
  }
  useEffect(() => {
    reload().catch((e) => notify(e.message));
  }, []);
  return (
    <>
      <p className="eyebrow">YOUR INDEPENDENT BROKER ACCOUNTS</p>
      <div className="page-heading">
        <div>
          <h1>Brokers & exchanges</h1>
          <p>
            Credentials are encrypted server-side and isolated by account owner.
          </p>
        </div>
        <span className="tag">
          {connections.filter((a) => a.status === "connected").length} CONNECTED
        </span>
      </div>
      <div className="notice">
        <p>
          Authentication availability does not authorize trading. All real-money
          execution remains disabled pending independent broker and production
          approval.
        </p>
      </div>
      <article className="panel">
        <h3>Your connection status</h3>
        {connections.length === 0 ? (
          <p>No broker accounts connected.</p>
        ) : (
          connections.map((a) => (
            <div className="market" key={a.id}>
              <b>
                {a.broker} · {a.account_identifier || "Pending identity"}
              </b>
              <span>{a.status}</span>
              <small>
                {a.expires_at
                  ? "Expires " + new Date(a.expires_at).toLocaleString()
                  : "Expiry not available"}
              </small>
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
            </div>
          ))
        )}
      </article>
      <div className="section-heading">
        <h3>Broker integrations</h3>
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
          .map((b, i) => (
            <article className="broker-card" key={b.id}>
              <div className="broker-card-top">
                <span className={"broker-logo color" + (i % 5)}>
                  {b.name[0]}
                </span>
                <span className="pending">
                  {b.auth_available
                    ? "Authentication available"
                    : "Pending verification"}
                </span>
              </div>
              <h3>{b.name}</h3>
              <p>Live execution unavailable</p>
              <div className="broker-divider" />
              <button
                className="button ghost wide"
                onClick={() => setSelected(b)}
              >
                Setup & authorization
              </button>
            </article>
          ))}
      </div>
      {selected && (
        <div className="modal-backdrop">
          <div
            role="dialog"
            aria-modal="true"
            aria-label="Broker setup"
            className="modal"
          >
            <button
              className="close"
              onClick={() => setSelected(null)}
              aria-label="Close"
            >
              ×
            </button>
            <h2>{selected.name}</h2>
            {!selected.auth_available ? (
              <p>
                This integration is disabled until official application setup
                and authentication have been verified. No credentials are
                collected.
              </p>
            ) : (
              <form
                onSubmit={async (e) => {
                  e.preventDefault();
                  setBusy(true);
                  const body = Object.fromEntries(
                    new FormData(e.currentTarget),
                  );
                  try {
                    const r = await api(
                      "/brokers/" + selected.id + "/connect",
                      "POST",
                      body,
                    );
                    const destination = new URL(r.authorization_url);
                    if (
                      destination.protocol !== "https:" ||
                      destination.hostname !== "api.upstox.com"
                    )
                      throw Error("Unexpected broker authorization URL");
                    window.location.assign(destination.href);
                  } catch (err) {
                    notify((err as Error).message);
                  } finally {
                    setBusy(false);
                  }
                }}
              >
                <label>
                  Credential ownership
                  <select name="mode" style={{ width: "100%", padding: 10 }}>
                    <option value="PLATFORM">
                      Approved platform application
                    </option>
                    <option value="INDIVIDUAL">
                      Your individual API application
                    </option>
                  </select>
                </label>
                <p>
                  For individual mode only, enter your API application
                  key/secret. Never enter a broker password, PIN or OTP.
                </p>
                <label>
                  Individual API client ID
                  <input name="client_id" autoComplete="off" />
                </label>
                <label>
                  Individual API client secret
                  <input
                    name="client_secret"
                    type="password"
                    autoComplete="off"
                  />
                </label>
                <button className="button wide" disabled={busy}>
                  Continue to official broker authorization
                </button>
              </form>
            )}
          </div>
        </div>
      )}
    </>
  );
}
