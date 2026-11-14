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
  const [draft, setDraft] = useState<{broker: string; primary_ip: string; secondary_ip: string | null; status: string} | null>();
  const [source, setSource] = useState<"manual" | "connection">("connection");
  const [saving, setSaving] = useState(false);
  const [draftError, setDraftError] = useState("");
  const [failed, setFailed] = useState(false);

  useEffect(() => {
    let active = true;
    api("/ip-management/current")
      .then(result => { if (active) setConnection(result); })
      .catch(() => { if (active) setFailed(true); });
    api("/ip-management/registrations")
      .then(result => { if (active) setDraft(result.draft); })
      .catch(() => { if (active) setDraftError("Could not load registration draft."); });
    return () => { active = false; };
  }, []);

  async function copyIp(address: string) {
    try {
      await navigator.clipboard.writeText(address);
      notify("Connection IP copied");
    } catch {
      notify("Clipboard unavailable. Select and copy the address.");
    }
  }

  return <div className="ip-management-grid">
    <fieldset className="settings-card ip-management-card ip-mode-picker">
      <legend>Choose one IP option</legend>
      <label><input type="radio" name="ip-mode" checked={source === "connection"}
        onChange={() => setSource("connection")} /> IP Whitelist</label>
      <label><input type="radio" name="ip-mode" checked={source === "manual"}
        onChange={() => setSource("manual")} /> Broker Static IP Registration</label>
    </fieldset>
    {source === "connection" && <section className="settings-card ip-management-card" aria-labelledby="connection-ip-heading">
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
    </section>}
    {source === "manual" && <section className="settings-card ip-management-card" aria-labelledby="static-ip-heading">
    <h2 id="static-ip-heading">Static IP Registration</h2>
    <p>Save addresses for review. Broker verification is required before registration.</p>
    {draftError && <p role="alert">{draftError}</p>}
    {draft !== undefined && (!draft || draft.status === "DRAFT") && <form onSubmit={async event => {
      event.preventDefault();
      if (saving) return;
      const fields = new FormData(event.currentTarget);
      setDraftError("");
      setSaving(true);
      try {
        const result = await api("/ip-management/registrations", "PUT", {
          broker: fields.get("broker"),
          source: "manual",
          primary_ip: String(fields.get("primary_ip")).trim(),
          secondary_ip: String(fields.get("secondary_ip")).trim() || null,
          ownership_confirmed: fields.has("ownership"),
        });
        setDraft(result.draft);
        notify("Static IP draft saved");
      } catch (error) {
        setDraftError((error as Error).message);
      } finally {
        setSaving(false);
      }
    }}>
      <label>Broker <select name="broker" defaultValue={draft?.broker ?? "dhan"}>
        <option value="dhan">Dhan</option><option value="fyers">FYERS</option><option value="upstox">Upstox</option>
      </select></label>
      <label>Primary IPv4 <input name="primary_ip" required maxLength={15} defaultValue={draft?.primary_ip} /></label>
      <label>Secondary IPv4 (optional) <input name="secondary_ip" maxLength={15} defaultValue={draft?.secondary_ip ?? ""} /></label>
      <label><input name="ownership" type="checkbox" required /> I control the addresses provided.</label>
      <button type="submit" disabled={saving}>{saving ? "Saving…" : "Save draft"}</button>
      {draft && <p>Saved draft · Primary IP {draft.primary_ip} · Pending verification</p>}
    </form>}
    {draft?.status === "DRAFT" && <form onSubmit={async event => {
      event.preventDefault();
      if (saving) return;
      const form = event.currentTarget;
      const code = new FormData(form).get("code");
      setSaving(true);
      setDraftError("");
      try {
        const result = await api("/ip-management/registrations/submit", "POST", { code });
        form.reset();
        setDraft({ ...draft, status: result.status });
      } catch (error) {
        setDraftError((error as Error).message);
      } finally {
        setSaving(false);
      }
    }}>
      <label>Authenticator code <input name="code" inputMode="numeric" pattern="[0-9]{6}"
        maxLength={6} autoComplete="one-time-code" required /></label>
      <button disabled={saving}>Submit saved draft</button>
    </form>}
    {draft?.status === "PENDING_ADMIN" && <p>Awaiting GNK administrator review.</p>}
    {draft?.status === "PENDING_BROKER" && <p>GNK review complete. Awaiting broker confirmation.</p>}
    </section>}
  </div>;
}
