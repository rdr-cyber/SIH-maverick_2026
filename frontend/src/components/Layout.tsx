/** Application shell: sidebar nav + main content area. */
import { NavLink, Outlet } from "react-router-dom";
import type { UserInfo } from "@/api/auth";

interface NavSection {
  label: string;
  items: { to: string; label: string; icon: string }[];
}

const NAV_SECTIONS: NavSection[] = [
  {
    label: "OVERVIEW",
    items: [
      { to: "/", label: "Dashboard", icon: "M3 12l2-2m0 0l7-7 7 7M5 10v10a1 1 0 001 1h3m10-11l2 2m-2-2v10a1 1 0 01-1 1h-3m-4 0h4" },
      { to: "/actors", label: "Actors", icon: "M17 20h5v-2a3 3 0 00-5.356-1.857M17 20H7m10 0v-2c0-.656-.126-1.283-.356-1.857M7 20H2v-2a3 3 0 015.356-1.857M7 20v-2c0-.656.126-1.283.356-1.857m0 0a5.002 5.002 0 019.288 0M15 7a3 3 0 11-6 0 3 3 0 016 0z" },
      { to: "/evidence", label: "Evidence", icon: "M9 12h6m-6 4h6m2 5H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
      { to: "/graph", label: "Graph", icon: "M13.828 10.172a4 4 0 00-5.656 0l-4 4a4 4 0 105.656 5.656l1.102-1.101m-.758-4.899a4 4 0 005.656 0l4-4a4 4 0 00-5.656-5.656l-1.1 1.1" },
      { to: "/timeline", label: "Timeline", icon: "M12 8v4l3 3m6-3a9 9 0 11-18 0 9 9 0 0118 0z" },
    ],
  },
  {
    label: "INVESTIGATIONS",
    items: [
      { to: "/investigations", label: "Workspaces", icon: "M3 7v10a2 2 0 002 2h14a2 2 0 002-2V9a2 2 0 00-2-2h-6l-2-2H5a2 2 0 00-2 2z" },
      { to: "/reports", label: "Reports", icon: "M9 17v-2m3 2v-4m3 4v-6m2 10H7a2 2 0 01-2-2V5a2 2 0 012-2h5.586a1 1 0 01.707.293l5.414 5.414a1 1 0 01.293.707V19a2 2 0 01-2 2z" },
    ],
  },
  {
    label: "INTELLIGENCE",
    items: [
      { to: "/infrastructure", label: "Infrastructure", icon: "M19 21V5a2 2 0 00-2-2H7a2 2 0 00-2 2v16m14 0h2m-2 0h-5m-9 0H3m2 0h5M9 7h1m-1 4h1m4-4h1m-1 4h1m-5 10v-5a1 1 0 011-1h2a1 1 0 011 1v5m-4 0h4" },
    ],
  },
  {
    label: "OPERATIONS",
    items: [
      { to: "/monitoring", label: "Monitoring", icon: "M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" },
    ],
  },
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
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-52 shrink-0 flex-col border-r border-line bg-panel">
        {/* Brand */}
        <div className="flex h-11 items-center border-b border-line px-4">
          <svg className="h-4 w-4 text-accent mr-2 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={2}>
            <path strokeLinecap="round" strokeLinejoin="round" d="M21 21l-6-6m2-5a7 7 0 11-14 0 7 7 0 0114 0z" />
          </svg>
          <span className="text-xs font-bold tracking-wide text-slate-300">
            MAVERICKS
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto py-2 px-2">
          {NAV_SECTIONS.map((section) => (
            <div key={section.label} className="mb-3">
              <p className="mb-1 px-2 text-2xs font-semibold uppercase tracking-widest text-slate-600">
                {section.label}
              </p>
              {section.items.map((item) => (
                <NavLink
                  key={item.to}
                  to={item.to}
                  end={item.to === "/"}
                  className={({ isActive }) =>
                    `flex items-center gap-2 rounded px-2.5 py-1.5 text-xs transition-colors ${
                      isActive
                        ? "bg-accent/10 text-accentLight font-medium"
                        : "text-slate-500 hover:bg-panel2 hover:text-slate-300"
                    }`
                  }
                >
                  <svg className="h-3.5 w-3.5 shrink-0" fill="none" viewBox="0 0 24 24" stroke="currentColor" strokeWidth={1.5}>
                    <path strokeLinecap="round" strokeLinejoin="round" d={item.icon} />
                  </svg>
                  {item.label}
                </NavLink>
              ))}
            </div>
          ))}
        </nav>

        {/* User */}
        <div className="border-t border-line px-3 py-2.5">
          <div className="flex items-center justify-between mb-2">
            <div className="min-w-0">
              <p className="text-xs font-medium text-slate-300 truncate">{user.full_name || user.username}</p>
              <p className="text-2xs text-accent font-mono">{ROLE_LABELS[user.role] || user.role}</p>
            </div>
          </div>
          <button
            onClick={onLogout}
            className="w-full rounded border border-line px-2 py-1 text-2xs text-slate-500 hover:border-danger/40 hover:text-danger/80 transition-colors"
          >
            Sign Out
          </button>
        </div>

        {/* Footer */}
        <div className="border-t border-line px-3 py-2">
          <p className="text-2xs text-slate-700">PS 26151</p>
          <p className="text-2xs text-slate-700">Synthetic data only</p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-y-auto bg-base p-5">
        <Outlet />
      </main>
    </div>
  );
}
