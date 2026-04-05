import { useCallback, useEffect, useState } from "react";
import { useNavigate } from "react-router-dom";
import { useQuery } from "@tanstack/react-query";
import {
  Stethoscope,
  BarChart3,
  MessageSquare,
  Play,
  Loader2,
  ChevronRight,
  MicOff,
  ThermometerSnowflake,
  ThermometerSun,
  AlertCircle,
} from "lucide-react";

import { Header } from "@/components/layout/Header";
import { StatusBar } from "@/components/layout/StatusBar";
import { Toast } from "@/components/ui/Toast";
import { RecordPanel } from "@/components/panels/RecordPanel";
import { SpectrogramView } from "@/components/panels/SpectrogramView";
import { TroubleCodePanel } from "@/components/panels/TroubleCodePanel";
import { ResultsPanel } from "@/components/panels/ResultsPanel";
import { ResultsPanelPlain } from "@/components/panels/ResultsPanelPlain";
import { ContextForm } from "@/components/panels/ContextForm";
import { ChatPanel } from "@/components/panels/ChatPanel";
import { SessionHistory } from "@/components/panels/SessionHistory";
import { Tabs } from "@/components/ui/Tabs";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/stores/appStore";
import { useToastStore } from "@/stores/toastStore";
import { useAuthStore } from "@/stores/authStore";
import { usePersona } from "@/contexts/PersonaContext";
import { diagnoseAudio, diagnoseText, getSelectedVehicle, ApiError } from "@/lib/api";
import { cn } from "@/lib/utils";

const WIZARD_STEPS = [
  { id: 1, label: "Symptoms", icon: Stethoscope },
  { id: 2, label: "Trouble codes", icon: MessageSquare },
  { id: 3, label: "Recording", icon: Play },
] as const;

const ONETIME_WIZARD_STEPS = [
  { id: 1, label: "What's wrong?", icon: Stethoscope },
  { id: 2, label: "Cold or warm?", icon: ThermometerSun },
  { id: 3, label: "Check engine light?", icon: AlertCircle },
] as const;

const BOTTOM_TABS = [
  { id: "results", label: "Results", icon: <BarChart3 size={14} /> },
  { id: "chat", label: "DiagBot", icon: <MessageSquare size={14} /> },
];

