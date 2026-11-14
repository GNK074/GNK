import { ConnectionIp } from "../components/ConnectionIp";
import { MfaRecoveryCodes } from "../components/MfaRecoveryCodes";
import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  Check,
  Copy,
  Camera,
  ShieldCheck,
  KeyRound,
  Monitor,
  UserRound,
  LogOut,
  ChevronRight,
  Mail,
  X,
} from "lucide-react";
import { api } from "../services/api";
import { PasswordStrength } from "../components/PasswordStrength";
import type { User } from "../store/session";
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
  const [photo, setPhoto] = useState<File>();
  const [preview, setPreview] = useState("");
  const [crop, setCrop] = useState({ zoom: 1, x: 50, y: 50 });
  const previewImage = useRef<HTMLImageElement>(null);
  useEffect(() => {
    if (!photo) { setPreview(""); return; }
    const url = URL.createObjectURL(photo);
    setPreview(url);
    return () => URL.revokeObjectURL(url);
  }, [photo]);
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
  function choosePhoto(file?: File) {
    if (photoInput.current) photoInput.current.value = "";
    if (!file) return;
    if (file.size > 2 * 1024 * 1024 || !["image/jpeg", "image/png", "image/webp"].includes(file.type)) {
      notify("Choose a JPEG, PNG or WebP image up to 2 MB.");
      return;
    }
    setCrop({ zoom: 1, x: 50, y: 50 });
    setPhoto(file);
  }

  async function upload() {
    await action("photo", async () => {
      const image = previewImage.current;
      if (!image?.naturalWidth) throw Error("The image could not be read.");
      const side = Math.min(image.naturalWidth, image.naturalHeight) / crop.zoom;
      const canvas = document.createElement("canvas");
      canvas.width = canvas.height = 512;
      const context = canvas.getContext("2d");
      if (!context) throw Error("Image editing is unavailable.");
      context.drawImage(image, (image.naturalWidth - side) * crop.x / 100,
        (image.naturalHeight - side) * crop.y / 100, side, side, 0, 0, 512, 512);
      const blob = await new Promise<Blob | null>(resolve => canvas.toBlob(resolve, "image/png"));
      if (!blob) throw Error("Could not prepare the photo.");
      const d = await api("/users/me/avatar", "PUT", new File([blob], "avatar.png", { type: blob.type }));
      setPhoto(undefined);
      update(d.user);
      notify(d.message);
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
              onChange={(e) => choosePhoto(e.target.files?.[0])}
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
            {preview && <section aria-label="Edit profile photo" className="avatar-editor">
              <div className="avatar-crop-preview">
                <img ref={previewImage} src={preview} alt="Profile photo preview"
                  style={{ objectPosition: `${crop.x}% ${crop.y}%`, transformOrigin: `${crop.x}% ${crop.y}%`, transform: `scale(${crop.zoom})` }} />
              </div>
              {(["zoom", "x", "y"] as const).map(key => <label key={key}>
                {key === "zoom" ? "Zoom" : key === "x" ? "Horizontal position" : "Vertical position"}
                <input type="range" min={key === "zoom" ? 1 : 0} max={key === "zoom" ? 3 : 100}
                  step={key === "zoom" ? .05 : 1} value={crop[key]}
                  onChange={event => setCrop({ ...crop, [key]: Number(event.target.value) })} />
              </label>)}
              <div className="photo-actions">
                <button type="button" disabled={!!busy} onClick={upload}>Save photo</button>
                <button type="button" disabled={!!busy} onClick={() => setPhoto(undefined)}>Cancel</button>
              </div>
            </section>}
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
          <ConnectionIp notify={notify} />
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
              {!user.mfa_enabled && <Link
                to="/mfa"
                className="settings-text-button"
              >
                Set up
                <ChevronRight size={14} />
              </Link>}
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
          {user.mfa_enabled && (
            <section className="settings-card">
              <h2>Authenticator recovery</h2>
              <MfaRecoveryCodes />
            </section>
          )}
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
