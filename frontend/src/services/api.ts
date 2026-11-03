let csrf = "";
export class ApiError extends Error {
  constructor(message: string, public status: number) { super(message); this.name="ApiError"; }
}
export const SESSION_ENDED_KEY = "gnk:session-ended";
export async function api(path: string, method = "GET", body?: unknown) {
  const raw = body instanceof Blob;
  const r = await fetch("/api/v1" + path, {
    method,
    credentials: "include",
    headers: {
      "Content-Type": raw
        ? body.type || "application/octet-stream"
        : "application/json",
      "X-CSRF-Token": csrf,
    },
    body: raw ? body : body ? JSON.stringify(body) : undefined,
  });
  let data: any;
  try {
    data = await r.json();
  } catch {
    throw Error(`The server returned HTTP ${r.status}. Please try again.`);
  }
  if (r.status === 428 && data.detail?.code === "DISCLOSURE_REQUIRED")
    window.dispatchEvent(new Event("gnk:disclosure-required"));
  if (!r.ok)
    throw new ApiError(
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.code === "DISCLOSURE_REQUIRED"
          ? data.detail.message
          : Array.isArray(data.detail)
            ? data.detail
                .map((v: any) => `${v.loc?.at(-1) || "Field"}: ${v.msg}`)
                .join(". ")
            : data.detail?.runtime_blocker
              ? `${data.detail.runtime_blocker}. Missing requirements: ${(data.detail.missing_requirements || []).join(", ") || "none; runtime checks still block approval"}`
              : "Please check the information entered.",
      r.status,
    );
  if (data.csrf_token) csrf = data.csrf_token;
  return data;
}


// Logout alone may renew its CSRF proof and retry a rejected request. Trading
// mutations and every other API request are never replayed by this helper.
export async function signOut(allDevices = false) {
  async function sessionProof() {
    try { await api("/auth/session"); }
    catch (error) {
      if (!(error instanceof ApiError) || error.status !== 401) throw error;
      if (allDevices) throw new Error("Your session has expired. Sign in again to sign out other devices, or choose This device.");
    }
  }
  await sessionProof();
  const path=allDevices?"/auth/logout-all":"/auth/logout";
  try { await api(path,"POST"); }
  catch (error) {
    if (!(error instanceof ApiError) || error.status !== 403) throw error;
    await sessionProof();
    await api(path,"POST");
  }
  csrf="";
  try { localStorage.setItem(SESSION_ENDED_KEY,JSON.stringify({at:Date.now(),nonce:crypto.randomUUID()})); } catch { /* Storage may be unavailable in private mode. */ }
}
