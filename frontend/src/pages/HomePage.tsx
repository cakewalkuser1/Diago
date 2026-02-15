import { useMemo, useState } from "react";
import { useNavigate } from "react-router-dom";
import { Activity, Car, History } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { SectionCard } from "@/components/ui/SectionCard";
import { Select } from "@/components/ui/Select";
import { Header } from "@/components/layout/Header";
import { StatusBar } from "@/components/layout/StatusBar";
import { PersonaSelector } from "@/components/onboarding/PersonaSelector";
import { usePersona } from "@/contexts/PersonaContext";
import { listSessions, getVehicleYears, getVehicleMakes, getVehicleModels, saveSelectedVehicle } from "@/lib/api";
import { formatTimestamp, formatDuration } from "@/lib/utils";
import { useAppStore } from "@/stores/appStore";
import type { Session } from "@/types";

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

  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => listSessions(5),
  });
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
            <section className="text-center space-y-3">
              <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-primary/10 mb-2">
                <Activity size={40} className="text-primary" />
              </div>
              <h1 className="text-2xl sm:text-3xl font-bold text-text">Diago</h1>
              <p className="text-subtext text-sm sm:text-base">
                Physics-aware automotive diagnostics
              </p>
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
          <section className="text-center space-y-3">
            <div className="inline-flex items-center justify-center p-3 rounded-2xl bg-primary/10 mb-2">
              <Activity size={40} className="text-primary" />
            </div>
            <h1 className="text-2xl sm:text-3xl font-bold text-text">
              Diago
            </h1>
            <p className="text-subtext text-sm sm:text-base">
              Physics-aware automotive diagnostics
            </p>
            <p className="text-overlay0 text-xs sm:text-sm max-w-md mx-auto">
              Record or describe symptoms, add OBD-II codes, decode your VIN, and get match results.
            </p>
          </section>

          {/* Vehicle (year / make / model / trim) + Start diagnosis */}
          <section className="space-y-4">
            <div className="grid grid-cols-1 sm:grid-cols-2 gap-3 p-4 rounded-xl bg-surface0/60 border border-surface1">
              <p className="text-xs text-subtext sm:col-span-2">
                Vehicle (optional — speeds up recalls & TSBs)
              </p>
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
              variant="primary"
              size="lg"
              className="w-full"
              onClick={onStartDiagnosis}
            >
              Next
            </Button>
            <Button
              variant="default"
              size="lg"
              className="w-full"
              onClick={() =>
                navigate("/diagnose", { state: { focus: "vehicle" } })
              }
            >
              <Car size={18} />
              Decode VIN & recalls
            </Button>
          </section>

          {/* Recent sessions */}
          <SectionCard
            title={
              <span className="flex items-center gap-2">
                <History size={16} className="text-primary" />
                Recent sessions
              </span>
            }
          >
            {sessions.isLoading ? (
              <p className="text-sm text-subtext">Loading…</p>
            ) : !sessions.data?.length ? (
              <p className="text-sm text-subtext">
                No sessions yet. Run a diagnosis to see history.
              </p>
            ) : (
              <ul className="space-y-2">
                {sessions.data.map((session: Session) => (
                  <li
                    key={session.id}
                    className="flex items-center justify-between gap-3 py-2 border-b border-surface1 last:border-0"
                  >
                    <div className="min-w-0">
                      <p className="text-sm text-text truncate">
                        {formatTimestamp(session.timestamp)}
                      </p>
                      <p className="text-xs text-overlay0">
                        {formatDuration(session.duration_seconds)}
                        {session.user_codes && ` · ${session.user_codes}`}
                      </p>
                    </div>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => navigate("/diagnose")}
                    >
                      Open
                    </Button>
                  </li>
                ))}
              </ul>
            )}
          </SectionCard>
        </div>
      </main>
      <StatusBar />
    </div>
  );
}
