import { useState, useEffect } from "react";
import { getJob } from "@/lib/api";
import { getApiBase } from "@/lib/env";

export interface JobTrackingState {
  job: Awaited<ReturnType<typeof getJob>> | null;
  mechanicLocation: { latitude: number; longitude: number; heading?: number; speed_mph?: number; eta_min?: number } | null;
  loading: boolean;
  error: string | null;
}

export function useJobTracking(jobId: number | null): JobTrackingState {
  const [job, setJob] = useState<Awaited<ReturnType<typeof getJob>> | null>(null);
  const [mechanicLocation, setMechanicLocation] = useState<{
    latitude: number;
    longitude: number;
    heading?: number;
    speed_mph?: number;
    eta_min?: number;
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    if (!jobId) {
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    getJob(jobId)
      .then((j) => {
        setJob(j);
        if (j.mechanic_lat != null && j.mechanic_lng != null) {
          setMechanicLocation({ latitude: j.mechanic_lat, longitude: j.mechanic_lng });
        }
      })
      .catch((e) => setError(e instanceof Error ? e.message : "Failed to load job"))
      .finally(() => setLoading(false));
  }, [jobId]);

  useEffect(() => {
    if (!jobId) return;
    const apiBase = getApiBase();
    // In dev (empty base) use window.location.host so the Vite proxy handles it.
    // In production use VITE_API_URL, converting http(s) to ws(s).
    const wsUrl = apiBase
      ? `${apiBase.replace(/^http/, "ws")}/api/v1/tracking/${jobId}`
      : `${window.location.protocol === "https:" ? "wss:" : "ws:"}//${window.location.host}/api/v1/tracking/${jobId}`;
    const ws = new WebSocket(wsUrl);
    ws.onmessage = (ev) => {
      try {
        const data = JSON.parse(ev.data);
        if (data.type === "location" && typeof data.latitude === "number" && typeof data.longitude === "number") {
          setMechanicLocation({
            latitude: data.latitude,
            longitude: data.longitude,
            heading: data.heading,
            speed_mph: data.speed_mph,
            eta_min: data.eta_min,
          });
        }
      } catch {
        /* ignore */
      }
    };
    ws.onerror = () => setError((e) => e || "WebSocket error");
    return () => ws.close();
  }, [jobId]);

  return { job, mechanicLocation, loading, error };
}
