import { useEffect, useRef, useState } from "react";
import type { FormEvent } from "react";
import { api } from "../services/api";
import "./live-trading.css";

const base = "/gnk/paper";
type Strategy = { id: string; name: string };
type Order = {
  id: string; symbol: string; side: string; price: string; quantity: number;
  status: string; version: number; execution_price: string | null; execution_reason: string | null;
};
type Position = {
  id: string; symbol: string; quantity: number; state: string; product: string;
  realized_pnl: string; unrealized_pnl: string | null; mark: string | null;
  stop_loss: string | null; target: string | null;
};
type Margin = { collateral: string; used: string; reserved: string; available: string; stopped: boolean };
type Workspace = {
  strategies: Strategy[]; orders: Order[]; positions: Position[]; margin: Margin;
};

export function LiveTrading() {
  const [workspace, setWorkspace] = useState<Workspace | null>(null);
  const [live, setLive] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);
  const [revision, setRevision] = useState(0);
  const [editing, setEditing] = useState<Order | null>(null);
  const attempt = useRef<{ fingerprint: string; key: string } | null>(null);

  useEffect(() => {
    let current = true;
    Promise.all([
      api(base + "/strategies"), api(base + "/orders"), api(base + "/positions"),
      api(base + "/risk/margin"), api("/gnk/live/status"),
    ]).then(([strategies, orders, positions, margin, status]) => {
      if (!current) return;
      setWorkspace({ strategies, orders, positions, margin });
      setLive(status.blocker);
    }).catch((error: Error) => {
      if (current) setMessage(error.message);
    });
    return () => { current = false; };
  }, [revision]);

  async function update(path: string, method = "POST", body?: unknown) {
    setBusy(true);
    setMessage("");
    try {
      const result = await api(base + path, method, body);
      const unpriced: string[] | undefined = result.unpriced_positions;
      setMessage(unpriced?.length
        ? "Emergency stop is active. Replay a price for " + unpriced.join(", ") + " before retrying."
        : "Paper workspace updated.");
      return true;
    } catch (error) {
      setMessage((error as Error).message);
      return false;
    } finally {
      setBusy(false);
      setRevision(value => value + 1);
    }
  }

  async function place(event: FormEvent<HTMLFormElement>) {
    event.preventDefault();
    const form = event.currentTarget;
    const fields = new FormData(form);
    const body = {
      strategy_id: fields.get("strategy"), symbol: String(fields.get("symbol")).trim().toUpperCase(),
      side: fields.get("side"), quantity: Number(fields.get("quantity")), price: fields.get("price"),
    };
    const fingerprint = JSON.stringify(body);
    if (attempt.current?.fingerprint !== fingerprint) {
      attempt.current = { fingerprint, key: crypto.randomUUID() };
    }
    if (await update("/orders", "POST", { ...body, idempotency_key: attempt.current.key })) {
      attempt.current = null;
      form.reset();
    }
  }

  return (
    <section className="gnk-live" aria-labelledby="trading-title">
      <div className="gnk-live-heading">
        <div><h1 id="trading-title">GNK Trading</h1><p>Paper trading workspace</p></div>
        <button type="button" disabled={busy} onClick={() => setRevision(value => value + 1)}>Refresh</button>
      </div>
      {live && <p className="gnk-live-blocker" role="status">{live}</p>}
      {message && <p role="status">{message}</p>}
      {workspace && <>
        <section className="gnk-live-panel">
          <h2>Order entry</h2>
          <form className="gnk-live-form" onSubmit={event => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            void update("/strategies", "POST", { name: fields.get("name") });
          }}>
            <label>Strategy name<input name="name" required minLength={2} maxLength={100} /></label>
            <button disabled={busy}>Add strategy</button>
          </form>
          {workspace.strategies.length > 0 && <form className="gnk-live-form" onSubmit={place}>
            <label>Strategy<select name="strategy">{workspace.strategies.map(strategy =>
              <option key={strategy.id} value={strategy.id}>{strategy.name}</option>,
            )}</select></label>
            <label>Symbol<input name="symbol" required maxLength={40} /></label>
            <label>Side<select name="side"><option>BUY</option><option>SELL</option></select></label>
            <label>Quantity<input name="quantity" type="number" min="1" max="100000" required /></label>
            <label>Limit price<input name="price" type="number" min=".0001" step=".0001" required /></label>
            <button disabled={busy || workspace.margin.stopped}>Place paper order</button>
          </form>}
          <form className="gnk-live-form" onSubmit={event => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            void update("/replay/price", "POST", {
              symbol: String(fields.get("symbol")).trim().toUpperCase(),
              price: fields.get("price"), sequence: Number(fields.get("sequence")),
            });
          }}>
            <label>Replay symbol<input name="symbol" required maxLength={40} /></label>
            <label>Replay price<input name="price" type="number" min=".0001" step=".0001" required /></label>
            <label>Replay sequence<input name="sequence" type="number" min="1" max="2147483647" required /></label>
            <button disabled={busy}>Replay price</button>
          </form>
        </section>
        <section className="gnk-live-panel">
          <h2>Order book and executions</h2>
          {editing && <form className="gnk-live-form" key={editing.id} onSubmit={async event => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            if (await update("/orders/" + editing.id, "PATCH", {
              quantity: Number(fields.get("quantity")), price: fields.get("price"), version: editing.version,
            })) setEditing(null);
          }}>
            <label>Quantity<input name="quantity" type="number" min="1" max="100000" defaultValue={editing.quantity} required /></label>
            <label>Limit price<input name="price" type="number" min=".0001" step=".0001" defaultValue={editing.price} required /></label>
            <button disabled={busy}>Save changes</button>
            <button type="button" onClick={() => setEditing(null)}>Close editor</button>
          </form>}
          {workspace.orders.length ? <div className="gnk-live-scroll"><table>
            <thead><tr><th>Symbol</th><th>Side</th><th>Qty</th><th>Limit</th><th>Status</th><th>Execution</th><th>Actions</th></tr></thead>
            <tbody>{workspace.orders.map(order => <tr key={order.id}>
              <th scope="row">{order.symbol}</th><td>{order.side}</td><td>{order.quantity}</td><td>{order.price}</td>
              <td>{order.status}</td><td>{order.execution_price ?? "—"} {order.execution_reason}</td>
              <td>{order.status === "open" && <div className="gnk-live-actions">
                <button disabled={busy || workspace.margin.stopped} onClick={() => setEditing(order)}>Modify</button>
                <button disabled={busy} onClick={() => void update("/orders/" + order.id + "?version=" + order.version, "DELETE")}>Cancel order</button>
              </div>}</td>
            </tr>)}</tbody>
          </table></div> : <p>No paper orders.</p>}
        </section>
        <section className="gnk-live-panel">
          <h2>Positions</h2>
          {workspace.positions.length ? <div className="gnk-live-scroll"><table>
            <thead><tr><th>Symbol</th><th>Qty</th><th>Product</th><th>Realized P&amp;L</th><th>Unrealized P&amp;L</th><th>Actions</th></tr></thead>
            <tbody>{workspace.positions.map(position => <tr key={position.id}>
              <th scope="row">{position.symbol}</th><td>{position.quantity}</td><td>{position.product}</td>
              <td>{position.realized_pnl}</td><td>{position.unrealized_pnl ?? "—"}</td>
              <td>{position.state === "open" && <details>
                <summary>Manage position</summary>
                <div className="gnk-live-actions">
                  <button disabled={busy || workspace.margin.stopped} onClick={() => void update(
                    "/positions/" + position.id + "/product", "PUT",
                    { product: position.product === "DELIVERY" ? "INTRADAY" : "DELIVERY" },
                  )}>Convert product</button>
                  <button disabled={busy || !position.mark} onClick={() => {
                    if (window.confirm("Square off this paper position at its latest replayed price?")) {
                      void update("/positions/" + position.id + "/square-off");
                    }
                  }}>Square off</button>
                </div>
                <form className="gnk-live-form" onSubmit={event => {
                  event.preventDefault();
                  const fields = new FormData(event.currentTarget);
                  void update("/positions/" + position.id + "/protection", "PUT", {
                    stop_loss: fields.get("stop") || null, target: fields.get("target") || null,
                  });
                }}>
                  <label>Stop-loss<input name="stop" type="number" min=".0001" step=".0001" defaultValue={position.stop_loss ?? ""} /></label>
                  <label>Target<input name="target" type="number" min=".0001" step=".0001" defaultValue={position.target ?? ""} /></label>
                  <button disabled={busy}>Save protection</button>
                </form>
              </details>}</td>
            </tr>)}</tbody>
          </table></div> : <p>No paper positions.</p>}
        </section>
        <section className="gnk-live-panel">
          <h2>Risk controls</h2>
          <p>Collateral {workspace.margin.collateral} · Used {workspace.margin.used} · Reserved {workspace.margin.reserved} · Available {workspace.margin.available}</p>
          <form className="gnk-live-form" onSubmit={event => {
            event.preventDefault();
            const fields = new FormData(event.currentTarget);
            void update("/risk/margin", "PUT", { amount: fields.get("amount") });
          }}>
            <label>Paper collateral<input name="amount" type="number" min=".0001" step=".0001" required /></label>
            <button disabled={busy}>Update collateral</button>
          </form>
          <p>{workspace.margin.stopped ? "GNK emergency stop is active." : "GNK emergency stop is inactive."}</p>
          <button disabled={busy} onClick={() => {
            if (window.confirm("Activate the GNK emergency stop, cancel paper orders, and close priced paper positions?")) {
              void update("/risk/emergency-exit");
            }
          }}>Paper emergency exit</button>
        </section>
      </>}
    </section>
  );
}
