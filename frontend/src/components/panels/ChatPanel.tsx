import { useState, useRef, useEffect, useCallback } from "react";
import { Send, Bot, User, Sparkles, Tag } from "lucide-react";
import { Button } from "@/components/ui/Button";
import { useAppStore } from "@/stores/appStore";
import { postChat } from "@/lib/api";
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
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const inputRef = useRef<HTMLTextAreaElement>(null);

  /* Scroll to bottom on new messages */
  useEffect(() => {
    messagesEndRef.current?.scrollIntoView({ behavior: "smooth" });
  }, [chatMessages, isTyping]);

  const sendMessage = useCallback(
    async (text: string) => {
      if (!text.trim()) return;

      addChatMessage("user", text.trim());
      setInput("");
      setIsTyping(true);

      try {
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

        const context = {
          symptoms: symptoms || undefined,
          vehicle: vehicleLabel || undefined,
          trouble_codes: activeCodes.length ? activeCodes : undefined,
          diagnosis_summary: diagnosis
            ? `${diagnosis.top_class_display} (${diagnosis.confidence} confidence)`
            : undefined,
        };

        const res = await postChat(messages, context);
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
          <Bot size={18} className="text-primary" />
          <div>
            <span className="text-sm font-semibold text-text">DiagBot</span>
            <span className="text-[10px] text-overlay0 ml-2">
              Local · No credits
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
                ? "border-primary text-primary bg-primary/10"
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
              Ask DiagBot about your vehicle's symptoms
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

        {/* Typing indicator */}
        {isTyping && (
          <div className="flex justify-start">
            <div className="bg-surface0 border border-surface1 rounded-2xl rounded-bl-sm px-4 py-3">
              <div className="flex gap-1">
                <span className="w-2 h-2 bg-overlay0 rounded-full animate-bounce [animation-delay:0ms]" />
                <span className="w-2 h-2 bg-overlay0 rounded-full animate-bounce [animation-delay:150ms]" />
                <span className="w-2 h-2 bg-overlay0 rounded-full animate-bounce [animation-delay:300ms]" />
              </div>
            </div>
          </div>
        )}

        <div ref={messagesEndRef} />
      </div>

      {/* Quick actions */}
      {chatMessages.length === 0 && (
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

      {/* Input */}
      <div className="flex items-end gap-2 px-4 py-3 border-t border-surface1">
        <textarea
          ref={inputRef}
          value={input}
          onChange={(e) => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask DiagBot..."
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
