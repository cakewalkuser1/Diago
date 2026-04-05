import { useState } from "react";
import { Car, AlertTriangle, Loader2, FileText, CheckCircle2, BookOpen } from "lucide-react";
import { useQuery } from "@tanstack/react-query";
import { Button } from "@/components/ui/Button";
import { SectionCard } from "@/components/ui/SectionCard";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { decodeVin, getRecalls, searchTsbs, getManualUrl } from "@/lib/api";
import { useAppStore } from "@/stores/appStore";
import type { VinDecodeResult, RecallsResult } from "@/types";

export function VehiclePanel() {
  const vehicleSelection = useAppStore((s) => s.vehicleSelection);
  const [vin, setVin] = useState("");
  const [decoded, setDecoded] = useState<VinDecodeResult | null>(null);
  const [recalls, setRecalls] = useState<RecallsResult | null>(null);
  const [recallsLoading, setRecallsLoading] = useState(false);

  const year = vehicleSelection.year ?? (decoded ? parseInt(decoded.model_year, 10) : undefined);
  const make = vehicleSelection.makeName || decoded?.make || "";
  const model = vehicleSelection.modelName || decoded?.model || "";
  const trimDisplay = vehicleSelection.trim || decoded?.trim || "";
  const hasStoredVehicle = Boolean(make && model);

  const vinDecode = useQuery({
    queryKey: ["vinDecode", vin],
    queryFn: () => decodeVin(vin),
    enabled: false,
  });

  const handleDecode = () => {
    const v = vin.trim();
    if (!v || v.length < 8) return;
    vinDecode.refetch().then((result) => {
      const data = result.data;
      if (data && !data.error) {
        setDecoded(data);
        const yr = parseInt(data.model_year, 10);
        if (!isNaN(yr) && data.make && data.model) {
          setRecallsLoading(true);
          getRecalls(data.make, data.model, yr)
            .then(setRecalls)
            .finally(() => setRecallsLoading(false));
        } else {
          setRecalls(null);
        }
      } else {
        setDecoded(null);
        setRecalls(null);
      }
    });
  };

  const recallsQuery = useQuery({
    queryKey: ["recalls", make, model, year],
    queryFn: () => getRecalls(make, model, year!),
    enabled: Boolean(make && model && year && !isNaN(year)),
  });

  const effectiveRecalls = decoded ? recalls : recallsQuery.data ?? null;
  const recallsLoadingState = decoded ? recallsLoading : recallsQuery.isLoading;

  const tsbSearch = useQuery({
    queryKey: ["tsbSearch", year, make, model],
    queryFn: () =>
      searchTsbs({
        model_year: year,
        make,
        model,
        limit: 10,
      }),
    enabled: Boolean(make && model),
  });

  const vehicleLabel = [year, make, model].filter(Boolean).join(" ");
  const showRecallsTsbs = Boolean(make && model);
  const canOpenManual = Boolean(make);

  const handleOpenManual = () => {
    const yr = year != null && !isNaN(year) ? year : undefined;
    getManualUrl(yr != null ? { make, model_year: yr } : { make })
      .then((res) => {
        if (res.url) window.open(res.url, "_blank", "noopener,noreferrer");
      })
      .catch(() => {});
  };

  return (
    <SectionCard
      title={
        <span className="flex items-center gap-2">
          <Car size={16} className="text-primary" />
          Vehicle (recalls & TSBs)
        </span>
      }
    >
      <div className="space-y-4">
        {hasStoredVehicle && (
          <div className="flex flex-wrap items-center gap-2">
            <p className="text-sm text-text font-medium">
              Your vehicle: {vehicleLabel}
              {trimDisplay && ` – ${trimDisplay}`}
            </p>
            {canOpenManual && (
              <Button
                variant="default"
                size="sm"
                onClick={handleOpenManual}
                className="shrink-0 flex items-center gap-1.5"
                title="Open repair manual for this make/year on charm.li (1982–2013)"
              >
                <BookOpen size={14} />
                View service manual
              </Button>
            )}
          </div>
        )}
        <div className="flex flex-col sm:flex-row gap-2">
          <input
            type="text"
            value={vin}
            onChange={(e) => setVin(e.target.value.toUpperCase())}
            placeholder="Or enter VIN to decode"
            maxLength={17}
            className="flex-1 bg-base text-text border border-surface1 rounded-md px-3 py-2 text-sm placeholder:text-overlay0 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
          />
          <Button
            size="sm"
            onClick={handleDecode}
            disabled={vin.trim().length < 8 || vinDecode.isFetching}
            className="sm:shrink-0"
          >
            {vinDecode.isFetching ? (
              <Loader2 size={14} className="animate-spin" />
            ) : (
              "Decode"
            )}
          </Button>
        </div>

        {vinDecode.isError && (
          <ErrorMessage
            message={(vinDecode.error as Error).message}
            onRetry={() => handleDecode()}
            compact
          />
        )}

        {decoded && !decoded.error && (
          <p className="text-subtext text-sm">
            Decoded: {decoded.model_year} {decoded.make} {decoded.model}
            {decoded.trim && ` – ${decoded.trim}`}
          </p>
        )}

        {showRecallsTsbs && (
          <div className="space-y-3 rounded-lg border border-surface1 bg-base p-3 text-sm">
            {/* Recalls */}
            {make && model && (
              <div className="mt-2 border-t border-surface1 pt-2">
                {recallsLoadingState ? (
                  <div className="flex items-center gap-2 text-subtext text-sm">
                    <Loader2 size={14} className="animate-spin" />
                    Checking recalls…
                  </div>
                ) : effectiveRecalls && effectiveRecalls.count > 0 ? (
                  <>
                    <p className="font-medium text-yellow flex items-center gap-1">
                      <AlertTriangle size={14} />
                      {effectiveRecalls.count} open recall(s)
                    </p>
                    <ul className="mt-1 space-y-1 text-subtext text-xs max-h-32 overflow-y-auto">
                      {effectiveRecalls.recalls.slice(0, 5).map((r, i) => (
                        <li key={i}>
                          <strong>{r.campaign_number}</strong>: {r.summary?.slice(0, 80)}
                          {r.summary && r.summary.length > 80 ? "…" : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : effectiveRecalls && effectiveRecalls.count === 0 ? (
                  <p className="text-subtext text-sm flex items-center gap-1.5">
                    <CheckCircle2 size={14} className="text-green" />
                    No open recalls for this vehicle
                  </p>
                ) : !year || isNaN(year) ? (
                  <p className="text-subtext text-xs">Select year on Home for recall check.</p>
                ) : null}
              </div>
            )}

            {/* TSBs */}
            {make && model && (
              <div className="mt-2 border-t border-surface1 pt-2">
                {tsbSearch.isLoading ? (
                  <div className="flex items-center gap-2 text-subtext text-sm">
                    <Loader2 size={14} className="animate-spin" />
                    Searching TSBs…
                  </div>
                ) : tsbSearch.data && tsbSearch.data.results.length > 0 ? (
                  <>
                    <p className="font-medium text-secondary flex items-center gap-1">
                      <FileText size={14} />
                      TSBs for this vehicle: {tsbSearch.data.count}
                    </p>
                    <ul className="mt-1 space-y-1 text-subtext text-xs max-h-24 overflow-y-auto">
                      {tsbSearch.data.results.slice(0, 3).map((tsb) => (
                        <li key={tsb.id}>
                          {tsb.component && `[${tsb.component}] `}
                          {tsb.summary?.slice(0, 60)}
                          {tsb.summary && tsb.summary.length > 60 ? "…" : ""}
                        </li>
                      ))}
                    </ul>
                  </>
                ) : tsbSearch.data && tsbSearch.data.count === 0 ? (
                  <p className="text-subtext text-sm flex items-center gap-1.5">
                    <FileText size={14} className="text-overlay0" />
                    No TSBs found for this vehicle
                  </p>
                ) : tsbSearch.isError ? (
                  <p className="text-red text-xs">
                    Could not load TSBs.
                  </p>
                ) : null}
              </div>
            )}
          </div>
        )}
      </div>
    </SectionCard>
  );
}
