/**
 * Application shell: top-center nav bar + main content area.
 *
 * NAV-RELOCATION: navigation moved from the left sidebar to an upper-center
 * bar — brand anchored left, nav links centered, user controls right.
 */
import { NavLink, Outlet } from "react-router-dom";
import type { UserInfo } from "@/api/auth";

interface NavItem {
  to: string;
  label: string;
  icon: string;
}

/** Flat, ordered nav for the horizontal bar; `divider` renders a group break before the item. */
const NAV_ITEMS: (NavItem & { divider?: boolean })[] = [
  { to: "/", label: "Dashboard", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" },
  { to: "/actors", label: "Actors", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
  { to: "/evidence", label: "Evidence", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { to: "/graph", label: "Graph", icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 005.656-5.656l-1.1 1.1" },
  { to: "/map", label: "Map", icon: "M9 20l-5.447-2.724A1 1 0 013 16.382V5.618a1 1 0 011.447-.894L9 7m0 13l6-3m-6 3V7m6 10l4.553 2.276A1 1 0 0021 18.382V7.618a1 1 0 00-.553-.894L15 4m0 13V4m0 0L9 7" },
  { to: "/timeline", label: "Timeline", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
  { to: "/investigations", label: "Workspaces", divider: true, icon: "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" },
  { to: "/reports", label: "Reports", icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
  { to: "/infrastructure", label: "Infrastructure", divider: true, icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
  { to: "/monitoring", label: "Monitoring", divider: true, icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
];

const ROLE_LABELS: Record<string, string> = {
  admin: "ADMIN",
  senior_analyst: "SR. ANALYST",
  analyst: "ANALYST",
};

interface Props {
  user: UserInfo;
  onLogout: () => void;
}

export function Layout({ user, onLogout }: Props) {
  return (
    <div className="flex h-full flex-col">
      {/* Top bar: brand left · nav center · user right */}
      <header className="relative flex h-11 shrink-0 items-center justify-between border-b border-line bg-panel px-4">
        {/* Brand */}
        <div
          className="flex items-center gap-2"
          title="PS 26151 · Synthetic data only"
        >
          <img src="/brand/logo-mark-simple.png" alt="" className="h-6 w-6 shrink-0" />
          <span className="text-xs font-bold tracking-wide text-slate-300">
            TRILOK <span className="text-accent">TRACE</span>
          </span>
        </div>

        {/* Upper-center navigation */}
        <nav
          aria-label="Primary"
          className="absolute left-1/2 top-1/2 flex -translate-x-1/2 -translate-y-1/2 items-center"
        >
          {NAV_ITEMS.map((item) => (
            <span key={item.to} className="flex items-center">
              {item.divider && <span className="mx-1.5 h-4 w-px bg-line" aria-hidden />}
              <NavLink
                to={item.to}
                end={item.to === "/"}
                title={item.label}
                className={({ isActive }) =>
                  `flex items-center gap-1.5 rounded px-2 py-1 text-xs transition-colors ${
                    isActive
                      ? "bg-accent/10 text-accentLight font-medium"
                      : "text-slate-500 hover:bg-panel2 hover:text-slate-300"
                  }`
                }
              >
                <svg
                  className="h-3.5 w-3.5 shrink-0"
                  fill="none"
                  viewBox="0 0 24 24"
                  stroke="currentColor"
                  strokeWidth={1.5}
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                </svg>
                <span className="hidden xl:inline">{item.label}</span>
              </NavLink>
            </span>
          ))}
        </nav>

        {/* User controls */}
        <div className="flex items-center gap-3">
          <div className="min-w-0 text-right">
            <p className="truncate text-xs font-medium text-slate-300">
              {user.full_name || user.username}
            </p>
            <p className="text-2xs font-mono leading-tight text-accent">
              {ROLE_LABELS[user.role] || user.role}
            </p>
          </div>
          <button
            onClick={onLogout}
            className="rounded border border-line px-2 py-1 text-2xs text-slate-500 hover:border-danger/40 hover:text-danger/80 transition-colors"
          >
            Sign Out
          </button>
        </div>
      </header>

      {/* Main content */}
      <main className="flex-1 overflow-y-auto bg-base p-5">
        <Outlet />
      </main>
    </div>
  );
}
