import { create } from "zustand";
import { persist } from "zustand/middleware";

export type PersonaTier = "onetime" | "diy" | "enterprise";
export type ThemeMode = "light" | "dark";

const STORAGE_KEY = "diago-persona";

interface PersonaState {
  personaTier: PersonaTier | null;
  themeMode: ThemeMode | null;
  showTechnicalData: boolean;

  setPersonaTier: (tier: PersonaTier) => void;
  setThemeMode: (mode: ThemeMode) => void;
  setShowTechnicalData: (show: boolean) => void;

  /** Resolve effective theme: tier default or user override */
  getEffectiveTheme: () => ThemeMode;

  /** Clear stored persona (e.g. for testing) */
  clearPersona: () => void;
}

const DEFAULT_THEME_BY_TIER: Record<PersonaTier, ThemeMode> = {
  onetime: "light",
  diy: "light",
  enterprise: "dark",
};

export const usePersonaStore = create<PersonaState>()(
  persist(
    (set, get) => ({
      personaTier: null,
      themeMode: null,
      showTechnicalData: true,

      setPersonaTier: (tier) => set({ personaTier: tier }),
      setThemeMode: (mode) => set({ themeMode: mode }),
      setShowTechnicalData: (show) => set({ showTechnicalData: show }),

      getEffectiveTheme: () => {
        const { themeMode, personaTier } = get();
        if (themeMode) return themeMode;
        if (personaTier) return DEFAULT_THEME_BY_TIER[personaTier];
        return "dark";
      },

      clearPersona: () =>
        set({
          personaTier: null,
          themeMode: null,
          showTechnicalData: true,
        }),
    }),
    {
      name: STORAGE_KEY,
      partialize: (s) => ({
        personaTier: s.personaTier,
        themeMode: s.themeMode,
        showTechnicalData: s.showTechnicalData,
      }),
    }
  )
);
