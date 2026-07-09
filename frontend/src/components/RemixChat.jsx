import { useEffect, useRef, useState } from "react";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";
import { Send, ChevronDown, Sparkles, CheckCircle2 } from "lucide-react";

const SCROLL_BOTTOM_THRESHOLD = 80;

/**
 * Conversational "remix this content for my brand/product" chat.
 * User turns render as solid brand-colored bubbles (right-aligned), assistant
 * turns render as light gray cards (left-aligned) - mirroring a familiar
 * chat-assistant layout: ask your goal, get a clarifying question back, and
 * go back and forth until the app has enough context to generate a prompt.
 */
export function RemixChat({
  messages = [],
  onSend,
  sending = false,
  readyToGenerate = false,
  placeholder = "Remix this content for your brand or product...",
  emptyState = null,
}) {
  const [draft, setDraft] = useState("");
  const [showScrollButton, setShowScrollButton] = useState(false);
  const scrollRef = useRef(null);
  const bottomRef = useRef(null);

  const scrollToBottom = (behavior = "smooth") => {
    bottomRef.current?.scrollIntoView({ behavior, block: "end" });
  };

  useEffect(() => {
    // Auto-scroll on new messages unless the user has scrolled up to read history.
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    if (distanceFromBottom < SCROLL_BOTTOM_THRESHOLD + 200) {
      scrollToBottom(messages.length <= 1 ? "auto" : "smooth");
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [messages.length, sending]);

  const handleScroll = () => {
    const el = scrollRef.current;
    if (!el) return;
    const distanceFromBottom = el.scrollHeight - el.scrollTop - el.clientHeight;
    setShowScrollButton(distanceFromBottom > SCROLL_BOTTOM_THRESHOLD);
  };

  const handleSend = () => {
    const text = draft.trim();
    if (!text || sending) return;
    setDraft("");
    onSend(text);
  };

  const handleKeyDown = (e) => {
    if (e.key === "Enter" && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <div className="flex flex-col h-full rounded-2xl border border-border bg-[color:var(--card)] shadow-[var(--shadow-soft)] overflow-hidden" data-testid="remix-chat">
      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="relative flex-1 overflow-y-auto px-4 md:px-5 py-4 space-y-4 min-h-[320px] max-h-[calc(100vh-320px)]"
        data-testid="remix-chat-scroll-area"
      >
        {messages.length === 0 && !sending ? (
          <div className="h-full flex items-center justify-center">{emptyState}</div>
        ) : (
          messages.map((m, idx) => (
            <ChatBubble key={idx} role={m.role} content={m.content} />
          ))
        )}

        {sending && (
          <div className="flex items-center gap-2 text-sm text-muted-foreground" data-testid="remix-chat-typing-indicator">
            <div className="rounded-2xl bg-muted px-4 py-3 flex items-center gap-1.5">
              <span className="sr-only">Thinking...</span>
              <TypingDot delay="0ms" />
              <TypingDot delay="150ms" />
              <TypingDot delay="300ms" />
            </div>
          </div>
        )}

        <div ref={bottomRef} />

        {showScrollButton && (
          <button
            type="button"
            onClick={() => scrollToBottom()}
            aria-label="Scroll to latest message"
            data-testid="remix-chat-scroll-bottom-button"
            className="sticky bottom-1 left-1/2 -translate-x-1/2 flex h-8 w-8 items-center justify-center rounded-full bg-card border border-border shadow-[var(--shadow-tight)] hover:-translate-y-0.5 active:translate-y-0 transition-transform"
          >
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {readyToGenerate && (
        <div className="px-4 md:px-5 py-2 border-t border-border bg-[color:rgba(13,148,136,0.06)] flex items-center gap-1.5 text-xs font-medium text-[color:var(--brand-teal-dark)]" data-testid="remix-chat-ready-banner">
          <CheckCircle2 className="h-3.5 w-3.5" /> We have enough to generate your video prompt below — keep chatting anytime to refine it.
        </div>
      )}

      <div className="border-t border-border p-3 md:p-4 space-y-2 bg-card/40">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={sending}
          className="min-h-[64px] max-h-40 resize-none bg-secondary"
          data-testid="remix-chat-input"
        />
        <div className="flex items-center justify-between">
          <span className="text-[11px] text-muted-foreground">Enter to send &middot; Shift+Enter for a new line</span>
          <Button
            type="button"
            onClick={handleSend}
            disabled={sending || !draft.trim()}
            size="sm"
            className="gap-1.5 bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
            data-testid="remix-chat-send-button"
          >
            {sending ? <Sparkles className="h-3.5 w-3.5 animate-pulse" /> : <Send className="h-3.5 w-3.5" />}
            {sending ? "Thinking..." : "Send"}
          </Button>
        </div>
      </div>
    </div>
  );
}

function ChatBubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div className={`flex ${isUser ? "justify-end" : "justify-start"}`} data-testid={isUser ? "remix-chat-user-message" : "remix-chat-assistant-message"}>
      <div
        className={`max-w-[85%] whitespace-pre-wrap text-sm leading-relaxed rounded-2xl px-4 py-3 ${
          isUser
            ? "bg-[color:var(--brand-teal)] text-white rounded-br-sm"
            : "bg-muted text-foreground rounded-bl-sm"
        }`}
      >
        {content}
      </div>
    </div>
  );
}

function TypingDot({ delay }) {
  return (
    <span
      className="h-1.5 w-1.5 rounded-full bg-muted-foreground/60 animate-bounce"
      style={{ animationDelay: delay }}
    />
  );
}

export default RemixChat;
