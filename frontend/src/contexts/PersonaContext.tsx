import {
  createContext,
  useContext,
  useEffect,
  type ReactNode,
} from "react";
import {
  usePersonaStore,
  type PersonaTier,
  type ThemeMode,
} from "@/stores/personaStore";

interface PersonaContextValue {
  personaTier: PersonaTier | null;
  themeMode: ThemeMode;
  showTechnicalData: boolean;
  setPersonaTier: (tier: PersonaTier) => void;
  setThemeMode: (mode: ThemeMode) => void;
  setShowTechnicalData: (show: boolean) => void;
  hasSelectedPersona: boolean;
}

const PersonaContext = createContext<PersonaContextValue | null>(null);

export function PersonaProvider({ children }: { children: ReactNode }) {
  const personaTier = usePersonaStore((s) => s.personaTier);
  const showTechnicalData = usePersonaStore((s) => s.showTechnicalData);
  const setPersonaTier = usePersonaStore((s) => s.setPersonaTier);
  const setThemeMode = usePersonaStore((s) => s.setThemeMode);
  const setShowTechnicalData = usePersonaStore((s) => s.setShowTechnicalData);
  const getEffectiveTheme = usePersonaStore((s) => s.getEffectiveTheme);

  const effectiveTheme = getEffectiveTheme();

  useEffect(() => {
    document.documentElement.setAttribute("data-theme", effectiveTheme);
  }, [effectiveTheme]);

  const value: PersonaContextValue = {
    personaTier,
    themeMode: effectiveTheme,
    showTechnicalData,
    setPersonaTier,
    setThemeMode,
    setShowTechnicalData,
    hasSelectedPersona: personaTier !== null,
  };

  return (
    <PersonaContext.Provider value={value}>{children}</PersonaContext.Provider>
  );
}

export function usePersona(): PersonaContextValue {
  const ctx = useContext(PersonaContext);
  if (!ctx) {
    throw new Error("usePersona must be used within PersonaProvider");
  }
  return ctx;
}

export function usePersonaOptional(): PersonaContextValue | null {
  return useContext(PersonaContext);
}
