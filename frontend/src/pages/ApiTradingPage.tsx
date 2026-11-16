import { Workflow } from "lucide-react";
import { Link } from "react-router-dom";
import { Logo } from "../components/Logo";
import "./api-trading.css";

const brokers = [
  ["Dhan", "In development", "Primary integration. Consent and account inspection require operator enablement and a registered Dhan app.", "https://dhanhq.co/docs/v2/authentication/"],
  ["FYERS", "In development", "Profile verification exists. Public onboarding is pending.", ""],
  ["Upstox", "Planned for this workspace", "OAuth and market-data components exist. Broker Setup onboarding is pending.", "https://upstox.com/developer/api-documentation/authentication/"],
  ["Zerodha", "Planned", "Broker Setup onboarding is pending.", ""],
  ["Angel One", "Planned", "Broker Setup onboarding is pending.", ""],
  ["Alice Blue", "Planned", "Broker Setup onboarding is pending.", ""],
] as const;

const steps = ["Register with GnKAlgo", "Select a supported broker", "Authorize with the broker", "Verify the account", "Configure an eligible strategy", "Validate risk controls", "Authorize execution", "Submit eligible instructions to the broker", "Monitor orders and portfolio"];
const architecture = ["Customer", "GnKAlgo platform", "Strategy engine", "Risk validation", "Broker adapter", "Supported broker", "Orders and portfolio", "GnKAlgo dashboard"];
const faq = [
  ["What is API trading?", "An authorized platform uses a broker’s documented interfaces to exchange account data or submit eligible instructions."],
  ["How does GnKAlgo connect to brokers?", "When onboarding is available, authorization and account verification follow the broker’s supported process."],
  ["Which brokers are supported?", "See the integration status above. Production connectivity depends on broker and account enablement."],
  ["Do I need to provide my broker password?", "Enter your trading password or OTP only on the broker’s own website."],
  ["Can I use paper trading?", "Paper trading simulates execution in an eligible workspace without sending live orders."],
  ["Can I control my automated strategies?", "Configure eligible strategies and apply execution stops where supported."],
  ["How are stop-loss and risk limits managed?", "GNK evaluates configured controls before submission. Stop-loss behavior depends on strategy and broker order support."],
  ["What happens when the broker disconnects?", "Review the last successful snapshot and reconnect. Check open orders and positions directly with the broker."],
  ["Can I monitor my orders?", "Supported accounts can display broker-reported orders and trades with their latest synchronization state."],
  ["Does API trading guarantee profits?", "No. Execution, fill prices and investment outcomes are uncertain."],
] as const;

export function ApiTradingPage() {
  return (
    <div className="api-trading">
      <header className="api-trading-nav"><Logo /><nav aria-label="Public navigation">
        <Link to="/contact-us">Contact</Link><Link to="/login">Sign in</Link>
      </nav></header>
      <main>
        <section className="api-trading-hero">
          <div><h1>Intelligent API Trading.<br />Built for Precision and Control.</h1>
            <p>Connect a supported broker account and manage strategy configuration, execution monitoring and risk controls in one workspace.</p>
            <div className="api-trading-actions"><a className="button" href="#how-it-works">Explore API Trading</a><Link to="/contact-us">Ask about broker availability</Link></div>
          </div>
          <div className="api-trading-diagram" aria-label="Illustrative view of strategy and broker checks">
            <Workflow size={42} aria-hidden="true" /><strong>Strategy workspace</strong>
            <span>Broker authorization → Risk validation → Execution</span>
            <small>Paper · Simulated</small><small>Live · Approval required</small>
          </div>
        </section>
        <section><h2>What is API trading?</h2><p>API trading connects an authorized platform to a supported broker through documented interfaces. Research signals can inform a strategy. User authorization and risk checks govern whether strategy instructions can be sent for broker-side execution. Review broker responses, positions and execution history in your workspace.</p></section>
        <section id="brokers"><h2>Broker integrations</h2><div className="api-trading-grid">
          {brokers.map(([name, status, summary, docs]) => <article key={name}><h3>{name}</h3><strong>{status}</strong><p>{summary}</p>{docs && <a href={docs}>Official documentation</a>}</article>)}
        </div></section>
        <section id="how-it-works"><h2>How it works</h2><ol className="api-trading-flow">{steps.map(step => <li key={step}>{step}</li>)}</ol></section>
        <section><h2>Trading modes</h2><div className="api-trading-grid">
          <article><h3>Paper trading</h3><p>Simulate orders, evaluate strategy behavior and test risk settings without sending orders to a broker.</p></article>
          <article><h3>Live trading</h3><p>Requires a verified broker connection, explicit authorization and applicable risk checks. The broker executes eligible orders, which are then reconciled and monitored.</p></article>
        </div></section>
        <section><h2>Risk management</h2><p>Depending on your account, broker and strategy, controls can include daily loss, order quantity, order value, capital and position limits, duplicate prevention, market-hours and price-deviation checks, connection monitoring and emergency stops. Verify stop-loss behavior and applicable limits before authorizing execution.</p></section>
        <section><h2>How instructions reach the broker</h2><ol className="api-trading-flow">{architecture.map(step => <li key={step}>{step}</li>)}</ol></section>
        <section><h2>Security and authorization</h2><p>GNK uses encrypted backend credential storage, authenticated sessions, ownership checks, role-based administration and audit events. Broker authorization uses the applicable provider flow. Access and session health depend on broker responses.</p></section>
        <section><h2>API trading use cases</h2><ul><li>Portfolio and position monitoring through supported account snapshots.</li><li>Order and strategy monitoring through eligible workspace views.</li><li>Equity and index-options automation subject to broker, strategy and execution approval.</li></ul></section>
        <section><h2>Frequently asked questions</h2>{faq.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
        <section><h2>Start Building Your Trading Workflow with GnKAlgo.</h2><p>Explore broker setup, strategy configuration and risk monitoring.</p><div className="api-trading-actions"><Link className="button" to="/register">Get started</Link><a href="#brokers">Explore brokers</a><Link to="/contact-us">Contact support</Link></div></section>
      </main>
      <footer><strong>GnKAlgo</strong><p>API trading information and broker workflow support. Trading involves market risk. API connectivity cannot guarantee execution, uninterrupted service or returns.</p><Link to="/register">Registration and account agreements</Link>{" · "}<Link to="/contact-us">Contact GnKAlgo</Link></footer>
    </div>
  );
}
