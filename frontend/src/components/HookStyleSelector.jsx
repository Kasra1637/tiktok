import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles, PenLine, AlertTriangle, Info } from "lucide-react";
import { Chip } from "./Chip";

/**
 * Hook Style Selector — lets creators optionally choose a hook *energy*
 * (category) and/or write a custom prompt to guide video generation.
 *
 * Collapsed by default so casual users get the existing flow untouched,
 * while power users can expand it to fine-tune their hook's intent.
 *
 * Safety features:
 * - Hard character limit (200 chars) enforced on input
 * - Visual feedback: green/amber/red counter as user approaches limit
 * - Guidelines shown to set expectations about allowed content
 * - Frontend filters obvious prompt-injection patterns before sending
 *
 * Props:
 *   hookCategory    — currently selected category key (string or "")
 *   onCategoryChange — (key: string) => void
 *   hookCustomPrompt — freeform prompt text (string)
 *   onCustomPromptChange — (text: string) => void
 *   disabled        — disable interactions during generation
 */

const HOOK_STYLE_CATEGORIES = [
  {
    key: "curiosity-gap",
    label: "Curiosity Gap",
    description: "Irresistible 'wait, what?' — show something partially, make them NEED to stay",
  },
  {
    key: "pattern-interrupt",
    label: "Pattern Interrupt",
    description: "Break passive scrolling — unexpected movement or visual that jolts the brain",
  },
  {
    key: "reveal",
    label: "Reveal / Transformation",
    description: "Dramatic before/after snap — start hidden or plain, instantly show the payoff",
  },
  {
    key: "reaction",
    label: "Reaction",
    description: "Exaggerated emotional response — shocked face, jaw drop, 'what did I just see?'",
  },
  {
    key: "authority",
    label: "Authority",
    description: "Confident expert energy — commanding eye contact, 'listen to me right now'",
  },
  {
    key: "confrontation",
    label: "Confrontation",
    description: "Challenge the viewer — 'you're doing it wrong' energy, pointed finger, tough love",
  },
];

// ─── Safety Constants ────────────────────────────────────────────────────────
// Hard max enforced at input level. Backend also enforces the same limit.
const CUSTOM_PROMPT_MAX = 200;
// Warning threshold — counter turns amber
const CUSTOM_PROMPT_WARN = 160;

/**
 * Sanitize user input on the client side before it's stored in state.
 * This is a first line of defense — the backend does its own sanitization too.
 *
 * - Collapses multiple whitespace/newlines into single spaces
 * - Strips control characters (non-printable)
 * - Removes obvious prompt-injection delimiters that serve no legitimate
 *   video-description purpose (triple backticks, XML-like system tags, etc.)
 */
