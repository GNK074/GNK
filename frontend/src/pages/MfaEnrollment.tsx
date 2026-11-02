import { useEffect, useState } from "react";
import { api } from "../services/api";
export function MfaEnrollment() {
  const [secret, setSecret] = useState(""),
    [code, setCode] = useState(""),
    [message, setMessage] = useState("");
  useEffect(() => {
    api("/auth/mfa/status").catch((e) => setMessage(e.message));
  }, []);
  return (
    <div className="auth-wrap">
      <h1>Secure your account</h1>
      <p>
        Enroll an authenticator before accessing your workspace. Keep the setup
        key private.
      </p>
      {message && <p role="status">{message}</p>}
      <button
        className="button"
        onClick={async () => {
          try {
            const data = await api("/auth/mfa/setup", "POST");
            setSecret(data.secret);
          } catch (e) {
            setMessage((e as Error).message);
          }
        }}
      >
        Generate authenticator setup key
      </button>
      {secret && (
        <form
          style={{ maxWidth: 450, margin: "30px auto" }}
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              await api("/auth/mfa/confirm", "POST", { code });
              window.location.assign("/user/dashboard");
            } catch (err) {
              setMessage((err as Error).message);
            }
          }}
        >
          <p>
            Add an account named GNK ALGO in your authenticator, using this key:
          </p>
          <code style={{ wordBreak: "break-all" }}>{secret}</code>
          <label>
            Confirmation code
            <input
              required
              pattern="[0-9]{6}"
              autoComplete="one-time-code"
              inputMode="numeric"
              value={code}
              onChange={(e) => setCode(e.target.value)}
            />
          </label>
          <button className="button">Confirm enrollment</button>
        </form>
      )}
    </div>
  );
}
