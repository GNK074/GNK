import { useEffect, useState } from "react";
import { ShieldCheck, ArrowUpRight, X } from "lucide-react";
export function PublicAwareness() {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const timer = window.setTimeout(() => setVisible(false), 5000);
    return () => window.clearTimeout(timer);
  }, []);
  if (!visible) return null;
  return (
    <div
      className="public-awareness"
      role="status"
      aria-label="Investor awareness"
    >
      <ShieldCheck size={23} aria-hidden="true" />
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
        SEBI investor awareness <ArrowUpRight size={13} />
      </a>
      <button
        className="awareness-close"
        aria-label="Close investor awareness message"
        onClick={() => setVisible(false)}
      >
        <X size={15} />
      </button>
    </div>
  );
}
