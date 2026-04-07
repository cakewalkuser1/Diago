import { useParams, useNavigate } from "react-router-dom";
import { MapPin, Loader2, ArrowLeft, Clock, CheckCircle2, Car, Wrench, Navigation } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { LiveTrackingMap } from "@/components/tracking/LiveTrackingMap";
import { useJobTracking } from "@/hooks/useJobTracking";

// ─── Status config ────────────────────────────────────────────────────────────

type JobStatus = "pending" | "accepted" | "en_route" | "arrived" | "in_progress" | "completed" | string;

interface StatusConfig {
  icon: React.ReactNode;
  label: string;
  subtext: (name: string) => string;
  color: string;
  bgColor: string;
}

function getStatusConfig(status: JobStatus, mechanicName: string): StatusConfig {
  const name = mechanicName || "Your mechanic";
  const configs: Record<string, StatusConfig> = {
    accepted: {
      icon: <CheckCircle2 size={22} />,
      label: "Mechanic accepted",
      subtext: () => `${name} has accepted your job`,
      color: "text-blue-400",
      bgColor: "bg-blue-400/10",
    },
    en_route: {
      icon: <Car size={22} />,
      label: "On the way",
      subtext: () => `${name} is heading to you`,
      color: "text-primary",
      bgColor: "bg-primary/10",
    },
    arrived: {
      icon: <MapPin size={22} />,
      label: "Mechanic arrived",
      subtext: () => `${name} is at your location`,
      color: "text-yellow-400",
      bgColor: "bg-yellow-400/10",
    },
    in_progress: {
      icon: <Wrench size={22} />,
      label: "Work in progress",
      subtext: () => `${name} is working on your vehicle`,
      color: "text-orange-400",
      bgColor: "bg-orange-400/10",
    },
    completed: {
      icon: <CheckCircle2 size={22} />,
      label: "Job complete",
      subtext: () => `${name} has finished the job`,
      color: "text-green-400",
      bgColor: "bg-green-400/10",
    },
  };
  return configs[status] ?? {
    icon: <Navigation size={22} />,
    label: "Mechanic dispatched",
    subtext: () => `${name} has been notified`,
    color: "text-primary",
    bgColor: "bg-primary/10",
  };
}

// ─── ETA pill ─────────────────────────────────────────────────────────────────

function EtaPill({ etaMin, arrivalAt }: { etaMin?: number | null; arrivalAt?: string | null }) {
  if (etaMin != null && etaMin > 0) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface1 text-sm font-medium">
        <Clock size={14} className="text-primary" />
        <span>{Math.round(etaMin)} min away</span>
      </div>
    );
  }
  if (arrivalAt) {
    return (
      <div className="flex items-center gap-1.5 px-3 py-1.5 rounded-full bg-surface1 text-sm font-medium">
        <Clock size={14} className="text-primary" />
        <span>Arrives by {new Date(arrivalAt).toLocaleTimeString([], { hour: "2-digit", minute: "2-digit" })}</span>
      </div>
    );
  }
  return null;
}

// ─── Progress steps ───────────────────────────────────────────────────────────

const JOB_STEPS: { key: JobStatus; label: string }[] = [
  { key: "accepted", label: "Accepted" },
  { key: "en_route", label: "En route" },
  { key: "arrived", label: "Arrived" },
  { key: "completed", label: "Done" },
];

const STEP_ORDER = ["accepted", "en_route", "arrived", "in_progress", "completed"];

function JobProgressBar({ status }: { status: JobStatus }) {
  const currentIdx = STEP_ORDER.indexOf(status);
  return (
    <div className="flex items-center gap-1 pt-1">
      {JOB_STEPS.map((s, i) => {
        const stepIdx = STEP_ORDER.indexOf(s.key);
        const done = currentIdx >= stepIdx;
        const active = currentIdx === stepIdx;
        return (
          <div key={s.key} className="flex items-center flex-1 last:flex-none">
            <div className="flex flex-col items-center gap-1">
              <div className={`w-2 h-2 rounded-full transition-colors ${
                done ? "bg-primary" : "bg-surface1"
              } ${active ? "ring-2 ring-primary/40 ring-offset-1 ring-offset-surface0" : ""}`} />
              <span className={`text-[10px] ${done ? "text-text" : "text-overlay1"}`}>{s.label}</span>
            </div>
            {i < JOB_STEPS.length - 1 && (
              <div className={`flex-1 h-px mx-1 mb-4 ${done ? "bg-primary" : "bg-surface1"}`} />
            )}
          </div>
        );
      })}
    </div>
  );
}

// ─── Main view ────────────────────────────────────────────────────────────────

