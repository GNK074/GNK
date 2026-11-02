import { useEffect, useState, type ReactNode } from "react";
import { api } from "../services/api";
import { RiskDisclosureModal } from "./RiskDisclosureModal";
import type { RiskDocument } from "./RiskDisclosureContent";
export function DisclosureGate({ children }: { children: ReactNode }) {
  const [document, setDocument] = useState<RiskDocument | null>(null),
    [required, setRequired] = useState(true),
    [loading, setLoading] = useState(true),
    [error, setError] = useState("");
  useEffect(() => {
    let live = true;
    let inFlight = false;
    async function check() {
      if (inFlight) return;
      inFlight = true;
      try {
        const [d, status] = await Promise.all([
          api("/compliance/disclosure"),
          api("/compliance/disclosure/status"),
        ]);
        if (live) {
          if (d.version !== status.disclosure_version)
            throw Error("The disclosure has changed. Please retry.");
          setDocument(d);
          setRequired(status.required);
          setError("");
        }
      } catch (e) {
        if (live) {
          setRequired(true);
          setError((e as Error).message);
        }
      } finally {
        inFlight = false;
        if (live) setLoading(false);
      }
    }
    check();
    const refresh = () => {
      if (globalThis.document.visibilityState === "visible") check();
    };
    const invalidate = () => {
      if (live) {
        setLoading(true);
        setRequired(true);
      }
      check();
    };
    window.addEventListener("focus", refresh);
    window.addEventListener("gnk:disclosure-required", invalidate);
    const interval = window.setInterval(refresh, 60000);
    return () => {
      live = false;
      clearInterval(interval);
      window.removeEventListener("focus", refresh);
      window.removeEventListener("gnk:disclosure-required", invalidate);
    };
  }, []);
  function reload() {
    window.location.reload();
  }
  if (loading)
    return (
      <div className="disclosure-check" role="status">
        Checking your risk disclosure acknowledgment…
      </div>
    );
  if (error)
    return (
      <section className="disclosure-check" role="alert">
        <h2>Risk disclosure unavailable</h2>
        <p>{error}</p>
        <p>
          Your trading workspace remains locked until the current disclosure can
          be verified.
        </p>
        <button className="settings-primary" onClick={reload}>
          Try again
        </button>
      </section>
    );
  if (required && document)
    return (
      <>
        <section className="disclosure-check">
          <h2>Your workspace is almost ready.</h2>
          <p>Please read and acknowledge the risk disclosure to continue.</p>
        </section>
        <RiskDisclosureModal
          key={document.version}
          document={document}
          onReload={reload}
          onAcknowledged={async () => {
            setLoading(true);
            try {
              const s = await api("/compliance/disclosure/status");
              if (s.required || s.disclosure_version !== document.version)
                throw Error(
                  "A new disclosure is required. Reload to continue.",
                );
              setRequired(false);
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setLoading(false);
            }
          }}
        />
      </>
    );
  return <>{children}</>;
}

