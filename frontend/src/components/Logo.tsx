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

export function Logo() {
  return (
    <Link to="/" className="logo">
      <span>
        <Activity size={25} />
      </span>{" "}
      GNK<span className="word">ALGO</span>
    </Link>
  );
}
