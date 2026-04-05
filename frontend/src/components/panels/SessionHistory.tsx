import { useState } from "react";
import { useQuery, useMutation, useQueryClient } from "@tanstack/react-query";
import {
  Clock,
  Trash2,
  ChevronRight,
  Loader2,
  History,
} from "lucide-react";
import { Button } from "@/components/ui/Button";
import { EmptyState } from "@/components/ui/EmptyState";
import { ErrorMessage } from "@/components/ui/ErrorMessage";
import { listSessions, deleteSession, getSessionMatches } from "@/lib/api";
import { formatTimestamp, formatDuration } from "@/lib/utils";
import type { Session, SessionMatch } from "@/types";

export function SessionHistory() {
  const queryClient = useQueryClient();
  const [expandedId, setExpandedId] = useState<number | null>(null);

  const sessions = useQuery({
    queryKey: ["sessions"],
    queryFn: () => listSessions(50),
  });

  const matches = useQuery({
    queryKey: ["sessionMatches", expandedId],
    queryFn: () => getSessionMatches(expandedId!),
    enabled: expandedId !== null,
  });

  const deleteMut = useMutation({
    mutationFn: deleteSession,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ["sessions"] });
    },
  });

  if (sessions.isLoading) {
    return (
      <div className="flex-1 flex items-center justify-center p-8">
        <Loader2 size={28} className="animate-spin text-primary" />
      </div>
    );
  }

  if (sessions.isError) {
    return (
      <div className="flex-1 p-4 space-y-3">
        <ErrorMessage
          message={sessions.error instanceof Error ? sessions.error.message : "Failed to load sessions"}
          onRetry={() => sessions.refetch()}
        />
      </div>
    );
  }

  if (!sessions.data?.length) {
    return (
      <EmptyState
        icon={History}
        title="No sessions yet"
        description="Run a diagnosis and save the session to see it here."
        className="flex-1 p-8"
      />
    );
  }

  return (
    <div className="flex-1 overflow-y-auto p-4 space-y-2">
      <h3 className="text-sm font-semibold text-text flex items-center gap-2 mb-3">
        <History size={16} className="text-[var(--color-secondary)]" />
        Session History
        <span className="text-xs text-overlay0 font-normal">
          ({sessions.data.length})
        </span>
      </h3>

      {sessions.data.map((session: Session) => (
        <div
          key={session.id}
          className="bg-surface0 border-l-4 border-l-[var(--color-secondary)] border border-surface1 rounded-lg overflow-hidden"
        >
          {/* Session header */}
          <button
            onClick={() =>
              setExpandedId(expandedId === session.id ? null : session.id)
            }
            className="w-full flex items-center justify-between px-4 py-3 hover:bg-surface1/50 transition-colors cursor-pointer text-left"
          >
            <div className="flex items-center gap-3">
              <Clock size={14} className="text-overlay0 shrink-0" />
              <div>
                <p className="text-sm text-text">
                  {formatTimestamp(session.timestamp)}
                </p>
                <p className="text-xs text-overlay0">
                  {formatDuration(session.duration_seconds)}
                  {session.user_codes && ` · ${session.user_codes}`}
                </p>
              </div>
            </div>
            <div className="flex items-center gap-2">
              <Button
                variant="ghost"
                size="sm"
                onClick={(e) => {
                  e.stopPropagation();
                  if (confirm("Delete this session?")) {
                    deleteMut.mutate(session.id);
                  }
                }}
              >
                <Trash2 size={14} className="text-red" />
              </Button>
              <ChevronRight
                size={14}
                className={`text-overlay0 transition-transform ${
                  expandedId === session.id ? "rotate-90" : ""
                }`}
              />
            </div>
          </button>

          {/* Expanded matches */}
          {expandedId === session.id && (
            <div className="border-t border-surface1 px-4 py-3 space-y-2">
              {session.notes && (
                <p className="text-xs text-subtext">{session.notes}</p>
              )}
              {matches.isLoading ? (
                <Loader2
                  size={14}
                  className="animate-spin text-primary mx-auto"
                />
              ) : matches.data?.length ? (
                matches.data.map((m: SessionMatch, i: number) => (
                  <div
                    key={i}
                    className="flex items-center justify-between text-xs bg-mantle rounded-md px-3 py-2"
                  >
                    <div>
                      <span className="text-text font-medium">
                        {m.fault_name}
                      </span>
                      <span className="text-overlay0 ml-2">
                        {m.category}
                      </span>
                    </div>
                    <span
                      className="font-mono font-semibold"
                      style={{
                        color:
                          m.confidence_pct >= 80
                            ? "var(--color-green)"
                            : m.confidence_pct >= 60
                            ? "var(--color-yellow)"
                            : "var(--color-red)",
                      }}
                    >
                      {m.confidence_pct.toFixed(1)}%
                    </span>
                  </div>
                ))
              ) : (
                <p className="text-xs text-overlay0">No matches recorded.</p>
              )}
            </div>
          )}
        </div>
      ))}
    </div>
  );
}
