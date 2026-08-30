/** Application shell: sidebar nav + main content area. */
import { NavLink, Outlet } from "react-router-dom";

const NAV = [
  { to: "/", label: "Command Center", icon: "◻" },
  { to: "/actors", label: "Actor Search", icon: "🔍" },
  { to: "/evidence", label: "Evidence", icon: "📋" },
  { to: "/graph", label: "Graph", icon: "🔗" },
  { to: "/timeline", label: "Timeline", icon: "📅" },
  { to: "/infrastructure", label: "Infrastructure", icon: "🏗" },
  { to: "/monitoring", label: "Monitoring", icon: "📡" },
  { to: "/investigations", label: "Investigations", icon: "📁" },
  { to: "/reports", label: "Reports", icon: "📊" },
];

export function Layout() {
  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="flex w-56 shrink-0 flex-col border-r border-line bg-panel">
        {/* Logo */}
        <div className="flex h-12 items-center border-b border-line px-4">
          <span className="text-sm font-bold tracking-wider text-slate-200">
            SHADOW<span className="text-teal-400">GRAPH</span>
          </span>
          <span className="ml-2 rounded bg-slate-800 px-1.5 py-0.5 text-[10px] text-slate-500">
            SIH
          </span>
        </div>

        {/* Navigation */}
        <nav className="flex-1 overflow-y-auto px-2 py-3">
          {NAV.map((item) => (
            <NavLink
              key={item.to}
              to={item.to}
              end={item.to === "/"}
              className={({ isActive }) =>
                `flex items-center gap-2.5 rounded-md px-3 py-2 text-sm transition-colors ${
                  isActive
                    ? "bg-teal-700/15 text-teal-400"
                    : "text-slate-400 hover:bg-slate-800/50 hover:text-slate-300"
                }`
              }
            >
              <span className="text-base">{item.icon}</span>
              {item.label}
            </NavLink>
          ))}
        </nav>

        {/* Footer */}
        <div className="border-t border-line px-4 py-3">
          <p className="text-[10px] text-slate-600">
            Synthetic data only
          </p>
          <p className="text-[10px] text-slate-600">
            PS 26151 · NTRO
          </p>
        </div>
      </aside>

      {/* Main content */}
      <main className="flex flex-1 flex-col overflow-y-auto bg-base p-6">
        <Outlet />
      </main>
    </div>
  );
}
