import { useEffect, useRef, useState } from "react";
import { Textarea } from "./ui/textarea";
import { Button } from "./ui/button";
import { Send, ChevronDown, Sparkles, CheckCircle2, Bot, User } from "lucide-react";

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
    <div
      className="surface flex h-full flex-col overflow-hidden rounded-2xl"
      data-testid="remix-chat"
    >
      {/* Chat header — gives the panel an identity and a status line. */}
      <div className="flex shrink-0 items-center gap-2.5 border-b border-[color:var(--hairline)] bg-[color:var(--indigo-4)] px-4 py-2.5 md:px-5">
        <span className="flex h-7 w-7 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-10)] text-[color:var(--brand-indigo)]">
          <Sparkles className="h-3.5 w-3.5" />
        </span>
        <div className="min-w-0 flex-1">
          <p className="font-display text-[13px] font-semibold leading-tight">Remix assistant</p>
          <p className="truncate text-xs text-muted-foreground">
            {sending ? "Thinking..." : readyToGenerate ? "Ready to write your prompt" : "Describe your brand and goal"}
          </p>
        </div>
        <span
          className={`h-1.5 w-1.5 shrink-0 rounded-full ${
            sending ? "animate-pulse bg-amber-400" : "bg-emerald-400"
          }`}
          aria-hidden="true"
        />
      </div>

      <div
        ref={scrollRef}
        onScroll={handleScroll}
        className="relative min-h-[320px] max-h-[calc(100vh-320px)] flex-1 space-y-4 overflow-y-auto px-4 py-4 md:px-5"
        data-testid="remix-chat-scroll-area"
      >
        {messages.length === 0 && !sending ? (
          <div className="flex h-full items-center justify-center">{emptyState}</div>
        ) : (
          messages.map((m, idx) => <ChatBubble key={idx} role={m.role} content={m.content} />)
        )}

        {sending && (
          <div className="flex items-end gap-2" data-testid="remix-chat-typing-indicator">
            <Avatar role="assistant" />
            <div className="flex items-center gap-1.5 rounded-2xl rounded-bl-md border border-[color:var(--hairline)] bg-secondary/50 px-4 py-3.5">
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
            className="sticky bottom-1 left-1/2 flex h-8 w-8 -translate-x-1/2 items-center justify-center rounded-full border border-[color:var(--hairline-strong)] bg-card shadow-[var(--shadow-lg)] backdrop-blur-sm transition-transform hover:-translate-y-0.5 active:translate-y-0"
          >
            <ChevronDown className="h-4 w-4 text-muted-foreground" />
          </button>
        )}
      </div>

      {readyToGenerate && (
        <div
          className="flex items-center gap-2 border-t border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] px-4 py-2.5 text-xs font-medium text-[color:var(--brand-indigo)] md:px-5"
          data-testid="remix-chat-ready-banner"
        >
          <CheckCircle2 className="h-3.5 w-3.5 shrink-0" />
          <span>We have enough to generate your video prompt below — keep chatting anytime to refine it.</span>
        </div>
      )}

      <div className="shrink-0 space-y-2 border-t border-[color:var(--hairline)] bg-[hsl(228_14%_8%_/_0.5)] p-3 md:p-4">
        <Textarea
          value={draft}
          onChange={(e) => setDraft(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder={placeholder}
          disabled={sending}
          className="max-h-40 min-h-[64px] resize-none"
          data-testid="remix-chat-input"
        />
        <div className="flex items-center justify-between gap-3">
          <span className="text-xs text-muted-foreground">
            <kbd className="rounded border border-[color:var(--hairline)] bg-secondary/60 px-1 py-px font-mono text-xs">
              Enter
            </kbd>{" "}
            to send &middot;{" "}
            <kbd className="rounded border border-[color:var(--hairline)] bg-secondary/60 px-1 py-px font-mono text-xs">
              Shift+Enter
            </kbd>{" "}
            for a new line
          </span>
          <Button
            type="button"
            onClick={handleSend}
            disabled={sending || !draft.trim()}
            size="sm"
            variant="accent"
            className="gap-1.5"
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

function Avatar({ role }) {
  const isUser = role === "user";
  return (
    <span
      aria-hidden="true"
      className={`mb-0.5 flex h-6 w-6 shrink-0 items-center justify-center rounded-lg border text-xs ${
        isUser
          ? "border-[color:var(--indigo-25)] bg-[color:var(--brand-indigo)] text-white"
          : "border-[color:var(--hairline)] bg-secondary/60 text-muted-foreground"
      }`}
    >
      {isUser ? <User className="h-3 w-3" /> : <Bot className="h-3 w-3" />}
    </span>
  );
}

function ChatBubble({ role, content }) {
  const isUser = role === "user";
  return (
    <div
      className={`flex items-end gap-2 ${isUser ? "flex-row-reverse justify-start" : "justify-start"}`}
      data-testid={isUser ? "remix-chat-user-message" : "remix-chat-assistant-message"}
    >
      <Avatar role={role} />
      <div
        className={`max-w-[85%] whitespace-pre-wrap px-4 py-3 text-sm leading-relaxed ${
          isUser
            ? "rounded-2xl rounded-br-md bg-gradient-to-br from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] text-white shadow-[var(--shadow-sm)]"
            : "rounded-2xl rounded-bl-md border border-[color:var(--hairline)] bg-secondary/50 text-foreground"
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