function sanitizeInput(raw) {
  let text = raw;
  // Strip control characters except basic whitespace
  text = text.replace(/[\x00-\x08\x0B\x0C\x0E-\x1F\x7F]/g, "");
  // Collapse newlines and excessive whitespace into single spaces
  text = text.replace(/[\r\n]+/g, " ").replace(/\s{2,}/g, " ");
  // Remove obvious injection patterns (these have no legitimate use in a
  // video direction prompt):
  // - Triple backticks (code fences)
  text = text.replace(/```/g, "");
  // - XML/HTML-style system or instruction tags
  text = text.replace(/<\/?(?:system|instruction|prompt|role|assistant|user|context)[^>]*>/gi, "");
  // Enforce hard character limit
  return text.slice(0, CUSTOM_PROMPT_MAX);
}

export default function HookStyleSelector({
  hookCategory = "",
  onCategoryChange,
  hookCustomPrompt = "",
  onCustomPromptChange,
  disabled = false,
}) {
  const [expanded, setExpanded] = useState(false);

  const hasSelection = !!(hookCategory || hookCustomPrompt.trim());
  const charCount = hookCustomPrompt.length;
  const isAtLimit = charCount >= CUSTOM_PROMPT_MAX;
  const isNearLimit = charCount >= CUSTOM_PROMPT_WARN;

  // Counter color: green (ok) → amber (approaching) → red (at limit)
  const counterColor = isAtLimit
    ? "text-destructive"
    : isNearLimit
      ? "text-amber-500"
      : "text-muted-foreground";

  const handlePromptChange = (e) => {
    const sanitized = sanitizeInput(e.target.value);
    onCustomPromptChange(sanitized);
  };

  return (
    <div className="space-y-2" data-testid="hook-style-selector">
      {/* Toggle header */}
      <button
        type="button"
        onClick={() => setExpanded((v) => !v)}
        disabled={disabled}
        className={`flex w-full items-center justify-between gap-2 rounded-xl border px-3.5 py-2.5 transition-colors duration-200 ${
          hasSelection
            ? "border-[color:var(--brand-teal)]/40 bg-[color:var(--indigo-8)]"
            : "border-[color:var(--hairline)] bg-secondary/30 hover:border-[color:var(--indigo-35)]"
        } disabled:cursor-not-allowed disabled:opacity-50`}
        aria-expanded={expanded}
        data-testid="hook-style-toggle"
      >
        <span className="flex items-center gap-2.5 text-left">
          <Sparkles className={`h-4 w-4 ${hasSelection ? "text-[color:var(--brand-teal)]" : "text-muted-foreground"}`} />
          <span className="text-[11px] font-semibold">
            {hasSelection
              ? `Hook style: ${HOOK_STYLE_CATEGORIES.find((c) => c.key === hookCategory)?.label || "Custom"}`
              : "Customize hook style (optional)"}
          </span>
        </span>
        {expanded ? (
          <ChevronUp className="h-3.5 w-3.5 text-muted-foreground" />
        ) : (
          <ChevronDown className="h-3.5 w-3.5 text-muted-foreground" />
        )}
      </button>

      {/* Expandable content */}
      {expanded && (
        <div className="space-y-3 rounded-xl border border-[color:var(--hairline)] bg-secondary/20 p-3.5 animate-in fade-in-0 slide-in-from-top-1 duration-200">
          {/* Category chips */}
          <div className="space-y-1.5">
            <p className="text-[10px] font-semibold uppercase tracking-wider text-muted-foreground">
              Hook energy
            </p>
            <div className="flex flex-wrap gap-1.5">
              {HOOK_STYLE_CATEGORIES.map((cat) => (
                <Chip
                  key={cat.key}
                  active={hookCategory === cat.key}
                  onClick={() =>
                    onCategoryChange(hookCategory === cat.key ? "" : cat.key)
                  }
                  disabled={disabled}
                  testId={`hook-style-${cat.key}`}
                  title={cat.description}
                >
                  {cat.label}
                </Chip>
              ))}
            </div>
            {/* Selected category description */}
            {hookCategory && (
              <p className="text-[10px] leading-snug text-muted-foreground italic">
                {HOOK_STYLE_CATEGORIES.find((c) => c.key === hookCategory)?.description}
              </p>
            )}
          </div>

          {/* Custom prompt textarea */}
          <div className="space-y-1.5">
            <label
              htmlFor="hook-custom-prompt"
              className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-wider text-muted-foreground"
            >
              <PenLine className="h-3 w-3" />
              Custom direction (optional)
            </label>

            {/* Guidelines */}
            <div className="flex items-start gap-1.5 rounded-lg bg-secondary/40 px-2.5 py-1.5">
              <Info className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
              <p className="text-[9px] leading-snug text-muted-foreground">
                Describe the <span className="font-medium text-foreground/80">physical movement, expression, or energy</span> you want.
                Keep it short and specific — e.g. body language, facial expressions, gestures, or camera framing.
              </p>
            </div>

            <textarea
              id="hook-custom-prompt"
              value={hookCustomPrompt}
              onChange={handlePromptChange}
              disabled={disabled}
              maxLength={CUSTOM_PROMPT_MAX}
              placeholder="E.g. 'Lean in with raised eyebrows, then point at camera with a confident smile'"
              rows={2}
              className={`w-full resize-none rounded-lg border bg-background px-3 py-2 text-xs leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:outline-none focus:ring-1 disabled:cursor-not-allowed disabled:opacity-50 ${
                isAtLimit
                  ? "border-destructive/60 focus:border-destructive focus:ring-destructive/30"
                  : "border-[color:var(--hairline)] focus:border-[color:var(--brand-teal)] focus:ring-[color:var(--brand-teal)]/30"
              }`}
              data-testid="hook-custom-prompt-input"
            />

            {/* Character counter + limit warning */}
            <div className="flex items-center justify-between">
              {isAtLimit ? (
                <span className="flex items-center gap-1 text-[9px] text-destructive">
                  <AlertTriangle className="h-2.5 w-2.5" />
                  Character limit reached
                </span>
              ) : (
                <span className="text-[9px] text-muted-foreground" />
              )}
              <span className={`text-[9px] font-medium tabular-nums ${counterColor}`}>
                {charCount}/{CUSTOM_PROMPT_MAX}
              </span>
            </div>
          </div>

          {/* Clear all button */}
          {hasSelection && (
            <button
              type="button"
              onClick={() => {
                onCategoryChange("");
                onCustomPromptChange("");
              }}
              disabled={disabled}
              className="text-[10px] font-medium text-muted-foreground hover:text-foreground transition-colors"
              data-testid="hook-style-clear"
            >
              Clear style customization
            </button>
          )}
        </div>
      )}
    </div>
  );
}
