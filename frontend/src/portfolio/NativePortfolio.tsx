import { useEffect, useState } from "react";
import { ArrowUpDown, BriefcaseBusiness, ChartNoAxesCombined, RefreshCw, Wallet } from "lucide-react";
import { Link } from "react-router-dom";
import { api } from "../services/api";
import "./native-portfolio.css";

const sections = [
  { id: "holdings", title: "Holdings", icon: BriefcaseBusiness },
  { id: "orders", title: "Orders", icon: ArrowUpDown },
  { id: "funds", title: "Funds", icon: Wallet },
  { id: "pnl", title: "P&L analysis", icon: ChartNoAxesCombined },
] as const;

type Section = (typeof sections)[number]["id"];
type Position = {
  id: string; symbol: string; product: string; state: string; quantity: number;
  average_price: string; mark: string | null; realized_pnl: string; unrealized_pnl: string | null;
};
type Portfolio = {
  as_of: string;
  holdings: Position[];
  orders: {
    id: string; symbol: string; side: string; quantity: number; price: string;
    execution_price: string | null; status: string;
  }[];
  funds: { collateral: string; used: string; reserved: string; available: string };
  pnl: {
    realized: string; unrealized: string | null; total: string | null;
    marked_value: string | null; unpriced_holdings: number; by_symbol: Position[];
  };
};

const format = new Intl.NumberFormat("en-IN", { minimumFractionDigits: 2, maximumFractionDigits: 4 });
const amount = (value: string | null) => value === null ? "—" : format.format(Number(value));
const tone = (value: string | null) => value === null || Number(value) === 0 ? undefined
  : Number(value) > 0 ? "gain" : "loss";

export function NativePortfolio() {
  const [section, setSection] = useState<Section>("holdings");
  const [data, setData] = useState<Portfolio | null>(null);
  const [error, setError] = useState("");
  const [pending, setPending] = useState(true);
  const [revision, setRevision] = useState(0);

  useEffect(() => {
    let current = true;
    api("/gnk/paper/portfolio").then((value: Portfolio) => {
      if (current) setData(value);
    }).catch((reason: Error) => {
      if (current) {
        setData(null);
        setError(reason.message);
      }
    }).finally(() => { if (current) setPending(false); });
    return () => { current = false; };
  }, [revision]);

  return (
    <section className="gnk-portfolio" aria-labelledby="portfolio-title">
      <div className="gnk-portfolio-header">
        <div className="gnk-portfolio-title">
          <span className="gnk-portfolio-icon"><BriefcaseBusiness size={27} aria-hidden="true" /></span>
          <div><h1 id="portfolio-title">Portfolio</h1><p>GNK paper trading</p></div>
        </div>
        <button type="button" disabled={pending} onClick={() => {
          setPending(true);
          setError("");
          setRevision(value => value + 1);
        }}><RefreshCw size={16} aria-hidden="true" /> Refresh</button>
      </div>
      <nav className="gnk-portfolio-sections" aria-label="Portfolio views">
        {sections.map(({ id, title, icon: Icon }) => (
          <button type="button" key={id} aria-pressed={section === id} onClick={() => setSection(id)}>
            <Icon size={17} aria-hidden="true" /> {title}
          </button>
        ))}
      </nav>
      {pending && !data && <p role="status">Loading portfolio…</p>}
      {error && <p role="alert">{error}</p>}
      {data && <section className="gnk-portfolio-panel" aria-busy={pending}>
        <h2>{sections.find(item => item.id === section)?.title}</h2>
        {section === "holdings" && <>
          <p>Marked value {amount(data.pnl.marked_value)} · {data.holdings.length} open holdings</p>
          {data.pnl.unpriced_holdings > 0 && <p>{data.pnl.unpriced_holdings} holdings need a replay price for valuation.</p>}
          {data.holdings.length ? <div className="gnk-portfolio-scroll"><table>
            <thead><tr><th>Symbol</th><th>Product</th><th>Quantity</th><th>Average cost</th><th>Last mark</th><th>Unrealized P&L</th></tr></thead>
            <tbody>{data.holdings.map(item => <tr key={item.id}>
              <th scope="row">{item.symbol}</th><td>{item.product}</td><td>{item.quantity}</td>
              <td>{amount(item.average_price)}</td><td>{amount(item.mark)}</td>
              <td data-pnl={tone(item.unrealized_pnl)}>{amount(item.unrealized_pnl)}</td>
            </tr>)}</tbody>
          </table></div> : <p>No open holdings. <Link to="/user/trading/orders">Open order entry</Link></p>}
        </>}
        {section === "orders" && <>
          {data.orders.length ? <div className="gnk-portfolio-scroll"><table>
            <thead><tr><th>Symbol</th><th>Side</th><th>Quantity</th><th>Limit</th><th>Fill</th><th>Status</th></tr></thead>
            <tbody>{data.orders.map(order => <tr key={order.id}>
              <th scope="row">{order.symbol}</th><td>{order.side}</td><td>{order.quantity}</td>
              <td>{amount(order.price)}</td><td>{amount(order.execution_price)}</td><td>{order.status}</td>
            </tr>)}</tbody>
          </table></div> : <p>No paper orders yet.</p>}
          <Link to="/user/trading/orders">Manage orders</Link>
        </>}
        {section === "funds" && <>
          <p>Virtual collateral for paper trading.</p>
          <dl className="gnk-portfolio-metrics">
            {[
              ["Available", data.funds.available], ["Total collateral", data.funds.collateral],
              ["Used", data.funds.used], ["Reserved", data.funds.reserved],
            ].map(([label, value]) => <div key={label}><dt>{label}</dt><dd>{amount(value)}</dd></div>)}
          </dl>
          <Link to="/user/trading/risk-controls">Manage paper collateral</Link>
        </>}
        {section === "pnl" && <>
          <dl className="gnk-portfolio-metrics">
            {([
              ["Total P&L", data.pnl.total], ["Realized", data.pnl.realized], ["Unrealized", data.pnl.unrealized],
            ] as const).map(([label, value]) => <div key={label}><dt>{label}</dt><dd data-pnl={tone(value)}>{amount(value)}</dd></div>)}
          </dl>
          {data.pnl.unpriced_holdings > 0 && <p>Replay prices for all holdings to calculate total and unrealized P&L.</p>}
          {data.pnl.by_symbol.length ? <div className="gnk-portfolio-scroll"><table>
            <thead><tr><th>Symbol</th><th>Position</th><th>Realized P&L</th><th>Unrealized P&L</th></tr></thead>
            <tbody>{data.pnl.by_symbol.map(item => <tr key={item.id}>
              <th scope="row">{item.symbol}</th><td>{item.state}</td>
              <td data-pnl={tone(item.realized_pnl)}>{amount(item.realized_pnl)}</td>
              <td data-pnl={tone(item.unrealized_pnl)}>{amount(item.unrealized_pnl)}</td>
            </tr>)}</tbody>
          </table></div> : <p>No position history yet.</p>}
        </>}
      </section>}
      {data && <small>Snapshot at {new Date(data.as_of).toLocaleString("en-IN", { timeZone: "Asia/Kolkata" })} IST</small>}
    </section>
  );
}
