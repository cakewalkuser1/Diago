import { useEffect, useMemo, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { Activity, Car, Stethoscope } from "lucide-react";
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

export function HomePage() {
  const navigate = useNavigate();
  const { hasSelectedPersona } = usePersona();
  const setVehicleSelection = useAppStore((s) => s.setVehicleSelection);
  const [year, setYear] = useState<string>("");
  const [makeId, setMakeId] = useState<string>("");
  const [modelId, setModelId] = useState<string>("");
  const [trim, setTrim] = useState<string>("");

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

  /* Reset model when options change so we never show a stale model from a different make/year */
  useEffect(() => {
    const validValues = new Set(modelOptions.map((o) => o.value));
    if (modelId && !validValues.has(modelId)) {
      setModelId("");
    }
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
        // non-blocking; store is already updated
      }
    }
    navigate("/diagnose");
  };

  if (!hasSelectedPersona) {
    return (
      <div className="h-full flex flex-col min-h-0">
        <Header />
        <main className="flex-1 overflow-y-auto flex items-center justify-center px-4 py-12">
          <div className="w-full max-w-2xl space-y-8">
            <section className="text-center space-y-4">
              <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10">
                <Activity size={28} className="text-primary" />
              </div>
              <h1 className="hero-headline text-text">Autopilot</h1>
              <p className="hero-sub">Choose how you’ll use diagnostics</p>
            </section>
            <PersonaSelector />
          </div>
        </main>
        <StatusBar />
      </div>
    );
  }

  return (
    <div className="h-full flex flex-col min-h-0">
      <Header />
      <main className="flex-1 overflow-y-auto">
        <div className="max-w-2xl mx-auto px-4 py-8 sm:py-12 space-y-8">
          {/* Hero */}
          <section className="text-center space-y-4">
            <div className="inline-flex items-center justify-center w-14 h-14 rounded-2xl bg-primary/10">
              <Activity size={28} className="text-primary" />
            </div>
            <h1 className="hero-headline text-text">
              Diagnose with confidence
            </h1>
            <p className="hero-sub max-w-sm mx-auto">
              Describe symptoms, add codes or record sound. Get physics-aware results and repair guidance.
            </p>
          </section>

          {/* Single primary CTA */}
          <section className="space-y-4">
            <Button
              variant="primary"
              size="xl"
              className="w-full max-w-sm mx-auto flex justify-center"
              onClick={onStartDiagnosis}
            >
              <Stethoscope size={20} />
              Start diagnosis
            </Button>
            <p className="text-sm text-subtext text-center">
              Already know what&apos;s wrong?{" "}
              <Link to="/find-mechanic" className="text-primary hover:underline">
                Find a mechanic
              </Link>
            </p>
            <details className="group max-w-xl mx-auto">
              <summary className="text-sm text-subtext cursor-pointer list-none py-2 text-center hover:text-text transition-colors">
                Add vehicle (optional)
              </summary>
              <div className="mt-3 grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl bg-mantle/80 border border-surface1/60">
                <Select
                label="Year"
                options={yearOptions}
                value={year}
                onChange={(e) => {
                  setYear(e.target.value);
                  setModelId("");
                }}
              />
              <Select
                label="Make"
                options={makeOptions}
                value={makeId}
                onChange={(e) => {
                  setMakeId(e.target.value);
                  setModelId("");
                }}
              />
              <Select
                key={`model-${makeId}-${year}`}
                label="Model"
                options={modelOptions}
                value={modelId}
                onChange={(e) => setModelId(e.target.value)}
                disabled={!year || !makeId}
              />
              <div className="sm:col-span-2 flex flex-col gap-1">
                <label className="text-xs text-subtext">Submodel / trim</label>
                <input
                  type="text"
                  placeholder="e.g. Sport, Limited"
                  value={trim}
                  onChange={(e) => setTrim(e.target.value)}
                  className="bg-surface0 text-text border border-surface1 rounded-md px-3 py-1.5 text-sm focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary"
                />
              </div>
            </div>
              <Button
                variant="orange"
                size="sm"
                className="w-full mt-2"
                onClick={() => navigate("/diagnose", { state: { focus: "vehicle" } })}
              >
                <Car size={14} />
                Decode VIN & recalls on diagnose page
              </Button>
            </details>
          </section>
        </div>
      </main>
      <StatusBar />
    </div>
  );
}
