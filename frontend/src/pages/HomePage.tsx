import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Car, Stethoscope, Zap, Wrench, Building2, ChevronRight, Mic, Search } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { Header } from "@/components/layout/Header";
import { StatusBar } from "@/components/layout/StatusBar";
import { PersonaSelector } from "@/components/onboarding/PersonaSelector";
import { usePersona } from "@/contexts/PersonaContext";
import { getVehicleYears, getVehicleMakes, getVehicleModels, saveSelectedVehicle } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";

const YEAR_PLACEHOLDER = "Year";
const MAKE_PLACEHOLDER = "Make";
const MODEL_PLACEHOLDER = "Model";

const HOW_IT_WORKS = [
  {
    icon: Mic,
    title: "Describe your problem",
    description: "Tell us your symptoms, scan codes, or record the engine sound — text or voice.",
  },
  {
    icon: Zap,
    title: "AI diagnoses instantly",
    description: "Physics-aware reasoning maps your symptoms to ranked failure modes in seconds.",
  },
  {
    icon: Wrench,
    title: "Fix it or find help",
    description: "Get step-by-step repair guidance or connect directly with a certified mechanic.",
  },
];

export function HomePage() {
  const navigate = useNavigate();
  const { hasSelectedPersona } = usePersona();
  const setVehicleSelection = useAppStore((s) => s.setVehicleSelection);
  const [year, setYear] = useState<string>("");
  const [makeId, setMakeId] = useState<string>("");
  const [modelId, setModelId] = useState<string>("");
  const [trim, setTrim] = useState<string>("");
  const [vehicleExpanded, setVehicleExpanded] = useState(false);

  const yearsQuery = useQuery({
    queryKey: ["vehicle", "years"],
    queryFn: () => getVehicleYears(),
  });
  const makesQuery = useQuery({
    queryKey: ["vehicle", "makes"],
    queryFn: () => getVehicleMakes("car"),
  });
  const modelsQuery = useQuery({
    queryKey: ["vehicle", "models", makeId, year],
    queryFn: () => getVehicleModels(Number(makeId), Number(year)),
    enabled: Boolean(makeId && year),
  });

  const yearOptions = useMemo(() => {
    const list = yearsQuery.data?.years ?? [];
    return [
      { value: "", label: YEAR_PLACEHOLDER },
      ...list.map((y) => ({ value: String(y), label: String(y) })),
    ];
  }, [yearsQuery.data?.years]);
  const makeOptions = useMemo(() => {
    const list = makesQuery.data?.makes ?? [];
    return [
      { value: "", label: MAKE_PLACEHOLDER },
      ...list.map((m) => ({ value: String(m.make_id), label: m.make_name })),
    ];
  }, [makesQuery.data?.makes]);
  const modelOptions = useMemo(() => {
    const list = modelsQuery.data?.models ?? [];
    return [
      { value: "", label: MODEL_PLACEHOLDER },
      ...list.map((m) => ({ value: String(m.model_id), label: m.model_name })),
    ];
  }, [modelsQuery.data?.models]);

  const selectedMake = makeOptions.find((o) => o.value === makeId);
  const selectedModel = modelOptions.find((o) => o.value === modelId);

  useEffect(() => {
    const validValues = new Set(modelOptions.map((o) => o.value));
    if (modelId && !validValues.has(modelId)) setModelId("");
  }, [modelOptions, modelId]);

  const onStartDiagnosis = async () => {
    const makeName = selectedMake?.label ?? "";
    const modelName = selectedModel?.label ?? "";
    const trimVal = trim.trim();
    const yearNum = year ? Number(year) : null;
    setVehicleSelection({
      year: yearNum,
      makeId: makeId ? Number(makeId) : null,
      makeName,
      modelId: modelId ? Number(modelId) : null,
      modelName,
      trim: trimVal,
    });
    if (makeName || modelName) {
      try {
        await saveSelectedVehicle({
          model_year: yearNum ?? null,
          make: makeName,
          model: modelName,
          submodel: trimVal,
        });
      } catch {
        // non-blocking
      }
    }
    navigate("/diagnose");
  };

  /* ── Pre-persona: role selection ── */
  if (!hasSelectedPersona) {
    return (
      <div className="h-full flex flex-col min-h-0 bg-base">
        <Header />
        <main className="flex-1 overflow-y-auto flex items-center justify-center px-4 py-12 relative">
          {/* Ambient glow */}
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            <div
              className="absolute top-1/3 left-1/2 -translate-x-1/2 -translate-y-1/2 w-[700px] h-[500px] rounded-full blur-[140px] glow-pulse"
              style={{ background: "radial-gradient(ellipse, rgba(255,86,56,0.07) 0%, transparent 70%)" }}
            />
          </div>
          <div className="relative w-full max-w-2xl space-y-10">
            <section className="text-center space-y-3">
              <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface0 text-xs text-subtext mb-2">
                <span
                  className="w-1.5 h-1.5 rounded-full ai-pulse"
                  style={{ background: "var(--ds-secondary-dim)" }}
                />
                AI Diagnostic Engine
              </div>
              <h1
                className="hero-headline text-text"
                style={{ fontFamily: '"Space Grotesk", ui-sans-serif, system-ui, sans-serif' }}
              >
                Autopilot
              </h1>
              <p className="hero-sub">Choose how you'll use diagnostics</p>
            </section>
            <PersonaSelector />
          </div>
        </main>
        <StatusBar />
      </div>
    );
  }

  /* ── Main landing ── */
  return (
    <div className="h-full flex flex-col min-h-0 bg-base">
      <Header />
      <main className="flex-1 overflow-y-auto">

        {/* ── HERO ── */}
        <section className="relative min-h-[60vh] flex items-center px-6 py-16 sm:py-24 overflow-hidden">
          {/* Ambient glows */}
          <div className="absolute inset-0 pointer-events-none overflow-hidden">
            <div
              className="absolute -top-20 left-0 w-[600px] h-[500px] rounded-full blur-[160px]"
              style={{ background: "radial-gradient(ellipse, rgba(255,86,56,0.09) 0%, transparent 70%)" }}
            />
            <div
              className="absolute bottom-0 right-0 w-[500px] h-[400px] rounded-full blur-[160px]"
              style={{ background: "radial-gradient(ellipse, rgba(0,218,243,0.06) 0%, transparent 70%)" }}
            />
          </div>

          <div className="relative z-10 max-w-3xl w-full mx-auto">
            {/* AI badge */}
            <div className="inline-flex items-center gap-2 px-3 py-1.5 rounded-full bg-surface0 text-xs mb-6"
              style={{ color: "var(--ds-secondary-dim)" }}
            >
              <span className="w-1.5 h-1.5 rounded-full ai-pulse" style={{ background: "var(--ds-secondary-dim)" }} />
              AI Diagnostic Engine Active
            </div>

            {/* Headline — asymmetric: left-aligned */}
            <h1
              className="hero-headline text-text mb-5"
              style={{ fontFamily: '"Space Grotesk", ui-sans-serif, system-ui, sans-serif' }}
            >
              Your car.<br />
              <span style={{ color: "var(--ds-primary-container)" }}>Diagnosed.</span>
            </h1>

            <p className="hero-sub max-w-md mb-8">
              Describe symptoms, scan codes, or record the sound.
              Get physics-aware diagnostics and step-by-step repair guidance.
            </p>

            {/* CTAs */}
            <div className="flex flex-wrap items-center gap-4 mb-10">
              <Button variant="primary" size="xl" onClick={onStartDiagnosis}>
                <Stethoscope size={18} />
                Start Diagnosis
              </Button>
              <Link
                to="/find-mechanic"
                className="inline-flex items-center gap-1.5 text-sm text-subtext hover:text-text transition-colors"
              >
                <Search size={14} />
                Find a mechanic
                <ChevronRight size={14} className="opacity-50" />
              </Link>
            </div>

            {/* Vehicle selector — glassmorphism */}
            <div className="max-w-xl">
              <button
                type="button"
                onClick={() => setVehicleExpanded((v) => !v)}
                className="flex items-center gap-2 text-sm text-subtext hover:text-text transition-colors mb-3"
              >
                <Car size={14} />
                {vehicleExpanded ? "Hide vehicle" : "Add your vehicle for precise results"}
                <ChevronRight
                  size={14}
                  className={`opacity-50 transition-transform duration-200 ${vehicleExpanded ? "rotate-90" : ""}`}
                />
              </button>
              {vehicleExpanded && (
                <div className="glass rounded-2xl p-5 space-y-4">
                  <div className="grid grid-cols-1 sm:grid-cols-2 gap-3">
                    <Select
                      label="Year"
                      options={yearOptions}
                      value={year}
                      onChange={(e) => { setYear(e.target.value); setModelId(""); }}
                    />
                    <Select
                      label="Make"
                      options={makeOptions}
                      value={makeId}
                      onChange={(e) => { setMakeId(e.target.value); setModelId(""); }}
                    />
                    <Select
                      key={`model-${makeId}-${year}`}
                      label="Model"
                      options={modelOptions}
                      value={modelId}
                      onChange={(e) => setModelId(e.target.value)}
                      disabled={!year || !makeId}
                    />
                    <div className="flex flex-col gap-1">
                      <label className="text-xs text-subtext">Submodel / trim</label>
                      <input
                        type="text"
                        placeholder="e.g. Sport, Limited"
                        value={trim}
                        onChange={(e) => setTrim(e.target.value)}
                        className="bg-surface0 text-text rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-[var(--ds-primary-container)]/40"
                      />
                    </div>
                  </div>
                  <Button
                    variant="ghost"
                    size="sm"
                    className="text-xs text-subtext"
                    onClick={() => navigate("/diagnose", { state: { focus: "vehicle" } })}
                  >
                    <Car size={13} />
                    Decode VIN & recalls
                    <ChevronRight size={13} className="opacity-50" />
                  </Button>
                </div>
              )}
            </div>
          </div>
        </section>

        {/* ── HOW IT WORKS ── */}
        <section className="px-6 py-16 sm:py-20 bg-mantle/60">
          <div className="max-w-4xl mx-auto">
            <h2
              className="section-headline text-text mb-3"
              style={{ fontFamily: '"Space Grotesk", ui-sans-serif, system-ui, sans-serif' }}
            >
              How it works
            </h2>
            <p className="hero-sub mb-12 max-w-md">Three steps from symptom to solution.</p>

            <div className="grid sm:grid-cols-3 gap-8 relative">
              {/* Dashed connector (desktop only) */}
              <div
                className="hidden sm:block absolute top-5 left-[calc(33%-12px)] right-[calc(33%-12px)] h-px"
                style={{ borderTop: "1.5px dashed var(--ds-primary-container)", opacity: 0.3 }}
              />
              {HOW_IT_WORKS.map((step, i) => {
                const Icon = step.icon;
                return (
                  <div key={i} className="relative space-y-4">
                    <div className="flex items-center gap-3">
                      <div
                        className="w-10 h-10 rounded-full flex items-center justify-center text-sm font-bold text-white flex-shrink-0"
                        style={{
                          background: "var(--ds-gradient-primary)",
                          fontFamily: '"Space Grotesk", ui-sans-serif',
                        }}
                      >
                        {i + 1}
                      </div>
                      <Icon size={18} style={{ color: "var(--ds-secondary-dim)" }} />
                    </div>
                    <h3
                      className="font-semibold text-text"
                      style={{ fontFamily: '"Space Grotesk", ui-sans-serif, system-ui, sans-serif' }}
                    >
                      {step.title}
                    </h3>
                    <p className="text-sm text-subtext leading-relaxed">{step.description}</p>
                  </div>
                );
              })}
            </div>
          </div>
        </section>

        {/* ── ROLE PILLS ── */}
        <section className="px-6 py-12 max-w-4xl mx-auto">
          <div className="flex flex-wrap gap-3">
            {[
              { icon: Zap, label: "Quick Answer", sub: "60 seconds" },
              { icon: Wrench, label: "D.I.Y Repair", sub: "Step-by-step" },
              { icon: Building2, label: "Shop / Pro", sub: "Full data" },
            ].map(({ icon: Icon, label, sub }) => (
              <div
                key={label}
                className="flex items-center gap-3 px-4 py-3 rounded-xl bg-surface0 hover:bg-surface1 transition-colors cursor-default"
              >
                <Icon size={16} style={{ color: "var(--ds-secondary-dim)" }} />
                <div>
                  <p className="text-sm font-medium text-text leading-none">{label}</p>
                  <p className="text-xs text-subtext mt-0.5">{sub}</p>
                </div>
              </div>
            ))}
          </div>
        </section>

      </main>
      <StatusBar />
    </div>
  );
}
