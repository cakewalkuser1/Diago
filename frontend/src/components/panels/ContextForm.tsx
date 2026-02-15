import { Gauge } from "lucide-react";
import { Checkbox } from "@/components/ui/Checkbox";
import { Select } from "@/components/ui/Select";
import { SectionCard } from "@/components/ui/SectionCard";
import { useAppStore } from "@/stores/appStore";
import { usePersona } from "@/contexts/PersonaContext";

const NOISE_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "whine", label: "Whine" },
  { value: "squeal", label: "Squeal" },
  { value: "knock", label: "Knock / Tap" },
  { value: "rattle", label: "Rattle / Buzz" },
  { value: "hum", label: "Hum / Drone" },
  { value: "click", label: "Click / Tick" },
  { value: "grind", label: "Grind / Scrape" },
  { value: "hiss", label: "Hiss" },
];

const PITCH_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "low", label: "Low" },
  { value: "mid", label: "Mid" },
  { value: "high", label: "High" },
];

const DURATION_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "just_started", label: "Just started" },
  { value: "days", label: "Days" },
  { value: "weeks", label: "Weeks" },
  { value: "months", label: "Months" },
];

const VEHICLE_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "sedan", label: "Sedan" },
  { value: "suv_truck", label: "SUV / Truck" },
  { value: "sports", label: "Sports car" },
  { value: "diesel", label: "Diesel" },
  { value: "hybrid_ev", label: "Hybrid / EV" },
];

const MILEAGE_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "under_50k", label: "Under 50k" },
  { value: "50k_100k", label: "50k – 100k" },
  { value: "100k_150k", label: "100k – 150k" },
  { value: "over_150k", label: "Over 150k" },
];

const MAINTENANCE_OPTIONS = [
  { value: "unknown", label: "Unknown" },
  { value: "none", label: "None" },
  { value: "oil_change", label: "Oil change" },
  { value: "belt_replacement", label: "Belt replacement" },
  { value: "brake_work", label: "Brake work" },
  { value: "suspension_work", label: "Suspension work" },
];

export function ContextForm() {
  const context = useAppStore((s) => s.context);
  const setContext = useAppStore((s) => s.setContext);
  const fuelTrims = useAppStore((s) => s.fuelTrims);
  const setFuelTrims = useAppStore((s) => s.setFuelTrims);
  const { personaTier, showTechnicalData } = usePersona();
  const showFuelTrims = personaTier === "diy" && showTechnicalData;

  return (
    <SectionCard
      title={
        <span className="flex items-center gap-2">
          <span className="w-1 h-4 bg-secondary rounded-full" />
          Noise Behavior & Vehicle Context
        </span>
      }
    >
      <div className="space-y-4">

      {/* Row 1: Checkboxes */}
      <div className="flex flex-wrap gap-x-5 gap-y-2">
        <Checkbox
          label="RPM dependent"
          checked={context.rpm_dependency}
          onChange={(e) => setContext({ rpm_dependency: e.target.checked })}
        />
        <Checkbox
          label="Speed dependent"
          checked={context.speed_dependency}
          onChange={(e) => setContext({ speed_dependency: e.target.checked })}
        />
        <Checkbox
          label="Load dependent"
          checked={context.load_dependency}
          onChange={(e) => setContext({ load_dependency: e.target.checked })}
        />
        <Checkbox
          label="Cold start only"
          checked={context.cold_only}
          onChange={(e) => setContext({ cold_only: e.target.checked })}
        />
        <Checkbox
          label="Occurs at idle"
          checked={context.occurs_at_idle}
          onChange={(e) => setContext({ occurs_at_idle: e.target.checked })}
        />
        <Checkbox
          label="Localized source"
          checked={context.mechanical_localization}
          onChange={(e) =>
            setContext({ mechanical_localization: e.target.checked })
          }
        />
        <Checkbox
          label="Comes & goes"
          checked={context.intermittent}
          onChange={(e) => setContext({ intermittent: e.target.checked })}
        />
      </div>

      {/* Row 2: Noise & Pitch */}
      <div className="flex flex-wrap gap-4">
        <Select
          label="Noise type"
          options={NOISE_OPTIONS}
          value={context.noise_character}
          onChange={(e) => setContext({ noise_character: e.target.value })}
        />
        <Select
          label="Pitch"
          options={PITCH_OPTIONS}
          value={context.perceived_frequency}
          onChange={(e) => setContext({ perceived_frequency: e.target.value })}
        />
      </div>

      {/* Fuel trims (DIYer + Show Technical Data) */}
      {showFuelTrims && (
        <div className="space-y-2 p-3 rounded-lg bg-mantle/50 border border-surface1">
          <p className="text-xs font-medium text-text flex items-center gap-2">
            <Gauge size={14} className="text-secondary" />
            Fuel trims (optional)
          </p>
          <p className="text-[11px] text-subtext">
            Short-term fuel trim adjusts quickly; long-term learns over time. High values can mean air leak or weak fuel delivery.
          </p>
          <div className="flex gap-4">
            <div>
              <label className="text-[11px] text-overlay0">STFT %</label>
              <input
                type="number"
                step="0.1"
                placeholder="—"
                value={fuelTrims.stft ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setFuelTrims({ stft: v === "" ? null : parseFloat(v) });
                }}
                className="w-20 bg-surface0 text-text border border-surface1 rounded px-2 py-1 text-sm"
              />
            </div>
            <div>
              <label className="text-[11px] text-overlay0">LTFT %</label>
              <input
                type="number"
                step="0.1"
                placeholder="—"
                value={fuelTrims.ltft ?? ""}
                onChange={(e) => {
                  const v = e.target.value;
                  setFuelTrims({ ltft: v === "" ? null : parseFloat(v) });
                }}
                className="w-20 bg-surface0 text-text border border-surface1 rounded px-2 py-1 text-sm"
              />
            </div>
          </div>
        </div>
      )}

      {/* Row 3: Vehicle info */}
      <div className="flex flex-wrap gap-4">
        <Select
          label="Duration"
          options={DURATION_OPTIONS}
          value={context.issue_duration}
          onChange={(e) => setContext({ issue_duration: e.target.value })}
        />
        <Select
          label="Vehicle type"
          options={VEHICLE_OPTIONS}
          value={context.vehicle_type}
          onChange={(e) => setContext({ vehicle_type: e.target.value })}
        />
        <Select
          label="Mileage"
          options={MILEAGE_OPTIONS}
          value={context.mileage_range}
          onChange={(e) => setContext({ mileage_range: e.target.value })}
        />
        <Select
          label="Recent work"
          options={MAINTENANCE_OPTIONS}
          value={context.recent_maintenance}
          onChange={(e) => setContext({ recent_maintenance: e.target.value })}
        />
      </div>
    </div>
    </SectionCard>
  );
}
