import { Wifi, WifiOff, Loader2 } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { healthCheck } from "@/lib/api";

export function StatusBar() {
  const health = useQuery({
    queryKey: ["health"],
    queryFn: healthCheck,
    refetchInterval: 30_000,
    retry: 1,
  });

  const isConnected = health.data?.status === "ok";
  const healthLoading = health.isLoading || health.isFetching;
  const healthError = health.isError;

  return (
    <footer className="flex items-center justify-center gap-2 px-3 py-1.5 border-t border-surface1/50 bg-mantle/80 text-[11px] text-overlay0">
      {healthLoading ? (
        <Loader2 size={10} className="animate-spin text-primary" />
      ) : isConnected ? (
        <Wifi size={10} className="text-green" />
      ) : (
        <WifiOff size={10} className="text-red" />
      )}
      <span>
        {healthLoading ? "Connecting…" : healthError ? "API error" : isConnected ? "Connected" : "Offline"}
      </span>
      <span className="text-overlay0/60">·</span>
      <span>v{health.data?.version ?? "?"}</span>
    </footer>
  );
}
