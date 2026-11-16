import { useEffect, useState } from "react";
import { api } from "../services/api";

type Connection = {
  public_ip: string | null;
  ip_version: 4 | 6 | null;
  detected_at: string;
  egress_status: "configured_unverified" | "not_configured";
};

export function ConnectionIp({ notify }: { notify: (message: string) => void }) {
  const [connection, setConnection] = useState<Connection>();
  const [addresses, setAddresses] = useState<string[]>([]);
  const [lookupError, setLookupError] = useState("");
  const [checking, setChecking] = useState(false);
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api("/ip-management/current")
      .then(result => { if (active) setConnection(result); })
      .catch(() => { if (active) setFailed(true); });
    return () => { active = false; };
  }, []);

  async function copyIp(address: string) {
    try {
      await navigator.clipboard.writeText(address);
      notify("IP copied");
    } catch {
      notify("Clipboard unavailable. Select and copy the address.");
    }
  }

  return <div className="ip-management-grid">
    <section className="settings-card ip-management-card" aria-labelledby="connection-ip-heading">
    <h2 id="connection-ip-heading">IP Whitelist</h2>
    {!connection ? <p role="status">{failed ? "Could not load connection information." : "Checking connection…"}</p> : <>
      <span>Hostname / Public IP</span>
      {connection.public_ip ? <div className="ip-address-row">
        <code>{connection.public_ip}</code>
        <button type="button" onClick={() => void copyIp(connection.public_ip!)}>Copy IP</button>
      </div> : <p>Public IP unavailable through the current connection.</p>}
      {connection.ip_version && <small>IPv{connection.ip_version} · </small>}
      <small>Checked <time dateTime={connection.detected_at}>{new Date(connection.detected_at).toLocaleString()}</time></small>
    </>}
    <form className="ip-lookup" onSubmit={async event => {
      event.preventDefault();
      if (checking) return;
      const value = String(new FormData(event.currentTarget).get("address") ?? "").trim();
      setChecking(true);
      setLookupError("");
      setAddresses([]);
      try {
        const result = await api("/ip-management/verify-address", "POST", { value });
        setAddresses(result.addresses);
      } catch (error) {
        setLookupError((error as Error).message);
      } finally {
        setChecking(false);
      }
    }}>
      <label>Hostname or public IP
        <input name="address" placeholder="49.205.39.45 or example.com" required maxLength={253}
          aria-describedby="ip-lookup-help" autoCapitalize="none" spellCheck={false} readOnly={checking} onChange={() => {
            setAddresses([]);
            setLookupError("");
          }} />
      </label>
      <button type="submit" disabled={checking}>{checking ? "Checking…" : "Verify address"}</button>
    </form>
    <p id="ip-lookup-help" className="ip-lookup-help">Checks whether an entered IP is public or a hostname resolves to public IPv4 or IPv6 addresses. Broker approval is a separate step.</p>
    {lookupError && <p role="alert">{lookupError}</p>}
    {addresses.length > 0 && <div role="status" className="ip-lookup-result">
      <strong>Public address lookup result</strong>
      {addresses.map(address => <div key={address} className="ip-address-row">
        <code>{address}</code>
        <span className="ip-version">{address.includes(":") ? "IPv6" : "IPv4"}</span>
        <button type="button" onClick={() => void copyIp(address)}>Copy IP</button>
      </div>)}
    </div>}
    </section>
  </div>;
}
