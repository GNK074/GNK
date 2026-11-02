import { BookOpen, ShieldCheck, Sparkles } from "lucide-react";
export type RiskDocument = {
  id: string;
  version: string;
  content_sha256: string;
  heading: string;
  subheading: string;
  points: string[];
  awareness_heading: string;
  awareness_messages: string[];
  source: string;
  historical_note: string;
  source_url: string;
  awareness_url: string;
  platform_note: string;
};
export function InvestorAwarenessSection({
  document: d,
}: {
  document: RiskDocument;
}) {
  return (
    <section className="investor-awareness">
      <div className="awareness-icon">
        <BookOpen size={23} />
      </div>
      <h3>{d.awareness_heading}</h3>
      <p className="awareness-kicker">
        A little understanding. A more informed tomorrow.
      </p>
      <ul>
        {d.awareness_messages.map((message) => (
          <li key={message}>
            <ShieldCheck size={15} />
            {message}
          </li>
        ))}
      </ul>
      <a href={d.awareness_url} target="_blank" rel="noopener noreferrer">
        Explore SEBI’s investor resources ↗
      </a>
    </section>
  );
}
export function RiskDisclosureContent({
  document: d,
}: {
  document: RiskDocument;
}) {
  return (
    <>
      <div className="risk-illustration" aria-hidden="true">
        <ShieldCheck size={40} />
        <Sparkles size={18} />
      </div>
      <p className="risk-eyebrow">KNOW THE RISKS. MAKE INFORMED DECISIONS.</p>
      <h2 id="risk-title">{d.heading}</h2>
      <p id="risk-description" className="risk-intro">
        Take a moment to understand the risks before entering your workspace.
      </p>
      <section className="risk-facts">
        <h3>{d.subheading}</h3>
        <ol>
          {d.points.map((point, i) => (
            <li key={point}>
              <span>{String(i + 1).padStart(2, "0")}</span>
              <p>{point}</p>
            </li>
          ))}
        </ol>
      </section>
      <InvestorAwarenessSection document={d} />
      <div className="risk-source">
        <strong>Source:</strong>
        <p>{d.source}</p>
        <p>{d.historical_note}</p>
        <a href={d.source_url} target="_blank" rel="noopener noreferrer">
          Read the original SEBI study ↗
        </a>
      </div>
    </>
  );
}
