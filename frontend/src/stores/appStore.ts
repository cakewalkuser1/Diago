import { create } from "zustand";
import type {
  BehavioralContext,
  DiagnosisResponse,
  ChatMessage,
  ViewMode,
  RecordDuration,
  VehicleSelection,
} from "@/types";
import { DEFAULT_CONTEXT } from "@/types";
import { uid } from "@/lib/utils";

/* ─── App Store ─── */
interface AppState {
  /* Audio */
  audioBlob: Blob | null;
  audioFileName: string | null;
  isRecording: boolean;
  recordDuration: RecordDuration;
  viewMode: ViewMode;

  /* Context & Codes */
  context: BehavioralContext;
  symptoms: string;
  activeCodes: string[];

  /* Diagnosis */
  diagnosis: DiagnosisResponse | null;
  isDiagnosing: boolean;

  /* Chat */
  chatMessages: ChatMessage[];
  chatMode: "keyword" | "agent";

  /* UI */
  activeTab: "symptoms" | "results" | "chat";
  sidebarOpen: boolean;

  /* Vehicle (year/make/model/trim for start diagnosis) */
  vehicleSelection: VehicleSelection;

  /* Fuel trims (optional, for DIYer) */
  fuelTrims: { stft: number | null; ltft: number | null };

  /* Actions */
  setAudioBlob: (blob: Blob | null, fileName?: string) => void;
  setIsRecording: (v: boolean) => void;
  setRecordDuration: (d: RecordDuration) => void;
  setViewMode: (m: ViewMode) => void;
  setContext: (ctx: Partial<BehavioralContext>) => void;
  resetContext: () => void;
  setSymptoms: (s: string) => void;
  addCode: (code: string) => void;
  removeCode: (code: string) => void;
  clearCodes: () => void;
  setDiagnosis: (d: DiagnosisResponse | null) => void;
  setIsDiagnosing: (v: boolean) => void;
  addChatMessage: (role: ChatMessage["role"], content: string) => void;
  clearChat: () => void;
  setChatMode: (m: "keyword" | "agent") => void;
  setActiveTab: (t: "symptoms" | "results" | "chat") => void;
  setSidebarOpen: (v: boolean) => void;
  setVehicleSelection: (v: Partial<VehicleSelection> | null) => void;
  setFuelTrims: (v: Partial<{ stft: number | null; ltft: number | null }>) => void;
}

export const useAppStore = create<AppState>((set) => ({
  /* Initial state */
  audioBlob: null,
  audioFileName: null,
  isRecording: false,
  recordDuration: "5",
  viewMode: "spectrogram",

  context: { ...DEFAULT_CONTEXT },
  symptoms: "",
  activeCodes: [],

  diagnosis: null,
  isDiagnosing: false,

  chatMessages: [],
  chatMode: "keyword",

  activeTab: "symptoms",
  sidebarOpen: false,

  vehicleSelection: {
    year: null,
    makeId: null,
    makeName: "",
    modelId: null,
    modelName: "",
    trim: "",
  },

  fuelTrims: { stft: null, ltft: null },

  /* Actions */
  setAudioBlob: (blob, fileName) =>
    set({ audioBlob: blob, audioFileName: fileName ?? null }),
  setIsRecording: (v) => set({ isRecording: v }),
  setRecordDuration: (d) => set({ recordDuration: d }),
  setViewMode: (m) => set({ viewMode: m }),

  setContext: (ctx) =>
    set((state) => ({ context: { ...state.context, ...ctx } })),
  resetContext: () => set({ context: { ...DEFAULT_CONTEXT } }),
  setSymptoms: (s) => set({ symptoms: s }),

  addCode: (code) =>
    set((state) => {
      const upper = code.toUpperCase().trim();
      if (!upper || state.activeCodes.includes(upper)) return state;
      return { activeCodes: [...state.activeCodes, upper] };
    }),
  removeCode: (code) =>
    set((state) => ({
      activeCodes: state.activeCodes.filter((c) => c !== code),
    })),
  clearCodes: () => set({ activeCodes: [] }),

  setDiagnosis: (d) => set({ diagnosis: d }),
  setIsDiagnosing: (v) => set({ isDiagnosing: v }),

  addChatMessage: (role, content) =>
    set((state) => ({
      chatMessages: [
        ...state.chatMessages,
        { id: uid(), role, content, timestamp: new Date() },
      ],
    })),
  clearChat: () => set({ chatMessages: [] }),
  setChatMode: (m) => set({ chatMode: m }),

  setActiveTab: (t) => set({ activeTab: t }),
  setSidebarOpen: (v) => set({ sidebarOpen: v }),
  setVehicleSelection: (v) =>
    set((state) => ({
      vehicleSelection:
        v === null
          ? {
              year: null,
              makeId: null,
              makeName: "",
              modelId: null,
              modelName: "",
              trim: "",
            }
          : { ...state.vehicleSelection, ...v },
    })),
  setFuelTrims: (v) =>
    set((state) => ({
      fuelTrims: { ...state.fuelTrims, ...v },
    })),
}));
