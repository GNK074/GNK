import { useState } from "react";
import { api } from "../services/api";

export function DhanConsent({
  callbackUrl = `${location.origin}/api/v1/dhan/oauth/callback`,
}: { callbackUrl?: string }) {
  const [client, setClient] = useState("");
  const [app, setApp] = useState("");
  const [secret, setSecret] = useState("");
  const [consent, setConsent] = useState(false);
  const [saved, setSaved] = useState(false);
  const [busy, setBusy] = useState(false);
  const [note, setNote] = useState("");

  function clearDetails() {
    setClient("");
    setApp("");
    setSecret("");
    setConsent(false);
    setSaved(false);
  }

  async function connect() {
    if (!saved || busy) return;
    setBusy(true);
    setNote("");
    try {
      await api("/auth/session");
      const result = await api("/dhan/oauth/start", "POST", {
        client_id: client.trim(),
        app_id: app,
        app_secret: secret,
        owns_account: consent,
        terms_accepted: consent,
      });
      clearDetails();
      const destination = new URL(result.authorization_url);
      if (destination.origin !== "https://auth.dhan.co") throw Error("Invalid Dhan destination.");
      location.assign(destination.href);
    } catch (error) {
      clearDetails();
      setNote((error as Error).message);
      setBusy(false);
    }
  }

  return (
    <section className="market-card">
      <h2>{saved ? "Step 3 · Connect broker" : "Step 2 · Save broker details"}</h2>
      <p>Register this callback in your individual Dhan application.</p>
      <p><code>{callbackUrl}</code>{" "}
        <button type="button" onClick={async () => {
          try {
            await navigator.clipboard.writeText(callbackUrl);
            setNote("Callback URL copied.");
          } catch {
            setNote("Select and copy the callback URL manually.");
          }
        }}>Copy</button>
      </p>
      {saved ? (
        <>
          <p>Continue to Dhan to authorize this account. Enter your PIN and authenticator on Dhan’s website.</p>
          <button type="button" disabled={busy} onClick={() => void connect()}>
            {busy ? "Connecting…" : "Connect broker"}
          </button>
          <button type="button" disabled={busy} onClick={() => setSaved(false)}>Edit details</button>
          <button type="button" disabled={busy} onClick={clearDetails}>Cancel</button>
        </>
      ) : (
        <form onSubmit={event => {
          event.preventDefault();
          if (!app.trim() || !secret.trim()) {
            setNote("Enter your Dhan application key and secret.");
            return;
          }
          setNote("");
          setSaved(true);
        }}>
          <div className="market-controls">
            <label>Client ID<input required maxLength={100} pattern="[A-Za-z0-9_\-]+" value={client}
              onChange={event => setClient(event.target.value)} /></label>
            <label>Application key<input required type="password" autoComplete="off" maxLength={4096}
              value={app} onChange={event => setApp(event.target.value)} /></label>
            <label>Application secret<input required type="password" autoComplete="off" maxLength={4096}
              value={secret} onChange={event => setSecret(event.target.value)} /></label>
          </div>
          <label><input type="checkbox" required checked={consent} onChange={event => setConsent(event.target.checked)} />
            I own this account and authorize GNK to verify it under the service terms.
          </label>
          <p>Details stay in this page until you connect.</p>
          <button type="submit">Save Details</button>
          <button type="button" onClick={() => { clearDetails(); setNote(""); }}>Cancel</button>
        </form>
      )}
      <p role="status">{note}</p>
    </section>
  );
}
