import { useEffect, useState } from "react";
import { api } from "../services/api";

type Notice = { id: string; message: string; created: string };
const timestamp = new Intl.DateTimeFormat("en-IN", {
  dateStyle: "medium", timeStyle: "short", timeZone: "Asia/Kolkata",
});

export function Notifications() {
  const [items, setItems] = useState<Notice[]>([]);
  const [status, setStatus] = useState("Loading notifications…");
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let active = true;
    let timer: ReturnType<typeof setTimeout>;
    async function refresh() {
      try {
        const result = await api("/notifications");
        if (active) { setItems(result.items); setStatus(""); }
      } catch {
        if (active) setStatus("Could not refresh notifications.");
      } finally {
        if (active) timer = setTimeout(refresh, 15000);
      }
    }
    void refresh();
    return () => { active = false; clearTimeout(timer); };
  }, [revision]);

  return <section className="panel">
    <h1>Notifications <span className="workspace-spark" aria-hidden="true">✳</span></h1>
    <button type="button" onClick={() => setRevision(value => value + 1)}>Refresh</button>
    {status && <p role="status">{status}</p>}
    {!status && !items.length && <p>No account notifications yet.</p>}
    {items.length > 0 && <ul>
      {items.map(item => <li key={item.id}>
        <p>{item.message}</p>
        <time dateTime={item.created}>{timestamp.format(new Date(item.created))} IST</time>
      </li>)}
    </ul>}
  </section>;
}
