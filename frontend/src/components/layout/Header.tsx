import { useState, useRef, useEffect } from "react";
import { Activity, Menu, Home, Stethoscope, Settings2, Zap, Wrench, Building2, CreditCard, Calendar } from "lucide-react";
import { Link, useLocation } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import { useAuthStore } from "@/stores/authStore";
import { getSubscriptionStatus } from "@/lib/api";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/stores/appStore";
import { usePersona } from "@/contexts/PersonaContext";
import type { PersonaTier } from "@/stores/personaStore";

const PERSONA_LABELS: Record<PersonaTier, string> = {
  onetime: "Quick answer",
  diy: "DIY",
  enterprise: "Pro / Shop",
};

export function Header() {
  const location = useLocation();
  const sidebarOpen = useAppStore((s) => s.sidebarOpen);
  const setSidebarOpen = useAppStore((s) => s.setSidebarOpen);
  const {
    personaTier,
    setPersonaTier,
    themeMode,
    setThemeMode,
    showTechnicalData,
    setShowTechnicalData,
    hasSelectedPersona,
  } = usePersona();
  const [personaMenuOpen, setPersonaMenuOpen] = useState(false);
  const menuRef = useRef<HTMLDivElement>(null);
  const isHome = location.pathname === "/";
  const isDiagnose = location.pathname === "/diagnose";
  const isFindMechanic = location.pathname === "/find-mechanic";
  const session = useAuthStore((s) => s.session);
  const { data: subscription } = useQuery({
    queryKey: ["subscription", session?.access_token],
    queryFn: () => getSubscriptionStatus(session!.access_token),
    enabled: Boolean(session?.access_token),
  });

  useEffect(() => {
    function handleClickOutside(e: MouseEvent) {
      if (menuRef.current && !menuRef.current.contains(e.target as Node)) {
        setPersonaMenuOpen(false);
      }
    }
    document.addEventListener("mousedown", handleClickOutside);
    return () => document.removeEventListener("mousedown", handleClickOutside);
  }, []);

  return (
    <header className="flex items-center justify-between px-4 sm:px-5 py-2.5 border-b border-surface1/60 bg-mantle/95 backdrop-blur-sm">
      <div className="flex items-center gap-2">
        <Button
          variant="ghost"
          size="sm"
          className="lg:hidden -ml-1"
          onClick={() => setSidebarOpen(!sidebarOpen)}
        >
          <Menu size={18} />
        </Button>
        <Link
          to="/"
          className="flex items-center gap-2 text-text no-underline hover:opacity-90"
        >
          <div className="p-1.5 rounded-lg bg-primary/10">
            <Activity size={20} className="text-primary" />
          </div>
          <span className="text-base font-semibold tracking-tight">Autopilot</span>
        </Link>
      </div>

      <nav className="flex items-center gap-1 sm:gap-2 text-xs text-overlay0">
        {subscription && (
          <Link to="/pricing" className="text-subtext hover:text-text transition-colors" title="Usage and plans">
            {subscription.used}/{subscription.limit}
          </Link>
        )}
        <Link to="/maintenance">
          <Button variant="ghost" size="sm" className="text-subtext">
            <Calendar size={14} />
            <span className="hidden sm:inline">Maintenance</span>
          </Button>
        </Link>
        <Link to="/mechanic/dashboard">
          <Button variant="ghost" size="sm" className="text-subtext">
            <Wrench size={14} />
            <span className="hidden sm:inline">Mechanic</span>
          </Button>
        </Link>
        <Link to="/pricing">
          <Button variant="ghost" size="sm" className="text-subtext">
            <CreditCard size={14} />
            <span className="hidden sm:inline">Pricing</span>
          </Button>
        </Link>
        {(isDiagnose || isFindMechanic) && (
          <Link to="/">
            <Button variant="ghost" size="sm">
              <Home size={14} />
              Home
            </Button>
          </Link>
        )}
        {isHome && hasSelectedPersona && (
          <Link to="/diagnose">
            <Button variant="default" size="sm">
              <Stethoscope size={14} />
              Diagnose
            </Button>
          </Link>
        )}
        {hasSelectedPersona && (
          <div className="relative" ref={menuRef}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPersonaMenuOpen((o) => !o)}
              title="Settings"
            >
              <Settings2 size={14} />
              {personaTier && (
                <span className="hidden sm:inline">{PERSONA_LABELS[personaTier]}</span>
              )}
            </Button>
            {personaMenuOpen && (
              <div className="absolute right-0 top-full mt-1 py-1 rounded-lg border border-surface1 bg-mantle shadow-lg z-50 min-w-[160px]">
                <p className="px-3 py-2 text-[10px] uppercase tracking-wider text-overlay0 font-medium">
                  Mode
                </p>
                {(["onetime", "diy", "enterprise"] as const).map((tier) => (
                  <button
                    key={tier}
                    type="button"
                    onClick={() => {
                      setPersonaTier(tier);
                      setPersonaMenuOpen(false);
                    }}
                    className="w-full flex items-center gap-2 px-3 py-2 text-left text-sm text-text hover:bg-surface0"
                  >
                    {tier === "onetime" && <Zap size={14} className="text-primary" />}
                    {tier === "diy" && <Wrench size={14} className="text-primary" />}
                    {tier === "enterprise" && <Building2 size={14} className="text-primary" />}
                    {PERSONA_LABELS[tier]}
                  </button>
                ))}
                {personaTier === "diy" && (
                  <>
                    <div className="border-t border-surface1 my-1" />
                    <label className="flex items-center gap-2 px-3 py-2 text-sm text-text cursor-pointer hover:bg-surface0">
                      <input
                        type="checkbox"
                        checked={showTechnicalData}
                        onChange={(e) => {
                          setShowTechnicalData(e.target.checked);
                          setPersonaMenuOpen(false);
                        }}
                      />
                      Show technical data
                    </label>
                  </>
                )}
                <div className="border-t border-surface1 my-1" />
                <p className="px-3 py-2 text-[10px] uppercase tracking-wider text-overlay0 font-medium">
                  Theme
                </p>
                <div className="flex gap-1 px-3 py-2">
                  <Button
                    variant={themeMode === "light" ? "primary" : "ghost"}
                    size="sm"
                    className="flex-1"
                    onClick={() => setThemeMode("light")}
                  >
                    Light
                  </Button>
                  <Button
                    variant={themeMode === "dark" ? "primary" : "ghost"}
                    size="sm"
                    className="flex-1"
                    onClick={() => setThemeMode("dark")}
                  >
                    Dark
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
        <span className="hidden sm:inline text-overlay0/80">v0.1.0</span>
      </nav>
    </header>
  );
}
