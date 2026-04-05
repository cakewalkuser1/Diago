import { useState, useCallback } from "react";
import { Plus, Trash2 } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Chip } from "@/components/ui/Chip";
import { SectionCard } from "@/components/ui/SectionCard";
import { useAppStore } from "@/stores/appStore";
import { codeColor } from "@/lib/utils";

/** OBD-II: P/B/C/U + 4 hex digits (e.g. P0300, P219A) */
const CODE_REGEX = /^[PBCU][0-9A-F]{4}$/i;

interface TroubleCodePanelProps {
  /** When true, only show the trouble codes section (no symptom textarea). */
  codesOnly?: boolean;
}

export function TroubleCodePanel({ codesOnly }: TroubleCodePanelProps) {
  const {
    symptoms,
    activeCodes,
    setSymptoms,
    addCode,
    removeCode,
    clearCodes,
  } = useAppStore();

  const [codeInput, setCodeInput] = useState("");
  const [codeError, setCodeError] = useState("");

  const handleAddCode = useCallback(() => {
    const code = codeInput.trim().toUpperCase();
    if (!code) return;
    if (!CODE_REGEX.test(code)) {
      setCodeError("Format: P/B/C/U + 4 hex digits (e.g. P0300, P219A)");
      return;
    }
    if (activeCodes.includes(code)) {
      setCodeError("Code already added");
      return;
    }
    addCode(code);
    setCodeInput("");
    setCodeError("");
  }, [codeInput, activeCodes, addCode]);

  const handleKeyDown = useCallback(
    (e: React.KeyboardEvent) => {
      if (e.key === "Enter") {
        e.preventDefault();
        handleAddCode();
      }
    },
    [handleAddCode]
  );

  return (
    <SectionCard
      title={
        <span className="flex items-center gap-2">
          <span className="w-1 h-4 bg-primary rounded-full" />
          {codesOnly ? "Trouble Codes (OBD-II)" : "Symptoms & Trouble Codes"}
        </span>
      }
    >
      <div className="space-y-4">
      {!codesOnly && (
        <div className="space-y-2">
          <p className="text-xs font-medium text-overlay0 uppercase tracking-wide">
            Symptoms
          </p>
          <textarea
            value={symptoms}
            onChange={(e) => setSymptoms(e.target.value)}
            placeholder="Describe the issue... e.g. 'High-pitched whine that increases with RPM, noticed after oil change'"
            className="w-full h-24 bg-surface0 text-text border border-surface1 rounded-lg px-3 py-2 text-sm resize-none placeholder:text-overlay0 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
          />
        </div>
      )}

      {/* Trouble codes */}
      <div className="space-y-2">
        <p className="text-xs font-medium text-overlay0 uppercase tracking-wide">
          Trouble Codes (OBD-II)
        </p>

        <div className="flex gap-2">
          <input
            type="text"
            value={codeInput}
            onChange={(e) => {
              setCodeInput(e.target.value);
              setCodeError("");
            }}
            onKeyDown={handleKeyDown}
            placeholder="P0300"
            maxLength={5}
            className="flex-1 bg-surface0 text-text border border-surface1 rounded-md px-3 py-1.5 text-sm uppercase placeholder:text-overlay0 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
          />
          <Button size="sm" onClick={handleAddCode}>
            <Plus size={14} />
            Add
          </Button>
          {activeCodes.length > 0 && (
            <Button variant="ghost" size="sm" onClick={clearCodes}>
              <Trash2 size={14} />
            </Button>
          )}
        </div>

        {codeError && (
          <p className="text-xs text-red">{codeError}</p>
        )}

        {/* Active codes */}
        {activeCodes.length > 0 && (
          <div className="flex flex-wrap gap-1.5 pt-1">
            {activeCodes.map((code) => (
              <Chip
                key={code}
                label={code}
                color={codeColor(code)}
                onRemove={() => removeCode(code)}
              />
            ))}
          </div>
        )}
      </div>
      </div>
    </SectionCard>
  );
}
