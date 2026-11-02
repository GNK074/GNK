import React, { useEffect, useState } from "react";
import {
  BrowserRouter,
  Link,
  useLocation,
  useNavigate,
} from "react-router-dom";
import {
  Activity,
  ArrowUpRight,
  ArrowRight,
  BarChart3,
  Blocks,
  Cable,
  ChevronRight,
  CircleHelp,
  Command,
  Gauge,
  LayoutDashboard,
  LockKeyhole,
  Search,
  Settings,
  ShieldCheck,
  Square,
  Zap,
} from "lucide-react";
import { api } from "../services/api";
import type { User } from "../store/session";

export function SettingsPage({
  user,
  notify,
}: {
  user: User;
  notify: (s: string) => void;
}) {
  return (
    <>
      <p className="eyebrow">YOUR ACCOUNT</p>
      <h1>Account settings</h1>
      <article className="panel settings">
        <h3>Profile information</h3>
        <form
          onSubmit={async (e) => {
            e.preventDefault();
            try {
              notify(
                (
                  await api(
                    "/users/me",
                    "PUT",
                    Object.fromEntries(new FormData(e.currentTarget)),
                  )
                ).message,
              );
            } catch (e) {
              notify((e as Error).message);
            }
          }}
        >
          <label>
            Full name
            <input
              name="name"
              defaultValue={user.name}
              required
              minLength={2}
            />
          </label>
          <label>
            Email address
            <input value={user.email} disabled />
          </label>
          <button className="button">Save changes</button>
        </form>
        <p className="green">✓ Email verified</p>
        <Link to="/forgot-password" className="text-link">
          Request a password reset →
        </Link>
      </article>
    </>
  );
}
