import { useEffect, useState } from "react";
import { api } from "../services/api";
export function RiskControls({ notify }: { notify: (s: string) => void }) {
  const [risk, setRisk] = useState<any>(null);
  async function load() {
    setRisk(await api("/risk/configuration"));
  }
  useEffect(() => {
    load().catch((e) => notify(e.message));
  }, []);
  return (
    <article className="panel" style={{ marginTop: 20 }}>
      <h3>Your paper risk limits</h3>
      <p>
        Limits apply only to your isolated manual paper simulation. Live
        execution remains unavailable.
      </p>
      {risk && (
        <>
          <p>Emergency stop: {risk.kill_switch ? "ACTIVE" : "OFF"}</p>
          <form
            onSubmit={async (e) => {
              e.preventDefault();
              const f = Object.fromEntries(new FormData(e.currentTarget));
              try {
                await api("/risk/configuration", "PUT", {
                  max_quantity: Number(f.max_quantity),
                  max_order_value: f.max_order_value,
                  max_daily_orders: Number(f.max_daily_orders),
                  max_daily_loss: f.max_daily_loss,
                  max_positions: Number(f.max_positions),
                });
                await load();
                notify("Personal risk limits updated");
              } catch (err) {
                notify((err as Error).message);
              }
            }}
          >
            {[
              ["max_quantity", "Maximum quantity"],
              ["max_order_value", "Maximum order value"],
              ["max_daily_orders", "Daily order limit"],
              ["max_daily_loss", "Daily realized-loss limit"],
              ["max_positions", "Maximum open positions"],
            ].map(([key, label]) => (
              <label key={key}>
                {label}
                <input
                  name={key}
                  type="number"
                  min={
                    key.includes("loss") || key.includes("value") ? "0.0001" : 1
                  }
                  step={
                    key.includes("loss") || key.includes("value") ? "0.0001" : 1
                  }
                  defaultValue={risk[key]}
                  required
                />
              </label>
            ))}
            <button className="button ghost">Save personal limits</button>
          </form>
          <button
            className="danger"
            style={{ marginTop: 20 }}
            onClick={async () => {
              try {
                await api("/risk/emergency-stop", "POST", {
                  enabled: !risk.kill_switch,
                });
                await load();
              } catch (e) {
                notify((e as Error).message);
              }
            }}
          >
            {risk.kill_switch
              ? "Resume paper simulation"
              : "Stop new paper orders"}
          </button>
        </>
      )}
    </article>
  );
}
