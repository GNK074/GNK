import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  Copy,
  Camera,
  ShieldCheck,
  KeyRound,
  Monitor,
  Palette,
  UserRound,
  LogOut,
  ChevronRight,
  Mail,
  X,
} from "lucide-react";
import { api } from "../services/api";
import { applyTheme } from "../services/theme";
import { PasswordStrength } from "../components/PasswordStrength";
import type { Theme, User } from "../store/session";
type Device = {
  id: string;
  agent: string;
  created: string;
  expires: string;
  current: boolean;
  revoked: boolean;
  expired: boolean;
};
export function SettingsPage({
  user: initial,
  notify,
  onUpdate,
  onSignOut,
}: {
  user: User;
  notify: (s: string) => void;
  onUpdate: (u: User) => void;
  onSignOut: () => void;
}) {
  const [user, setUser] = useState(initial),
    [editing, setEditing] = useState(false),
    [busy, setBusy] = useState(""),
    [error, setError] = useState(""),
    [copied, setCopied] = useState(false);
  const [passwordOpen, setPasswordOpen] = useState(false),
    [password, setPassword] = useState(""),
    [emailOpen, setEmailOpen] = useState(false),
    [devicesOpen, setDevicesOpen] = useState(false),
    [devices, setDevices] = useState<Device[]>([]),
    [deviceError, setDeviceError] = useState("");
  const photoInput = useRef<HTMLInputElement>(null);
  function update(u: User) {
    setUser(u);
    onUpdate(u);
  }
  useEffect(() => {
    let live = true;
    api("/users/me")
      .then((d) => {
        if (live) {
          setUser(d.user);
          onUpdate(d.user);
          applyTheme(d.user.theme || "carbon_black");
        }
      })
      .catch((e) => live && setError(e.message));
    return () => {
      live = false;
    };
  }, []);
  async function action(key: string, task: () => Promise<void>) {
    if (busy) return;
    setBusy(key);
    setError("");
    try {
      await task();
    } catch (e) {
      setError((e as Error).message);
      notify((e as Error).message);
    } finally {
      setBusy("");
    }
  }
  async function loadDevices() {
    setDeviceError("");
    try {
      setDevices(await api("/users/me/sessions"));
    } catch (e) {
      setDeviceError((e as Error).message);
    }
  }
  async function upload(file?: File) {
    if (!file) return;
    await action("photo", async () => {
      if (file.size > 2 * 1024 * 1024)
        throw Error("Choose an image 2 MB or smaller.");
      const d = await api("/users/me/avatar", "PUT", file);
      update(d.user);
      notify(d.message);
    });
    if (photoInput.current) photoInput.current.value = "";
  }
  async function theme(value: Theme) {
    const before = user.theme || "carbon_black";
    await action("theme", async () => {
      applyTheme(value);
      setUser({ ...user, theme: value });
      try {
        const d = await api("/users/me/preferences", "PUT", { theme: value });
        update(d.user);
      } catch (e) {
        applyTheme(before);
        setUser({ ...user, theme: before });
        throw e;
      }
    });
  }
  const date = new Date().toISOString().slice(0, 10);
  return (
    <div className="profile-settings">
      <div className="settings-title">
        <div>
          <p className="eyebrow">YOUR WORKSPACE, YOUR WAY</p>
          <h1>Profile & settings</h1>
          <p>Manage your personal details, security and preferences.</p>
        </div>
        <span className="settings-secure">
          <ShieldCheck size={15} /> Secure account
        </span>
      </div>
      {error && (
        <div className="settings-alert" role="alert">
          {error}
          <button aria-label="Dismiss error" onClick={() => setError("")}>
            <X size={16} />
          </button>
        </div>
      )}
      <div className="settings-grid">
        <section className="profile-summary">
          <div className="profile-cover">
            <span>GNK ALGO</span>
            <i />
            <i />
          </div>
          <div className="profile-identity">
            <div className="profile-photo">
              {user.avatar_url ? (
                <img src={user.avatar_url} alt={`${user.name}'s profile`} />
              ) : (
                <span>
                  {user.name
                    .split(" ")
                    .map((n) => n[0])
                    .slice(0, 2)
                    .join("")
                    .toUpperCase()}
                </span>
              )}
              <button
                disabled={!!busy}
                aria-label="Upload profile photo"
                onClick={() => photoInput.current?.click()}
              >
                <Camera size={16} />
              </button>
            </div>
            <h2>{user.name}</h2>
            <p className="profile-email">{user.email}</p>
            <span
              className={`account-badge ${user.active === false ? "inactive" : ""}`}
            >
              <i />
              {user.active === false
                ? "Inactive account"
                : user.verified
                  ? "Verified account"
                  : "Email verification pending"}
            </span>
            <input
              ref={photoInput}
              type="file"
              accept="image/png,image/jpeg,image/webp"
              hidden
              onChange={(e) => upload(e.target.files?.[0])}
            />
            <div className="photo-actions">
              <button
                disabled={!!busy}
                onClick={() => photoInput.current?.click()}
              >
                {busy === "photo" ? "Uploading…" : "Upload new"}
              </button>
              <button
                disabled={!!busy || !user.avatar_url}
                onClick={() =>
                  action("photo", async () => {
                    const d = await api("/users/me/avatar", "DELETE");
                    update(d.user);
                    notify(d.message);
                  })
                }
              >
                Reset
              </button>
            </div>
            <small>JPG, PNG or WebP · Max 2 MB</small>
          </div>
          <div className="profile-meta">
            <span>USER ID</span>
            <div>
              <code>{user.id || "Loading…"}</code>
              <button
                aria-label="Copy user ID"
                onClick={async () => {
                  try {
                    await navigator.clipboard.writeText(user.id);
                    setCopied(true);
                    setTimeout(() => setCopied(false), 2000);
                  } catch {
                    notify(
                      "Clipboard unavailable. Select and copy your user ID.",
                    );
                  }
                }}
              >
                {copied ? <Check size={16} /> : <Copy size={16} />}
              </button>
            </div>
            {copied && <small role="status">User ID copied</small>}
          </div>
          <div className="profile-note">
            <ShieldCheck size={20} />
            <p>
              Your account. Your control.
              <small>
                Keep your information current and your workspace protected.
              </small>
            </p>
          </div>
        </section>
        <div className="settings-main">
          <section className="settings-card" id="profile-details">
            <div className="card-heading">
              <div className="section-icon">
                <UserRound size={19} />
              </div>
              <div>
                <h2>Profile details</h2>
                <p>Your personal information, in one place.</p>
              </div>
              {!editing && (
                <button
                  className="subtle-button"
                  disabled={!!busy}
                  onClick={() => setEditing(true)}
                >
                  Edit profile
                </button>
              )}
            </div>
            <form
              key={JSON.stringify([
                editing,
                user.name,
                user.email,
                user.gender,
                user.date_of_birth,
                user.mobile,
              ])}
              onSubmit={(e) => {
                e.preventDefault();
                const data = Object.fromEntries(new FormData(e.currentTarget));
                action("profile", async () => {
                  const d = await api("/users/me", "PUT", {
                    name: data.name,
                    gender: data.gender || null,
                    date_of_birth: data.date_of_birth || null,
                    mobile: data.mobile || null,
                  });
                  update(d.user);
                  setEditing(false);
                  notify(d.message);
                });
              }}
            >
              <div className="profile-fields">
                <label>
                  Full name
                  <input
                    name="name"
                    defaultValue={user.name}
                    readOnly={!editing}
                    required
                    minLength={2}
                    maxLength={100}
                    autoComplete="name"
                  />
                </label>
                <label>
                  Gender
                  <select
                    aria-label="Gender"
                    name="gender"
                    defaultValue={user.gender || ""}
                    disabled={!editing}
                  >
                    <option value="">Not specified</option>
                    <option value="female">Female</option>
                    <option value="male">Male</option>
                    <option value="non_binary">Non-binary</option>
                    <option value="prefer_not_to_say">Prefer not to say</option>
                  </select>
                </label>
                <label>
                  Date of birth
                  <input
                    type="date"
                    name="date_of_birth"
                    defaultValue={user.date_of_birth || ""}
                    readOnly={!editing}
                    min="1900-01-01"
                    max={date}
                    autoComplete="bday"
                  />
                </label>
                <label>
                  Mobile number
                  <input
                    type="tel"
                    name="mobile"
                    defaultValue={user.mobile || ""}
                    placeholder="+919876543210"
                    readOnly={!editing}
                    pattern="\+[1-9][0-9]{7,14}"
                    title="International format without spaces, for example +919876543210"
                    autoComplete="tel"
                  />
                </label>
                <label className="field-wide">
                  Email address
                  <div className="email-field">
                    <input value={user.email} readOnly type="email" />
                    <span>
                      <Check size={13} />
                      {user.verified ? "Verified" : "Pending"}
                    </span>
                  </div>
                </label>
              </div>
              {editing && (
                <div className="settings-form-actions">
                  <button
                    type="button"
                    disabled={!!busy}
                    className="subtle-button"
                    onClick={() => setEditing(false)}
                  >
                    Cancel
                  </button>
                  <button disabled={!!busy} className="settings-primary">
                    {busy === "profile" ? "Saving…" : "Save changes"}
                  </button>
                </div>
              )}
            </form>
            <div className="card-footnote">
              <Mail size={14} />
              <span>Email changes require verification.</span>
              <button
                disabled={!!busy}
                onClick={() => setEmailOpen(!emailOpen)}
              >
                {emailOpen ? "Cancel" : "Change email"}
                <ChevronRight size={14} />
              </button>
            </div>
            {emailOpen && (
              <form
                className="settings-inline"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = Object.fromEntries(new FormData(e.currentTarget));
                  const form = e.currentTarget;
                  action("email", async () => {
                    const d = await api("/auth/change-email", "POST", f);
                    notify(d.message);
                    form.reset();
                    setEmailOpen(false);
                  });
                }}
              >
                <label>
                  New email address
                  <input
                    name="email"
                    type="email"
                    autoComplete="email"
                    required
                    maxLength={254}
                  />
                </label>
                <label>
                  Current password
                  <input
                    type="password"
                    name="current_password"
                    required
                    autoComplete="current-password"
                    maxLength={128}
                  />
                </label>
                <p>
                  A confirmation link will be sent to the new address.
                  Confirming signs out all sessions.
                </p>
                <button className="settings-primary" disabled={!!busy}>
                  Send confirmation link
                </button>
              </form>
            )}
          </section>
          <section className="settings-card">
            <div className="card-heading">
              <div className="section-icon">
                <KeyRound size={19} />
              </div>
              <div>
                <h2>Password & security</h2>
                <p>A little peace of mind for every session.</p>
              </div>
              <span className="protected-badge">
                <ShieldCheck size={13} /> Protected
              </span>
            </div>
            <div className="setting-row">
              <div>
                <h3>Password</h3>
                <p>Use a strong, unique password for your account.</p>
              </div>
              <button
                className="subtle-button"
                disabled={!!busy}
                onClick={() => setPasswordOpen(!passwordOpen)}
              >
                {passwordOpen ? "Cancel" : "Change password"}
              </button>
            </div>
            {passwordOpen && (
              <form
                className="settings-inline"
                onSubmit={(e) => {
                  e.preventDefault();
                  const f = Object.fromEntries(new FormData(e.currentTarget));
                  action("password", async () => {
                    if (f.password !== f.confirm)
                      throw Error("Passwords do not match.");
                    await api("/auth/change-password", "POST", {
                      current_password: f.current_password,
                      password: f.password,
                    });
                    window.location.assign("/login");
                  });
                }}
              >
                <label>
                  Current password
                  <input
                    name="current_password"
                    type="password"
                    required
                    autoComplete="current-password"
                    maxLength={128}
                  />
                </label>
                <label>
                  New password
                  <input
                    name="password"
                    type="password"
                    value={password}
                    onChange={(e) => setPassword(e.target.value)}
                    required
                    minLength={12}
                    maxLength={128}
                    autoComplete="new-password"
                  />
                </label>
                <PasswordStrength value={password} />
                <label>
                  Confirm new password
                  <input
                    name="confirm"
                    type="password"
                    required
                    autoComplete="new-password"
                    maxLength={128}
                  />
                </label>
                <p>
                  Changing your password signs out all devices, including this
                  one.
                </p>
                <button className="settings-primary" disabled={!!busy}>
                  Update password & sign out
                </button>
              </form>
            )}
            <div className="setting-row">
              <div>
                <h3>Password recovery</h3>
                <p>Receive a reset link at your registered email.</p>
              </div>
              <button
                className="settings-text-button"
                disabled={!!busy}
                onClick={() =>
                  action("reset", async () => {
                    const d = await api("/auth/forgot-password", "POST", {
                      email: user.email,
                    });
                    notify(d.message);
                  })
                }
              >
                Request reset
                <ChevronRight size={14} />
              </button>
            </div>
            <div className="setting-row">
              <div>
                <h3>Two-factor authentication</h3>
                <p>
                  {user.mfa_enabled
                    ? "Authenticator verification is enabled."
                    : "Add an authenticator to protect sign-ins."}
                </p>
              </div>
              <Link
                to={user.mfa_enabled ? "/user/security" : "/mfa"}
                className="settings-text-button"
              >
                {user.mfa_enabled ? "View security" : "Set up"}
                <ChevronRight size={14} />
              </Link>
            </div>
            <div className="setting-row">
              <div>
                <h3>
                  <Monitor size={15} /> Active sessions
                </h3>
                <p>Review devices and revoke access remotely.</p>
              </div>
              <button
                className="settings-text-button"
                onClick={() => {
                  setDevicesOpen(!devicesOpen);
                  if (!devicesOpen) loadDevices();
                }}
              >
                {devicesOpen ? "Hide sessions" : "Manage sessions"}
                <ChevronRight size={14} />
              </button>
            </div>
            {devicesOpen && (
              <div className="session-list">
                {deviceError && <p role="alert">{deviceError}</p>}
                {!devices.length && !deviceError && (
                  <p>No sessions to display.</p>
                )}
                {devices.map((d) => (
                  <div className="session-item" key={d.id}>
                    <Monitor size={18} />
                    <div>
                      <strong>
                        {d.current ? "This device" : "Browser session"}
                      </strong>
                      <small title={d.agent}>
                        {d.agent || "Unknown browser"}
                      </small>
                      <small>
                        Signed in {new Date(d.created).toLocaleString()} ·{" "}
                        {d.revoked
                          ? "Signed out"
                          : d.expired
                            ? "Expired"
                            : "Active"}
                      </small>
                    </div>
                    {!d.revoked && !d.expired && !d.current && (
                      <button
                        className="subtle-button"
                        disabled={!!busy}
                        onClick={() =>
                          action("session", async () => {
                            await api(`/users/me/sessions/${d.id}`, "DELETE");
                            await loadDevices();
                            notify("Session signed out");
                          })
                        }
                      >
                        Revoke
                      </button>
                    )}
                    {d.current && (
                      <span className="current-badge">Current</span>
                    )}
                  </div>
                ))}
              </div>
            )}
          </section>
          <section className="settings-card">
            <div className="card-heading">
              <div className="section-icon">
                <Palette size={19} />
              </div>
              <div>
                <h2>Appearance</h2>
                <p>Make this workspace feel like yours.</p>
              </div>
            </div>
            <div
              className="theme-options"
              role="group"
              aria-label="Workspace theme"
            >
              {(
                [
                  ["light", "Light"],
                  ["carbon_black", "Carbon Black"],
                  ["royal_blue", "Royal Blue"],
                ] as [Theme, string][]
              ).map(([value, label]) => (
                <button
                  key={value}
                  disabled={!!busy}
                  className={`theme-option ${user.theme === value ? "is-selected" : ""}`}
                  aria-pressed={user.theme === value}
                  onClick={() => theme(value)}
                >
                  <span className={`theme-preview preview-${value}`}>
                    <i className="preview-nav" />
                    <i className="preview-top" />
                    <i className="preview-card" />
                    <i className="preview-card second" />
                    <i className="preview-line" />
                  </span>
                  <span className="theme-label">
                    {label}
                    <span className="theme-radio">
                      {user.theme === value && <Check size={11} />}
                    </span>
                  </span>
                </button>
              ))}
            </div>
            <p className="theme-hint">
              Applied instantly. Saved to your account for your next visit.
            </p>
          </section>
          <section className="settings-card">
            <div className="card-heading">
              <div className="section-icon">
                <ShieldCheck size={19} />
              </div>
              <div>
                <h2>Account settings</h2>
                <p>Stay informed. Stay in control.</p>
              </div>
            </div>
            <details className="account-details">
              <summary>
                Account information
                <ChevronRight size={16} />
              </summary>
              <dl>
                <div>
                  <dt>Account type</dt>
                  <dd>
                    {user.role === "ADMIN" ? "Administrator" : "Individual"}
                  </dd>
                </div>
                <div>
                  <dt>Member since</dt>
                  <dd>
                    {user.created
                      ? new Date(user.created).toLocaleDateString()
                      : "—"}
                  </dd>
                </div>
                <div>
                  <dt>Email status</dt>
                  <dd>{user.verified ? "Verified" : "Pending"}</dd>
                </div>
              </dl>
            </details>
            <Link to="/user/security" className="account-link">
              Security preferences
              <ChevronRight size={16} />
            </Link>
            <button className="account-signout" onClick={onSignOut}>
              <span>
                <LogOut size={16} />
                Sign out
              </span>
              <ChevronRight size={16} />
            </button>
          </section>
        </div>
      </div>
      <p className="settings-bottom">
        <ShieldCheck size={13} /> Your preferences are saved securely to your
        GNK ALGO account.
      </p>
    </div>
  );
}
