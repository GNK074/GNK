let csrf = "";
export async function api(path: string, method = "GET", body?: unknown) {
  const r = await fetch("/api/v1" + path, {
    method,
    credentials: "include",
    headers: { "Content-Type": "application/json", "X-CSRF-Token": csrf },
    body: body ? JSON.stringify(body) : undefined,
  });
  const data = await r.json();
  if (!r.ok)
    throw Error(
      typeof data.detail === "string"
        ? data.detail
        : data.detail?.runtime_blocker
          ? `${data.detail.runtime_blocker}. Missing requirements: ${(data.detail.missing_requirements || []).join(", ") || "none; runtime checks still block approval"}`
          : "Please check the information entered.",
    );
  if (data.csrf_token) csrf = data.csrf_token;
  return data;
}
