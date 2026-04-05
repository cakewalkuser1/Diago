import { useState, useEffect } from "react";
import { useQuery } from "@tanstack/react-query";
import {
  AlertTriangle,
  CheckCircle2,
  Download,
  XCircle,
  Wrench,
  Package,
  FlaskConical,
  Gauge,
  Activity,
  FileEdit,
  BookOpen,
  MapPin,
  Truck,
  Loader2,
  type LucideIcon,
} from "lucide-react";
import { loadStripe } from "@stripe/stripe-js";
import { Elements } from "@stripe/react-stripe-js";
import { Button } from "@/components/ui/Button";
import { ProgressBar } from "@/components/ui/ProgressBar";
import { EmptyState } from "@/components/ui/EmptyState";
import { usePersona } from "@/contexts/PersonaContext";
import { confidenceColor, cn } from "@/lib/utils";
import { useAppStore } from "@/stores/appStore";
import { useToastStore } from "@/stores/toastStore";
import { confirmTest, createRepair, getRepairGuidesForDiagnosis, dispatchRun, dispatchContinue, geocodeAddress, createPartsOrder, getPaymentsConfig, exportDiagnosisPdf } from "@/lib/api";
import { PartPaymentForm } from "@/components/PartPaymentForm";

/** Wrapper that loads Stripe and renders Elements + PartPaymentForm */
function PartPaymentFormWrapper({
  clientSecret,
  amountCents,
  onSuccess,
  onError,
}: {
  clientSecret: string;
  amountCents: number;
  onSuccess: (paymentIntentId: string) => void;
  onError: (msg: string) => void;
}) {
  const [stripePromise, setStripePromise] = useState<ReturnType<typeof loadStripe> | null>(null);
  useEffect(() => {
    getPaymentsConfig().then((c) => {
      if (c.stripe_publishable_key) setStripePromise(loadStripe(c.stripe_publishable_key));
    });
  }, []);
  if (!stripePromise) return <p className="text-sm text-subtext">Loading payment form…</p>;
  return (
    <Elements stripe={stripePromise} options={{ clientSecret }}>
      <PartPaymentForm amountCents={amountCents} onSuccess={onSuccess} onError={onError} />
    </Elements>
  );
}

/** Map tool names to Lucide icons for confirm tests */
const TOOL_ICONS: Record<string, LucideIcon> = {
  multimeter: Activity,
  pressure_tester: Gauge,
  gauge: Gauge,
  vacuum_gauge: Gauge,
  compression_tester: Gauge,
  scan_tool: Activity,
  oscilloscope: Activity,
  stethoscope: Activity,
  default: Wrench,
};
function getToolIcon(tool?: string): LucideIcon {
  if (!tool) return TOOL_ICONS.default;
  const key = tool.toLowerCase().replace(/\s+/g, "_");
  return TOOL_ICONS[key] ?? TOOL_ICONS.default;
}

/** Suggested parts by mechanical class (for part suggestions section). */
const PARTS_BY_CLASS: Record<string, string[]> = {
  rolling_element_bearing: ["Wheel bearing", "Idler pulley", "Alternator bearing", "Water pump bearing", "A/C compressor clutch"],
  gear_mesh_drivetrain: ["Differential gears", "Transmission gears", "Transfer case", "CV axle", "Drive shaft support bearing"],
  belt_drive_friction: ["Serpentine belt", "Belt tensioner", "Idler pulley", "A/C belt", "Alternator belt"],
  hydraulic_flow_cavitation: ["Power steering pump", "Power steering fluid", "Transmission cooler", "Hydraulic pump"],
  electrical_interference: ["Alternator", "Fuel pump", "Ignition coil", "Spark plug wires", "Ground strap"],
  combustion_impulse: ["Spark plugs", "Ignition coils", "Fuel injectors", "Knock sensor", "Timing chain/belt"],
  structural_resonance: ["Motor mount", "Transmission mount", "Exhaust hanger", "Heat shield", "Suspension bushing"],
  unknown: ["Inspect symptom area", "Check related sensors", "Review codes"],
};

