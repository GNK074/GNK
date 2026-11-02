import { useState } from "react";
import { api } from "../services/api";
export function BrokerApprovals() {
  const [broker, setBroker] = useState("upstox"),
    [requirements, setRequirements] = useState<any[]>([]),
    [message, setMessage] = useState("");
  async function load() {
    try {
      const d = await api(`/admin/brokers/${broker}/requirements`);
      setRequirements(d.requirements);
    } catch (e) {
      setMessage((e as Error).message);
    }
  }
  return (
    <article className="panel" style={{ marginTop: 25 }}>
      <p className="eyebrow">SUPER ADMIN · EVIDENCE REVIEW</p>
      <h2>Broker production gate</h2>
      <p>
        Each broker requires 18 independent, current evidence records. Live
        execution is unavailable in this release; recording evidence cannot
        enable it.
      </p>
      {message && <p role="status">{message}</p>}
      <label>
        Broker
        <select
          value={broker}
          onChange={(e) => {
            setBroker(e.target.value);
            setRequirements([]);
          }}
          style={{ padding: 10 }}
        >
          {[
            "upstox",
            "dhan",
            "zerodha",
            "angelone",
            "fyers",
            "5paisa",
            "icici",
          ].map((b) => (
            <option key={b}>{b}</option>
          ))}
        </select>
      </label>
      <div style={{ display: "flex", gap: 10, flexWrap: "wrap" }}>
        <button
          className="button ghost"
          onClick={async () => {
            try {
              await api(`/admin/brokers/${broker}/approval`, "POST");
              await load();
            } catch (e) {
              setMessage((e as Error).message);
            }
          }}
        >
          Create review request
        </button>
        <button className="button ghost" onClick={load}>
          Refresh requirements
        </button>
      </div>
      {requirements.map((r) => (
        <div className="check-row" key={r.id}>
          <b>{String(r.id).padStart(2, "0")}</b>
          {r.name}
          <small>{r.passed ? "Evidence current" : "Pending / expired"}</small>
        </div>
      ))}
      <form
        onSubmit={async (e) => {
          e.preventDefault();
          const f = Object.fromEntries(new FormData(e.currentTarget));
          try {
            await api(
              `/admin/brokers/${broker}/requirements/${f.requirement}/verify`,
              "POST",
              {
                reference: f.reference,
                sha256: f.sha256,
                expires_at: new Date(String(f.expires_at)).toISOString(),
              },
            );
            setMessage(
              "Evidence attestation recorded. Production remains blocked.",
            );
            await load();
          } catch (err) {
            setMessage((err as Error).message);
          }
        }}
      >
        <label>
          Requirement number
          <input name="requirement" type="number" min={1} max={18} required />
        </label>
        <label>
          Evidence reference (HTTPS or evidence registry)
          <input
            name="reference"
            required
            minLength={10}
            placeholder="https://your-evidence-registry/review-id"
          />
        </label>
        <label>
          Evidence file SHA-256
          <input name="sha256" pattern="[a-f0-9]{64}" required />
        </label>
        <label>
          Evidence expires (within 90 days)
          <input name="expires_at" type="datetime-local" required />
        </label>
        <p>
          This records your attestation; it does not fetch or independently
          authenticate the external evidence file.
        </p>
        <button className="button ghost">Record reviewed evidence</button>
      </form>
      <button
        className="danger"
        style={{ marginTop: 25 }}
        onClick={async () => {
          try {
            await api(`/admin/brokers/${broker}/production-approval`, "POST");
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        Run production approval gate
      </button>
    </article>
  );
}
