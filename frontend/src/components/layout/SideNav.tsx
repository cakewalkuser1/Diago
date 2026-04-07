import { Link, useLocation } from "react-router-dom";
import {
  LayoutDashboard,
  Stethoscope,
  Truck,
  Calendar,
  CreditCard,
  Wrench,
  ChevronLeft,
  ChevronRight,
  Zap,
} from "lucide-react";
import { useAppStore } from "@/stores/appStore";
import { usePersona } from "@/contexts/PersonaContext";
import type { PersonaTier } from "@/stores/personaStore";

const TIER_LABELS: Record<PersonaTier, string> = {
  onetime: "Quick Answer",
  diy: "D.I.Y Repair",
  enterprise: "Pro / Shop",
};

const NAV_ITEMS = [
  { to: "/",               icon: LayoutDashboard, label: "Dashboard" },
  { to: "/diagnose",       icon: Stethoscope,     label: "Diagnostics" },
  { to: "/find-mechanic",  icon: Truck,           label: "Find Mechanic" },
  { to: "/maintenance",    icon: Calendar,        label: "Maintenance" },
  { to: "/pricing",        icon: CreditCard,      label: "Plans" },
  { to: "/mechanic/dashboard", icon: Wrench,      label: "Mechanic Hub" },
];

export function SideNav() {
  const location = useLocation();
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  const { personaTier, hasSelectedPersona } = usePersona();

  const collapsed = !sidebarOpen;

  return (
    <>
      {/* Mobile backdrop */}
      {sidebarOpen && (
        <div
          className="fixed inset-0 z-30 bg-black/60 backdrop-blur-sm md:hidden"
          onClick={() => setSidebarOpen(false)}
        />
      )}

      <aside
        className={`
          fixed left-0 top-0 z-40 h-screen flex flex-col
          bg-mantle border-r border-surface1
          transition-all duration-300 ease-in-out
          ${collapsed ? "-translate-x-full md:translate-x-0 md:w-16" : "translate-x-0 w-64"}
        `}
      >
        {/* Logo row */}
        <div className={`flex items-center h-16 border-b border-surface1 flex-shrink-0 ${collapsed ? "justify-center px-0" : "px-5 justify-between"}`}>
          {!collapsed && (
            <Link to="/" className="flex items-center gap-2.5 no-underline group">
              <div className="p-1.5 rounded-lg bg-primary/10 group-hover:bg-primary/15 transition-colors kinetic-glow">
                <Zap size={16} className="text-primary drop-shadow-[0_0_6px_rgba(88,191,255,0.5)]" />
              </div>
              <span
                className="text-base font-bold tracking-tighter text-primary drop-shadow-[0_0_8px_rgba(88,191,255,0.4)]"
                style={{ fontFamily: '"Space Grotesk", sans-serif' }}
              >
                DIAGO
              </span>
            </Link>
          )}
          <button
            type="button"
            onClick={() => setSidebarOpen(!sidebarOpen)}
            className={`p-1.5 rounded-lg text-subtext hover:text-text hover:bg-surface0 transition-colors hidden md:flex items-center justify-center ${collapsed ? "" : ""}`}
            title={collapsed ? "Expand sidebar" : "Collapse sidebar"}
          >
            {collapsed ? <ChevronRight size={16} /> : <ChevronLeft size={16} />}
          </button>
        </div>

        {/* User info */}
        {!collapsed && hasSelectedPersona && (
          <div className="px-5 py-3 border-b border-surface1 flex-shrink-0">
            <p
              className="text-[10px] font-bold uppercase tracking-widest text-primary"
              style={{ fontFamily: '"Space Grotesk", sans-serif' }}
            >
              {personaTier ? TIER_LABELS[personaTier] : "Guest"}
            </p>
            <p className="text-[10px] text-overlay1 uppercase tracking-widest mt-0.5">
              Station 01 · active
            </p>
          </div>
        )}

        {/* Nav links */}
        <nav className="flex-1 py-3 space-y-0.5 overflow-y-auto">
          {NAV_ITEMS.map(({ to, icon: Icon, label }) => {
            const isActive = to === "/"
              ? location.pathname === "/"
              : location.pathname.startsWith(to);

            return (
              <Link
                key={to}
                to={to}
                title={collapsed ? label : undefined}
                className={`
                  flex items-center gap-4 transition-all duration-200 group
                  ${collapsed ? "px-0 justify-center py-3.5" : "px-5 py-3"}
                  ${isActive
                    ? "text-primary bg-surface0 border-l-4 border-primary font-bold"
                    : "text-subtext hover:text-primary/70 hover:bg-surface0/50 border-l-4 border-transparent hover:translate-x-0.5"}
                `}
                style={{ fontFamily: '"Space Grotesk", sans-serif' }}
                onClick={() => { if (window.innerWidth < 768) setSidebarOpen(false); }}
              >
                <Icon
                  size={18}
                  className={`flex-shrink-0 transition-colors ${isActive ? "text-primary" : "text-subtext group-hover:text-primary/70"}`}
                />
                {!collapsed && (
                  <span className="text-xs uppercase tracking-widest">{label}</span>
                )}
              </Link>
            );
          })}
        </nav>

        {/* CTA */}
        <div className={`flex-shrink-0 border-t border-surface1 ${collapsed ? "p-3" : "p-4"}`}>
          <Link to="/diagnose" onClick={() => { if (window.innerWidth < 768) setSidebarOpen(false); }}>
            <button
              type="button"
              className={`
                w-full bg-gradient-primary text-white font-bold text-xs tracking-widest uppercase rounded-lg
                hover:shadow-[0_0_22px_rgba(0,168,238,0.4)] active:scale-[0.98] transition-all kinetic-glow
                ${collapsed ? "p-2.5 flex items-center justify-center" : "py-3"}
              `}
              style={{ fontFamily: '"Space Grotesk", sans-serif' }}
            >
              {collapsed ? <Stethoscope size={16} /> : "Initialize Scan"}
            </button>
          </Link>
        </div>
      </aside>
    </>
  );
}
