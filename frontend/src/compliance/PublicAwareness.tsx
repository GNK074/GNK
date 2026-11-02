import { ShieldCheck, ArrowUpRight } from "lucide-react";
export function PublicAwareness() {
  return (
    <section className="public-awareness" aria-label="Investor awareness">
      <ShieldCheck size={24} />
      <div>
        <strong>Understand before you invest.</strong>
        <p>
          Choose regulated investment products. Start early, stay invested.
          Beware of investment frauds.
        </p>
      </div>
      <a
        href="https://investor.sebi.gov.in/"
        target="_blank"
        rel="noopener noreferrer"
      >
        SEBI investor awareness
        <ArrowUpRight size={14} />
      </a>
    </section>
  );
}