export function ResultsPanel() {
  const diagnosis = useAppStore((s) => s.diagnosis);
  const setDiagnosis = useAppStore((s) => s.setDiagnosis);
  const symptoms = useAppStore((s) => s.symptoms);
  const activeCodes = useAppStore((s) => s.activeCodes);
  const context = useAppStore((s) => s.context);
  const dispatchResponse = useAppStore((s) => s.dispatchResponse);
  const setDispatchResponse = useAppStore((s) => s.setDispatchResponse);
  const vehicleSelection = useAppStore((s) => s.vehicleSelection);
  const { personaTier, showTechnicalData } = usePersona();
  const toast = useToastStore((s) => s.show);
  const [confirmingTestId, setConfirmingTestId] = useState<string | null>(null);
  const [repairFormOpen, setRepairFormOpen] = useState(false);
  const [repairDesc, setRepairDesc] = useState("");
  const [repairParts, setRepairParts] = useState("");
  const [repairOutcome, setRepairOutcome] = useState("");
  const [repairSubmitting, setRepairSubmitting] = useState(false);
  const [dispatchLoading, setDispatchLoading] = useState(false);
  const [selectedPart, setSelectedPart] = useState<{ name: string } | null>(null);
  const [selectedRetailerId, setSelectedRetailerId] = useState<string | null>(null);
  const [selectedMechanicId, setSelectedMechanicId] = useState<number | null>(null);
  const [userLatitude, setUserLatitude] = useState<number | null>(null);
  const [userLongitude, setUserLongitude] = useState<number | null>(null);
  const [locationLoading, setLocationLoading] = useState(false);
  const [locationError, setLocationError] = useState<string | null>(null);
  const [addressInput, setAddressInput] = useState("");
  const [paymentClientSecret, setPaymentClientSecret] = useState<string | null>(null);
  const [paymentIntentId, setPaymentIntentId] = useState<string | null>(null);
  const [paymentAmountCents, setPaymentAmountCents] = useState(0);
  const [paymentStub, setPaymentStub] = useState(false);
  const showAllTechnical =
    personaTier === "enterprise" || (personaTier === "diy" && showTechnicalData);

  const repairGuides = useQuery({
    queryKey: [
      "repair-guides",
      vehicleSelection.makeName,
      vehicleSelection.modelName,
      vehicleSelection.year,
      diagnosis?.top_class_display,
    ],
    queryFn: () =>
      getRepairGuidesForDiagnosis({
        make: vehicleSelection.makeName || undefined,
        model: vehicleSelection.modelName || undefined,
        year: vehicleSelection.year ?? undefined,
        q: diagnosis?.top_class_display || diagnosis?.report_text?.slice(0, 100),
        limit: 5,
      }),
    enabled: Boolean(diagnosis),
  });

  if (!diagnosis) {
    return (
      <EmptyState
        icon={AlertTriangle}
        title="Run a diagnosis to see results here"
        description="Complete the steps, then click Diagnose."
        className="flex-1 p-8"
      />
    );
  }

  const confColor = confidenceColor(diagnosis.confidence);
  const suggestedParts = PARTS_BY_CLASS[diagnosis.top_class] ?? PARTS_BY_CLASS.unknown;
  const topSolutions = diagnosis.class_scores.slice(0, 4);

  const ConfIcon =
    diagnosis.confidence === "high"
      ? CheckCircle2
      : diagnosis.confidence === "medium"
      ? AlertTriangle
      : XCircle;

  const handleExport = () => {
    const blob = new Blob([diagnosis.report_text], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `diago_report_${Date.now()}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  };

  const handleExportPdf = async () => {
    const vehicleLabel = [
      vehicleSelection.year,
      vehicleSelection.makeName,
      vehicleSelection.modelName,
      vehicleSelection.trim,
    ]
      .filter(Boolean)
      .join(" ");
    try {
      const blob = await exportDiagnosisPdf({
        top_class: diagnosis.top_class,
        top_class_display: diagnosis.top_class_display,
        confidence: diagnosis.confidence,
        is_ambiguous: diagnosis.is_ambiguous,
        report_text: diagnosis.report_text,
        llm_narrative: diagnosis.llm_narrative,
        class_scores: diagnosis.class_scores,
        ranked_failure_modes: diagnosis.ranked_failure_modes,
        symptoms,
        vehicle: vehicleLabel || undefined,
      });
      const url = URL.createObjectURL(blob);
      const a = document.createElement("a");
      a.href = url;
      a.download = `diago-diagnosis-${Date.now()}.pdf`;
      a.click();
      URL.revokeObjectURL(url);
    } catch {
      /* toast on error if desired */
    }
  };

  const handleConfirmTest = async (testId: string, result: "pass" | "fail") => {
    const ranked = diagnosis.ranked_failure_modes ?? [];
    if (ranked.length === 0) return;
    setConfirmingTestId(testId);
    try {
      const res = await confirmTest({
        ranked_failure_modes: ranked,
        test_id: testId,
        result,
      });
      setDiagnosis({ ...diagnosis, ranked_failure_modes: res.ranked_failure_modes });
    } finally {
      setConfirmingTestId(null);
    }
  };

  const isEnterprise = personaTier === "enterprise";

  return (
    <div
      className={cn(
        "flex-1 overflow-y-auto space-y-5",
        isEnterprise ? "p-3 space-y-3 text-sm" : "p-4"
      )}
    >
      {/* Most likely solutions */}
      <div className="space-y-3">
        <h3 className="text-base font-semibold text-text flex items-center gap-2">
          <Wrench size={18} className="text-primary" />
          Most likely solutions
        </h3>
        <div
          className="rounded-lg p-4 border-l-4"
          style={{
            borderColor: confColor,
            backgroundColor: `color-mix(in srgb, ${confColor} 8%, var(--color-surface0))`,
          }}
        >
          <div className="flex items-start gap-3">
            <ConfIcon
              size={24}
              style={{ color: confColor }}
              className="shrink-0 mt-0.5"
            />
            <div>
              <p className="font-bold text-lg" style={{ color: confColor }}>
                {diagnosis.is_ambiguous
                  ? "AMBIGUOUS RESULT"
                  : diagnosis.top_class_display}
              </p>
              <p className="text-sm text-subtext mt-0.5">
                Confidence: <span className="font-medium" style={{ color: confColor }}>{diagnosis.confidence}</span>
                {showAllTechnical && diagnosis.fingerprint_count > 0 && ` · ${diagnosis.fingerprint_count} fingerprint match(es)`}
              </p>
            </div>
          </div>
        </div>
        <ul className="space-y-1.5 pl-1">
          {topSolutions.slice(1).map((cs, i) => (
            <li key={cs.class_name} className="text-sm text-subtext flex items-center gap-2">
              <span className="text-overlay0 font-medium">{i + 2}.</span>
              {cs.display_name}
              {showAllTechnical && (
                <span className="text-overlay0/70">{(cs.score * 100).toFixed(0)}%</span>
              )}
            </li>
          ))}
        </ul>
      </div>

      {/* Repair guidance (CarDiagn + charm.li) */}
      {repairGuides.data && repairGuides.data.length > 0 && (
        <div className="space-y-3">
          <h3 className="text-base font-semibold text-text flex items-center gap-2">
            <BookOpen size={18} className="text-[var(--color-secondary)]" />
            Repair guidance
          </h3>
          <ul className="space-y-2">
            {repairGuides.data.map((guide) => (
              <li key={guide.id}>
                <a
                  href={guide.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline flex items-center gap-1.5"
                >
                  {guide.title}
                  {guide.source && (
                    <span className="text-[10px] text-overlay0">({guide.source})</span>
                  )}
                </a>
                {guide.summary && (
                  <p className="text-xs text-subtext mt-0.5 pl-5">{guide.summary}</p>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {/* Ranked failure modes (master-tech pattern layer) */}
      {diagnosis.ranked_failure_modes && diagnosis.ranked_failure_modes.length > 0 && (
        <div className="space-y-3">
          {isEnterprise && (
            <div className="flex flex-wrap gap-1 mb-2">
              {diagnosis.ranked_failure_modes
                .filter((fm) => fm.score > 0)
                .slice(0, 5)
                .map((fm, i) => (
                  <a
                    key={fm.failure_id}
                    href={`#failure-${fm.failure_id}`}
                    className="text-xs px-2 py-0.5 rounded bg-surface1 text-subtext hover:text-text hover:bg-surface2"
                  >
                    {i + 1}. {fm.display_name}
                  </a>
                ))}
            </div>
          )}
          <h4 className="text-sm font-semibold text-text flex items-center gap-2">
            <CheckCircle2 size={16} className="text-green" />
            Ranked failure modes
          </h4>
          <div className="space-y-3">
            {diagnosis.ranked_failure_modes
              .filter((fm) => fm.score > 0)
              .slice(0, 3)
              .map((fm, idx) => (
                <div
                  key={fm.failure_id}
                  id={`failure-${fm.failure_id}`}
                  className="bg-surface0 rounded-lg p-4 border border-surface1 space-y-2 scroll-mt-4"
                >
                  <div className="flex items-baseline justify-between gap-2">
                    <span className="font-semibold text-text">
                      {idx + 1}. {fm.display_name}
                    </span>
                    {showAllTechnical && (
                      <span className="text-xs text-overlay0">
                        {(fm.score * 100).toFixed(0)}% match
                      </span>
                    )}
                  </div>
                  {fm.description && (
                    <p className="text-sm text-subtext">{fm.description}</p>
                  )}
                  {fm.matched_conditions.length > 0 && (
                    <p className="text-xs text-overlay0">
                      <span className="font-medium text-text">Matched: </span>
                      {fm.matched_conditions.join(", ")}
                    </p>
                  )}
                  {fm.ruled_out_disqualifiers.length > 0 && (
                    <p className="text-xs text-red/90">
                      <span className="font-medium">Ruled out: </span>
                      {fm.ruled_out_disqualifiers.join(", ")}
                    </p>
                  )}
                  {fm.confirm_tests && fm.confirm_tests.length > 0 && (
                    <div className="pt-1">
                      <p className="text-xs font-medium text-text mb-1">Confirm by:</p>
                      <ul className="list-disc list-inside text-xs text-subtext space-y-0.5">
                        {fm.confirm_tests.map((t, i) => {
                          const ct = t as { test?: string; tool?: string; expected?: string };
                          const label = ct.test ?? String(t);
                          const tool = ct.tool;
                          const ToolIcon = getToolIcon(tool);
                          return (
                            <li key={i} className="flex items-center gap-1.5">
                              <ToolIcon size={12} className="shrink-0 text-primary" />
                              {label}
                              {tool && <span className="text-overlay0">— {tool}</span>}
                            </li>
                          );
                        })}
                      </ul>
                    </div>
                  )}
                </div>
              ))}
          </div>

          {/* Suggested confirm tests: Pass/Fail for top failure modes */}
          {(() => {
            const topWithTests = (diagnosis.ranked_failure_modes ?? [])
              .filter((fm) => fm.score > 0)
              .slice(0, 2);
            const testEntries: { testId: string; label: string; tool?: string }[] = [];
            const seen = new Set<string>();
            for (const fm of topWithTests) {
              for (const t of fm.confirm_tests ?? []) {
                const ct = t as { test?: string; tool?: string };
                const id = ct.test ?? String(t);
                if (id && !seen.has(id)) {
                  seen.add(id);
                  testEntries.push({
                    testId: id,
                    label: id.replace(/_/g, " "),
                    tool: ct.tool,
                  });
                }
              }
            }
            if (testEntries.length === 0) return null;
            return (
              <div className="pt-2 border-t border-surface1">
                <p className="text-xs font-semibold text-text mb-2 flex items-center gap-2">
                  <FlaskConical size={14} />
                  Did you perform this test?
                </p>
                <ul className="space-y-2">
                  {testEntries.map(({ testId, label, tool }) => (
                    <li
                      key={testId}
                      className="flex flex-wrap items-center gap-2 text-sm"
                    >
                      <span className="text-subtext">{label}</span>
                      {tool && (
                        <span className="text-xs text-overlay0">({tool})</span>
                      )}
                      <span className="flex gap-1">
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={confirmingTestId !== null}
                          onClick={() => handleConfirmTest(testId, "pass")}
                          className="text-green border border-green/50 hover:bg-green/10"
                        >
                          {confirmingTestId === testId ? "…" : "Pass"}
                        </Button>
                        <Button
                          size="sm"
                          variant="ghost"
                          disabled={confirmingTestId !== null}
                          onClick={() => handleConfirmTest(testId, "fail")}
                          className="text-red border border-red/50 hover:bg-red/10"
                        >
                          Fail
                        </Button>
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            );
          })()}
        </div>
      )}

      {/* Part suggestions */}
      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-text flex items-center gap-2">
          <Package size={16} className="text-secondary" />
          Part suggestions
        </h4>
        <div className="bg-surface0 rounded-lg p-3 border border-surface1">
          <ul className="flex flex-wrap gap-2">
            {suggestedParts.map((part) => (
              <li
                key={part}
                className="px-2.5 py-1 rounded-md bg-mantle text-sm text-text border border-surface1"
              >
                {part}
              </li>
            ))}
          </ul>
        </div>
      </div>

      {/* Get parts & find mechanic (dispatch flow) */}
      <div className="space-y-3 rounded-lg p-4 border border-surface1 bg-surface0">
        <h4 className="text-sm font-semibold text-text flex items-center gap-2">
          <Truck size={16} className="text-primary" />
          Get parts & find mechanic
        </h4>
        {!dispatchResponse ? (
          <div>
            <p className="text-sm text-subtext mb-2">
              Order a part from a local retailer and have a mobile mechanic pick it up and come to you.
            </p>
            <Button
              size="sm"
              variant="primary"
              disabled={dispatchLoading}
              onClick={async () => {
                setDispatchLoading(true);
                try {
                  const res = await dispatchRun({
                    symptoms,
                    codes: activeCodes,
                    behavioral_context: context as unknown as Record<string, unknown>,
                  });
                  setDispatchResponse(res);
                } catch (e) {
                  toast(e instanceof Error ? e.message : "Dispatch failed. Please try again.", "error");
                } finally {
                  setDispatchLoading(false);
                }
              }}
            >
              {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : <Package size={14} />}
              {dispatchLoading ? "Starting…" : "Get parts"}
            </Button>
          </div>
        ) : dispatchResponse.current_step === "awaiting_get_parts" ? (
          <div>
            <p className="text-sm text-subtext mb-2">{dispatchResponse.prompt_for_user}</p>
            <Button
              size="sm"
              variant="primary"
              disabled={dispatchLoading || !dispatchResponse.thread_id}
              onClick={async () => {
                if (!dispatchResponse.thread_id) return;
                setDispatchLoading(true);
                try {
                  const res = await dispatchContinue({
                    thread_id: dispatchResponse.thread_id,
                    action: "get_parts",
                  });
                  setDispatchResponse(res);
                } catch (e) {
                  toast(e instanceof Error ? e.message : "Action failed. Please try again.", "error");
                } finally {
                  setDispatchLoading(false);
                }
              }}
            >
              {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : null}
              {dispatchLoading ? "Loading…" : "Show parts & retailers"}
            </Button>
          </div>
        ) : (dispatchResponse.part_retailers?.length ?? 0) > 0 &&
          dispatchResponse.current_step !== "awaiting_mechanic_selection" &&
          dispatchResponse.current_step !== "awaiting_mechanic_response" &&
          dispatchResponse.current_step !== "dispatched" &&
          dispatchResponse.current_step !== "no_mechanic_accepted" ? (
          <div className="space-y-3">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <div>
              <p className="text-xs font-medium text-text mb-1">Pick a part</p>
              <ul className="flex flex-wrap gap-1.5 mb-2">
                {(dispatchResponse.suggested_parts ?? []).map((p) => (
                  <li key={p.name}>
                    <button
                      type="button"
                      onClick={() => setSelectedPart(p)}
                      className={cn(
                        "px-2.5 py-1 rounded-md text-sm border",
                        selectedPart?.name === p.name
                          ? "bg-primary/20 border-primary text-text"
                          : "bg-mantle border-surface1 text-subtext hover:text-text"
                      )}
                    >
                      {p.name}
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-medium text-text mb-1">Pick a retailer (local first)</p>
              <ul className="space-y-1">
                {(dispatchResponse.part_retailers ?? []).map((r) => (
                  <li key={r.id}>
                    <button
                      type="button"
                      onClick={() => setSelectedRetailerId(r.id)}
                      className={cn(
                        "w-full text-left px-3 py-2 rounded-md text-sm border flex items-center justify-between",
                        selectedRetailerId === r.id
                          ? "bg-primary/20 border-primary text-text"
                          : "bg-mantle border-surface1 text-subtext hover:text-text"
                      )}
                    >
                      <span>{r.name}</span>
                      <span className="text-xs text-overlay0">{r.distance_mi} mi</span>
                    </button>
                  </li>
                ))}
              </ul>
            </div>
            <div>
              <p className="text-xs font-medium text-text mb-1">Your location (for nearby mechanics)</p>
              <p className="text-xs text-subtext mb-2">Use geolocation or enter an address to find mechanics near you.</p>
              <div className="flex flex-wrap gap-2 mb-2">
                <Button
                  size="sm"
                  variant="secondary"
                  disabled={locationLoading}
                  onClick={async () => {
                    setLocationLoading(true);
                    setLocationError(null);
                    try {
                      const pos = await new Promise<GeolocationPosition>((resolve, reject) => {
                        navigator.geolocation.getCurrentPosition(resolve, reject, { enableHighAccuracy: true, timeout: 10000 });
                      });
                      setUserLatitude(pos.coords.latitude);
                      setUserLongitude(pos.coords.longitude);
                    } catch (e) {
                      setLocationError(e instanceof Error ? e.message : "Location unavailable");
                    } finally {
                      setLocationLoading(false);
                    }
                  }}
                >
                  {locationLoading ? <Loader2 size={14} className="animate-spin" /> : <MapPin size={14} />}
                  {locationLoading ? "Getting…" : "Use my location"}
                </Button>
                <div className="flex gap-1 flex-1 min-w-0">
                  <input
                    type="text"
                    placeholder="Or enter address"
                    value={addressInput}
                    onChange={(e) => setAddressInput(e.target.value)}
                    className="flex-1 min-w-0 px-2 py-1.5 rounded-md text-sm bg-mantle border border-surface1 text-text placeholder:text-overlay1"
                  />
                  <Button
                    size="sm"
                    variant="secondary"
                    disabled={locationLoading || !addressInput.trim()}
                    onClick={async () => {
                      if (!addressInput.trim()) return;
                      setLocationLoading(true);
                      setLocationError(null);
                      try {
                        const res = await geocodeAddress(addressInput.trim());
                        setUserLatitude(res.latitude);
                        setUserLongitude(res.longitude);
                      } catch (e) {
                        setLocationError(e instanceof Error ? e.message : "Address not found");
                      } finally {
                        setLocationLoading(false);
                      }
                    }}
                  >
                    {locationLoading ? <Loader2 size={14} className="animate-spin" /> : "Find"}
                  </Button>
                </div>
              </div>
              {(userLatitude != null && userLongitude != null) && (
                <p className="text-xs text-green">Location set: {userLatitude.toFixed(4)}, {userLongitude.toFixed(4)}</p>
              )}
              {locationError && <p className="text-xs text-red">{locationError}</p>}
            </div>
            {!paymentClientSecret && !paymentStub ? (
              <Button
                size="sm"
                variant="primary"
                disabled={dispatchLoading || !selectedPart || !selectedRetailerId || !dispatchResponse.thread_id}
                onClick={async () => {
                  if (!dispatchResponse.thread_id || !selectedPart || !selectedRetailerId) return;
                  const retailer = dispatchResponse.part_retailers?.find((r) => r.id === selectedRetailerId);
                  if (!retailer) return;
                  setDispatchLoading(true);
                  try {
                    const orderRes = await createPartsOrder({
                      thread_id: dispatchResponse.thread_id,
                      part: selectedPart,
                      retailer_id: retailer.id,
                      retailer_name: retailer.name,
                      retailer_store_id: retailer.store_id ?? retailer.id,
                    });
                    if (orderRes.stub) {
                      setPaymentIntentId("stub");
                      setPaymentStub(true);
                    } else {
                      setPaymentClientSecret(orderRes.client_secret ?? null);
                      setPaymentIntentId(orderRes.payment_intent_id);
                      setPaymentAmountCents(orderRes.amount_cents ?? 0);
                    }
                  } catch (e) {
                    toast(e instanceof Error ? e.message : "Could not create parts order.", "error");
                  } finally {
                    setDispatchLoading(false);
                  }
                }}
              >
                {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : null}
                {dispatchLoading ? "Creating…" : "Proceed to payment"}
              </Button>
            ) : paymentStub && paymentIntentId ? (
              <Button
                size="sm"
                variant="primary"
                disabled={dispatchLoading || !dispatchResponse.thread_id}
                onClick={async () => {
                  if (!dispatchResponse.thread_id || !selectedPart) return;
                  setDispatchLoading(true);
                  try {
                    const res = await dispatchContinue({
                      thread_id: dispatchResponse.thread_id,
                      action: "part_selected",
                      selected_part: selectedPart,
                      payment_intent_id: paymentIntentId,
                      user_latitude: userLatitude ?? undefined,
                      user_longitude: userLongitude ?? undefined,
                    });
                    setDispatchResponse(res);
                  } catch (e) {
                    toast(e instanceof Error ? e.message : "Action failed. Please try again.", "error");
                  } finally {
                    setDispatchLoading(false);
                  }
                }}
              >
                {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : null}
                {dispatchLoading ? "Confirming…" : "Confirm & pay"}
              </Button>
            ) : paymentClientSecret && paymentIntentId ? (
              <div className="rounded-lg p-3 border border-surface1 bg-mantle">
                <PartPaymentFormWrapper
                  clientSecret={paymentClientSecret}
                  amountCents={paymentAmountCents}
                  onSuccess={async (paidIntentId: string) => {
                    if (!dispatchResponse.thread_id || !selectedPart) return;
                    setDispatchLoading(true);
                    try {
                      const res = await dispatchContinue({
                        thread_id: dispatchResponse.thread_id,
                        action: "part_selected",
                        selected_part: selectedPart,
                        payment_intent_id: paidIntentId,
                        payment_intent_id: paymentIntentId,
                        user_latitude: userLatitude ?? undefined,
                        user_longitude: userLongitude ?? undefined,
                      });
                      setDispatchResponse(res);
                    } catch (e) {
                      toast(e instanceof Error ? e.message : "Failed to continue dispatch", "error");
                    } finally {
                      setDispatchLoading(false);
                    }
                  }}
                  onError={(msg) => toast(msg || "Payment failed. Please try again.", "error")}
                />
              </div>
            ) : null}
          </div>
        ) : dispatchResponse.current_step === "awaiting_stock_confirmation" ? (
          <div className="space-y-3">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <Button
              size="sm"
              variant="primary"
              disabled={dispatchLoading || !dispatchResponse.thread_id}
              onClick={async () => {
                if (!dispatchResponse.thread_id) return;
                setDispatchLoading(true);
                try {
                  const res = await dispatchContinue({
                    thread_id: dispatchResponse.thread_id,
                    action: "stock_confirmed",
                  });
                  setDispatchResponse(res);
                } catch (e) {
                  toast(e instanceof Error ? e.message : "Action failed. Please try again.", "error");
                } finally {
                  setDispatchLoading(false);
                }
              }}
            >
              {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : null}
              {dispatchLoading ? "Loading…" : "I confirmed it's in stock"}
            </Button>
          </div>
        ) : (dispatchResponse.mechanic_list?.length ?? 0) > 0 &&
          dispatchResponse.current_step === "awaiting_mechanic_selection" ? (
          <div className="space-y-3">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <ul className="space-y-2">
              {(dispatchResponse.mechanic_list ?? []).map((m) => (
                <li key={m.id}>
                  <button
                    type="button"
                    onClick={() => setSelectedMechanicId(m.id)}
                    className={cn(
                      "w-full text-left px-3 py-2 rounded-md text-sm border flex items-center justify-between",
                      selectedMechanicId === m.id
                        ? "bg-primary/20 border-primary text-text"
                        : "bg-mantle border-surface1 text-subtext hover:text-text"
                    )}
                  >
                    <span className="flex items-center gap-2">
                      <MapPin size={14} className="text-overlay0" />
                      {m.name}
                    </span>
                    <span className="text-xs text-overlay0">{m.distance_mi} mi · {m.availability}</span>
                  </button>
                </li>
              ))}
            </ul>
            <Button
              size="sm"
              variant="primary"
              disabled={dispatchLoading || selectedMechanicId === null || !dispatchResponse.thread_id}
              onClick={async () => {
                if (!dispatchResponse.thread_id || selectedMechanicId === null) return;
                setDispatchLoading(true);
                try {
                  const res = await dispatchContinue({
                    thread_id: dispatchResponse.thread_id,
                    action: "mechanic_selected",
                    selected_mechanic_id: selectedMechanicId,
                  });
                  setDispatchResponse(res);
                } catch (e) {
                  toast(e instanceof Error ? e.message : "Action failed. Please try again.", "error");
                } finally {
                  setDispatchLoading(false);
                }
              }}
            >
              {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : null}
              {dispatchLoading ? "Sending…" : "Send job to mechanic"}
            </Button>
          </div>
        ) : dispatchResponse.current_step === "awaiting_mechanic_response" ? (
          <div className="space-y-3">
            <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
            <p className="text-sm text-green">Mechanic has been notified. Waiting for their response.</p>
            <Button
              size="sm"
              variant="ghost"
              disabled={dispatchLoading || !dispatchResponse.thread_id}
              onClick={async () => {
                if (!dispatchResponse.thread_id) return;
                setDispatchLoading(true);
                try {
                  const res = await dispatchContinue({
                    thread_id: dispatchResponse.thread_id,
                    action: "mechanic_responded",
                    mechanic_accepted: true,
                  });
                  setDispatchResponse(res);
                } catch (e) {
                  toast(e instanceof Error ? e.message : "Action failed. Please try again.", "error");
                } finally {
                  setDispatchLoading(false);
                }
              }}
            >
              {dispatchLoading ? <Loader2 size={14} className="animate-spin" /> : null}
              Simulate mechanic accepted
            </Button>
          </div>
        ) : dispatchResponse.current_step === "dispatched" ? (
          <div className="text-sm text-green flex items-center gap-2">
            <CheckCircle2 size={18} />
            {dispatchResponse.prompt_for_user}
          </div>
        ) : dispatchResponse.current_step === "no_mechanic_accepted" ? (
          <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
        ) : (
          <p className="text-sm text-subtext">{dispatchResponse.prompt_for_user}</p>
        )}
      </div>

      {/* Score Bars (detail) - hidden when technical data off for DIYer */}
      {showAllTechnical && (
      <div className="space-y-2">
        <h4 className="text-sm font-semibold text-text flex items-center gap-2">
          <span className="w-1 h-4 bg-primary rounded-full" />
          All class scores
        </h4>
        <div className="space-y-1.5">
          {diagnosis.class_scores.map((cs, index) => {
            const pct = cs.score * 100;
            const hasPenalty = cs.penalty > 0;
            const isTopBar = index === 0;
            return (
              <div key={cs.class_name} className="flex items-center gap-2">
                <ProgressBar
                  value={pct}
                  label={cs.display_name}
                  sublabel={`${pct.toFixed(1)}%`}
                  color={
                    isTopBar
                      ? undefined
                      : pct >= 70
                        ? "var(--color-green)"
                        : pct >= 40
                          ? "var(--color-yellow)"
                          : "var(--color-surface2)"
                  }
                  className="flex-1"
                />
                {hasPenalty && (
                  <span
                    className="text-[10px] text-red shrink-0"
                    title={`Penalty: -${(cs.penalty * 100).toFixed(0)}%`}
                  >
                    -{(cs.penalty * 100).toFixed(0)}%
                  </span>
                )}
              </div>
            );
          })}
        </div>
      </div>
      )}

      {/* Narrative */}
      {diagnosis.llm_narrative && (
        <div className="space-y-2">
          <h4 className="text-sm font-semibold text-text flex items-center gap-2">
            <span className="w-1 h-4 bg-primary rounded-full" />
            Analysis Narrative
          </h4>
          <div className="bg-surface0 rounded-lg p-4 text-sm text-subtext leading-relaxed border border-surface1">
            {diagnosis.llm_narrative}
          </div>
        </div>
      )}

      {/* Report text (collapsed) */}
      <details className="group">
        <summary className="text-sm font-semibold text-text cursor-pointer flex items-center gap-2 select-none">
          <span className="w-1 h-4 bg-secondary rounded-full" />
          Full Report
          <span className="text-xs text-overlay0 group-open:hidden">
            (click to expand)
          </span>
        </summary>
        <pre className="mt-2 bg-surface0 rounded-lg p-4 text-xs text-subtext overflow-x-auto border border-surface1 whitespace-pre-wrap font-mono">
          {diagnosis.report_text}
        </pre>
      </details>

      {/* Actions */}
      <div className="flex flex-wrap gap-2 pt-2">
        <Button
          size="sm"
          onClick={handleExport}
          data-action="export-report"
          title="Ctrl+E"
        >
          <Download size={14} />
          Export TXT
        </Button>
        <Button
          size="sm"
          variant="secondary"
          onClick={handleExportPdf}
          title="Export as PDF"
        >
          <Download size={14} />
          Export PDF
        </Button>
        {isEnterprise && (
          <>
            <Button
              size="sm"
              variant="ghost"
              onClick={() => setRepairFormOpen((o) => !o)}
            >
              <FileEdit size={14} />
              Log repair
            </Button>
            {repairFormOpen && (
              <div className="w-full mt-2 p-3 rounded-lg border border-surface1 bg-surface0 space-y-2">
                <input
                  placeholder="Repair description"
                  value={repairDesc}
                  onChange={(e) => setRepairDesc(e.target.value)}
                  className="w-full bg-mantle text-text border border-surface1 rounded px-2 py-1 text-sm"
                />
                <input
                  placeholder="Parts used (optional)"
                  value={repairParts}
                  onChange={(e) => setRepairParts(e.target.value)}
                  className="w-full bg-mantle text-text border border-surface1 rounded px-2 py-1 text-sm"
                />
                <input
                  placeholder="Outcome (optional)"
                  value={repairOutcome}
                  onChange={(e) => setRepairOutcome(e.target.value)}
                  className="w-full bg-mantle text-text border border-surface1 rounded px-2 py-1 text-sm"
                />
                <Button
                  size="sm"
                  variant="primary"
                  disabled={!repairDesc.trim() || repairSubmitting}
                  onClick={async () => {
                    setRepairSubmitting(true);
                    try {
                      await createRepair({
                        repair_description: repairDesc.trim(),
                        parts_used: repairParts.trim(),
                        outcome: repairOutcome.trim(),
                        vin: vehicleSelection.makeName && vehicleSelection.modelName
                          ? `${vehicleSelection.year ?? ""} ${vehicleSelection.makeName} ${vehicleSelection.modelName}`.trim()
                          : null,
                      });
                      setRepairDesc("");
                      setRepairParts("");
                      setRepairOutcome("");
                      setRepairFormOpen(false);
                    } finally {
                      setRepairSubmitting(false);
                    }
                  }}
                >
                  {repairSubmitting ? "Saving…" : "Save"}
                </Button>
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
