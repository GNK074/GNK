import { useState } from "react";
import { api } from "../services/api";

type Draft = { broker: string; primary_ip: string; secondary_ip: string | null; status: string };

export function StaticIpReview() {
  const [owner, setOwner] = useState("");
  const [review, setReview] = useState<{ owner: string; draft: Draft }>();
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function run(task: () => Promise<void>) {
    setBusy(true);
    setMessage("");
    try { await task(); }
    catch (error) { setMessage((error as Error).message); }
    finally { setBusy(false); }
  }

  return <article className="panel">
    <h2>Static IP review</h2>
    <form onSubmit={event => {
      event.preventDefault();
      setReview(undefined);
      void run(async () => {
        const id = owner.trim();
        const result = await api("/ip-management/review/" + encodeURIComponent(id));
        if (result.draft) setReview({ owner: id, draft: result.draft });
        else setMessage("No static IP draft found.");
      });
    }}>
      <label>User ID <input value={owner} onChange={event => setOwner(event.target.value)} required maxLength={36} /></label>
      <button disabled={busy}>Look up request</button>
    </form>
    {review && <>
      <p>{review.draft.broker} · {review.draft.primary_ip}{review.draft.secondary_ip && " / " + review.draft.secondary_ip}</p>
      <p>{review.draft.status.replaceAll("_", " ")}</p>
      {review.draft.status === "PENDING_ADMIN" && (["approve", "reject"] as const).map(decision =>
        <button key={decision} type="button" disabled={busy} onClick={() => void run(async () => {
          const result = await api("/ip-management/review/" + encodeURIComponent(review.owner), "POST", { decision });
          setReview({ ...review, draft: { ...review.draft, status: result.status } });
        })}>{decision === "approve" ? "Approve for broker review" : "Reject"}</button>)}
    </>}
    <p role="status">{message}</p>
  </article>;
}
