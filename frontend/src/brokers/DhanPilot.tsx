import { useEffect, useState } from "react";
import { api } from "../services/api";
import "../markets/markets.css";
import "../portfolio/portfolio.css";

const kinds = ["holdings", "positions", "funds", "orders", "trades"] as const;
type Kind = typeof kinds[number];
type PilotStatus = { connected: boolean; expires_at: string | null };

export function DhanPilot() {
  const [status, setStatus] = useState<PilotStatus>();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [ip, setIp] = useState("");
  const [kind, setKind] = useState<Kind>("holdings");
  const [result, setResult] = useState<{ data: Record<string, unknown>[]; fetched_at: string }>();

  useEffect(() => {
    let mounted = true;
    async function refreshStatus() {
      try {
        const next = await api("/dhan/pilot/session");
        if (!mounted) return;
        setStatus(next);
        if (!next.connected) { setResult(undefined); setIp(""); }
      } catch (error) {
        if (mounted) setError((error as Error).message);
      }
    }
    void refreshStatus();
    const timer = window.setInterval(refreshStatus, 15000);
    return () => { mounted = false; window.clearInterval(timer); };
  }, []);

  async function run(action: () => Promise<void>) {
    setBusy(true);
    setError("");
    try { await action(); }
    catch (error) { setError((error as Error).message); }
    finally { setBusy(false); }
  }

  return <section className="market-card">
    <h2>Dhan read-only pilot</h2>
    <p>This browser login can use a verified Dhan session for up to 15 minutes. Reconnect after expiry or a server restart. Pilot portfolio results appear here.</p>
    <p role="status">{status ? status.connected ? "Connected" : "Reauthentication required" : "Checking session…"}</p>
    {error && <p role="alert">{error}</p>}
    <form autoComplete="off" onSubmit={event => {
      event.preventDefault();
      const form = event.currentTarget;
      const fields = new FormData(form);
      form.reset();
      void run(async () => {
        setResult(undefined);
        setIp("");
        await api("/auth/session");
        try {
          setStatus(await api("/dhan/pilot/session", "POST", {
            client_id: String(fields.get("client_id")).trim(),
            access_token: String(fields.get("access_token")).trim(),
            owns_account: fields.get("owns_account") === "on",
          }));
        } catch (error) {
          setStatus(await api("/dhan/pilot/session").catch(() => undefined));
          throw error;
        }
      });
    }}>
      <fieldset className="pf-filters" disabled={busy}>
        <label>Dhan Client ID<input name="client_id" required maxLength={64} autoComplete="off" /></label>
        <label>Dhan access token<input name="access_token" type="password" required maxLength={16384} autoComplete="off" /></label>
        <label><input name="owns_account" type="checkbox" required /> I own this Dhan account</label>
        <button type="submit">{status?.connected ? "Reconnect" : "Verify and connect"}</button>
      </fieldset>
    </form>
    {status?.connected && <div className="pf-toolbar">
      <button disabled={busy} onClick={() => run(async () => {
        await api("/auth/session");
        setStatus(await api("/dhan/pilot/session", "DELETE"));
        setResult(undefined);
        setIp("");
      })}>Disconnect pilot</button>
      <button disabled={busy} onClick={() => run(async () => {
        setIp("");
        const { data } = await api("/dhan/pilot/ip");
        setIp(data.state === "MATCH" ? "The configured GNK egress IP matches a Dhan whitelist entry."
          : data.state === "NO_MATCH" ? "The configured GNK egress IP does not match a Dhan whitelist entry."
          : "The operator has not configured the GNK egress IP.");
      })}>Check Dhan IP whitelist</button>
      <label>Portfolio data<select disabled={busy} value={kind} onChange={event => {
        setKind(event.target.value as Kind);
        setResult(undefined);
      }}>{kinds.map(item => <option key={item}>{item}</option>)}</select></label>
      <button disabled={busy} onClick={() => run(async () => {
        setResult(undefined);
        setResult(await api("/dhan/pilot/portfolio/" + kind));
      })}>Refresh {kind}</button>
    </div>}
    {ip && <p role="status">{ip}</p>}
    {result && <div className="pf-table-wrap">
      <p>Fetched {new Date(result.fetched_at).toLocaleString()} · {result.data.length} records</p>
      {result.data.length > 0 && <table><thead><tr>
        {Object.keys(result.data[0]).map(key => <th key={key} scope="col">{key.replaceAll("_", " ")}</th>)}
      </tr></thead><tbody>{result.data.map((row, index) => <tr key={index}>
        {Object.keys(result.data[0]).map(key => <td key={key}>{String(row[key] ?? "—")}</td>)}
      </tr>)}</tbody></table>}
    </div>}
  </section>;
}
