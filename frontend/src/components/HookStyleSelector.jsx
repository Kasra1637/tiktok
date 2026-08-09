import { useState } from "react";
import { ChevronDown, ChevronUp, Sparkles, PenLine } from "lucide-react";
import { Chip } from "./Chip";

/**
 * Hook Style Selector — lets creators optionally choose a hook *energy*
 * (category) and/or write a custom prompt to guide video generation.
 *
 * Collapsed by default so casual users get the existing flow untouched,
 * while power users can expand it to fine-tune their hook's intent.
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
    key: "intrigue",
    label: "Intrigue",
    description: "Curiosity-driven — 'wait, what?' energy that makes viewers stay",
  },
  {
    key: "reveal",
    label: "Reveal",
    description: "Dramatic before/after — start hidden, snap into the reveal",
  },
  {
    key: "reaction",
    label: "Reaction",
    description: "Exaggerated response — shocked face, jaw drop, double-take",
  },
  {
    key: "tutorial",
    label: "Tutorial",
    description: "Confident educator — 'let me show you' authority energy",
  },
  {
    key: "lifestyle",
    label: "Lifestyle",
    description: "Aspirational & aesthetic — pull viewers into your world",
  },
  {
    key: "transformation",
    label: "Transformation",
    description: "Glow-up energy — dramatic change from one state to another",
  },
];

const CUSTOM_PROMPT_MAX = 500;

export default function HookStyleSelector({
  hookCategory = "",
  onCategoryChange,
  hookCustomPrompt = "",
  onCustomPromptChange,
  disabled = false,
}) {
  const [expanded, setExpanded] = useState(false);

  const hasSelection = !!(hookCategory || hookCustomPrompt.trim());

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
            <textarea
              id="hook-custom-prompt"
              value={hookCustomPrompt}
              onChange={(e) => onCustomPromptChange(e.target.value.slice(0, CUSTOM_PROMPT_MAX))}
              disabled={disabled}
              placeholder="E.g. 'Start with a confused expression, then slowly realize something amazing — end with a big smile pointing at camera'"
              rows={3}
              className="w-full resize-none rounded-lg border border-[color:var(--hairline)] bg-background px-3 py-2 text-xs leading-relaxed text-foreground placeholder:text-muted-foreground/60 focus:border-[color:var(--brand-teal)] focus:outline-none focus:ring-1 focus:ring-[color:var(--brand-teal)]/30 disabled:cursor-not-allowed disabled:opacity-50"
              data-testid="hook-custom-prompt-input"
            />
            <p className="text-right text-[9px] text-muted-foreground">
              {hookCustomPrompt.length}/{CUSTOM_PROMPT_MAX}
            </p>
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
