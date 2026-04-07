import { useState, useEffect } from "react";
import { ref, onValue, off } from "firebase/database";
import { getJob } from "@/lib/api";
import { getApiBase } from "@/lib/env";
import { getFirebaseDb, isFirebaseConfigured } from "@/lib/firebase";

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

  // Real-time location: Firebase Realtime DB (preferred) or WebSocket (fallback)
  useEffect(() => {
    if (!jobId) return;

    if (isFirebaseConfigured) {
      const db = getFirebaseDb();
      if (!db) return;
      const locationRef = ref(db, `tracking/${jobId}/location`);
      onValue(locationRef, (snapshot) => {
        const data = snapshot.val();
        if (data && typeof data.latitude === "number" && typeof data.longitude === "number") {
          setMechanicLocation({
            latitude: data.latitude,
            longitude: data.longitude,
            heading: data.heading,
            speed_mph: data.speed_mph,
            eta_min: data.eta_min,
          });
        }
      });
      return () => off(locationRef);
    }

    // Fallback: WebSocket
    const apiBase = getApiBase();
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
