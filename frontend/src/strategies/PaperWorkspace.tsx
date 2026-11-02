import { useEffect, useState } from "react";
import { api } from "../services/api";
export function PaperWorkspace({ notify }: { notify: (s: string) => void }) {
  const [strategies, setStrategies] = useState<any[]>([]),
    [orders, setOrders] = useState<any[]>([]),
    [positions, setPositions] = useState<any[]>([]),
    [selected, setSelected] = useState("");
  async function reload() {
    const [ss, oo, pp] = await Promise.all([
      api("/strategies"),
      api("/orders"),
      api("/positions"),
    ]);
    setStrategies(ss);
    setOrders(oo);
    setPositions(pp);
    if (!selected && ss.length) setSelected(ss[0].id);
  }
  useEffect(() => {
    reload().catch((e) => notify(e.message));
  }, []);
  return (
    <>
      <p className="eyebrow">ISOLATED RESEARCH ENVIRONMENT</p>
      <h1>Paper trading workspace</h1>
      <div className="notice">
        <p>
          Manual simulation at your entered price. No live quotes, broker
          orders, margin, fees or slippage are modeled. Results are research
          records.
        </p>
      </div>
      <div className="dash-grid">
        <article className="panel">
          <h3>Your strategies</h3>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const name = new FormData(e.currentTarget).get("name");
              try {
                const s = await api("/strategies", "POST", { name });
                setSelected(s.id);
                await reload();
              } catch (err) {
                notify((err as Error).message);
              }
            }}
          >
            <label>
              Strategy name
              <input name="name" minLength={2} maxLength={100} required />
            </label>
            <button className="button">Create research strategy</button>
          </form>
          {strategies.map((s) => (
            <p key={s.id}>{s.name}</p>
          ))}
        </article>
        <article className="panel">
          <h3>Simulate a paper order</h3>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = Object.fromEntries(new FormData(e.currentTarget));
              try {
                await api("/paper/orders", "POST", {
                  ...f,
                  strategy_id: selected,
                  quantity: Number(f.quantity),
                  idempotency_key: crypto.randomUUID(),
                });
                await reload();
                notify(
                  "Simulated paper fill recorded. No real order submitted.",
                );
              } catch (err) {
                notify((err as Error).message);
              }
            }}
          >
            <label>
              Strategy
              <select
                value={selected}
                onChange={(e) => setSelected(e.target.value)}
                required
                style={{ width: "100%", padding: 10 }}
              >
                <option value="">Select strategy</option>
                {strategies.map((s) => (
                  <option key={s.id} value={s.id}>
                    {s.name}
                  </option>
                ))}
              </select>
            </label>
            <label>
              Research symbol
              <input
                name="symbol"
                pattern="[A-Z0-9_.-]{1,40}"
                required
                defaultValue="TEST"
              />
            </label>
            <label>
              Side
              <select name="side" style={{ padding: 10 }}>
                <option>BUY</option>
                <option>SELL</option>
              </select>
            </label>
            <label>
              Quantity
              <input
                name="quantity"
                type="number"
                min={1}
                required
                defaultValue={1}
              />
            </label>
            <label>
              Simulation price
              <input
                name="price"
                type="number"
                min="0.0001"
                step="0.0001"
                required
              />
            </label>
            <button className="button" disabled={!selected}>
              Record simulated fill
            </button>
          </form>
        </article>
      </div>
      <article className="panel" style={{ marginTop: 20 }}>
        <h3>Paper positions</h3>
        {positions.map((p) => (
          <div className="market" key={p.id}>
            <b>{p.symbol}</b>
            <span>{p.quantity} units</span>
            <small>
              Average {p.average_price} · Realized P&amp;L {p.realized_pnl}
            </small>
          </div>
        ))}
        <h3>Recent paper fills</h3>
        {orders.map((o) => (
          <div className="market" key={o.id}>
            <b>
              {o.side} {o.symbol}
            </b>
            <span>
              {o.quantity} @ {o.price}
            </span>
            <small>
              {o.status} · {o.mode}
            </small>
          </div>
        ))}
      </article>
    </>
  );
}
