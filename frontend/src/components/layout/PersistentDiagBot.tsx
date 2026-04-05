import { useState } from "react";
import { MessageSquare, X } from "lucide-react";
import { usePersona } from "@/contexts/PersonaContext";
import { ChatPanel } from "@/components/panels/ChatPanel";
import { cn } from "@/lib/utils";

/**
 * Floating DiagBot entry point shown on every page (after persona is selected).
 * Opens a slide-out panel with ChatPanel so the user can talk to their diagnostic buddy anywhere.
 */
export function PersistentDiagBot() {
  const { hasSelectedPersona } = usePersona();
  const [open, setOpen] = useState(false);

  if (!hasSelectedPersona) return null;

  return (
    <>
      {/* FAB — hidden when panel is open */}
      {!open && (
      <button
        type="button"
        onClick={() => setOpen(true)}
        className={cn(
          "fixed bottom-6 right-6 z-40 flex items-center justify-center",
          "w-14 h-14 rounded-full shadow-lg",
          "bg-[var(--color-primary)] text-white",
          "hover:opacity-90 focus:outline-none focus:ring-2 focus:ring-[var(--color-primary)] focus:ring-offset-2 focus:ring-offset-[var(--color-base)]",
          "transition-transform hover:scale-105"
        )}
        aria-label="Open DiagBot"
      >
        <MessageSquare size={24} />
      </button>
      )}

      {/* Backdrop when open */}
      {open && (
        <button
          type="button"
          aria-label="Close DiagBot"
          className="fixed inset-0 z-40 bg-black/30 transition-opacity"
          onClick={() => setOpen(false)}
        />
      )}

      {/* Slide-out panel */}
      <div
        className={cn(
          "fixed top-0 right-0 bottom-0 z-50 w-full max-w-md",
          "bg-[var(--color-base)] shadow-xl",
          "flex flex-col",
          "transition-transform duration-200 ease-out",
          open ? "translate-x-0" : "translate-x-full"
        )}
      >
        <div className="flex items-center justify-between px-4 py-3 border-b border-[var(--color-surface1)] shrink-0">
          <span className="text-sm font-semibold text-[var(--color-text)]">
            DiagBot — your diagnostic buddy
          </span>
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="p-2 rounded-lg text-[var(--color-subtext)] hover:bg-[var(--color-surface1)] hover:text-[var(--color-text)] transition-colors"
            aria-label="Close"
          >
            <X size={18} />
          </button>
        </div>
        <div className="flex-1 min-h-0 flex flex-col">
          <ChatPanel />
        </div>
      </div>
    </>
  );
}
