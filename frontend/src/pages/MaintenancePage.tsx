import { useQuery } from "@tanstack/react-query";
import { Calendar, Wrench, Loader2, Plus, AlertTriangle } from "lucide-react";
import { useState } from "react";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import {
  getMaintenanceRecords,
  getMaintenanceDue,
  type MaintenanceRecord,
} from "@/lib/api";
import { useAuthStore } from "@/stores/authStore";

export function MaintenancePage() {
  const session = useAuthStore((s) => s.session);
  const userId = session?.user?.id ?? "anon";
  const [currentMileage, setCurrentMileage] = useState("");
  const [showForm, setShowForm] = useState(false);

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
          onClick={() => setShowForm(!showForm)}
        >
          <Plus size={18} />
          Add record
        </Button>
      </main>
    </div>
  );
}
