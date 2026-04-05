import { useRef, useCallback, useEffect, useState } from "react";
import { Mic, Square, Upload, Loader2, AlertTriangle, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { Select } from "@/components/ui/Select";
import { useAppStore } from "@/stores/appStore";
import { formatDuration } from "@/lib/utils";
import type { RecordDuration, ViewMode } from "@/types";

const DURATION_OPTIONS: { value: RecordDuration; label: string }[] = [
  { value: "manual", label: "Manual" },
  { value: "3", label: "3 sec" },
  { value: "5", label: "5 sec" },
  { value: "10", label: "10 sec" },
  { value: "15", label: "15 sec" },
  { value: "30", label: "30 sec" },
  { value: "60", label: "60 sec" },
];

const VIEW_OPTIONS: { value: ViewMode; label: string }[] = [
  { value: "spectrogram", label: "Spectrogram" },
  { value: "mel", label: "Mel Spectrogram" },
  { value: "waveform", label: "Waveform" },
];

export function RecordPanel() {
  const {
    isRecording,
    recordDuration,
    viewMode,
    audioBlob,
    audioFileName,
    setIsRecording,
    setRecordDuration,
    setViewMode,
    setAudioBlob,
  } = useAppStore();

  const mediaRecorderRef = useRef<MediaRecorder | null>(null);
  const chunksRef = useRef<Blob[]>([]);
  const timerRef = useRef<ReturnType<typeof setInterval> | null>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const startTimeRef = useRef<number>(0);
  const [elapsed, setElapsed] = useState(0);
  const [statusText, setStatusText] = useState("No audio loaded");
  const [micError, setMicError] = useState<string | null>(null);

  /* Stop recording */
  const stopRecording = useCallback(() => {
    if (mediaRecorderRef.current?.state === "recording") {
      mediaRecorderRef.current.stop();
    }
    if (timerRef.current) {
      clearInterval(timerRef.current);
      timerRef.current = null;
    }
    setIsRecording(false);
  }, [setIsRecording]);

  /* Start recording */
  const startRecording = useCallback(async () => {
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ audio: true });
      const mr = new MediaRecorder(stream, { mimeType: "audio/webm" });
      chunksRef.current = [];

      mr.ondataavailable = (e) => {
        if (e.data.size > 0) chunksRef.current.push(e.data);
      };

      mr.onstop = () => {
        const blob = new Blob(chunksRef.current, { type: "audio/webm" });
        setAudioBlob(blob, `recording_${Date.now()}.webm`);
        // Use ref for accurate final duration — the closure over `elapsed` state
        // would always capture the value at recording start (0).
        const finalSecs = (Date.now() - startTimeRef.current) / 1000;
        setStatusText(`Recorded: ${formatDuration(finalSecs)}`);
        stream.getTracks().forEach((t) => t.stop());
      };

      mr.start(200);
      mediaRecorderRef.current = mr;
      setIsRecording(true);
      setElapsed(0);

      startTimeRef.current = Date.now();
      timerRef.current = setInterval(() => {
        const secs = (Date.now() - startTimeRef.current) / 1000;
        setElapsed(secs);
        setStatusText(`Recording: ${formatDuration(secs)}`);

        if (recordDuration !== "manual" && secs >= Number(recordDuration)) {
          stopRecording();
        }
      }, 100);
    } catch {
      setMicError("Microphone access denied. Check browser permissions.");
      setStatusText("Microphone access denied");
    }
  }, [recordDuration, setAudioBlob, setIsRecording, stopRecording]);

  /* Import file */
  const handleImport = useCallback(() => {
    fileInputRef.current?.click();
  }, []);

  const handleFileChange = useCallback(
    (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (file) {
        setAudioBlob(file, file.name);
        setStatusText(`Loaded: ${file.name} (${(file.size / 1024).toFixed(0)} KB)`);
      }
    },
    [setAudioBlob]
  );

  /* Cleanup on unmount */
  useEffect(() => {
    return () => {
      if (timerRef.current) clearInterval(timerRef.current);
      if (mediaRecorderRef.current?.state === "recording") {
        mediaRecorderRef.current.stop();
      }
    };
  }, []);

  /* Update status when audioBlob changes externally */
  useEffect(() => {
    if (audioBlob && audioFileName) {
      setStatusText(
        `Loaded: ${audioFileName} (${(audioBlob.size / 1024).toFixed(0)} KB)`
      );
    }
  }, [audioBlob, audioFileName]);

  return (
    <div className="flex flex-col gap-0">
      {micError && (
        <div className="flex items-center gap-2 px-4 py-2 bg-red/10 border-b border-red/20 text-red text-sm">
          <AlertTriangle size={16} className="shrink-0" />
          <span className="flex-1">{micError}</span>
          <button
            type="button"
            onClick={() => setMicError(null)}
            className="p-1 rounded hover:bg-red/20"
            aria-label="Dismiss"
          >
            <X size={14} />
          </button>
        </div>
      )}
      <div className="flex flex-wrap items-center gap-3 px-3 sm:px-4 py-3 bg-mantle border-b border-surface1">
        {/* Record / Stop */}
        <div className="flex items-center gap-2">
        {isRecording ? (
          <Button variant="red" size="sm" onClick={stopRecording}>
            <Square size={14} />
            Stop
          </Button>
        ) : (
          <Button variant="green" size="sm" onClick={startRecording}>
            <Mic size={14} />
            Record
          </Button>
        )}

        <Button variant="default" size="sm" onClick={handleImport}>
          <Upload size={14} />
          Import
        </Button>
        <input
          ref={fileInputRef}
          type="file"
          accept="audio/*,.wav,.mp3,.mp4,.m4a,.flac,.ogg,.webm"
          className="hidden"
          onChange={handleFileChange}
        />
      </div>

      {/* Separator */}
      <div className="w-px h-6 bg-surface1" />

      {/* Duration */}
      <Select
        label="Duration"
        options={DURATION_OPTIONS}
        value={recordDuration}
        onChange={(e) =>
          setRecordDuration(e.target.value as RecordDuration)
        }
      />

      {/* View mode */}
      <Select
        label="View"
        options={VIEW_OPTIONS}
        value={viewMode}
        onChange={(e) => setViewMode(e.target.value as ViewMode)}
      />

      {/* Separator */}
      <div className="w-px h-6 bg-surface1" />

      {/* Status */}
      <span className="text-xs text-subtext flex items-center gap-1.5">
          {isRecording && (
            <Loader2 size={12} className="animate-spin text-red" />
          )}
        {statusText}
      </span>
      </div>
    </div>
  );
}
