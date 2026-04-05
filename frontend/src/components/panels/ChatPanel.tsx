import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Sparkles, Tag, ImagePlus, X } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/stores/appStore";
import { postChat, postChatStream, uploadDiagnosisPhoto } from "@/lib/api";
import { getApiBase } from "@/lib/env";
import { cn } from "@/lib/utils";

const QUICK_ACTIONS = [
  "What could cause this noise?",
  "How urgent is this repair?",
  "What parts might I need?",
  "Can I drive safely with this issue?",
  "What's an estimated repair cost?",
];

const MAX_HISTORY = 50;

export function ChatPanel() {
  const {
    chatMessages,
    chatMode,
    symptoms,
    activeCodes,
    vehicleSelection,
    diagnosis,
    addChatMessage,
    setChatMode,
  } = useAppStore();

  const [input, setInput] = useState("");
  const [isTyping, setIsTyping] = useState(false);
  const [streamingContent, setStreamingContent] = useState("");
  const [lastSources, setLastSources] = useState<string[]>([]);
  const [pendingPhotos, setPendingPhotos] = useState<string[]>([]);
  const [photoUploading, setPhotoUploading] = useState(false);
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);
  const hasGreetedRef = useRef(false);
  const streamingAccumulatorRef = useRef("");

  /* Auto-greet on first open (context-aware, once per session) */
  useEffect(() => {
    if (hasGreetedRef.current || chatMessages.length > 0) return;
    hasGreetedRef.current = true;

    const vehicleLabel = [
      vehicleSelection.year,
      vehicleSelection.makeName,
      vehicleSelection.modelName,
      vehicleSelection.trim,
    ]
      .filter(Boolean)
      .join(" ");
    const hasVehicle = Boolean(vehicleLabel);
    const hasSymptoms = Boolean(symptoms?.trim());
    const hasCodes = activeCodes.length > 0;

    let greeting: string;
    if (hasVehicle && (hasSymptoms || hasCodes)) {
      const context = hasSymptoms ? (symptoms || "").trim() : activeCodes.join(", ");
      greeting = `Welcome to DiagBot. I see you're working on a ${vehicleLabel} with ${context}. Let's figure this out together.`;
    } else if (hasVehicle) {
      greeting = `Welcome to DiagBot. I see you're working on a ${vehicleLabel}. What's going on with it?`;
    } else {
      greeting =
        "Welcome to DiagBot. I'm here to help diagnose your vehicle -- describe what you're experiencing, or tap a question below to get started.";
    }

    addChatMessage("assistant", greeting);
  }, [addChatMessage, vehicleSelection, symptoms, activeCodes]);

  /* Scroll to bottom on new messages */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isTyping, streamingContent]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      addChatMessage("user", text.trim());
      setInput("");
      setPendingPhotos([]);
      setIsTyping(true);
      setStreamingContent("");
      streamingAccumulatorRef.current = "";

      const messages = chatMessages
        .concat([{ role: "user" as const, content: text.trim(), id: "", timestamp: new Date() }])
        .slice(-MAX_HISTORY)
        .map((m) => ({ role: m.role, content: m.content }));

      const vehicleLabel = [
        vehicleSelection.year,
        vehicleSelection.makeName,
        vehicleSelection.modelName,
        vehicleSelection.trim,
      ]
        .filter(Boolean)
        .join(" ");

      const baseUrl = typeof window !== "undefined" ? window.location.origin : "";
      const context = {
        symptoms: symptoms || undefined,
        vehicle: vehicleLabel || undefined,
        trouble_codes: activeCodes.length ? activeCodes : undefined,
        diagnosis_summary: diagnosis
          ? `${diagnosis.top_class_display} (${diagnosis.confidence} confidence)`
          : undefined,
        photo_urls: pendingPhotos.length ? pendingPhotos.map((u) => (u.startsWith("http") ? u : baseUrl + u)) : undefined,
      };

      const useStream = await postChatStream(messages, context, {
        onToken: (token) => {
          streamingAccumulatorRef.current += token;
          setStreamingContent(streamingAccumulatorRef.current);
        },
        onDone: (sources) => {
          setLastSources(sources);
          const finalContent = streamingAccumulatorRef.current || "No response.";
          addChatMessage("assistant", finalContent);
          setStreamingContent("");
          streamingAccumulatorRef.current = "";
          setIsTyping(false);
        },
        onError: (err) => {
          addChatMessage(
            "assistant",
            `Couldn't reach DiagBot: ${err}. If this is your first time, the chat model may still be downloading. Try again in a moment.`
          );
          setStreamingContent("");
          setIsTyping(false);
        },
      });

      if (!useStream) {
        try {
          const res = await postChat(messages, context);
          setLastSources(res.sources ?? []);
          addChatMessage("assistant", res.content || "No response.");
        } catch (e) {
          const msg = e instanceof Error ? e.message : "Request failed";
          addChatMessage(
            "assistant",
          `Couldn’t reach DiagBot: ${msg}. If this is your first time, the chat model may still be downloading. Try again in a moment.`
          );
        } finally {
          setIsTyping(false);
        }
      }
    },
    [
      addChatMessage,
      chatMessages,
      symptoms,
      activeCodes,
      vehicleSelection,
      diagnosis,
    ]
  );

  const handleKeyDown = (e: React.KeyboardEvent) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      sendMessage(input);
    }
  };

  return (
    <div className="flex-1 flex flex-col min-h-0">
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-surface1">
        <div className="flex items-center gap-2">
          <Bot size={18} className="text-[var(--color-secondary)]" />
          <div>
            <span className="text-sm font-semibold text-text">DiagBot</span>
            <span className="text-[10px] text-overlay0 ml-2">
              Your diagnostic buddy & pro mentor
            </span>
          </div>
        </div>
        <div className="flex items-center gap-2">
          <button
            onClick={() =>
              setChatMode(chatMode === "keyword" ? "agent" : "keyword")
            }
            className={cn(
              "text-xs px-2.5 py-1 rounded-full border transition-colors cursor-pointer",
              chatMode === "agent"
                ? "border-[var(--color-secondary)] text-[var(--color-secondary)] bg-[var(--color-secondary)]/10"
                : "border-surface1 text-subtext"
            )}
          >
            {chatMode === "agent" ? (
              <span className="flex items-center gap-1">
                <Sparkles size={10} />
                Full Agent
              </span>
            ) : (
              <span className="flex items-center gap-1">
                <Tag size={10} />
                Keyword Only
              </span>
            )}
          </button>
          <span
            className={cn(
              "w-2 h-2 rounded-full",
              chatMode === "agent" ? "bg-green" : "bg-yellow"
            )}
          />
        </div>
      </div>

      {/* Messages */}
      <div className="flex-1 overflow-y-auto p-4 space-y-3 bg-mantle">
        {chatMessages.length === 0 && (
          <div className="text-center py-8">
            <Bot size={32} className="text-surface2 mx-auto mb-2" />
            <p className="text-sm text-subtext">
              Ask me anything—we’ll figure it out together
            </p>
          </div>
        )}

        {chatMessages.map((msg) => (
          <div
            key={msg.id}
            className={cn(
              "flex",
              msg.role === "user" ? "justify-end" : "justify-start"
            )}
          >
            <div
              className={cn(
                "max-w-[80%] px-3.5 py-2.5 text-sm leading-relaxed",
                msg.role === "user"
                  ? "bg-surface1 text-text rounded-2xl rounded-br-sm"
                  : msg.role === "system"
                  ? "bg-transparent text-overlay0 text-xs italic"
                  : "bg-surface0 text-text rounded-2xl rounded-bl-sm border border-surface1"
              )}
            >
              <div className="flex items-center gap-1.5 mb-1">
                {msg.role === "user" ? (
                  <User size={12} className="text-primary" />
                ) : (
                  <Bot size={12} className="text-secondary" />
                )}
                <span className="text-[10px] text-overlay0">
                  {msg.role === "user" ? "You" : "DiagBot"}
                  {" · "}
                  {msg.timestamp.toLocaleTimeString([], {
                    hour: "2-digit",
                    minute: "2-digit",
                  })}
                </span>
              </div>
              {msg.content}
            </div>
          </div>
        ))}

        {/* ASE sources from last response */}
        {lastSources.length > 0 && !isTyping && (
          <p className="text-[10px] text-overlay0 px-4 pt-1">
            Based on: {lastSources.join("; ")}
          </p>
        )}

        {/* Streaming content or typing indicator */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-surface0 border border-surface1 rounded-2xl rounded-bl-sm px-4 py-3 max-w-[80%]">
              {streamingContent ? (
                <div className="flex items-center gap-1.5 mb-1">
                  <Bot size={12} className="text-secondary" />
                  <span className="text-[10px] text-overlay0">DiagBot</span>
                </div>
              ) : null}
              {streamingContent ? (
                <p className="text-sm leading-relaxed">{streamingContent}</p>
              ) : (
                <div className="flex gap-1">
                  <span className="w-2 h-2 bg-overlay0 rounded-full animate-bounce [animation-delay:0ms]" />
                  <span className="w-2 h-2 bg-overlay0 rounded-full animate-bounce [animation-delay:150ms]" />
                  <span className="w-2 h-2 bg-overlay0 rounded-full animate-bounce [animation-delay:300ms]" />
                </div>
              )}
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions (show until user sends first message) */}
      {!chatMessages.some((m) => m.role === "user") && (
        <div className="flex flex-wrap gap-1.5 px-4 py-2 border-t border-surface1">
          {QUICK_ACTIONS.map((action) => (
            <button
              key={action}
              onClick={() => sendMessage(action)}
              className="text-xs px-2.5 py-1.5 rounded-full border border-surface1 text-subtext hover:border-primary hover:text-primary transition-colors cursor-pointer"
            >
              {action}
            </button>
          ))}
        </div>
      )}

      {/* Pending photo previews */}
      {pendingPhotos.length > 0 && (
        <div className="flex flex-wrap gap-2 px-4 py-2 border-t border-surface1">
          {pendingPhotos.map((url) => (
            <div key={url} className="relative">
              <img
                src={url.startsWith("http") ? url : getApiBase() + url}
                alt="Attached"
                className="w-14 h-14 object-cover rounded-lg border border-surface1"
              />
              <button
                type="button"
                onClick={() => setPendingPhotos((p) => p.filter((u) => u !== url))}
                className="absolute -top-1 -right-1 w-5 h-5 rounded-full bg-red text-white flex items-center justify-center"
              >
                <X size={12} />
              </button>
            </div>
          ))}
        </div>
      )}

      {/* Input */}
      <div className="flex items-end gap-2 px-4 py-3 border-t border-surface1">
        <input
          type="file"
          accept="image/jpeg,image/png,image/webp"
          capture="environment"
          className="hidden"
          id="chat-photo-input"
          onChange={async (e) => {
            const file = e.target.files?.[0];
            if (!file) return;
            setPhotoUploading(true);
            try {
              const { url } = await uploadDiagnosisPhoto(file);
              setPendingPhotos((p) => [...p, url]);
            } catch {
              /* ignore */
            } finally {
              setPhotoUploading(false);
              e.target.value = "";
            }
          }}
        />
        <label
          htmlFor="chat-photo-input"
          className={cn(
            "p-2 rounded-lg border cursor-pointer transition-colors",
            photoUploading ? "opacity-50 cursor-not-allowed" : "border-surface1 hover:border-primary"
          )}
        >
          <ImagePlus size={18} className="text-subtext" />
        </label>
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask your diagnostic buddy..."
          rows={1}
          className="flex-1 bg-surface0 text-text border border-surface1 rounded-lg px-3 py-2 text-sm resize-none max-h-20 placeholder:text-overlay0 focus:outline-none focus:ring-2 focus:ring-primary/40 focus:border-primary transition-colors"
        />
        <Button
          variant="primary"
          size="sm"
          onClick={() => sendMessage(input)}
          disabled={!input.trim() || isTyping}
        >
          <Send size={14} />
        </Button>
      </div>
    </div>
  );
}
