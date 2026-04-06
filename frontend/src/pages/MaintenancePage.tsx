import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import { Calendar, Wrench, Loader2, Plus, AlertTriangle, X } from "lucide-react";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import {
  getMaintenanceRecords,
  getMaintenanceDue,
  createMaintenanceRecord,
  type MaintenanceRecord,
} from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";
import { useAppStore } from "@/stores/appStore";

const COMMON_SERVICES = [
  "Oil & filter change",
  "Tire rotation",
  "Brake inspection",
  "Air filter replacement",
  "Cabin air filter replacement",
  "Spark plug replacement",
  "Coolant flush",
  "Transmission fluid service",
  "Brake fluid flush",
  "Serpentine belt replacement",
  "Battery replacement",
  "Wheel alignment",
  "Oil & filter change", "Tire rotation", "Brake inspection",
  "Air filter replacement", "Cabin air filter replacement",
  "Spark plug replacement", "Coolant flush", "Transmission fluid service",
  "Brake fluid flush", "Serpentine belt replacement", "Battery replacement", "Wheel alignment",
];

export function MaintenancePage() {
  const session = useAuthStore((s) => s.session);
  const userId = session?.user?.id ?? "anon";
  const vehicleSelection = useAppStore((s) => s.vehicleSelection);
  const qc = useQueryClient();
  const [currentMileage, setCurrentMileage] = useState("");
  const [showForm, setShowForm] = useState(false);
  const [formService, setFormService] = useState("");
  const [formMileage, setFormMileage] = useState("");
  const [formDate, setFormDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [formNextMileage, setFormNextMileage] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const addRecord = useMutation({
    mutationFn: () => createMaintenanceRecord({
      service_type: formService.trim(),
      mileage: formMileage ? parseInt(formMileage, 10) : undefined,
      performed_at: formDate || undefined,
      next_due_mileage: formNextMileage ? parseInt(formNextMileage, 10) : undefined,
      notes: formNotes.trim() || undefined,
      vehicle_make: vehicleSelection.makeName || undefined,
      vehicle_model: vehicleSelection.modelName || undefined,
      vehicle_year: vehicleSelection.year ? parseInt(vehicleSelection.year, 10) : undefined,
    }, userId),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance-records", userId] });
      setShowForm(false);
      setFormService(""); setFormMileage(""); setFormNextMileage(""); setFormNotes(""); setFormError(null);
    },
    onError: (e: unknown) => setFormError(e instanceof Error ? e.message : "Failed to save record"),
  });

  // Form state
  const [formService, setFormService] = useState("");
  const [formMileage, setFormMileage] = useState("");
  const [formDate, setFormDate] = useState(() => new Date().toISOString().slice(0, 10));
  const [formNextMileage, setFormNextMileage] = useState("");
  const [formNotes, setFormNotes] = useState("");
  const [formError, setFormError] = useState<string | null>(null);

  const addRecord = useMutation({
    mutationFn: () =>
      createMaintenanceRecord(
        {
          service_type: formService.trim(),
          mileage: formMileage ? parseInt(formMileage, 10) : undefined,
          performed_at: formDate || undefined,
          next_due_mileage: formNextMileage ? parseInt(formNextMileage, 10) : undefined,
          notes: formNotes.trim() || undefined,
          vehicle_make: vehicleSelection.makeName || undefined,
          vehicle_model: vehicleSelection.modelName || undefined,
          vehicle_year: vehicleSelection.year ? parseInt(vehicleSelection.year, 10) : undefined,
        },
        userId
      ),
    onSuccess: () => {
      qc.invalidateQueries({ queryKey: ["maintenance-records", userId] });
      setShowForm(false);
      setFormService("");
      setFormMileage("");
      setFormNextMileage("");
      setFormNotes("");
      setFormError(null);
    },
    onError: (e: unknown) => {
      setFormError(e instanceof Error ? e.message : "Failed to save record");
    },
  });

  const { data: records, isLoading } = useQuery({
    queryKey: ["maintenance-records", userId],
    queryFn: () => getMaintenanceRecords(userId),
  });
  const { data: due } = useQuery({
    queryKey: ["maintenance-due", userId, currentMileage ? parseInt(currentMileage, 10) : null],
    queryFn: () => getMaintenanceDue(userId, currentMileage ? parseInt(currentMileage, 10) : undefined),
  });

  return (
    <div className="min-h-screen bg-base text-text flex flex-col">
      <Header />
      <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <div className="flex items-center gap-2 mb-6">
          <div className="p-2 rounded-lg bg-primary/10">
            <Calendar size={24} className="text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Maintenance tracking</h1>
            <p className="text-sm text-subtext">Track service history and due dates.</p>
          </div>
        </div>

        <div className="mb-4">
          <label className="block text-sm font-medium text-text mb-1">Current mileage</label>
          <input
            type="number"
            value={currentMileage}
            onChange={(e) => setCurrentMileage(e.target.value)}
            placeholder="e.g. 45000"
            className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text placeholder:text-overlay1"
          />
        </div>

        {due && due.length > 0 && (
          <div className="rounded-lg p-4 border border-amber-500/50 bg-amber-500/10 mb-4">
            <h2 className="font-medium flex items-center gap-2 text-amber-600 dark:text-amber-400">
              <AlertTriangle size={18} />
              Due soon
            </h2>
            <ul className="mt-2 space-y-1 text-sm text-subtext">
              {due.map((d: MaintenanceRecord) => (
                <li key={d.id}>
                  {d.service_type}
                  {d.vehicle_make && ` — ${d.vehicle_make} ${d.vehicle_model || ""}`}
                </li>
              ))}
            </ul>
          </div>
        )}

        <h2 className="font-medium text-text mb-2">Service history</h2>
        {isLoading ? (
          <Loader2 size={24} className="animate-spin text-primary" />
        ) : records && records.length > 0 ? (
          <ul className="space-y-2">
            {records.map((r) => (
              <li
                key={r.id}
                className="rounded-lg p-3 border border-surface1 bg-surface0 flex items-center gap-3"
              >
                <Wrench size={18} className="text-primary" />
                <div>
                  <p className="font-medium">{r.service_type}</p>
                  <p className="text-xs text-overlay0">
                    {r.mileage != null && `${r.mileage.toLocaleString()} mi`}
                    {r.performed_at && ` • ${r.performed_at}`}
                    {r.vehicle_make && ` • ${r.vehicle_make}`}
                  </p>
                </div>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-subtext">No records yet. Add your first service.</p>
        )}

        <Button
          variant="secondary"
          className="mt-4"
          onClick={() => { setShowForm(true); setFormError(null); }}
        >
          <Plus size={18} />
          Add record
        </Button>

        {/* Add-record form */}
        <Button variant="secondary" className="mt-4" onClick={() => { setShowForm(true); setFormError(null); }}>
          <Plus size={18} /> Add record
        </Button>

        {showForm && (
          <div className="mt-4 rounded-lg border border-surface1 bg-surface0 p-4 space-y-3">
            <div className="flex items-center justify-between mb-1">
              <h3 className="font-medium text-sm">New service record</h3>
              <button
                type="button"
                onClick={() => setShowForm(false)}
                className="text-subtext hover:text-text"
                aria-label="Close form"
              >
                <X size={16} />
              </button>
            </div>

            <div>
              <label className="block text-xs font-medium text-subtext mb-1">Service type *</label>
              <input
                list="service-suggestions"
                value={formService}
                onChange={(e) => setFormService(e.target.value)}
                placeholder="e.g. Oil & filter change"
                className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1"
              />
              <datalist id="service-suggestions">
                {COMMON_SERVICES.map((s) => <option key={s} value={s} />)}
              </datalist>
            </div>

            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-subtext mb-1">Mileage at service</label>
                <input
                  type="number"
                  value={formMileage}
                  onChange={(e) => setFormMileage(e.target.value)}
                  placeholder="e.g. 45000"
                  className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1"
                />
              </div>
              <div>
                <label className="block text-xs font-medium text-subtext mb-1">Date</label>
                <input
                  type="date"
                  value={formDate}
                  onChange={(e) => setFormDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm"
                />
              </div>
            </div>

            <div>
              <label className="block text-xs font-medium text-subtext mb-1">Next due (mileage)</label>
              <input
                type="number"
                value={formNextMileage}
                onChange={(e) => setFormNextMileage(e.target.value)}
                placeholder="e.g. 50000"
                className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1"
              />
            </div>

            <div>
              <label className="block text-xs font-medium text-subtext mb-1">Notes</label>
              <textarea
                value={formNotes}
                onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Shop, parts used, observations…"
                rows={2}
                className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1 resize-none"
              />
            </div>

            {formError && (
              <p className="text-xs text-red-400">{formError}</p>
            )}

            <div className="flex gap-2 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowForm(false)}>
                Cancel
              </Button>
              <Button
                variant="primary"
                size="sm"
                disabled={!formService.trim() || addRecord.isPending}
                onClick={() => {
                  if (!formService.trim()) { setFormError("Service type is required"); return; }
                  addRecord.mutate();
                }}
              >
                {addRecord.isPending ? <Loader2 size={14} className="animate-spin" /> : null}
                Save
              <button type="button" onClick={() => setShowForm(false)} className="text-subtext hover:text-text" aria-label="Close form"><X size={16} /></button>
            </div>
            <div>
              <label className="block text-xs font-medium text-subtext mb-1">Service type *</label>
              <input list="service-suggestions" value={formService} onChange={(e) => setFormService(e.target.value)}
                placeholder="e.g. Oil & filter change"
                className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1" />
              <datalist id="service-suggestions">{COMMON_SERVICES.map((s) => <option key={s} value={s} />)}</datalist>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div>
                <label className="block text-xs font-medium text-subtext mb-1">Mileage at service</label>
                <input type="number" value={formMileage} onChange={(e) => setFormMileage(e.target.value)}
                  placeholder="e.g. 45000"
                  className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1" />
              </div>
              <div>
                <label className="block text-xs font-medium text-subtext mb-1">Date</label>
                <input type="date" value={formDate} onChange={(e) => setFormDate(e.target.value)}
                  className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm" />
              </div>
            </div>
            <div>
              <label className="block text-xs font-medium text-subtext mb-1">Next due mileage</label>
              <input type="number" value={formNextMileage} onChange={(e) => setFormNextMileage(e.target.value)}
                placeholder="e.g. 50000"
                className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1" />
            </div>
            <div>
              <label className="block text-xs font-medium text-subtext mb-1">Notes</label>
              <textarea value={formNotes} onChange={(e) => setFormNotes(e.target.value)}
                placeholder="Shop, parts used, observations…" rows={2}
                className="w-full px-3 py-2 rounded-lg bg-mantle border border-surface1 text-text text-sm placeholder:text-overlay1 resize-none" />
            </div>
            {formError && <p className="text-xs text-red-400">{formError}</p>}
            <div className="flex gap-2 justify-end">
              <Button variant="secondary" size="sm" onClick={() => setShowForm(false)}>Cancel</Button>
              <Button variant="primary" size="sm"
                disabled={!formService.trim() || addRecord.isPending}
                onClick={() => { if (!formService.trim()) { setFormError("Service type is required"); return; } addRecord.mutate(); }}>
                {addRecord.isPending ? <Loader2 size={14} className="animate-spin" /> : null} Save
              </Button>
            </div>
          </div>
        )}
      </main>
    </div>
  );
}
