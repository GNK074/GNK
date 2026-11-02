import { useEffect, useRef, useState } from "react";
import { ArrowRight, LockKeyhole } from "lucide-react";
import { api } from "../services/api";
import {
  RiskDisclosureContent,
  type RiskDocument,
} from "./RiskDisclosureContent";
export function RiskDisclosureModal({
  document: d,
  onAcknowledged,
  onReload,
}: {
  document: RiskDocument;
  onAcknowledged: () => void;
  onReload: () => void;
}) {
  const ref = useRef<HTMLDialogElement>(null);
  const [checked, setChecked] = useState(false),
    [busy, setBusy] = useState(false),
    [error, setError] = useState("");
  useEffect(() => {
    const dialog = ref.current;
    dialog?.showModal();
    return () => dialog?.close();
  }, []);
  return (
    <dialog
      className="risk-dialog"
      ref={ref}
      aria-labelledby="risk-title"
      aria-describedby="risk-description"
      onCancel={(e) => e.preventDefault()}
    >
      <div className="risk-scroll" tabIndex={0}>
        <RiskDisclosureContent document={d} />
        <label className="risk-consent">
          <input
            type="checkbox"
            checked={checked}
            disabled={busy}
            onChange={(e) => setChecked(e.target.checked)}
          />
          I have read and understood this risk disclosure.
        </label>
      </div>
      <div className="risk-actions">
        {!checked && <p className="risk-read-hint">Scroll to read the full disclosure, then tick the acknowledgment box.</p>}
        {error && (
          <div className="risk-error" role="alert">
            {error}
            <button disabled={busy} onClick={onReload}>
              Reload disclosure
            </button>
          </div>
        )}
        <button
          className="risk-proceed"
          disabled={!checked || busy}
          onClick={async () => {
            if (busy || !checked) return;
            setBusy(true);
            setError("");
            try {
              await api("/compliance/disclosure/acknowledge", "POST", {
                disclosure_id: d.id,
                disclosure_version: d.version,
                content_sha256: d.content_sha256,
                acknowledged: true,
              });
              onAcknowledged();
            } catch (e) {
              setError((e as Error).message);
            } finally {
              setBusy(false);
            }
          }}
        >
          {busy ? "Recording acknowledgment…" : "Proceed Ahead to Trade"}
          <ArrowRight size={18} />
        </button>
        <p>
          <LockKeyhole size={12} />
          {d.platform_note}
        </p>
        <small>Disclosure version {d.version}</small>
      </div>
    </dialog>
  );
}
