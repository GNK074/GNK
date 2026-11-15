import { BrainCircuit } from "lucide-react";
import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import "./broker-directory.css";

export const BROKER_SETUP_LABEL = "Broker_Stepup";

type Broker = {
  id: string;
  name: string;
  steps: string[];
  portal_url: string | null;
  docs_url: string | null;
};

type Connection = { id: string; broker: string };

export function BrokerDirectory({ path }: { path: string }) {
  const [data, setData] = useState<{ brokers: Broker[]; connections: Connection[] }>();
  const [failed, setFailed] = useState(false);
  const [query, setQuery] = useState("");
  useEffect(() => {
    let active = true;
    Promise.all([api("/brokers"), api("/broker-connections")])
      .then(([brokers, connections]) => {
        if (active) setData({ brokers, connections });
      })
      .catch(() => {
        if (active) setFailed(true);
      });
    return () => { active = false; };
  }, []);

  if (failed) return <p role="alert">Broker information could not be loaded. Refresh to retry.</p>;
  if (!data) return <p role="status">Loading broker information…</p>;

  const detail = /^\/user\/brokers\/(setup|help)\/([a-z0-9-]+)$/.exec(path);
  if (detail) {
    const broker = data.brokers.find(({ id }) => id === detail[2]);
    return (
      <>
        <Link to="/user/brokers">All brokers</Link>
        {broker ? (
          <article className="panel">
            <h1>{broker.name} {detail[1] === "help" ? "help" : "setup"}</h1>
            <p>New connections through this workspace are currently unavailable.</p>
            <ol>{broker.steps.map(step => <li key={step}>{step}</li>)}</ol>
            {broker.portal_url && <p><a href={broker.portal_url}>Broker portal</a></p>}
            {broker.docs_url && <p><a href={broker.docs_url}>Official API documentation</a></p>}
            {detail[1] === "setup" && <Link to={`/user/brokers/help/${broker.id}`}>Broker help</Link>}
          </article>
        ) : <p>Broker not found.</p>}
      </>
    );
  }

  if (path !== "/user/brokers") return <Link to="/user/brokers">Back to {BROKER_SETUP_LABEL}</Link>;

  const visible = data.brokers.filter(broker =>
    broker.name.toLowerCase().includes(query.trim().toLowerCase())
  );
  return (
    <>
      <div className="page-heading">
        <h1 className="broker-setup-heading">
          <BrainCircuit className="broker-setup-icon" size={28} aria-hidden="true" />
          {BROKER_SETUP_LABEL}
        </h1>
      </div>
      <article className="panel">
        <h2>Available brokers</h2>
        <label htmlFor="broker-search">Search brokers</label>
        <input id="broker-search" type="search" placeholder="Search or Select Broker"
          value={query} onChange={event => setQuery(event.target.value)} />
        {visible.length === 0 && <p role="status">No matching brokers.</p>}
        {visible.map(broker => (
          <div className="market" key={broker.id}>
            <strong>{broker.name}</strong>
            <span>{data.connections.filter(connection => connection.broker === broker.id).length} accounts</span>
            <Link to={`/user/brokers/setup/${broker.id}`}>Setup guide</Link>
          </div>
        ))}
      </article>
    </>
  );
}
