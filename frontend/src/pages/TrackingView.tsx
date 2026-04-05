import { useParams, useNavigate } from "react-router-dom";
import { MapPin, Loader2, Truck, ArrowLeft } from "lucide-react";
import { Header } from "@/components/layout/Header";
import { Button } from "@/components/ui/Button";
import { LiveTrackingMap } from "@/components/tracking/LiveTrackingMap";
import { useJobTracking } from "@/hooks/useJobTracking";

export function TrackingView() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const id = jobId ? parseInt(jobId, 10) : null;
  const { job, mechanicLocation, loading, error } = useJobTracking(id);

  if (loading && !job) {
    return (
      <div className="min-h-screen bg-base text-text flex flex-col">
        <Header />
        <main className="flex-1 flex items-center justify-center p-6">
          <Loader2 size={32} className="animate-spin text-primary" />
        </main>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen bg-base text-text flex flex-col">
        <Header />
        <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
          <div className="rounded-lg p-6 border border-surface1 bg-surface0 text-center">
            <p className="text-subtext mb-4">{error || "Job not found"}</p>
            <Button variant="secondary" onClick={() => navigate("/find-mechanic")}>
              <ArrowLeft size={18} />
              Back to find mechanic
            </Button>
          </div>
        </main>
      </div>
    );
  }

  const userLat = job.user_latitude;
  const userLng = job.user_longitude;
  const mechLat = mechanicLocation?.latitude ?? job.mechanic_lat;
  const mechLng = mechanicLocation?.longitude ?? job.mechanic_lng;

  return (
    <div className="min-h-screen bg-base text-text flex flex-col">
      <Header />
      <main className="flex-1 p-4 sm:p-6 max-w-lg mx-auto w-full">
        <div className="flex items-center gap-2 mb-4">
          <div className="p-2 rounded-lg bg-primary/10">
            <MapPin size={24} className="text-primary" />
          </div>
          <div>
            <h1 className="text-lg font-semibold">Track mechanic</h1>
            <p className="text-sm text-subtext">
              {job.mechanic_name || "Mechanic"} is on the way
            </p>
          </div>
        </div>

        <LiveTrackingMap
          userLat={userLat}
          userLng={userLng}
          mechanicLat={mechLat}
          mechanicLng={mechLng}
          mechanicName={job.mechanic_name}
          className="mb-4"
        />

        <div className="rounded-lg p-4 border border-surface1 bg-surface0 space-y-2">
          <p className="text-sm text-subtext">{job.part_info}</p>
          {job.route_duration_min != null && job.route_duration_min > 0 && (
            <p className="text-sm text-text flex items-center gap-2">
              <Truck size={16} />
              ETA: ~{Math.round(job.route_duration_min)} min
            </p>
          )}
          {job.estimated_arrival_at && (
            <p className="text-xs text-overlay0">
              Arrival by {new Date(job.estimated_arrival_at).toLocaleTimeString()}
            </p>
          )}
        </div>

        <Button
          variant="secondary"
          className="mt-4"
          onClick={() => navigate("/find-mechanic")}
        >
          <ArrowLeft size={18} />
          Back to find mechanic
        </Button>
      </main>
    </div>
  );
}