export function TrackingView() {
  const { jobId } = useParams<{ jobId: string }>();
  const navigate = useNavigate();
  const id = jobId ? parseInt(jobId, 10) : null;
  const { job, mechanicLocation, loading, error } = useJobTracking(id);

  if (loading && !job) {
    return (
      <div className="min-h-screen bg-base text-text flex items-center justify-center">
        <div className="flex flex-col items-center gap-3">
          <Loader2 size={36} className="animate-spin text-primary" />
          <p className="text-sm text-subtext">Loading tracking info…</p>
        </div>
      </div>
    );
  }

  if (error || !job) {
    return (
      <div className="min-h-screen bg-base text-text flex flex-col">
        <div className="p-4">
          <button type="button" onClick={() => navigate("/find-mechanic")} className="flex items-center gap-2 text-sm text-subtext hover:text-text">
            <ArrowLeft size={16} /> Back
          </button>
        </div>
        <div className="flex-1 flex items-center justify-center p-6">
          <div className="rounded-2xl border border-surface1 bg-surface0 p-6 text-center max-w-sm w-full">
            <p className="text-subtext mb-4">{error || "Job not found"}</p>
            <Button variant="secondary" onClick={() => navigate("/find-mechanic")}>
              <ArrowLeft size={18} /> Find mechanic
            </Button>
          </div>
        </div>
      </div>
    );
  }

  const userLat = job.user_latitude;
  const userLng = job.user_longitude;
  const mechLat = mechanicLocation?.latitude ?? job.mechanic_lat;
  const mechLng = mechanicLocation?.longitude ?? job.mechanic_lng;
  const jobStatus: JobStatus = (job as { status?: string }).status ?? "accepted";
  const statusConfig = getStatusConfig(jobStatus, job.mechanic_name || "");
  const etaMin = mechanicLocation?.eta_min ?? job.route_duration_min;
  const isCompleted = jobStatus === "completed";

  return (
    <div className="min-h-screen bg-base text-text flex flex-col relative">
      {/* Full-screen map */}
      <div className="absolute inset-0">
        <LiveTrackingMap
          userLat={userLat}
          userLng={userLng}
          mechanicLat={mechLat}
          mechanicLng={mechLng}
          mechanicName={job.mechanic_name}
          className="w-full h-full rounded-none border-0"
          height={window.innerHeight}
        />
      </div>

      {/* Top bar */}
      <div className="relative z-10 flex items-center justify-between p-4 pt-safe">
        <button
          type="button"
          onClick={() => navigate("/find-mechanic")}
          className="w-10 h-10 rounded-full bg-surface0/90 backdrop-blur flex items-center justify-center shadow-md"
        >
          <ArrowLeft size={18} className="text-text" />
        </button>

        <div className="flex items-center gap-2">
          <div className={`w-8 h-8 rounded-full ${statusConfig.bgColor} flex items-center justify-center ${statusConfig.color}`}>
            {statusConfig.icon}
          </div>
          <span className="text-sm font-semibold bg-surface0/90 backdrop-blur px-3 py-1 rounded-full shadow-md">
            {statusConfig.label}
          </span>
        </div>

        <EtaPill etaMin={etaMin} arrivalAt={job.estimated_arrival_at} />
      </div>

      {/* Bottom sheet */}
      <div className="relative z-10 mt-auto">
        <div className="bg-surface0/95 backdrop-blur-lg rounded-t-3xl shadow-2xl border-t border-surface1 px-5 pt-4 pb-6 pb-safe">
          {/* Handle */}
          <div className="w-10 h-1 rounded-full bg-surface2 mx-auto mb-4" />

          {/* Mechanic info */}
          <div className="flex items-center gap-3 mb-4">
            <div className={`w-12 h-12 rounded-full ${statusConfig.bgColor} flex items-center justify-center ${statusConfig.color} flex-shrink-0`}>
              {statusConfig.icon}
            </div>
            <div className="flex-1 min-w-0">
              <p className="font-semibold text-base truncate">{job.mechanic_name || "Your mechanic"}</p>
              <p className="text-sm text-subtext">{statusConfig.subtext(job.mechanic_name || "")}</p>
            </div>
          </div>

          {/* Progress bar */}
          {!isCompleted && <JobProgressBar status={jobStatus} />}

          {/* Divider */}
          <div className="h-px bg-surface1 my-4" />

          {/* Job details */}
          <div className="flex items-start gap-2 mb-4">
            <Wrench size={15} className="text-overlay1 mt-0.5 flex-shrink-0" />
            <p className="text-sm text-subtext flex-1">{job.part_info}</p>
          </div>

          {/* CTA */}
          {isCompleted ? (
            <Button size="lg" variant="primary" className="w-full" onClick={() => navigate("/")}>
              <CheckCircle2 size={18} /> Done
            </Button>
          ) : (
            <Button size="lg" variant="secondary" className="w-full" onClick={() => navigate("/find-mechanic")}>
              <ArrowLeft size={18} /> Back to find mechanic
            </Button>
          )}
        </div>
      </div>
    </div>
  );
}