export function DiagnoseView() {
  const navigate = useNavigate();
  const [diagnosisStep, setDiagnosisStep] = useState<1 | 2 | 3>(1);
  const [onetimeStep, setOnetimeStep] = useState<1 | 2 | 3>(1);
  const [checkEngineOn, setCheckEngineOn] = useState<boolean | null>(null);
  const [chatExpanded, setChatExpanded] = useState(false);
  const [showPaywall, setShowPaywall] = useState(false);

  const {
    activeTab,
    setActiveTab,
    diagnosis,
    audioBlob,
    symptoms,
    activeCodes,
    context,
    fuelTrims,
    vehicleSelection,
    setVehicleSelection,
    setSymptoms,
    setAudioBlob,
    clearCodes,
    isDiagnosing,
    setIsDiagnosing,
    setDiagnosis,
    setContext,
    sidebarOpen,
    setSidebarOpen,
  } = useAppStore();

  const { hasSelectedPersona, personaTier } = usePersona();
  const session = useAuthStore((s) => s.session);
  const accessToken = session?.access_token ?? null;
  const isOnetime = personaTier === "onetime";
  const inWizard = diagnosis === null;

  useEffect(() => {
    if (!hasSelectedPersona) {
      navigate("/", { replace: true });
    }
  }, [hasSelectedPersona, navigate]);

  const selectedVehicleQuery = useQuery({
    queryKey: ["selectedVehicle"],
    queryFn: getSelectedVehicle,
    staleTime: 60_000,
    refetchOnWindowFocus: false,
  });

  useEffect(() => {
    const data = selectedVehicleQuery.data;
    if (data && (data.make || data.model)) {
      setVehicleSelection({
        year: data.model_year,
        makeId: null,
        makeName: data.make,
        modelId: null,
        modelName: data.model,
        trim: data.submodel ?? "",
      });
    }
  }, [selectedVehicleQuery.data, setVehicleSelection]);

  const toast = useToastStore((s) => s.show);

  const handleAnalyze = useCallback(async () => {
    setShowPaywall(false);
    setIsDiagnosing(true);
    try {
      const vehicleType =
        vehicleSelection.makeName || vehicleSelection.modelName
          ? [vehicleSelection.year, vehicleSelection.makeName, vehicleSelection.modelName, vehicleSelection.trim]
              .filter(Boolean)
              .join(" ")
          : context.vehicle_type;
      const contextWithVehicle = { ...context, vehicle_type: vehicleType || context.vehicle_type };
      const plainEnglish = personaTier === "onetime";
      let result;
      if (audioBlob) {
        result = await diagnoseAudio(
          audioBlob,
          symptoms,
          activeCodes.join(","),
          plainEnglish,
          accessToken
        );
      } else {
        result = await diagnoseText(
          {
            symptoms,
            codes: activeCodes,
            context: contextWithVehicle,
            plain_english: plainEnglish,
            fuel_trims: (fuelTrims.stft != null || fuelTrims.ltft != null) ? fuelTrims : undefined,
          },
          accessToken
        );
      }
      setDiagnosis(result);
      setActiveTab("results");
    } catch (e) {
      if (e instanceof ApiError && e.status === 429) {
        setShowPaywall(true);
        toast("Monthly diagnosis limit reached. Upgrade for more.", "error");
      } else {
        const msg = e instanceof Error ? e.message : "Unknown error";
        console.error("Diagnosis failed:", e);
        toast(`Diagnosis failed: ${msg}`, "error");
      }
    } finally {
      setIsDiagnosing(false);
    }
  }, [
    audioBlob,
    symptoms,
    activeCodes,
    context,
    fuelTrims,
    vehicleSelection,
    personaTier,
    accessToken,
    toast,
    setIsDiagnosing,
    setDiagnosis,
    setActiveTab,
  ]);

  useEffect(() => {
    const onKeyDown = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey) {
        if (e.key === "Enter" && !inWizard) {
          e.preventDefault();
          if (!isDiagnosing && (symptoms || activeCodes.length > 0 || audioBlob)) {
            handleAnalyze();
          }
        }
        if (e.key === "e") {
          e.preventDefault();
          const exportBtn = document.querySelector('[data-action="export-report"]');
          if (exportBtn instanceof HTMLElement) exportBtn.click();
        }
      }
    };
    window.addEventListener("keydown", onKeyDown);
    return () => window.removeEventListener("keydown", onKeyDown);
  }, [inWizard, isDiagnosing, symptoms, activeCodes.length, audioBlob, handleAnalyze]);

  return (
    <div className="h-full flex flex-col min-h-0">
      <Header />
      <Toast />

      {showPaywall && (
        <div className="flex items-center justify-between gap-3 px-4 py-2 bg-yellow/15 border-b border-yellow/30 text-sm">
          <span className="text-text">
            Monthly diagnosis limit reached. Upgrade for more diagnoses.
          </span>
          <Button
            size="sm"
            variant="primary"
            onClick={() => navigate("/pricing")}
          >
            Upgrade
          </Button>
        </div>
      )}

      {inWizard && !isOnetime && diagnosisStep === 3 && <RecordPanel />}

      <div className="flex-1 flex min-h-0 overflow-hidden">
        <div className="flex-1 flex flex-col min-w-0">
          {inWizard && !isOnetime && diagnosisStep === 3 && <SpectrogramView />}

          {inWizard ? (
            isOnetime ? (
              /* One-Time simplified wizard */
              <>
<div className="flex items-center justify-center gap-2 px-3 py-2 border-b border-surface1/60 bg-mantle/30">
                {ONETIME_WIZARD_STEPS.map(({ id }, i) => (
                  <span key={id} className="flex items-center gap-2">
                    <span
                      className={cn(
                        "w-2 h-2 rounded-full transition-colors",
                        onetimeStep === id ? "bg-primary" : onetimeStep > id ? "bg-primary/50" : "bg-surface2"
                      )}
                    />
                    {i < ONETIME_WIZARD_STEPS.length - 1 && (
                      <span className="w-4 h-px bg-surface2" />
                    )}
                  </span>
                ))}
              </div>
                <div className="flex-1 min-h-0 overflow-y-auto">
                  <div className="p-6 sm:p-8 max-w-xl mx-auto space-y-6">
                    {onetimeStep === 1 && (
                      <>
                        <label className="text-base font-medium text-text">
                          What&apos;s wrong?
                        </label>
                        <textarea
                          value={symptoms}
                          onChange={(e) => setSymptoms(e.target.value)}
                          placeholder="Describe the issue in your own words..."
                          className="w-full h-32 bg-surface0 text-text border border-surface1 rounded-xl px-4 py-3 text-base resize-none placeholder:text-overlay0 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
                        />
                        <Button
                          variant="primary"
                          size="xl"
                          className="w-full"
                          onClick={() => setOnetimeStep(2)}
                          disabled={!symptoms.trim()}
                        >
                          Next
                          <ChevronRight size={20} />
                        </Button>
                      </>
                    )}
                    {onetimeStep === 2 && (
                      <>
                        <label className="text-base font-medium text-text">
                          Does it happen when the engine is cold or warm?
                        </label>
                        <div className="grid grid-cols-2 gap-3">
                          {[
                            { val: true, label: "Cold", icon: ThermometerSnowflake },
                            { val: false, label: "Warm", icon: ThermometerSun },
                            { val: false, label: "Both", icon: ThermometerSun },
                            { val: false, label: "Not sure", icon: ThermometerSun },
                          ].map(({ val, label, icon: Icon }) => (
                            <button
                              key={label}
                              type="button"
                              onClick={() => {
                                setContext({ cold_only: val });
                                setOnetimeStep(3);
                              }}
                              className="flex items-center justify-center gap-2 p-4 rounded-xl border-2 border-surface1 bg-surface0/60 hover:bg-surface0 hover:border-primary/50 text-text font-medium transition-all"
                            >
                              <Icon size={20} className="text-primary" />
                              {label}
                            </button>
                          ))}
                        </div>
                      </>
                    )}
                    {onetimeStep === 3 && (
                      <>
                        <label className="text-base font-medium text-text">
                          Is the check engine light on?
                        </label>
                        <div className="flex gap-3">
                          <Button
                            variant={checkEngineOn === true ? "primary" : "default"}
                            size="xl"
                            className="flex-1"
                            onClick={() => setCheckEngineOn(true)}
                          >
                            Yes
                          </Button>
                          <Button
                            variant={checkEngineOn === false ? "primary" : "default"}
                            size="xl"
                            className="flex-1"
                            onClick={() => {
                              setCheckEngineOn(false);
                              clearCodes();
                            }}
                          >
                            No
                          </Button>
                        </div>
                        {checkEngineOn === true && (
                          <div className="space-y-2 pt-2">
                            <label className="text-sm text-subtext">
                              Enter trouble codes if you have them (optional)
                            </label>
                            <TroubleCodePanel codesOnly />
                          </div>
                        )}
                        <Button
                          variant="primary"
                          size="xl"
                          className="w-full"
                          onClick={() => {
                            setAudioBlob(null);
                            handleAnalyze();
                          }}
                          disabled={isDiagnosing || !symptoms.trim() || checkEngineOn === null}
                        >
                          {isDiagnosing ? (
                            <>
                              <Loader2 size={20} className="animate-spin" />
                              Analyzing...
                            </>
                          ) : (
                            <>
                              <Play size={20} />
                              Get answer
                            </>
                          )}
                        </Button>
                      </>
                    )}
                  </div>
                </div>
              </>
            ) : (
            /* DIY/Enterprise step-by-step wizard */
            <>
              <div className="flex items-center justify-center gap-2 px-3 py-2 border-b border-surface1/60 bg-mantle/30">
                {WIZARD_STEPS.map(({ id }, i) => (
                  <span key={id} className="flex items-center gap-2">
                    <span
                      className={cn(
                        "w-2 h-2 rounded-full transition-colors",
                        diagnosisStep === id ? "bg-primary" : diagnosisStep > id ? "bg-primary/50" : "bg-surface2"
                      )}
                    />
                    {i < WIZARD_STEPS.length - 1 && (
                      <span className="w-4 h-px bg-surface2" />
                    )}
                  </span>
                ))}
              </div>

              <div className="flex-1 min-h-0 overflow-y-auto">
                <div className="p-4 sm:p-5 md:p-6 max-w-2xl mx-auto space-y-6">
                  {/* Step 1: Symptoms */}
                  {diagnosisStep === 1 && (
                    <>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-text">
                          What’s wrong with the car?
                        </label>
                        <textarea
                          value={symptoms}
                          onChange={(e) => setSymptoms(e.target.value)}
                          placeholder="Describe the issue... e.g. 'High-pitched whine that increases with RPM, noticed after oil change'"
                          className="w-full h-28 bg-surface0 text-text border border-surface1 rounded-lg px-3 py-2 text-sm resize-none placeholder:text-overlay0 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
                        />
                      </div>
                      <div className="space-y-2">
                        <Button
                          variant="ghost"
                          size="sm"
                          onClick={() => setChatExpanded((e) => !e)}
                          className="text-subtext"
                        >
                          <MessageSquare size={14} />
                          {chatExpanded ? "Hide" : "Get help from DiagBot"}
                        </Button>
                        {chatExpanded && (
                          <div className="rounded-lg border border-surface1 overflow-hidden">
                            <ChatPanel />
                          </div>
                        )}
                      </div>
                      <details className="group">
                        <summary className="text-sm font-medium text-subtext cursor-pointer select-none list-none py-2">
                          More symptom details (optional)
                        </summary>
                        <div className="mt-2">
                          <ContextForm />
                        </div>
                      </details>
                      <Button
                        variant="primary"
                        size="lg"
                        className="w-full"
                        onClick={() => setDiagnosisStep(2)}
                      >
                        Next
                        <ChevronRight size={18} />
                      </Button>
                    </>
                  )}

                  {/* Step 2: Trouble codes */}
                  {diagnosisStep === 2 && (
                    <>
                      <div className="space-y-2">
                        <label className="text-sm font-medium text-text">
                          Any OBD-II trouble codes? (optional)
                        </label>
                        <TroubleCodePanel codesOnly />
                      </div>
                      <div className="flex flex-col gap-2">
                        <div className="flex flex-col sm:flex-row gap-2">
                          <Button
                            variant="default"
                            size="lg"
                            className="flex-1"
                            onClick={() => {
                              clearCodes();
                              setDiagnosisStep(3);
                            }}
                          >
                            Don’t have
                          </Button>
                          <Button
                            variant="primary"
                            size="lg"
                            className="flex-1"
                            onClick={() => setDiagnosisStep(3)}
                          >
                            Next (record audio)
                            <ChevronRight size={18} />
                          </Button>
                        </div>
                        <Button
                          variant="default"
                          size="lg"
                          className="w-full"
                          onClick={() => {
                            setAudioBlob(null);
                            handleAnalyze();
                          }}
                          disabled={isDiagnosing || (!symptoms.trim() && activeCodes.length === 0)}
                        >
                          <MicOff size={18} />
                          Skip recording — diagnose from symptoms & codes
                        </Button>
                      </div>
                    </>
                  )}

                  {/* Step 3: Recording */}
                  {diagnosisStep === 3 && (
                    <>
                      <p className="text-sm text-subtext">
                        Record engine or road noise for better analysis, or skip to run diagnosis from symptoms and codes only.
                      </p>
                      <div className="flex flex-col sm:flex-row gap-2">
                        <Button
                          variant="default"
                          size="lg"
                          className="flex-1"
                          onClick={() => {
                            setAudioBlob(null);
                            handleAnalyze();
                          }}
                          disabled={isDiagnosing || (!symptoms.trim() && activeCodes.length === 0)}
                        >
                          <MicOff size={18} />
                          Skip recording
                        </Button>
                        <Button
                          variant="primary"
                          size="lg"
                          className="flex-1"
                          onClick={handleAnalyze}
                          disabled={
                            isDiagnosing ||
                            (!audioBlob && !symptoms.trim() && activeCodes.length === 0)
                          }
                        >
                          {isDiagnosing ? (
                            <>
                              <Loader2 size={18} className="animate-spin" />
                              Analyzing...
                            </>
                          ) : (
                            <>
                              <Play size={18} />
                              Diagnose
                            </>
                          )}
                        </Button>
                      </div>
                    </>
                  )}
                </div>
              </div>
            </>
            )
          ) : (
            /* Post-diagnosis: results + chat tabs */
            <>
              {!isOnetime && <RecordPanel />}
              {!isOnetime && <SpectrogramView />}
              <div className="flex items-center justify-center px-3 py-2 border-y border-surface1/60 bg-mantle/20">
                <Button
                  variant="primary"
                  size="lg"
                  onClick={handleAnalyze}
                  disabled={
                    isDiagnosing ||
                    (!audioBlob && !symptoms && activeCodes.length === 0)
                  }
                  className="w-full sm:w-auto min-w-[140px]"
                >
                  {isDiagnosing ? (
                    <>
                      <Loader2 size={16} className="animate-spin" />
                      Analyzing...
                    </>
                  ) : (
                    <>
                      <Play size={16} />
                      Diagnose again
                    </>
                  )}
                </Button>
              </div>
              <Tabs
                tabs={BOTTOM_TABS}
                activeTab={activeTab === "symptoms" ? "results" : activeTab}
                onTabChange={(id) =>
                  setActiveTab(id as "results" | "chat")
                }
              />
              <div className="flex-1 min-h-0 overflow-y-auto">
                {(activeTab === "symptoms" || activeTab === "results") &&
                  (isOnetime ? <ResultsPanelPlain /> : <ResultsPanel />)}
                {activeTab === "chat" && <ChatPanel />}
              </div>
            </>
          )}
        </div>

        <aside
          className={cn(
            "w-80 border-l border-surface1 bg-mantle flex-col",
            "hidden lg:flex"
          )}
        >
          <SessionHistory />
        </aside>

        {sidebarOpen && (
          <>
            <div
              className="fixed inset-0 bg-black/50 z-40 lg:hidden"
              onClick={() => setSidebarOpen(false)}
            />
            <aside className="fixed right-0 top-0 bottom-0 w-80 bg-mantle border-l border-surface1 z-50 flex flex-col lg:hidden">
              <div className="flex items-center justify-between px-4 py-3 border-b border-surface1">
                <span className="text-sm font-semibold text-text">
                  Session History
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setSidebarOpen(false)}
                >
                  ✕
                </Button>
              </div>
              <SessionHistory />
            </aside>
          </>
        )}
      </div>

      <StatusBar />
    </div>
  );
}
