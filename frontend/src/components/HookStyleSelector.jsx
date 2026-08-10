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
 * Owns every control that steers the hook away from a literal replication of
 * the source: hook energy, motion style, and freeform direction. They live
 * together because they share one consequence — any of them turns off the
 * exact-edit engine — so surfacing some prominently and burying others
 * misrepresented their relative importance.
 *
 * Props:
 *   hookCategory    — currently selected category key (string or "")
 *   onCategoryChange — (key: string) => void
 *   hookCustomPrompt — freeform prompt text (string)
 *   onCustomPromptChange — (text: string) => void
 *   motionStyle     — currently selected motion key (string, "" = Default)
 *   onMotionStyleChange — (key: string) => void
 *   motionStyles    — [{key,label,summary,motion,overlaps}] from the backend,
 *                     or null while loading. Never hardcoded here: the server
 *                     is the single source of truth for both the copy and the
 *                     prompt text so the two cannot diverge.
 *   exactEditAvailable — true | false | null, from the backend. Only `true`
 *                     means an exact edit is genuinely on the table.
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
  motionStyle = "",
  onMotionStyleChange,
  motionStyles = null,
  exactEditAvailable = null,
  disabled = false,
}) {
  const [expanded, setExpanded] = useState(false);
  // Off by default: the exact prompt text is the ground truth but reads like a
  // model instruction, so it's available on request rather than as the primary
  // description.
  const [showPromptText, setShowPromptText] = useState(false);

  const selectedMotion = (motionStyles || []).find((m) => m.key === motionStyle) || null;
  // A motion and a hook energy that describe the same effect layer two competing
  // directives into one prompt. Surfaced rather than silently allowed.
  const overlapsSelectedEnergy = !!(
    selectedMotion && hookCategory && (selectedMotion.overlaps || []).includes(hookCategory)
  );

  const hasSelection = !!(hookCategory || hookCustomPrompt.trim() || motionStyle);
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
            ? "border-[color:var(--brand-indigo)]/40 bg-[color:var(--indigo-8)]"
            : "border-[color:var(--hairline)] bg-secondary/30 hover:border-[color:var(--indigo-35)]"
        } disabled:cursor-not-allowed disabled:opacity-50`}
        aria-expanded={expanded}
        data-testid="hook-style-toggle"
      >
        <span className="flex items-center gap-2.5 text-left">
          <Sparkles className={`h-4 w-4 ${hasSelection ? "text-[color:var(--brand-indigo)]" : "text-muted-foreground"}`} />
          <span className="text-xs font-semibold">
            {hasSelection
              ? `Hook style: ${[
                  HOOK_STYLE_CATEGORIES.find((c) => c.key === hookCategory)?.label,
                  selectedMotion?.label,
                  hookCustomPrompt.trim() ? "custom direction" : null,
                ]
                  .filter(Boolean)
                  .join(" + ")}`
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
            <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
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
              <p className="text-xs leading-snug text-muted-foreground italic">
                {HOOK_STYLE_CATEGORIES.find((c) => c.key === hookCategory)?.description}
              </p>
            )}
          </div>

          {/* Motion style */}
          <div className="space-y-1.5">
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs font-semibold uppercase tracking-wider text-muted-foreground">
                Motion style
              </p>
              {/* The verbatim instruction stays one click away rather than being
                  the default description — readable copy first, ground truth on
                  demand. */}
              <button
                type="button"
                onClick={() => setShowPromptText((v) => !v)}
                disabled={disabled}
                className="text-xs font-medium text-muted-foreground transition-colors hover:text-foreground disabled:cursor-not-allowed disabled:opacity-50"
                data-testid="toggle-prompt-text"
              >
                {showPromptText ? "Hide exact instruction" : "Show exact instruction"}
              </button>
            </div>

            <div className="grid grid-cols-1 gap-1.5 sm:grid-cols-2">
              {/* Default / no override */}
              <button
                type="button"
                onClick={() => onMotionStyleChange("")}
                disabled={disabled}
                className={`rounded-lg border p-2 text-left transition-colors duration-200 ${
                  !motionStyle
                    ? "border-[color:var(--brand-indigo)] bg-[color:var(--indigo-8)]"
                    : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                } disabled:cursor-not-allowed disabled:opacity-50`}
                data-testid="motion-default"
              >
                <span
                  className={`block text-xs font-semibold ${
                    !motionStyle ? "text-[color:var(--brand-indigo)]" : "text-foreground"
                  }`}
                >
                  Default {exactEditAvailable === true ? "— Match original" : "— Let AI choose"}
                </span>
                <span className="text-xs leading-snug text-muted-foreground">
                  {exactEditAvailable === true
                    ? "Replicate the original hook's real movement exactly. The only option that uses the exact-edit engine."
                    : "Let AI pick the movement that best fits your photo."}
                </span>
              </button>

              {(motionStyles || []).map((m) => {
                const active = motionStyle === m.key;
                return (
                  <button
                    key={m.key}
                    type="button"
                    /* Toggle: clicking the active card returns to Default, so a
                       selection is never a one-way door. */
                    onClick={() => onMotionStyleChange(active ? "" : m.key)}
                    disabled={disabled}
                    className={`rounded-lg border p-2 text-left transition-colors duration-200 ${
                      active
                        ? "border-[color:var(--brand-indigo)] bg-[color:var(--indigo-8)]"
                        : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                    } disabled:cursor-not-allowed disabled:opacity-50`}
                    data-testid={`motion-${m.key}`}
                  >
                    <span
                      className={`block text-xs font-semibold ${
                        active ? "text-[color:var(--brand-indigo)]" : "text-foreground"
                      }`}
                    >
                      {m.label}
                    </span>
                    <span className="text-xs leading-snug text-muted-foreground">{m.summary}</span>
                    {showPromptText && m.motion && (
                      <span className="mt-1 block border-t border-[color:var(--hairline)] pt-1 text-xs italic leading-snug text-muted-foreground/70">
                        Sends: “{m.motion}”
                      </span>
                    )}
                  </button>
                );
              })}
            </div>

            {/* Overlap warning — both inputs describing the same effect */}
            {overlapsSelectedEnergy && (
              <div
                className="flex items-start gap-1.5 rounded-lg bg-amber-500/5 px-2.5 py-1.5"
                data-testid="motion-energy-overlap"
              >
                <AlertTriangle className="mt-0.5 h-3 w-3 shrink-0 text-amber-500" />
                <p className="text-xs leading-snug text-muted-foreground">
                  <span className="font-medium text-amber-500">
                    {selectedMotion.label}
                  </span>{" "}
                  and{" "}
                  <span className="font-medium text-amber-500">
                    {HOOK_STYLE_CATEGORIES.find((c) => c.key === hookCategory)?.label}
                  </span>{" "}
                  describe the same effect. Setting both sends two competing
                  instructions for one moment — consider picking just one.
                </p>
              </div>
            )}
          </div>

          {/* Custom prompt textarea */}
          <div className="space-y-1.5">
            <label
              htmlFor="hook-custom-prompt"
              className="flex items-center gap-1.5 text-xs font-semibold uppercase tracking-wider text-muted-foreground"
            >
              <PenLine className="h-3 w-3" />
              Custom direction (optional)
            </label>

            {/* Guidelines */}
            <div className="flex items-start gap-1.5 rounded-lg bg-secondary/40 px-2.5 py-1.5">
              <Info className="mt-0.5 h-3 w-3 shrink-0 text-muted-foreground" />
              <p className="text-xs leading-snug text-muted-foreground">
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
                  : "border-[color:var(--hairline)] focus:border-[color:var(--brand-indigo)] focus:ring-[color:var(--brand-indigo)]/30"
              }`}
              data-testid="hook-custom-prompt-input"
            />

            {/* Character counter + limit warning */}
            <div className="flex items-center justify-between">
              {isAtLimit ? (
                <span className="flex items-center gap-1 text-xs text-destructive">
                  <AlertTriangle className="h-2.5 w-2.5" />
                  Character limit reached
                </span>
              ) : (
                <span className="text-xs text-muted-foreground" />
              )}
              <span className={`text-xs font-medium tabular-nums ${counterColor}`}>
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
                onMotionStyleChange("");
              }}
              disabled={disabled}
              className="text-xs font-medium text-muted-foreground hover:text-foreground transition-colors"
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
