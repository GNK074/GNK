let csrf = "";
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
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : Array.isArray(data.detail)
          ? data.detail
              .map((v: any) => `${v.loc?.at(-1) || "Field"}: ${v.msg}`)
              .join(". ")
          : data.detail?.runtime_blocker
            ? `${data.detail.runtime_blocker}. Missing requirements: ${(data.detail.missing_requirements || []).join(", ") || "none; runtime checks still block approval"}`
            : "Please check the information entered.",
    );
  if (data.csrf_token) csrf = data.csrf_token;
  return data;
}
