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
  diy: "D.I.Y",
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
    <header className="sticky top-0 z-50 flex items-center justify-between px-5 py-3 bg-mantle/95 backdrop-blur-md">
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
          className="flex items-center gap-2.5 no-underline group"
        >
          <div className="p-1.5 rounded-lg bg-[var(--ds-primary)]/10 group-hover:bg-[var(--ds-primary)]/15 transition-colors kinetic-glow">
            <Activity size={18} className="text-[var(--ds-primary)] drop-shadow-[0_0_6px_rgba(88,191,255,0.5)]" />
          </div>
          <span
            className="text-base font-bold tracking-tighter text-[var(--ds-primary)] drop-shadow-[0_0_8px_rgba(88,191,255,0.4)]"
            style={{ fontFamily: '"Space Grotesk", ui-sans-serif, system-ui, sans-serif' }}
          >
            DIAGO
          </span>
        </Link>
      </div>

      <nav className="flex items-center gap-0.5 sm:gap-1">
        {subscription && (
          <Link
            to="/pricing"
            className="hidden sm:flex items-center gap-1.5 px-3 py-1.5 rounded-lg text-xs text-subtext hover:text-text hover:bg-surface0 transition-all"
            title="Usage and plans"
          >
            <span className="text-[var(--ds-secondary-dim)] font-medium">{subscription.used}</span>
            <span className="text-overlay0">/</span>
            <span>{subscription.limit}</span>
          </Link>
        )}
        <Link to="/maintenance">
          <Button variant="ghost" size="sm" className="text-subtext hover:text-text">
            <Calendar size={14} />
            <span className="hidden sm:inline">Maintenance</span>
          </Button>
        </Link>
        <Link to="/mechanic/dashboard">
          <Button variant="ghost" size="sm" className="text-subtext hover:text-text">
            <Wrench size={14} />
            <span className="hidden sm:inline">Mechanic</span>
          </Button>
        </Link>
        <Link to="/pricing">
          <Button variant="ghost" size="sm" className="text-subtext hover:text-text">
            <CreditCard size={14} />
            <span className="hidden sm:inline">Plans</span>
          </Button>
        </Link>
        {(isDiagnose || isFindMechanic) && (
          <Link to="/">
            <Button variant="ghost" size="sm">
              <Home size={14} />
              <span className="hidden sm:inline">Home</span>
            </Button>
          </Link>
        )}
        {isHome && hasSelectedPersona && (
          <Link to="/diagnose">
            <Button variant="primary" size="sm">
              <Stethoscope size={14} />
              Diagnose
            </Button>
          </Link>
        )}
        {hasSelectedPersona && (
          <div className="relative ml-1" ref={menuRef}>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPersonaMenuOpen((o) => !o)}
              title="Settings"
              className="text-subtext hover:text-text"
            >
              <Settings2 size={14} />
              {personaTier && (
                <span className="hidden sm:inline text-xs">{PERSONA_LABELS[personaTier]}</span>
              )}
            </Button>
            {personaMenuOpen && (
              <div className="absolute right-0 top-full mt-2 py-1.5 rounded-xl bg-surface0 shadow-[0_20px_40px_rgba(0,0,0,0.5)] z-50 min-w-[180px]">
                <p className="px-3.5 py-2 text-[10px] uppercase tracking-widest text-overlay0 font-medium">
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
                    className="w-full flex items-center gap-2.5 px-3.5 py-2 text-left text-sm text-text hover:bg-surface1 transition-colors"
                  >
                    {tier === "onetime" && <Zap size={13} className="text-[var(--ds-secondary-dim)]" />}
                    {tier === "diy"     && <Wrench size={13} className="text-[var(--ds-secondary-dim)]" />}
                    {tier === "enterprise" && <Building2 size={13} className="text-[var(--ds-secondary-dim)]" />}
                    {PERSONA_LABELS[tier]}
                    {personaTier === tier && (
                      <span className="ml-auto w-1.5 h-1.5 rounded-full bg-[var(--ds-primary-container)]" />
                    )}
                  </button>
                ))}
                {personaTier === "diy" && (
                  <>
                    <div className="my-1.5 mx-3.5 h-px bg-surface1" />
                    <label className="flex items-center gap-2.5 px-3.5 py-2 text-sm text-text cursor-pointer hover:bg-surface1 transition-colors">
                      <input
                        type="checkbox"
                        checked={showTechnicalData}
                        onChange={(e) => {
                          setShowTechnicalData(e.target.checked);
                          setPersonaMenuOpen(false);
                        }}
                        className="accent-[var(--ds-primary-container)]"
                      />
                      Technical data
                    </label>
                  </>
                )}
                <div className="my-1.5 mx-3.5 h-px bg-surface1" />
                <p className="px-3.5 py-2 text-[10px] uppercase tracking-widest text-overlay0 font-medium">
                  Theme
                </p>
                <div className="flex gap-1.5 px-3.5 pb-2">
                  <Button
                    variant={themeMode === "light" ? "primary" : "ghost"}
                    size="sm"
                    className="flex-1 text-xs"
                    onClick={() => setThemeMode("light")}
                  >
                    Light
                  </Button>
                  <Button
                    variant={themeMode === "dark" ? "primary" : "ghost"}
                    size="sm"
                    className="flex-1 text-xs"
                    onClick={() => setThemeMode("dark")}
                  >
                    Dark
                  </Button>
                </div>
              </div>
            )}
          </div>
        )}
      </nav>
    </header>
  );
}
