import { useEffect, useRef, useState } from "react";
import { signOut } from "../services/api";
export function SignOutDialog({
  onClose,
  onSignedOut,
  onError,
}: {
  onClose: () => void;
  onSignedOut: () => void;
  onError: (s: string) => void;
}) {
  const dialog = useRef<HTMLDialogElement>(null);
  const [busy, setBusy] = useState(false);
  const [error,setError] = useState("");
  const submitting = useRef(false);
  useEffect(() => {
    dialog.current?.showModal();
    return () => dialog.current?.close();
  }, []);
  return (
    <dialog
      ref={dialog}
      className="settings-dialog"
      aria-labelledby="signout-title"
      onCancel={(e) => {
        e.preventDefault();
        if (!busy) onClose();
      }}
      onClick={(e) => {
        if (e.target === e.currentTarget && !busy) {
          const r = e.currentTarget.getBoundingClientRect();
          if (
            e.clientX < r.left ||
            e.clientX > r.right ||
            e.clientY < r.top ||
            e.clientY > r.bottom
          )
            onClose();
        }
      }}
    >
      <h2 id="signout-title">Sign out of GNK ALGO?</h2>
      <p>Choose whether to end this session or sign out of every device.</p>
      {error && <p role="alert">{error}</p>}
      <div>
        <button
          autoFocus
          disabled={busy}
          className="subtle-button"
          onClick={onClose}
        >
          Cancel
        </button>
        {[
          ["/auth/logout", "This device"],
          ["/auth/logout-all", "All devices"],
        ].map(([path, label]) => (
          <button
            key={path}
            disabled={busy}
            className="settings-primary"
            onClick={async () => {
              if(submitting.current)return;
              submitting.current=true;
              setBusy(true);
              setError("");
              try {
                await signOut(path === "/auth/logout-all");
                onSignedOut();
              } catch (e) {
                setError((e as Error).message);
                onError((e as Error).message);
              } finally {
                submitting.current=false;
                setBusy(false);
              }
            }}
          >
            {label}
          </button>
        ))}
      </div>
    </dialog>
  );
}
