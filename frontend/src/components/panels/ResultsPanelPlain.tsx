import { useQuery } from "@tanstack/react-query";
import { AlertTriangle, ChevronRight, BookOpen } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { useAppStore } from "@/stores/appStore";
import { usePersona } from "@/contexts/PersonaContext";
import { toPlainEnglish, PLAIN_ENGLISH_CLASS_MAP, PLAIN_ENGLISH_FAILURE_MAP } from "@/lib/translations";
import { getRepairGuidesForDiagnosis } from "@/lib/api";
import type { RankedFailureMode } from "@/types";

export function ResultsPanelPlain() {
  const diagnosis = useAppStore((s) => s.diagnosis);
  const vehicleSelection = useAppStore((s) => s.vehicleSelection);
  const { setPersonaTier } = usePersona();

  const repairGuides = useQuery({
    queryKey: [
      "repair-guides-plain",
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

  const topCause =
    PLAIN_ENGLISH_CLASS_MAP[diagnosis.top_class] ??
    toPlainEnglish(diagnosis.top_class_display, PLAIN_ENGLISH_CLASS_MAP) ??
    diagnosis.top_class_display;
  const narrative = diagnosis.llm_narrative ?? topCause;

  const topFailures = (diagnosis.ranked_failure_modes ?? [])
    .filter((fm) => fm.score > 0)
    .slice(0, 3)
    .map((fm: RankedFailureMode) =>
      toPlainEnglish(fm.display_name, PLAIN_ENGLISH_FAILURE_MAP) || fm.description || fm.display_name
    );

  return (
    <div className="flex-1 overflow-y-auto p-6 max-w-xl mx-auto space-y-6">
      <div className="space-y-4">
        <h2 className="text-xl font-semibold text-text">Likely cause</h2>
        <div className="rounded-xl border border-surface1 bg-surface0/80 p-5 card-shadow">
          <p className="text-base text-text leading-relaxed">{topCause}</p>
        </div>
      </div>

      {narrative && narrative !== topCause && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-text">What this means</h3>
          <p className="text-sm text-subtext leading-relaxed whitespace-pre-wrap">{narrative}</p>
        </div>
      )}

      {topFailures.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-text">Other possibilities</h3>
          <ul className="space-y-2">
            {topFailures.slice(1).map((desc, i) => (
              <li key={i} className="text-sm text-subtext flex items-start gap-2">
                <ChevronRight size={14} className="shrink-0 mt-0.5 text-overlay0" />
                {desc}
              </li>
            ))}
          </ul>
        </div>
      )}

      {repairGuides.data && repairGuides.data.length > 0 && (
        <div className="space-y-2">
          <h3 className="text-sm font-semibold text-text flex items-center gap-2">
            <BookOpen size={16} className="text-[var(--color-secondary)]" />
            Repair guidance
          </h3>
          <ul className="space-y-2">
            {repairGuides.data.map((guide) => (
              <li key={guide.id}>
                <a
                  href={guide.source_url}
                  target="_blank"
                  rel="noopener noreferrer"
                  className="text-sm text-primary hover:underline"
                >
                  {guide.title}
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="pt-4 space-y-3">
        <Button
          variant="primary"
          size="xl"
          className="w-full"
          onClick={() => setPersonaTier("diy")}
        >
          Get more technical details
          <ChevronRight size={20} />
        </Button>
        <p className="text-xs text-overlay0 text-center">
          Switch to DIY mode for step-by-step tests and part suggestions.
        </p>
      </div>
    </div>
  );
}
