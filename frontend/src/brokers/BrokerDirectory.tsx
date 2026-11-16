import { BrainCircuit } from "lucide-react";
import { useEffect, useRef, useState } from "react";
import { DhanConsent } from "./DhanConsent";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { api } from "../services/api";
import "./broker-directory.css";

export const BROKER_SETUP_LABEL = "Broker Setup";

type Broker = {
  id: string;
  name: string;
  steps: string[];
  portal_url: string | null;
  docs_url: string | null;
  browser_consent_available: boolean;
  browser_callback_url: string | null;
};

export function BrokerDirectory({ path }: { path: string }) {
  const [data, setData] = useState<Broker[]>();
  const [failed, setFailed] = useState(false);
  const [params] = useSearchParams();
  const picker = useRef<HTMLDialogElement>(null);
  const [pickerQuery, setPickerQuery] = useState("");
  const [selection, setSelection] = useState("");
  const navigate = useNavigate();
  useEffect(() => {
    let active = true;
    api("/brokers")
      .then(brokers => {
        if (active) setData(brokers);
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
    const broker = data.find(({ id }) => id === detail[2]);
    return (
      <>
        <Link to="/user/brokers">Change broker</Link>
        {broker ? (
          <article className="panel">
            <h1>{broker.name} {detail[1] === "help" ? "help" : "setup"}</h1>
            {broker.id !== "dhan" && <p>Coming soon</p>}
            {broker.id === "dhan" && !broker.browser_consent_available && <p>Dhan authorization is currently disabled.</p>}
            {detail[1] === "setup" && broker.browser_consent_available && broker.browser_callback_url &&
              <DhanConsent callbackUrl={broker.browser_callback_url} />}
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

  return (
    <>
      <div className="page-heading">
        <h1 className="broker-setup-heading">
          <BrainCircuit className="broker-setup-icon" size={28} aria-hidden="true" />
          {BROKER_SETUP_LABEL}
        </h1>
        <button type="button" onClick={() => {
          setPickerQuery("");
          setSelection("");
          picker.current?.showModal();
        }}>Add Broker</button>
      </div>
      <dialog ref={picker} className="panel broker-picker" aria-labelledby="broker-picker-title">
        <form onSubmit={event => {
          event.preventDefault();
          if (!data.some(broker => broker.id === selection && broker.browser_consent_available)) return;
          picker.current?.close();
          navigate(`/user/brokers/setup/${selection}`);
        }}>
          <h2 id="broker-picker-title">Select a broker</h2>
          <label>Search brokers
            <input type="search" value={pickerQuery} onChange={event => setPickerQuery(event.target.value)} />
          </label>
          <fieldset>
            <legend>Broker availability</legend>
            {data.filter(broker => broker.name.toLowerCase().includes(pickerQuery.trim().toLowerCase())).map(broker => (
              <label key={broker.id}>
                <input type="radio" name="broker" value={broker.id} checked={selection === broker.id}
                  disabled={!broker.browser_consent_available} onChange={() => setSelection(broker.id)} />
                {broker.name} · {broker.browser_consent_available ? "Available" : broker.id === "dhan" ? "Authorization disabled" : "Coming soon"}
              </label>
            ))}
          </fieldset>
          <button type="button" onClick={() => picker.current?.close()}>Cancel</button>
          <button type="submit" disabled={!data.some(broker => broker.id === selection &&
            broker.name.toLowerCase().includes(pickerQuery.trim().toLowerCase()))}>Continue</button>
        </form>
      </dialog>
      {params.get("oauth") === "failed" && <p role="alert">Dhan authorization did not complete. Check your app details and try again.</p>}
    </>
  );
}
