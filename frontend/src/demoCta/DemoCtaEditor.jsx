import { useCallback, useEffect, useId, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  ChevronUp,
  Download,
  Film,
  Info,
  Loader2,
  Megaphone,
  Pause,
  Play,
  RotateCcw,
  SlidersHorizontal,
  Smartphone,
  Type,
  Upload,
  Volume2,
  VolumeX,
  X,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Progress } from "../components/ui/progress";
import { Slider } from "../components/ui/slider";
import { Switch } from "../components/ui/switch";
import { Checkbox } from "../components/ui/checkbox";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../components/ui/tooltip";
import { useReducedMotion } from "framer-motion";
import { SectionCard, GroupLabel } from "../components/SectionCard";
import { PostKitSection } from "../components/PostKitSection";
import { CONTROL_CLASS } from "../components/formControls";
import { Chip } from "../components/Chip";
import { recordSignal } from "../lib/feedback";
import {
  ANIMATIONS,
  BACKGROUNDS,
  BASE_PHONE_H,
  COLOR_PALETTES,
  DEFAULT_SCREEN,
  DEFAULTS,
  DEVICES,
  ENVIRONMENTS,
  PRESETS,
  RANGES,
  ACCENT_SWATCHES,
  OVERLAY_FONTS,
  OVERLAY_ANIMS,
  TEXT_STYLES,
  CTA_TIMING_PRESETS,
  formatTime,
  resolveCtaWindow,
  resolveStoryWindow,
} from "./constants";
import { checkOverlaySafety, drawEndCard, drawHookOverlay, drawStoryOverlay, getEndCardBounds, getHookBounds } from "./overlays";
import { useOverlayTaste } from "./useOverlayTaste";
import { fitVideoToScreen } from "./fit";
import { preloadHandViewImages } from "./handView";
import { describeFraming, getEffectiveZoom, tickInterval } from "./zoom";
import { useZoomKeyframes } from "./useZoomKeyframes";
import { usePreviewLoop } from "./usePreviewLoop";
import { useExportFlow } from "./exportFlow";
import { ExportFailureNote } from "./ExportFailureNote";
import { sourceErrorMessage, useHistorySource } from "./useHistorySource";
import { useOpeningMessages } from "./useOpeningMessages";

const SECTIONS_KEY = "hookforge.demoCta.openSections.v4";

// Render order, which is also the order that decides which group wins when a
// stored value somehow has more than one open (older versions allowed it).
// "second" owns the appended clip so Source & Look stays about the base.
const SECTION_ORDER = ["source", "second", "hook", "story", "cta", "advanced"];

/** The one-open shape: every key present, exactly one true (or none). */
function singleOpen(openKey) {
  return SECTION_ORDER.reduce((acc, key) => {
    acc[key] = key === openKey;
    return acc;
  }, {});
}

// Heights, radii, borders and focus rings copied from ui/input.jsx so the
// editor's selects and fields are indistinguishable from the app's own inputs.
// The earlier hand-rolled `rounded-[10px]` and a `/40` focus ring were both
// deviations: design_guidelines.md:124 fixes control radii at rounded-xl, and
// ui/input.jsx uses --indigo-35 border with a --indigo-15 ring. The page had
// three more `rounded-[10px]` callers (transport buttons, the view-mode
// segmented control, the platform preset); all four are now rounded-xl.
// What each crop mode does to the clip, in words, because the three names look
// interchangeable and are not. Cover crops, Contain pads, Fill stretches — and
// only Fill exists to guarantee no uncovered strip, which is what it now does.
// Copy says the trade-off rather than promising a result, so nobody picks a
// mode expecting behaviour it does not have.
const VIDEO_FIT_HINTS = {
  cover: "Fills the screen and crops the overflow. Nothing blank is left.",
  contain: "Shows the whole clip and pads the difference.",
  fill: "Stretches the clip to the screen. No bars, but the shape can distort.",
};

const INPUT_CLASS =
  "h-10 w-full rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3.5 py-1 text-sm shadow-[var(--shadow-xs)] transition-colors placeholder:text-muted-foreground hover:border-[color:var(--hairline-strong)] focus-visible:border-[color:var(--indigo-35)] focus-visible:bg-secondary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)]";

const TEXTAREA_CLASS =
  "w-full resize-none rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3.5 py-2 text-sm leading-snug shadow-[var(--shadow-xs)] transition-colors placeholder:text-muted-foreground hover:border-[color:var(--hairline-strong)] focus-visible:border-[color:var(--indigo-35)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)]";

/**
 * Overlay font id → canvas font stack. Unknown ids fall back to the first
 * catalog entry (Anton) rather than a bare generic: a missing file must never
 * render tofu, and the default must match what shipped before the picker.
 */
function fontStack(id) {
  const found = OVERLAY_FONTS.find((f) => f.id === id);
  return (found || OVERLAY_FONTS[0]).stack;
}

/**
 * One collapsible control group.
 *
 * The card is `flush`: `.surface` is un-layered CSS with its own 28px padding,
 * and every group carrying it put 24px of dead space around a 32px header,
 * which is most of what made the old panel feel bloated. `.surface-flush`
 * zeroes the gutter in the stylesheet, where it beats the utility layer, so
 * this component no longer reaches for `!p-0`. Content padding is 20px with
 * 20px stacks, the shared card rhythm.
 *
 * `open`/`onToggle` are lifted so the parent can persist which groups are open.
 */
function EditorSection({ title, icon, open, onToggle, testId, children }) {
  const panelId = useId();
  return (
    <SectionCard flush data-testid={testId}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        aria-controls={open ? panelId : undefined}
        className="row-pad focus-ring flex w-full items-center justify-between gap-2 text-left transition duration-150 hover:bg-[color:var(--indigo-6)]"
      >
        <GroupLabel as="h2" icon={icon}>{title}</GroupLabel>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div id={panelId} className="space-y-5 px-5 pb-5">{children}</div>}
    </SectionCard>
  );
}

/** Small caps sub-label for blocks nested inside a group card.
 *
 *  Uses `.eyebrow` rather than re-stating it. A hand-rolled
 *  `text-[11px] uppercase` copy was both a duplicate of an existing primitive
 *  and below the 12px floor design_guidelines.md:94 sets with no exceptions.
 */
function SubLabel({ children }) {
  return <span className="eyebrow block">{children}</span>;
}

function FieldLabel({ children }) {
  return <span className="text-xs text-muted-foreground">{children}</span>;
}

/**
 * Three-way presentation picker shared by both clips. `prefix` namespaces
 * the testids (`view-mode-*` for the base, `append-mode-*` for the added
 * clip) so the two pickers drive independent state from one component.
 */
function StylePicker({ label, hint, value, onChange, prefix }) {
  return (
    <>
      <SubLabel>{label}</SubLabel>
      {hint && <p className="text-xs text-muted-foreground">{hint}</p>}
      <div className="grid grid-cols-3 gap-1 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 p-1">
        {[
          ["floating", "Floating Phone"],
          ["hand", "Hand Holding"],
          ["realistic", "Real Video"],
        ].map(([id, label]) => (
          <button
            key={id}
            type="button"
            onClick={() => onChange(id)}
            aria-pressed={value === id}
            data-testid={`${prefix}${id}`}
            className={`focus-ring h-8 rounded-lg text-xs font-semibold transition duration-150 ${
              value === id
                ? "bg-[color:var(--brand-indigo)]/15 text-foreground shadow-[var(--shadow-xs)]"
                : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
            }`}
          >
            {label}
          </button>
        ))}
      </div>
    </>
  );
}

/** Hand-scene environment grid, one per clip (`prefix` namespaces testids). */
function EnvGrid({ value, onChange, prefix }) {
  return (
    <div className="grid grid-cols-5 gap-1.5">
      {ENVIRONMENTS.map((env) => (
        <button
          key={env.id}
          type="button"
          onClick={() => onChange(env.id)}
          title={env.label}
          data-testid={`${prefix}env-${env.id}`}
          className={`focus-ring overflow-hidden rounded-xl border text-xs transition ${
            value === env.id ? "border-[color:var(--brand-indigo)]" : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
          }`}
        >
          <img src={env.url} alt={env.label} className="aspect-[3/4] w-full object-cover" loading="lazy" crossOrigin="anonymous" />
          <div className="px-0.5 py-1 text-center text-xs leading-tight text-muted-foreground">{env.label}</div>
        </button>
      ))}
    </div>
  );
}

/** Floating-phone backdrop swatches, one set per clip. */
function BackgroundPicker({ value, onChange, prefix }) {
  return (
    <div className="space-y-2">
      <SubLabel>Background</SubLabel>
      <div className="flex flex-wrap items-center gap-2">
        {BACKGROUNDS.map((b) => (
          <button
            key={b.id}
            type="button"
            onClick={() => onChange(b.id)}
            title={b.label}
            aria-label={b.label}
            aria-pressed={value === b.id}
            data-testid={`${prefix}background-${b.id}`}
            className={`focus-ring h-10 w-10 shrink-0 overflow-hidden rounded-xl border transition duration-150 ${
              value === b.id
                ? "border-[color:var(--brand-indigo)] ring-2 ring-[color:var(--indigo-45)]"
                : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
            }`}
            style={
              b.preview === "transparent"
                ? { backgroundImage: "linear-gradient(45deg,#666 25%,transparent 25%),linear-gradient(-45deg,#666 25%,transparent 25%),linear-gradient(-45deg,transparent 75%,#666 75%),linear-gradient(-45deg,transparent 75%,#666 75%)", backgroundSize: "8px 8px", backgroundPosition: "0 0,0 4px,4px -4px,-4px 0", backgroundColor: "#222" }
                : { background: b.preview }
            }
          />
        ))}
      </div>
    </div>
  );
}

/** Floating-phone motion picker. The app's own selectable pill rather than
 *  another hand-rolled row of text buttons: this list is a segmented choice,
 *  which is what `Chip` is for, and it carries the visible border, hover
 *  state and indigo selected state a plain row lacks. */
function AnimationPicker({ value, onChange, prefix }) {
  return (
    <div className="space-y-2">
      <SubLabel>Animation</SubLabel>
      <div
        role="group"
        aria-label="Animation"
        data-testid={`${prefix}animation-group`}
        className="grid grid-cols-3 gap-1.5 lg:grid-cols-2 xl:grid-cols-3"
      >
        {ANIMATIONS.map((a) => (
          <Chip
            key={a.id}
            active={value === a.id}
            onClick={() => onChange(a.id)}
            testId={`${prefix}animation-${a.id}`}
            ariaLabel={a.label}
          >
            {a.label}
          </Chip>
        ))}
      </div>
    </div>
  );
}



/**
 * A labelled slider with its current value right-aligned in the label row, so
 * the number sits where the eye already is rather than needing a second pass.
 */
function ControlSlider({ label, value, min, max, step, onChange, testId, format }) {
  const display = format ? format(value) : value;
  return (
    <div className="space-y-2">
      <div className="flex items-baseline justify-between gap-2">
        <FieldLabel>{label}</FieldLabel>
        <span className="font-mono text-xs tabular-nums text-foreground">{display}</span>
      </div>
      <Slider
        data-testid={testId}
        value={[value]}
        min={min}
        max={max}
        step={step}
        onValueChange={([next]) => onChange(next)}
      />
    </div>
  );
}

/**
 * One-tap text-size presets beside the fine slider. S/M/L map onto the same
 * 70–130% scale the slider drives, so the preview, the export and the
 * remembered prefs all follow without a second path. A preset reads pressed
 * only when the slider sits exactly on it — a dragged value in between
 * presses nothing, which is the truth.
 */
const SCALE_PRESETS = [
  { id: "s", label: "S", value: 0.85 },
  { id: "m", label: "M", value: 1 },
  { id: "l", label: "L", value: 1.15 },
];

function ScalePresets({ value, onChange, testPrefix, ariaLabel }) {
  return (
    <div className="flex items-center gap-2" role="group" aria-label={ariaLabel}>
      {SCALE_PRESETS.map((p) => {
        const active = Math.abs(value - p.value) < 1e-9;
        return (
          <button
            key={p.id}
            type="button"
            data-testid={`${testPrefix}-${p.id}`}
            onClick={() => onChange(p.value)}
            aria-pressed={active}
            className={`focus-ring flex-1 rounded-xl border px-3 py-2 text-xs transition-colors ${
              active
                ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-foreground"
                : "border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--hairline-strong)]"
            }`}
          >
            {p.label}
          </button>
        );
      })}
    </div>
  );
}

function ResetButton({ onClick, children, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className="focus-ring rounded text-xs text-muted-foreground underline-offset-2 transition duration-150 hover:text-foreground hover:underline"
    >
      {children || "Reset"}
    </button>
  );
}

/**
 * Up/down stepper for overlay copy. Hook and end-card text travel vertically
 * only, so this is the keyboard- and touch-accessible path beside vertical
 * drag: one tap moves 1% of canvas height, Shift+tap jumps 5%.
 */
function VerticalNudge({ label, onNudge, upTestId, downTestId }) {
  const btn =
    "rounded-lg border border-[color:var(--hairline)] p-1.5 text-muted-foreground transition hover:border-[color:var(--hairline-strong)] hover:text-foreground focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-indigo)]/40";
  return (
    <div className="flex shrink-0 items-center gap-1" role="group" aria-label={label}>
      <button
        type="button"
        data-testid={upTestId}
        title="Move up (Shift: larger step)"
        aria-label={`${label}: move up`}
        onClick={(e) => onNudge(-(e.shiftKey ? 0.05 : 0.01))}
        className={btn}
      >
        <ChevronUp className="h-4 w-4" />
      </button>
      <button
        type="button"
        data-testid={downTestId}
        title="Move down (Shift: larger step)"
        aria-label={`${label}: move down`}
        onClick={(e) => onNudge(e.shiftKey ? 0.05 : 0.01)}
        className={btn}
      >
        <ChevronDown className="h-4 w-4" />
      </button>
    </div>
  );
}

/**
 * A transport control: a real 44px target with a tooltip.
 *
 * These were 28px text buttons, which is below the 44px touch guideline and
 * hard to hit while watching the preview. The size is on the button rather than
 * an icon so the whole square is the hit area.
 */
function TransportButton({ label, onClick, disabled, children, testId }) {
  const button = (
    <button
      type="button"
      onClick={onClick}
      disabled={disabled}
      data-testid={testId}
      aria-label={label}
      className="flex h-11 w-11 shrink-0 items-center justify-center rounded-xl border border-[color:var(--hairline)] bg-secondary/40 text-foreground transition duration-150 hover:border-[color:var(--hairline-strong)] hover:bg-secondary/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-indigo)]/40 disabled:pointer-events-none disabled:opacity-40"
    >
      {children}
    </button>
  );
  return (
    <Tooltip>
      <TooltipTrigger asChild>{button}</TooltipTrigger>
      <TooltipContent>{label}</TooltipContent>
    </Tooltip>
  );
}

/**
 * One entrance grid for both overlays: hook text and end card render the
 * same shared OVERLAY_ANIMS catalog through this component, parameterized
 * by selected value, setter, testid namespace and group label — so a change
 * to entrance layout lands once, not twice.
 *
 * Three columns with no narrow-width guard: the text-xs labels were measured
 * live fitting without wrap or overflow at phone width, unlike the
 * background chips. No Classic/Bold grouping either: with twenty entrances
 * the headers would add back the rows the third column saves.
 */
function EntranceGrid({ value, onChange, testPrefix, ariaLabel }) {
  return (
    <div className="grid grid-cols-3 gap-2" role="group" aria-label={ariaLabel}>
      {OVERLAY_ANIMS.map((a) => (
        <button
          key={a.id}
          type="button"
          data-testid={`${testPrefix}-${a.id}`}
          onClick={() => onChange(a.id)}
          aria-pressed={value === a.id}
          className={`focus-ring rounded-xl border px-3 py-2 text-left text-xs transition-colors ${
            value === a.id
              ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-foreground"
              : "border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--hairline-strong)]"
          }`}
        >
          {a.label}
        </button>
      ))}
    </div>
  );
}

/**
 * Collapsible wrapper for everything from the entrance picker down: the
 * twenty entrances plus text size, accent where it lives, and the rest of
 * the section. Collapsed by default; laid out flat it all pushes the section
 * tall, which is why it collapses. Collapsed, the summary still names the
 * current entrance so the choice stays visible. Controlled <details> keeps
 * every control in the DOM, with the parent owning the single open disclosure.
 * The "Customize" label names the group; the summary below
 * it names the current entrance.
 */
/**
 * The disclosure triggers below are native <summary> elements, which some
 * accessibility trees expose as disclosure triangles without a clickable
 * reference. The button role (plus expanded state) fixes the exposure; state
 * stays with the parent-owned disclosure, so this changes operability, not
 * behavior. Keyboard activation is Enter, which fires click natively and
 * reaches onToggle through the existing handler. Space is deliberately left
 * alone: the global playback shortcut owns Space everywhere outside text
 * entry, and swallowing it here would break preview transport (enforced by
 * the "Font & Animation close each other" smoke check).
 */
function AnimDisclosure({ testId, currentLabel, open, onToggle, children }) {
  const panelId = useId();
  return (
    <div className="space-y-2">
      <SubLabel>Customize</SubLabel>
      <details open={open} data-testid={testId} className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-1.5">
        <summary onClick={(event) => { event.preventDefault(); onToggle(); }} role="button" tabIndex={0} aria-expanded={open} aria-controls={panelId} className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
          <span>Animation · <span className="text-foreground">{currentLabel}</span></span>
          <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180" />
        </summary>
        <div id={panelId} className="space-y-5 pb-1 pt-3">
          {children}
        </div>
      </details>
    </div>
  );
}

/**
 * Collapsible wrapper for the font tile grid, mirroring AnimDisclosure:
 * collapsed by default, summary names the current face, and opening this
 * closes Animation through the same parent-owned disclosure state.
 */
function FontDisclosure({ testId, groupLabel, currentLabel, open, onToggle, children }) {
  const panelId = useId();
  return (
    <div className="space-y-2">
      <details open={open} data-testid={testId} className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-1.5">
        <summary onClick={(event) => { event.preventDefault(); onToggle(); }} role="button" tabIndex={0} aria-expanded={open} aria-controls={panelId} className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
          <span>Font · <span className="text-foreground">{currentLabel}</span></span>
          <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180" />
        </summary>
        <div id={panelId} className="pb-1 pt-3" role="group" aria-label={groupLabel}>
          {children}
        </div>
      </details>
    </div>
  );
}

/**
 * Accent swatch picker, shared by Hook Text and End Card CTA. One global
 * accent colors both the hook text line and the end-card handle chip, so
 * both sections offer the same control rather than one hiding it from the
 * other. `testPrefix` keeps the two instances' testids distinct.
 */
function AccentPicker({ testPrefix, accent, onAccentChange }) {
  return (
    <div className="space-y-2">
      <SubLabel>Accent</SubLabel>
      <p className="text-xs text-muted-foreground">Colors hook text and handle chip.</p>
      <div className="flex flex-wrap items-center gap-2">
        {ACCENT_SWATCHES.map((c) => (
          <button
            key={c}
            type="button"
            data-testid={`${testPrefix}-${c.replace("#", "")}`}
            onClick={() => onAccentChange(c)}
            style={{ background: c }}
            aria-label={`Accent ${c}`}
            aria-pressed={accent === c}
            className={`focus-ring h-10 w-10 shrink-0 rounded-full border-2 transition duration-150 ${
              accent === c
                ? "border-[color:var(--brand-indigo)] ring-2 ring-[color:var(--indigo-45)]"
                : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
            }`}
          />
        ))}
      </div>
    </div>
  );
}

/**
 * The native Product Demo + CTA editor.
 *
 * Behavior is a faithful port of the standalone app: same defaults, ranges,
 * keyframe semantics, canvas math, overlay timing and export pipeline. What
 * changed is the shell around it:
 *
 * - The input is the finished HookForge generation, fetched and pinned as a
 *   Blob on mount. No download, no upload, no second app.
 * - The export is saved straight into History as a child of that generation.
 *   The local download remains as a secondary action, never the only path.
 * - The file picker is the original import path, preserved. Entered from a
 *   Hook + Story it is a fallback that swaps the source for this edit; entered
 *   from the sidebar with no generation it is the whole input, and the export
 *   is saved standalone. Either way it never creates a Hook + Story.
 */
export function DemoCtaEditor({ generation = null, sourceUrl = null, onSaved }) {
  // A programmatic scroll cannot be switched off by a Tailwind motion-reduce
  // variant, so the preference is read here and honoured in JS.
  const reduceMotion = useReducedMotion();
  // At most ONE group is open at a time. This panel describes one clip, and
  // eleven groups open at once made the settings column taller than the video
  // they were describing — the preview shrank to fit a wall of controls. One
  // group also means one obvious next place to look.
  //
  // Which group is still remembered across visits: this is a workspace, not a
  // form, and re-opening Source & Look over whatever someone was tuning is the
  // same friction as before, just inverted.
  const [openSections, setOpenSections] = useState(() => {
    const raw = (() => {
      try {
        return window.localStorage.getItem(SECTIONS_KEY);
      } catch {
        return null;
      }
    })();
    if (!raw) return singleOpen("source");
    try {
      const saved = JSON.parse(raw);
      if (!saved || typeof saved !== "object") return singleOpen("source");
      return singleOpen(SECTION_ORDER.find((k) => saved[k]) || "source");
    } catch {
      // Private mode, quota, or malformed JSON. The default is a fine answer.
      return singleOpen("source");
    }
  });
  const [openDisclosure, setOpenDisclosure] = useState(null);
  const toggleDisclosure = (key) => setOpenDisclosure((current) => current === key ? null : key);
  const historyPanelId = useId();
  const toggleSection = useCallback((key) => {
    setOpenSections((prev) => {
      // Clicking the open group closes it. Nothing open is a valid state, the
      // same as Radix's `type="single"` + `collapsible`.
      const next = singleOpen(prev[key] ? null : key);
      try {
        window.localStorage.setItem(SECTIONS_KEY, JSON.stringify(next));
      } catch {
        // Nothing to do: persistence is a convenience, not the feature.
      }
      return next;
    });
  }, []);

  const [videoUrl, setVideoUrl] = useState(null);
  // Name of a founder-supplied file, so the upload control can show what is
  // actually loaded rather than an anonymous "replace" affordance.
  const [sourceFileName, setSourceFileName] = useState("");
  const [sourceReplaced, setSourceReplaced] = useState(false);
  const [loadingSource, setLoadingSource] = useState(true);
  const [videoMeta, setVideoMeta] = useState(null);
  // Fixed frame: Samsung Galaxy S24 Ultra. The picker is gone by design —
  // one frame, no choice — so this is state only so the painters keep
  // reading it like any other value.
  const [device] = useState(DEFAULTS.device);
  const preset = "tiktok";
  const [bg, setBg] = useState(DEFAULTS.bg);
  const [anim, setAnim] = useState(DEFAULTS.anim);
  const [scale, setScale] = useState(DEFAULTS.scale);
  const [mockupStretchY, setMockupStretchY] = useState(DEFAULTS.mockupStretchY);
  const [videoFit, setVideoFit] = useState(DEFAULTS.videoFit);
  const [videoScale, setVideoScale] = useState(DEFAULTS.videoScale);
  const [videoOffsetX, setVideoOffsetX] = useState(DEFAULTS.videoOffsetX);
  const [videoOffsetY, setVideoOffsetY] = useState(DEFAULTS.videoOffsetY);
  const [recording, setRecording] = useState(false);
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(null);
  const [saveError, setSaveError] = useState(null);
  const [error, setError] = useState(null);
  const [viewMode, setViewMode] = useState(DEFAULTS.viewMode);
  const [envBg, setEnvBg] = useState(DEFAULTS.envBg);
  const [screenX, setScreenX] = useState(DEFAULT_SCREEN.x);
  const [screenY, setScreenY] = useState(DEFAULT_SCREEN.y);
  const [screenW, setScreenW] = useState(DEFAULT_SCREEN.w);
  const [screenH, setScreenH] = useState(DEFAULT_SCREEN.h);
  const [handZoom, setHandZoom] = useState(DEFAULTS.handZoom);
  const [handPanX, setHandPanX] = useState(DEFAULTS.handPanX);
  const [handPanY, setHandPanY] = useState(DEFAULTS.handPanY);
  const [hookEnabled, setHookEnabled] = useState(DEFAULTS.hookEnabled);
  const [hookText, setHookText] = useState(DEFAULTS.hookText);
  const [openingProfileId, setOpeningProfileId] = useState(generation?.brand_profile_id || null);
  const openingMessages = useOpeningMessages({ profileId: openingProfileId, text: hookText, onText: setHookText });
  const [hookDuration, setHookDuration] = useState(DEFAULTS.hookDuration);
  const [hookOffsetX, setHookOffsetX] = useState(DEFAULTS.hookOffsetX);
  const [hookOffsetY, setHookOffsetY] = useState(DEFAULTS.hookOffsetY);
  const [ctaEnabled, setCtaEnabled] = useState(DEFAULTS.ctaEnabled);
  const [ctaHeadline, setCtaHeadline] = useState(DEFAULTS.ctaHeadline);
  const [ctaHandle, setCtaHandle] = useState(DEFAULTS.ctaHandle);
  const [ctaDuration, setCtaDuration] = useState(DEFAULTS.ctaDuration);
  const [ctaOffsetX, setCtaOffsetX] = useState(DEFAULTS.ctaOffsetX);
  const [ctaOffsetY, setCtaOffsetY] = useState(DEFAULTS.ctaOffsetY);
  // Scope for remembered overlay taste. Resolved once at mount: the editor
  // remounts per route, and reseeding mid-edit would clobber live changes.
  const overlayScope = generation?.brand_profile_id || "global";
  // Overlay taste lives in useOverlayTaste: same values, setters and
  // helpers as the inline state it replaces, so everything below reads
  // unchanged. Copy text stays here; variant picks report back through
  // the callbacks.
  const {
    overlayAccent, setOverlayAccent,
    captionFont, setCaptionFont,
    ctaFont, setCtaFont,
    captionAnim, setCaptionAnim,
    ctaAnim, setCtaAnim,
    captionScale, setCaptionScale,
    ctaScale, setCtaScale,
    textStyle, setTextStyle,
    updateCtaHeadline, surpriseCtaVariant,
    customLookPresets,
    allLookPresets,
    newLookName, setNewLookName,
    reviewedLookKey, setReviewedLookKey,
    savedLookNotice,
    lookReviewKey, canReviewLook, lookReviewed, canSaveLook,
    isLookPresetActive, applyLookPreset,
    handleSaveLookPreset, handleDeleteLookPreset,
  } = useOverlayTaste({
    overlayScope,
    videoUrl,
    clipDuration: videoMeta?.d,
    recording,
    onCtaHeadline: setCtaHeadline,
  });
  const [ctaTimingMode, setCtaTimingMode] = useState("custom");
  const [storyEnabled, setStoryEnabled] = useState(false);
  const [storyText, setStoryText] = useState("");
  const [storyTiming, setStoryTiming] = useState({ start: 0, end: null });
  const [storyOffsetY, setStoryOffsetY] = useState(0);
  const storyWindow = resolveStoryWindow({
    clipDuration: videoMeta?.d ?? 0,
    hookEnabled, hookDuration, ctaEnabled, ctaDuration, ctaTimingMode,
    ...storyTiming,
  });
  const { start: storyStart, end: storyEnd, available: storyAvailable } = storyWindow;
  useEffect(() => {
    if (storyAvailable) setStoryTiming({ start: storyStart, end: storyEnd });
  }, [storyStart, storyEnd, storyAvailable]);
  const selectCtaTimingPreset = (presetId) => {
    setCtaTimingMode(presetId);
    const dur = videoMeta?.d || 0;
    if (presetId === "last2") {
      setCtaDuration(2);
    } else if (presetId === "last3") {
      setCtaDuration(3);
    } else if (presetId === "full") {
      setCtaDuration(dur > 0 ? Math.min(RANGES.ctaDuration.max, Math.max(RANGES.ctaDuration.min, Number(dur.toFixed(1)))) : RANGES.ctaDuration.max);
    }
  };


  const {
    zoomKeyframes,
    zoomKeyframesRef,
    sortedKeyframes,
    captureZoomKeyframe,
    removeZoomKeyframe,
    clearZoomKeyframes,
  } = useZoomKeyframes();

  // Optional second segment. The preview hook owns sequence transport;
  // export decodes both sources on the same joined timeline.
  const [appendUrl, setAppendUrl] = useState(null);
  const [appendMeta, setAppendMeta] = useState(null);
  const [appendMode, setAppendMode] = useState("realistic");
  // The added clip keeps its own look: background, motion and hand scene
  // start from the same defaults as the base but diverge independently.
  // Zoom framing and phone size stay shared — one timeline, one mockup
  // geometry — so locks and sliders keep working across the cut.
  const [appendBg, setAppendBg] = useState(DEFAULTS.bg);
  const [appendAnim, setAppendAnim] = useState(DEFAULTS.anim);
  const [appendEnv, setAppendEnv] = useState(DEFAULTS.envBg);
  const [appendOverlays, setAppendOverlays] = useState(false);
  // Per-clip audio: each segment mutes independently in preview and
  // export. Export keeps the segment's video length and writes silence
  // for a muted clip, so the join never shifts.
  const [baseMuted, setBaseMuted] = useState(false);
  const [appendMuted, setAppendMuted] = useState(false);
  const [appendName, setAppendName] = useState("");
  const [appendError, setAppendError] = useState(null);
  const appendVideoRef = useRef(null);
  const appendObjectUrlRef = useRef(null);
  const appendInputRef = useRef(null);

  // Preview transport + scoped replay + frame painting live in
  // usePreviewLoop; the editor only reads the playhead and calls the
  // transport helpers. Zoom editing stays here and works through the
  // refs/helpers the hook owns.
  const {
    videoRef, previewCanvasRef,
    isPlaying, setIsPlaying,
    previewMuted, setPreviewMuted, togglePreviewMuted,
    currentTime, setCurrentTime,
    isSeeking, setIsSeeking,
    startScopedPreview, ensureScopedPreview,
    togglePlayPause, handleSeek,
    cancelScopedReplay, dirtyRef,
    showZoomValues, zoomValuesAt,
    editingZoomRef, liveZoomRef,
    paintFrameRef, kickPreviewRef, isExportingRef, activeVideoRef,
  } = usePreviewLoop({
    device, preset, mockupStretchY, scale, videoMeta, bg, anim,
    videoFit, videoScale, videoOffsetX, videoOffsetY,
    viewMode, envBg, screenX, screenY, screenW, screenH,
    handZoom, handPanX, handPanY,
    appendUrl, appendMeta, appendMode, appendBg, appendAnim, appendEnv, appendVideoRef, appendOverlays,
    baseMuted, appendMuted,
    hookEnabled, hookText, hookDuration, hookOffsetX, hookOffsetY,
    storyEnabled, storyAvailable, storyText, storyStart, storyEnd, storyOffsetY,
    ctaEnabled, ctaHeadline, ctaHandle, ctaDuration, ctaTimingMode, ctaOffsetX, ctaOffsetY,
    overlayAccent, captionFont, ctaFont, captionAnim, ctaAnim,
    captionScale, ctaScale, textStyle,
    fontStack,
    zoomKeyframes, zoomKeyframesRef,
    setVideoScale, setVideoOffsetX, setVideoOffsetY,
    setHandZoom, setHandPanX, setHandPanY, setScale,
  });


  // The one file input, referenced so the empty frame's upload button can
  // drive it. Two inputs would mean two sources of truth and a duplicate
  // `data-testid` for the same control.
  const fileInputRef = useRef(null);
  const sourceObjectUrlRef = useRef(null);
  const resultObjectUrlRef = useRef(null);

  // Export recording, MP4 validation and History save live in
  // useExportFlow (with failure history via useExportErrors); the editor
  // only calls the two actions and reads the outcome states it owns.
  const { saveExport, exportVideo, exportErrors, clearExportErrors } = useExportFlow({
    generation, onSaved,
    videoUrl, videoMeta, device, preset, viewMode, appendMode, envBg, appendEnv,
    appendUrl, appendMeta, appendVideoRef, baseMuted, appendMuted,
    captionFont, ctaFont, fontStack,
    videoRef, activeVideoRef, paintFrameRef, isExportingRef, dirtyRef, kickPreviewRef,
    resultObjectUrlRef,
    setIsPlaying,
    setRecording, setProgress, setResult,
    setSaving, setSaved, setSaveError, setError,
  });
  const latestExportError = exportErrors[exportErrors.length - 1] || null;
  // The "Export ready" card, so a finished export can put itself in front of
  // the founder. A ref rather than a scrollIntoView on mount because the card
  // renders inside the PREVIEW column, which is its own scroll container at
  // lg+ (lg:sticky lg:overflow-y-auto). Scrolling the window would move nothing
  // there; scrollIntoView resolves whichever ancestor actually scrolls.
  const resultCardRef = useRef(null);

  useEffect(() => {
    preloadHandViewImages();
  }, []);

  useEffect(() => {
    // Every selectable overlay face must be ready before the first paint:
    // canvas falls back silently to a wrong face, and the export would then
    // bake in a typeface the founder never picked. Fire-and-forget on purpose
    // — a slow face resolves into later frames, never an error state.
    if (document.fonts?.load) {
      for (const face of OVERLAY_FONTS) {
        document.fonts.load(`100px ${face.stack}`).catch(() => {});
      }
    }
  }, []);

  /**
   * Put a finished export in front of the founder.
   *
   * Tapping Export is a commitment of several seconds, and when it lands the
   * result — the video, the Download button, and the History confirmation — is
   * below the fold in the preview column. Without this the export appears to
   * have done nothing, and the natural next action is to press Export again.
   *
   * Two triggers, because the card fills in over time: once when the recording
   * lands (so the video and Download are visible immediately) and again when
   * the save reaches History (so the "In History" badge and View in History
   * are visible too). Keyed on those two values rather than run on every
   * render, so a founder who scrolls away to look at something else is not
   * yanked back on an unrelated state change.
   *
   * `block: "nearest"` scrolls the minimum distance that reveals the card. The
   * preview column is height-capped and sticky at lg+, so "center" would move
   * the phone frame out of view to satisfy the result card.
   */
  useEffect(() => {
    if (!result) return;
    const card = resultCardRef.current;
    if (!card) return;
    const behavior = reduceMotion ? "auto" : "smooth";
    // rAF so the card has been laid out before we measure and scroll to it.
    const raf = requestAnimationFrame(() => {
      card.scrollIntoView({ behavior, block: "nearest", inline: "nearest" });
    });
    return () => cancelAnimationFrame(raf);
    // `result` rather than `result?.url`: it is set once per export, so its
    // identity changes exactly when a recording lands and when one is cleared,
    // which is the behaviour being asked for here.
  }, [result, saved?.id, reduceMotion]);

  // Pin the generation's bytes on mount so a signed URL expiring mid-edit
  // cannot pull the source out from under the canvas or the recorder. With no
  // generation there is nothing to fetch: the editor opens empty and waits for a
  // file, which is how someone uses it without generating a hook first.
  useEffect(() => {
    let cancelled = false;
    if (!sourceUrl) {
      setLoadingSource(false);
      return undefined;
    }
    setLoadingSource(true);
    setError(null);
    (async () => {
      try {
        const res = await fetch(sourceUrl);
        if (!res.ok) {
          const auth = res.status === 401 || res.status === 403;
          throw new Error(
            auth
              ? "This render's link requires a credential the browser can't send. " +
                  "Refresh for a fresh link, or choose a different render."
              : "The finished render returned an error. Refresh for a fresh link."
          );
        }
        const blob = await res.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        sourceObjectUrlRef.current = url;
        setVideoUrl(url);
        setSourceReplaced(false);
      } catch (e) {
        if (!cancelled) {
          clearExportErrors();
          setError(sourceErrorMessage(e, "The finished render could not be loaded."));
        }
      } finally {
        if (!cancelled) setLoadingSource(false);
      }
    })();
    return () => {
      cancelled = true;
      if (sourceObjectUrlRef.current) {
        URL.revokeObjectURL(sourceObjectUrlRef.current);
        sourceObjectUrlRef.current = null;
      }
    };
  }, [sourceUrl]);

  const handleFile = (file) => {
    if (!file) return;
    setError(null);
    setSaveError(null);
    setSaved(null);
    clearExportErrors();
    // The new clip has no metadata until the probe below reads it. Clearing
    // here (not just on load) keeps a stale duration from the previous clip
    // from holding Export enabled for a file that may never play.
    setVideoMeta(null);
    setResult(null);
    editingZoomRef.current = false;
    clearZoomKeyframes();
    if (resultObjectUrlRef.current) {
      URL.revokeObjectURL(resultObjectUrlRef.current);
      resultObjectUrlRef.current = null;
    }
    if (sourceObjectUrlRef.current) URL.revokeObjectURL(sourceObjectUrlRef.current);
    const url = URL.createObjectURL(file);
    sourceObjectUrlRef.current = url;
    setVideoUrl(url);
    setSourceFileName(file.name || "video");
    setSourceReplaced(true);
  };

  /**
   * Drop a founder-supplied clip and go back to the render that was here before.
   * Restoring the pinned bytes rather than clearing the source is what makes
   * "Remove" reversible: without it the panel would sit empty with no way back
   * short of a reload.
   *
   * From the standalone route there is no pinned render, so Remove clears to
   * the empty state instead of doing nothing: a visible button that cannot act
   * is the silent failure this panel refuses everywhere else.
   *
   * Either way the old export goes with the old source. The result card
   * describes a recording of the removed clip, and keeping it mounted let one
   * export be saved to History over and over as duplicate rows.
   */
  const clearSource = () => {
    // Wipe failure history even on a no-op Remove so a stale
    // "Failed during save" note can never outlive its source.
    clearExportErrors();
    // State, not the prop: from the standalone route there is no pinned
    // sourceUrl, only a founder-supplied object URL in videoUrl.
    if (!videoUrl && !sourceUrl) return;
    setOpeningProfileId(generation?.brand_profile_id || null);
    if (resultObjectUrlRef.current) {
      URL.revokeObjectURL(resultObjectUrlRef.current);
      resultObjectUrlRef.current = null;
    }
    setVideoMeta(null);
    setResult(null);
    editingZoomRef.current = false;
    clearZoomKeyframes();
    setSaved(null);
    setSaveError(null);
    if (!generation) {
      if (sourceObjectUrlRef.current) URL.revokeObjectURL(sourceObjectUrlRef.current);
      sourceObjectUrlRef.current = null;
      setVideoUrl(null);
      setSourceFileName("");
      setSourceReplaced(false);
      setError(null);
      setLoadingSource(false);
      return;
    }
    setSourceFileName("");
    setSourceReplaced(false);
    setError(null);
    setLoadingSource(true);
    (async () => {
      try {
        const res = await fetch(sourceUrl);
        if (!res.ok) {
          const auth = res.status === 401 || res.status === 403;
          throw new Error(
            auth
              ? "This render's link requires a credential the browser can't send. " +
                  "Refresh for a fresh link, or choose a different render."
              : "The finished render returned an error. Refresh for a fresh link."
          );
        }
        const blob = await res.blob();
        if (sourceObjectUrlRef.current) URL.revokeObjectURL(sourceObjectUrlRef.current);
        const url = URL.createObjectURL(blob);
        sourceObjectUrlRef.current = url;
        setVideoUrl(url);
      } catch (e) {
        setError(sourceErrorMessage(e, "The finished render could not be reloaded."));
      } finally {
        setLoadingSource(false);
      }
    })();
  };

  // History-as-source lives in useHistorySource: same open/rows/error/
  // attaching state and the same attach behavior as the inline code it
  // replaces, so everything below reads unchanged.
  const {
    historyOpen,
    setHistoryOpen,
    historyRows,
    historyError,
    attachingId,
    attachHistoryVideo,
  } = useHistorySource({
    onAttachFile: (file, row) => {
      handleFile(file);
      setOpeningProfileId(row?.brand_profile_id || null);
    },
  });

  const invalidateSequence = () => {
    if (resultObjectUrlRef.current) URL.revokeObjectURL(resultObjectUrlRef.current);
    resultObjectUrlRef.current = null;
    setResult(null);
    setSaved(null);
    setSaveError(null);
    clearExportErrors();
  };

  const handleAppendFile = (file) => {
    if (!file) return;
    invalidateSequence();
    setAppendError(null);
    if (appendObjectUrlRef.current) URL.revokeObjectURL(appendObjectUrlRef.current);
    const url = URL.createObjectURL(file);
    appendObjectUrlRef.current = url;
    setAppendMeta(null);
    setAppendUrl(url);
    setAppendName(file.name || "added clip");
  };

  const removeAppend = () => {
    invalidateSequence();
    if (appendObjectUrlRef.current) URL.revokeObjectURL(appendObjectUrlRef.current);
    appendObjectUrlRef.current = null;
    setAppendUrl(null);
    setAppendMeta(null);
    setAppendName("");
    setAppendError(null);
  };

  useEffect(() => () => {
    if (appendObjectUrlRef.current) URL.revokeObjectURL(appendObjectUrlRef.current);
  }, []);

  // Probe metadata and ensure preview video starts playing
  useEffect(() => {
    if (!videoUrl) return;
    const v = document.createElement("video");
    v.src = videoUrl;
    v.muted = true;
    v.onloadedmetadata = () => {
      setVideoMeta({ w: v.videoWidth, h: v.videoHeight, d: v.duration });
    };
    // An unloadable file (wrong type, corrupt bytes) never fires
    // loadedmetadata, which used to leave the previous clip's metadata in
    // place: the filename looked loaded, Export stayed enabled, and clicking
    // it silently did nothing. Fail loudly instead, with the file named.
    v.onerror = () => {
      setVideoMeta(null);
      setError(
        `"${sourceFileName || "That file"}" couldn't be played as video. ` +
          "Choose an MP4 or WebM clip, or try another file."
      );
    };
    const refVideo = videoRef.current;
    if (refVideo) {
      refVideo.src = videoUrl;
      refVideo.muted = true;
      setPreviewMuted(true);
      refVideo.playsInline = true;
      refVideo.load();
      refVideo.play().catch(() => {});
      setIsPlaying(true);
      setCurrentTime(0);
    }
  }, [videoUrl, sourceFileName, videoRef, setPreviewMuted, setIsPlaying, setCurrentTime]);











  const updateZoomDraft = (patch) => {
    if (isExportingRef.current) return;
    const video = activeVideoRef.current || videoRef.current;
    const base = editingZoomRef.current ? liveZoomRef.current : zoomValuesAt(currentTime);
    cancelScopedReplay();
    video?.pause();
    setIsPlaying(false);
    editingZoomRef.current = true;
    showZoomValues({ ...base, ...(typeof patch === "function" ? patch(base) : patch) });
    dirtyRef.current = true;
    kickPreviewRef.current?.();
  };

  const isAppendTime = (time) => !!appendMeta && time >= (videoMeta?.d ?? 0);
  const modeAt = (time) => (isAppendTime(time) ? appendMode : viewMode);
  const handleCaptureZoomLock = () => {
    const video = videoRef.current;
    if (!video || !videoMeta || isExportingRef.current) return;
    if (isAppendTime(currentTime) && appendMode === "realistic") return;
    const time = video.currentTime;
    const snapshot = editingZoomRef.current ? liveZoomRef.current : zoomValuesAt(time);
    captureZoomKeyframe(time, snapshot);
    editingZoomRef.current = false;
    dirtyRef.current = true;
    kickPreviewRef.current?.();
  };

  const handleRemoveZoomKeyframe = (id) => {
    editingZoomRef.current = false;
    removeZoomKeyframe(id);
  };

  const handleClearZoomKeyframes = () => {
    editingZoomRef.current = false;
    clearZoomKeyframes();
  };


  const handlePointerDown = (e) => {
    if (isExportingRef.current) return;
    const el = e.currentTarget;
    el.setPointerCapture(e.pointerId);
    const rect = el.getBoundingClientRect();
    const startX = e.clientX;
    const startY = e.clientY;

    const canvasW = el.width;
    const canvasH = el.height;
    const scaleX = canvasW / rect.width;
    const scaleY = canvasH / rect.height;
    const cx = (e.clientX - rect.left) * scaleX;
    const cy = (e.clientY - rect.top) * scaleY;

    const vt = currentTime;
    const dur = videoMeta?.d ?? 0;
    const hookWindow = hookDuration + 0.28;
    const ctaWindow = resolveCtaWindow(ctaDuration, dur, ctaTimingMode) + 0.4;
    const hookVisible = hookEnabled && vt <= hookWindow;
    const ctaVisible = ctaEnabled && dur > 0 && (dur - vt) <= ctaWindow && (dur - vt) >= 0;

    let dragTarget = "video";
    if (storyEnabled && storyAvailable && vt >= storyStart && vt < storyEnd) {
      const bounds = getHookBounds(canvasW, canvasH, storyText, 0, storyOffsetY, fontStack(captionFont), captionScale);
      if (bounds && cx >= bounds.x && cx <= bounds.x + bounds.w && cy >= bounds.y && cy <= bounds.y + bounds.h) {
        dragTarget = "story";
      }
    }
    if (hookVisible && dragTarget === "video") {
      const hb = getHookBounds(canvasW, canvasH, hookText, hookOffsetX, hookOffsetY, fontStack(captionFont), captionScale);
      if (hb && cx >= hb.x && cx <= hb.x + hb.w && cy >= hb.y && cy <= hb.y + hb.h) {
        dragTarget = "hook";
      }
    }
    if (ctaVisible && dragTarget === "video") {
      const cb = getEndCardBounds(canvasW, canvasH, ctaHeadline, ctaHandle, ctaOffsetX, ctaOffsetY, fontStack(ctaFont), ctaScale);
      if (cb && cx >= cb.x && cx <= cb.x + cb.w && cy >= cb.y && cy <= cb.y + cb.h) {
        dragTarget = "cta";
      }
    }

    const startStoryY = storyOffsetY;
    const startHookY = hookOffsetY;
    const startCtaY = ctaOffsetY;
    const isHand = modeAt(currentTime) === "hand";
    const framing = editingZoomRef.current ? liveZoomRef.current : zoomValuesAt(vt);
    const startOffX = isHand ? framing.handPanX : framing.offX;
    const startOffY = isHand ? framing.handPanY : framing.offY;

    const move = (ev) => {
      const dx = (ev.clientX - startX) / rect.width;
      const dy = (ev.clientY - startY) / rect.height;
      // Hook and end-card copy travel vertically only: sideways drift would
      // push text out of the centered safe column, so dx is ignored here and
      // X stays pinned at zero. Video/hand framing below keeps both axes.
      if (dragTarget === "hook") {
        setHookOffsetX(0);
        setHookOffsetY(startHookY + dy);
      } else if (dragTarget === "story") {
        setStoryOffsetY(startStoryY + dy);
      } else if (dragTarget === "cta") {
        setCtaOffsetX(0);
        setCtaOffsetY(startCtaY + dy);
      } else if (isHand) {
        updateZoomDraft({ handPanX: startOffX + dx, handPanY: startOffY + dy });
      } else {
        updateZoomDraft({
          offX: Math.max(-100, Math.min(100, Math.round(startOffX + dx * 200))),
          offY: Math.max(-100, Math.min(100, Math.round(startOffY + dy * 200))),
        });
      }
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    // In Real Video there is no phone to resize, so the wheel drives the
    // same video zoom the crop slider owns — otherwise scrolling would
    // silently do nothing in this mode.
    const wheelMode = modeAt(currentTime);
    if (isAppendTime(currentTime) && wheelMode === "realistic") return;
    updateZoomDraft((values) => wheelMode === "hand"
      ? { handZoom: Math.max(RANGES.handZoom.min, Math.min(RANGES.handZoom.max, +(values.handZoom - e.deltaY * 0.0015).toFixed(3))) }
      : wheelMode === "realistic"
      ? { scale: Math.max(RANGES.videoScale.min, Math.min(RANGES.videoScale.max, +(values.scale - e.deltaY * 0.0015).toFixed(3))) }
      : { phoneScale: Math.max(RANGES.scale.min, Math.min(RANGES.scale.max, +(values.phoneScale - e.deltaY * 0.0015).toFixed(3))) });
  };

  const duration = (videoMeta?.d ?? 0) + (appendMeta?.d ?? 0);
  const interval = tickInterval(duration);
  const ticks = [];
  if (duration > 0) {
    for (let t = 0; t <= duration; t += interval) ticks.push(t);
    if (ticks[ticks.length - 1] < duration - interval * 0.3) ticks.push(duration);
  }

  const activeDevice = DEVICES.find((d) => d.id === device) || DEVICES[0];
  const activePreset = PRESETS.find((p) => p.id === preset) || PRESETS[0];
  const safetyCw = activePreset.id === "source" ? Math.round(BASE_PHONE_H * activeDevice.aspect) : activePreset.w;
  const safetyCh = activePreset.id === "source" ? Math.round(BASE_PHONE_H * mockupStretchY) : activePreset.h;
  const hookSafety = hookEnabled
    ? checkOverlaySafety(
        getHookBounds(safetyCw, safetyCh, hookText, hookOffsetX, hookOffsetY, fontStack(captionFont), captionScale),
        safetyCw,
        safetyCh,
        captionScale,
        "hook",
        hookOffsetX,
        hookOffsetY
      )
    : { ok: true, issues: [], message: null };
  const ctaSafety = ctaEnabled
    ? checkOverlaySafety(
        getEndCardBounds(safetyCw, safetyCh, ctaHeadline, ctaHandle, ctaOffsetX, ctaOffsetY, fontStack(ctaFont), ctaScale),
        safetyCw,
        safetyCh,
        ctaScale,
        "cta",
        ctaOffsetX,
        ctaOffsetY
      )
    : { ok: true, issues: [], message: null };

  // The settings panel is its own scroll container and the preview column is
  // pinned beside it.
  //
  // This is the fix for the one that mattered: the preview card carried
  // `position: sticky`, but it sits inside a column that also holds the player,
  // the export bar and the export result — so its sticky travel was bounded by
  // that column and the video scrolled away with the page. Sticky has to be on
  // the COLUMN, and the settings column has to own the scrolling.
  //
  // `max-h-[calc(100vh-12rem)]` on the settings column is what makes the two
  // columns peers: the page itself stops growing, the panel scrolls inside its
  // own box, and the preview stays put no matter how long the panel gets.
  // 12rem is the page chrome above the grid (PageHeader, main padding, grid
  // gap, sticky offset) — without it the capped columns plus the header
  // always exceed the viewport and the page grows a scrollbar beside a
  // studio that fits.
  const settingsRef = useRef(null);
  const appendNotReady = !!appendUrl && !appendMeta;

  return (
    // Radix tooltips need a provider ancestor; the app has none, and the
    // transport buttons are the first tooltips on this page.
    <TooltipProvider delayDuration={200}>
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,0.85fr)_minmax(0,1.3fr)] xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)]">
      <div className="relative min-w-0">
        {/* Own scroll container, own slim scrollbar, and enough right padding that a
            6px bar never sits over a card edge. */}
        <div
          ref={settingsRef}
          inert={recording ? true : undefined}
          className="demo-cta-panel-scroll space-y-3 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-2.5"
        >
        {/* The file input lives outside the collapsible section content on
            purpose. The preview frame's Upload button drives it by ref from
            outside every group, and collapsed groups unmount their children —
            so an input nested in here becomes a null ref the moment another
            group opens, and the button silently stops working. `sr-only`
            keeps it out of sight; the aria-label keeps it named for
            assistive tech. */}
        <input
          ref={fileInputRef}
          type="file"
          accept="video/*"
          aria-label="Choose a video file"
          data-testid="demo-cta-file-input"
          className="sr-only"
          onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
        />
        {/* The added clip drives a separate input for the same reason: one input
            per source, so neither upload can clobber the other. Resetting the
            value lets the same file be picked twice in a row. It only exists
            once a base does — two upload doors with no clip loaded read as a
            broken choice, and the section button below covers the same input. */}
        {videoUrl && (
        <input
          ref={appendInputRef}
          type="file"
          accept="video/*"
          aria-label="Choose a clip to add after base"
          data-testid="append-upload-input"
          className="sr-only"
          onChange={(e) => {
            const file = e.target.files?.[0];
            e.target.value = "";
            if (file) handleAppendFile(file);
          }}
        />
        )}
        <EditorSection title="Source & Look" icon={Film} open={openSections.source} onToggle={() => toggleSection("source")} testId="demo-cta-source">
          {generation ? (
            <>
              <p className="text-xs text-muted-foreground">
                This finished render is the base clip. Use Second clip to add footage after it, or Real Video for a phone overlay.
              </p>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="secondary">Hook + Story</Badge>
                {videoMeta && <span className="text-muted-foreground">{videoMeta.w}x{videoMeta.h} • {videoMeta.d.toFixed(1)}s</span>}
              </div>
              {loadingSource && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading the finished render…
                </p>
              )}
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              Upload one clip to start — footage or a finished render.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            {/* No picker button here. The frame carries the upload action in
                both routes, so a second button in this group was two doors to
                the same input. The input itself lives above the sections —
                the frame's button drives it by ref — since collapsed groups
                unmount their children. */}
            {sourceFileName && (
              <>
                <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={sourceFileName}>
                  {sourceFileName}
                </span>
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-10"
                  onClick={clearSource}
                  title={generation ? "Remove this upload and go back to the finished render" : "Remove this clip and choose another"}
                  data-testid="demo-cta-remove-source"
                >
                  <X className="h-3.5 w-3.5" />
                  <span>Remove</span>
                </Button>
              </>
            )}
          </div>
          {sourceReplaced && generation && (
            <p className="text-xs text-muted-foreground">
              Source replaced; export stays under this Hook + Story.
            </p>
          )}
          <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
            <StylePicker
              label="First clip style"
              hint="Floating phone, hand-held mockup, or the real video full-frame. Drag preview to reframe; in hand mode, pick a scene."
              value={viewMode}
              onChange={(id) => { invalidateSequence(); setViewMode(id); }}
              prefix="view-mode-"
            />
          </div>
          {videoUrl && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input type="checkbox" checked={baseMuted} data-testid="base-audio-mute"
                onChange={(event) => { invalidateSequence(); setBaseMuted(event.target.checked); }} />
              Mute base clip audio in preview and export
            </label>
          )}
          {/* Base scene only. The added clip picks its own scene in Second
              clip, and the painter resolves per segment, so one hand photo
              can open into a different room. */}
          {viewMode === "hand" && (
            <EnvGrid value={envBg} onChange={setEnvBg} prefix="" />
          )}
          {viewMode === "floating" && (
            <>
              <BackgroundPicker value={bg} onChange={setBg} prefix="" />
              <AnimationPicker value={anim} onChange={setAnim} prefix="" />
              <ControlSlider label="Phone size" value={scale} min={RANGES.scale.min} max={RANGES.scale.max} step={RANGES.scale.step} onChange={(phoneScale) => updateZoomDraft({ phoneScale })} testId="phone-size-slider" format={(v) => `${Math.round(v * 100)}%`} />
            </>
          )}
          {viewMode === "hand" && (
            <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
              <SubLabel>Hand size &amp; position</SubLabel>
              <p className="text-xs text-muted-foreground">Drag to move • scroll to zoom</p>
              <ControlSlider label="Zoom" value={handZoom} min={RANGES.handZoom.min} max={RANGES.handZoom.max} step={RANGES.handZoom.step} onChange={(handZoom) => updateZoomDraft({ handZoom })} testId="hand-zoom-slider" format={(v) => `${v.toFixed(2)}x`} />
              <ControlSlider label="H position" value={handPanX} min={RANGES.handPan.min} max={RANGES.handPan.max} step={RANGES.handPan.step} onChange={(handPanX) => updateZoomDraft({ handPanX })} testId="hand-panx-slider" format={(v) => `${Math.round(v * 100)}%`} />
              <ControlSlider label="V position" value={handPanY} min={RANGES.handPan.min} max={RANGES.handPan.max} step={RANGES.handPan.step} onChange={(handPanY) => updateZoomDraft({ handPanY })} testId="hand-pany-slider" format={(v) => `${Math.round(v * 100)}%`} />
              <ResetButton testId="hand-transform-reset-btn" onClick={() => updateZoomDraft({ handZoom: 1, handPanX: 0, handPanY: 0 })}>
                Reset hand framing
              </ResetButton>
            </div>
          )}
        </EditorSection>

        {/* The appended clip lives in its own group so Source & Look stays
            about the base: one clip per group, one style picker per clip.
            Gated on a loaded base — offering an "after" before there is a
            "before" was the second upload button nobody could place. */}
        {videoUrl && (
        <EditorSection title="Second clip" icon={Smartphone} open={openSections.second} onToggle={() => toggleSection("second")} testId="demo-cta-second">
          <p className="text-xs text-muted-foreground">The full base plays first, then this upload, each with its own audio. Export length covers both clips, and each clip keeps its own style.</p>
          <div className="flex flex-wrap items-center gap-2">
            <Button
              variant="secondary"
              size="sm"
              className="h-10"
              onClick={() => appendInputRef.current?.click()}
              data-testid="append-upload-button"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>{appendUrl ? "Replace added clip" : "Add clip after base"}</span>
            </Button>
            {appendName && (
              <span className="min-w-0 flex-1 truncate text-xs text-muted-foreground" title={appendName} data-testid="append-file-name">
                {appendName}
                {appendMeta && Number.isFinite(appendMeta.d) ? ` • ${appendMeta.d.toFixed(1)}s` : ""}
              </span>
            )}
            {appendUrl && (
              <Button
                variant="ghost"
                size="sm"
                className="h-10"
                onClick={removeAppend}
                title="Remove the added clip"
                data-testid="append-remove"
              >
                <X className="h-3.5 w-3.5" />
                <span>Remove</span>
              </Button>
            )}
          </div>
          {appendError && <p role="alert" className="text-xs text-destructive">{appendError}</p>}
          {appendUrl && !appendMeta && !appendError && <p role="status" className="text-xs text-muted-foreground">Loading added clip…</p>}
          {appendUrl && (
            <StylePicker
              label="Added clip style"
              value={appendMode}
              onChange={(id) => { invalidateSequence(); setAppendMode(id); }}
              prefix="append-mode-"
            />
          )}
          {appendMeta && appendMode === "hand" && (
            <EnvGrid value={appendEnv} onChange={setAppendEnv} prefix="append-" />
          )}
          {appendMeta && appendMode === "floating" && (
            <>
              <BackgroundPicker value={appendBg} onChange={setAppendBg} prefix="append-" />
              <AnimationPicker value={appendAnim} onChange={setAppendAnim} prefix="append-" />
            </>
          )}
          {appendUrl && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input type="checkbox" checked={appendOverlays} data-testid="append-overlays"
                onChange={(event) => { invalidateSequence(); setAppendOverlays(event.target.checked); }} />
              Apply text and overlays to the added clip too
            </label>
          )}
          {appendUrl && (
            <label className="flex items-center gap-2 text-xs text-muted-foreground">
              <input type="checkbox" checked={appendMuted} data-testid="append-audio-mute"
                onChange={(event) => { invalidateSequence(); setAppendMuted(event.target.checked); }} />
              Mute added clip audio in preview and export
            </label>
          )}
        </EditorSection>
        )}

        <EditorSection title="Hook Text" icon={Type} open={openSections.hook} onToggle={() => toggleSection("hook")} testId="hook-controls">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid="hook-toggle" checked={hookEnabled} onCheckedChange={(next) => { setHookEnabled(next); if (next) startScopedPreview("hook"); }} />
            Show opening hook text
          </label>
          <p className="text-xs text-muted-foreground">On-screen overlay only; spoken script unchanged.</p>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">Text to show at the opening</span>
              <div className="flex items-center gap-1.5" role="group" aria-label="Hook copy variants">
                <Chip
                  onClick={async () => {
                    if (await openingMessages.surprise()) startScopedPreview("hook");
                  }}
                  disabled={openingMessages.generating || recording}
                  testId="hook-variant-surprise"
                  ariaLabel="Generate a fresh hook message"
                >
                  {openingMessages.generating ? "Writing fresh openings…" : "Surprise me"}
                </Chip>
              </div>
            </div>
            <textarea
              data-testid="hook-text-input"
              aria-label="Text to show at the opening"
              value={hookText}
              onChange={(e) => openingMessages.updateText(e.target.value)}
              rows={3}
              placeholder="I built this so I'd stop journaling in Notes app"
              className={TEXTAREA_CLASS}
            />
          </div>
          {openingMessages.error && (
            <p role="alert" className="text-xs text-destructive" data-testid="hook-message-error">
              {openingMessages.error} <Link to="/brand">Review App Profile</Link>
            </p>
          )}
          <ControlSlider label="On screen" value={hookDuration} min={RANGES.hookDuration.min} max={RANGES.hookDuration.max} step={RANGES.hookDuration.step} onChange={(val) => { setHookDuration(val); ensureScopedPreview("hook"); }} testId="hook-duration-slider" format={(v) => `${v.toFixed(1)}s`} />
          {/* Caption face: each tile set in its own face so the choice is
              visual, not a name to imagine. Selected state is the indigo
              ring, the same language as the accent swatches below. */}
          <FontDisclosure
            testId="caption-fonts-disclosure"
            open={openDisclosure === "caption-font"}
            onToggle={() => toggleDisclosure("caption-font")}
            groupLabel="Caption font"
            currentLabel={(OVERLAY_FONTS.find((f) => f.id === captionFont) || {}).label}
          >
            <div className="grid grid-cols-3 gap-2">
              {OVERLAY_FONTS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  data-testid={`caption-font-${f.id}`}
                  onClick={() => { setCaptionFont(f.id); startScopedPreview("hook"); }}
                  aria-pressed={captionFont === f.id}
                  className={`focus-ring flex items-center gap-2 rounded-xl border px-3 py-2 text-left transition-colors ${
                    captionFont === f.id
                      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                  }`}
                >
                  <span aria-hidden="true" style={{ fontFamily: f.stack }} className="text-sm">Aa</span>
                  <span className="text-xs text-muted-foreground">{f.label}</span>
                </button>
              ))}
            </div>
          </FontDisclosure>
          {/* Shared text treatment for hook, story and end card: one picker
              here, one state, all three painters. Scoped replay resets to
              the hook so the change is visible without scrubbing. */}
          <div className="space-y-2">
            <GroupLabel>Text style</GroupLabel>
            <div className="grid grid-cols-3 gap-2" role="group" aria-label="Text style">
              {TEXT_STYLES.map((s) => (
                <button
                  key={s.id}
                  type="button"
                  data-testid={`text-style-${s.id}`}
                  onClick={() => { setTextStyle(s.id); startScopedPreview("hook"); }}
                  aria-pressed={textStyle === s.id}
                  className={`focus-ring rounded-xl border px-3 py-2 text-left text-xs transition-colors ${
                    textStyle === s.id
                      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                  }`}
                >{s.label}</button>
              ))}
            </div>
            <p className="text-xs text-muted-foreground">Hook, story &amp; end card share this style.</p>
          </div>
          <AccentPicker testPrefix="hook-accent" accent={overlayAccent} onAccentChange={(c) => { setOverlayAccent(c); startScopedPreview("hook"); }} />
          <AnimDisclosure
            testId="caption-anim-disclosure"
            open={openDisclosure === "caption-animation"}
            onToggle={() => toggleDisclosure("caption-animation")}
            currentLabel={(OVERLAY_ANIMS.find((a) => a.id === captionAnim) || {}).label}
          >
            <EntranceGrid value={captionAnim} onChange={(id) => { setCaptionAnim(id); startScopedPreview("hook"); }} testPrefix="caption-anim" ariaLabel="Caption animation" />
            <div className="space-y-2">
              <ControlSlider label="Text size" value={captionScale} min={RANGES.overlayScale.min} max={RANGES.overlayScale.max} step={RANGES.overlayScale.step} onChange={(val) => { setCaptionScale(val); ensureScopedPreview("hook"); }} testId="caption-size-slider" format={(v) => `${Math.round(v * 100)}%`} />
              <ScalePresets value={captionScale} onChange={(val) => { setCaptionScale(val); startScopedPreview("hook"); }} testPrefix="caption-size-preset" ariaLabel="Caption size presets" />
            </div>
            {!hookSafety.ok && (
              <div
                role="status"
                data-testid="hook-safety-warning"
                className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-foreground"
              >
                <span className="flex items-center gap-1.5">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                  <span>{hookSafety.message}</span>
                </span>
                <ResetButton
                  testId="hook-safety-fix"
                  onClick={() => {
                    setHookOffsetX(0);
                    setHookOffsetY(0);
                    if (captionScale < 0.8) setCaptionScale(1);
                  }}
                >
                  Fit safe area
                </ResetButton>
              </div>
            )}
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs italic text-muted-foreground">Drag hook text on preview to reposition</p>
              <VerticalNudge label="Hook text position" upTestId="hook-nudge-up" downTestId="hook-nudge-down" onNudge={(dy) => setHookOffsetY((y) => y + dy)} />
            </div>
            {(hookOffsetX !== 0 || hookOffsetY !== 0) && (
              <ResetButton onClick={() => { setHookOffsetX(0); setHookOffsetY(0); }}>Reset position</ResetButton>
            )}
          </AnimDisclosure>
        </EditorSection>

        <EditorSection title="Story Text" icon={Type} open={openSections.story} onToggle={() => toggleSection("story")} testId="story-controls">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid="story-toggle" checked={storyEnabled} onCheckedChange={setStoryEnabled} />
            Show Story text
          </label>
          <label className="block space-y-2">
            <span className="text-xs text-muted-foreground">Your message</span>
            <textarea
              data-testid="story-text-input"
              value={storyText}
              onChange={(e) => setStoryText(e.target.value)}
              rows={3}
              placeholder="Add a detail, tip, or moment to your story"
              className={TEXTAREA_CLASS}
            />
          </label>
          <p className="text-xs text-muted-foreground">Uses Hook Text style; spoken script unchanged.</p>
          {storyAvailable ? (
            <>
              <p className="text-xs text-muted-foreground" data-testid="story-timing-hint">
                Available: {storyWindow.min.toFixed(1)}–{storyWindow.max.toFixed(1)}s. Auto-keeps clear of hook & end card.
              </p>
              <ControlSlider label="Starts at" value={storyStart} min={storyWindow.min} max={Math.max(storyWindow.min, storyEnd - 0.1)} step={0.1} onChange={(start) => setStoryTiming({ start, end: storyEnd })} testId="story-start-slider" format={(v) => `${v.toFixed(1)}s`} />
              <ControlSlider label="Ends at" value={storyEnd} min={Math.min(storyWindow.max, storyStart + 0.1)} max={storyWindow.max} step={0.1} onChange={(end) => setStoryTiming({ start: storyStart, end })} testId="story-end-slider" format={(v) => `${v.toFixed(1)}s`} />
              <Button variant="outline" size="sm" disabled={!storyEnabled || !storyText.trim()} onClick={() => handleSeek(storyStart + Math.min(0.4, (storyEnd - storyStart) / 2))} data-testid="story-preview-button">Preview Story text</Button>
            </>
          ) : (
            <p role="status" className="text-xs text-muted-foreground" data-testid="story-no-room">
              {videoMeta ? "No room for Story text. Shorten hook or end card to free time." : "Upload a clip to time Story text."}
            </p>
          )}
          <div className="flex items-center justify-between gap-2">
            <p className="text-xs italic text-muted-foreground">Drag Story text on preview to reposition</p>
            <VerticalNudge label="Story text position" upTestId="story-nudge-up" downTestId="story-nudge-down" onNudge={(dy) => setStoryOffsetY((y) => y + dy)} />
          </div>
          {storyOffsetY !== 0 && <ResetButton onClick={() => setStoryOffsetY(0)}>Reset position</ResetButton>}
        </EditorSection>

        <EditorSection title="End Card CTA" icon={Megaphone} open={openSections.cta} onToggle={() => toggleSection("cta")} testId="cta-controls">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid="cta-toggle" checked={ctaEnabled} onCheckedChange={(next) => { setCtaEnabled(next); if (next) startScopedPreview("cta"); }} />
            Show closing call-to-action card
          </label>
          <p className="text-xs text-muted-foreground">On-screen end card. Write one clear next step.</p>
          <div className="space-y-2">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="text-xs text-muted-foreground">Call-to-action text</span>
              <div className="flex items-center gap-1.5" role="group" aria-label="CTA copy variants">
                <Chip
                  onClick={() => { surpriseCtaVariant(); startScopedPreview("cta"); }}
                  testId="cta-variant-surprise"
                  ariaLabel="Generate a fresh call-to-action"
                >
                  Surprise me
                </Chip>
              </div>
            </div>
            <input
              data-testid="cta-headline-input"
              aria-label="Call-to-action text"
              value={ctaHeadline}
              onChange={(e) => updateCtaHeadline(e.target.value)}
              placeholder="Try it free — link in bio"
              className={INPUT_CLASS}
            />
          </div>
          <label className="space-y-2">
            <span className="text-xs text-muted-foreground">Social handle (optional)</span>
            <input
              data-testid="cta-handle-input"
              value={ctaHandle}
              onChange={(e) => setCtaHandle(e.target.value)}
              placeholder="@yourhandle"
              className={INPUT_CLASS}
            />
          </label>
          <div className="space-y-2">
            <ControlSlider
              label="Visible for"
              value={ctaDuration}
              min={RANGES.ctaDuration.min}
              max={RANGES.ctaDuration.max}
              step={RANGES.ctaDuration.step}
              onChange={(val) => {
                setCtaTimingMode("custom");
                setCtaDuration(val);
                ensureScopedPreview("cta");
              }}
              testId="cta-duration-slider"
              format={(v) => (ctaTimingMode === "full" ? (duration > 0 ? `${duration.toFixed(1)}s` : "Full") : `${v.toFixed(1)}s`)}
            />
            <div className="flex items-center gap-2" role="group" aria-label="End-card timing presets">
              {CTA_TIMING_PRESETS.map((p) => {
                const active =
                  ctaTimingMode === p.id ||
                  (ctaTimingMode === "custom" && p.seconds !== null && Math.abs(ctaDuration - p.seconds) < 1e-6);
                return (
                  <button
                    key={p.id}
                    type="button"
                    data-testid={`cta-timing-${p.id}`}
                    onClick={() => { selectCtaTimingPreset(p.id); startScopedPreview("cta"); }}
                    aria-pressed={active}
                    className={`focus-ring flex-1 rounded-xl border px-3 py-2 text-xs transition-colors ${
                      active
                        ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-foreground"
                        : "border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--hairline-strong)]"
                    }`}
                  >
                    {p.label}
                  </button>
                );
              })}
            </div>
          </div>
          <FontDisclosure
            testId="cta-fonts-disclosure"
            open={openDisclosure === "cta-font"}
            onToggle={() => toggleDisclosure("cta-font")}
            groupLabel="CTA font"
            currentLabel={(OVERLAY_FONTS.find((f) => f.id === ctaFont) || {}).label}
          >
            <div className="grid grid-cols-3 gap-2">
              {OVERLAY_FONTS.map((f) => (
                <button
                  key={f.id}
                  type="button"
                  data-testid={`cta-font-${f.id}`}
                  onClick={() => { setCtaFont(f.id); startScopedPreview("cta"); }}
                  aria-pressed={ctaFont === f.id}
                  className={`focus-ring flex items-center gap-2 rounded-xl border px-3 py-2 text-left transition-colors ${
                    ctaFont === f.id
                      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                  }`}
                >
                  <span aria-hidden="true" style={{ fontFamily: f.stack }} className="text-sm">Aa</span>
                  <span className="text-xs text-muted-foreground">{f.label}</span>
                </button>
              ))}
            </div>
          </FontDisclosure>
          <AnimDisclosure
            testId="cta-anim-disclosure"
            open={openDisclosure === "cta-animation"}
            onToggle={() => toggleDisclosure("cta-animation")}
            currentLabel={(OVERLAY_ANIMS.find((a) => a.id === ctaAnim) || {}).label}
          >
            <EntranceGrid value={ctaAnim} onChange={(id) => { setCtaAnim(id); startScopedPreview("cta"); }} testPrefix="cta-anim" ariaLabel="CTA animation" />
            <div className="space-y-2">
              <ControlSlider label="Text size" value={ctaScale} min={RANGES.overlayScale.min} max={RANGES.overlayScale.max} step={RANGES.overlayScale.step} onChange={(val) => { setCtaScale(val); ensureScopedPreview("cta"); }} testId="cta-size-slider" format={(v) => `${Math.round(v * 100)}%`} />
              <ScalePresets value={ctaScale} onChange={(val) => { setCtaScale(val); startScopedPreview("cta"); }} testPrefix="cta-size-preset" ariaLabel="CTA size presets" />
            </div>
            {!ctaSafety.ok && (
            <div
              role="status"
              data-testid="cta-safety-warning"
              className="flex flex-wrap items-center justify-between gap-2 rounded-xl border border-amber-500/30 bg-amber-500/10 px-3 py-2 text-xs text-foreground"
            >
              <span className="flex items-center gap-1.5">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-amber-400" />
                <span>{ctaSafety.message}</span>
              </span>
              <ResetButton
                testId="cta-safety-fix"
                onClick={() => {
                  setCtaOffsetX(0);
                  setCtaOffsetY(0);
                  if (ctaScale < 0.8) setCtaScale(1);
                }}
              >
                Fit safe area
              </ResetButton>
            </div>
          )}
            <div className="flex items-center justify-between gap-2">
              <p className="text-xs italic text-muted-foreground">Drag the end card up or down on the preview to reposition</p>
              <VerticalNudge label="End card position" upTestId="cta-nudge-up" downTestId="cta-nudge-down" onNudge={(dy) => setCtaOffsetY((y) => y + dy)} />
            </div>
            {(ctaOffsetX !== 0 || ctaOffsetY !== 0) && (
              <ResetButton onClick={() => { setCtaOffsetX(0); setCtaOffsetY(0); }}>Reset position</ResetButton>
            )}
          <AccentPicker testPrefix="overlay-accent" accent={overlayAccent} onAccentChange={(c) => { setOverlayAccent(c); startScopedPreview("cta"); }} />
            <p className="text-xs leading-snug text-muted-foreground">
              Laid out inside TikTok&apos;s safe area — clear of the right icon rail and bottom caption strip.
            </p>
          </AnimDisclosure>
          <div className="space-y-3 border-t border-[color:var(--hairline)] pt-3" data-testid="look-save-review">
            <SubLabel>Happy with your look?</SubLabel>
            <p className="text-xs text-muted-foreground">
              Review the hook &amp; end card in the preview, then save their fonts, entrances, text sizes &amp; accent for your next video. Footage, copy &amp; zoom locks are not included.
            </p>
            <div className="space-y-2" data-testid="look-presets-block">
              <SubLabel>Your looks</SubLabel>
              <div className="flex flex-wrap items-center gap-1.5" role="group" aria-label="Look presets">
                {allLookPresets.map((look) => {
                  const active = isLookPresetActive(look);
                  return (
                    <div key={look.id} className="inline-flex items-center gap-1">
                      <Chip
                        active={active}
                        onClick={() => { applyLookPreset(look); startScopedPreview(hookEnabled ? "hook" : "cta"); }}
                        testId={`look-preset-${look.id}`}
                        ariaLabel={look.name}
                      >
                        {look.name}
                      </Chip>
                      {!look.builtin && (
                        <button
                          type="button"
                          data-testid={`delete-look-preset-${look.id}`}
                          aria-label={`Remove ${look.name}`}
                          onClick={() => handleDeleteLookPreset(look.id)}
                          className="focus-ring rounded-full p-1.5 text-muted-foreground transition-colors hover:text-foreground"
                        >
                          <X className="h-3 w-3" />
                        </button>
                      )}
                    </div>
                  );
                })}
              </div>
            </div>
            {!canReviewLook && (
              <p className="text-xs text-muted-foreground" data-testid="look-review-hint">
                {recording ? "Wait for export to finish before saving a look." : "Upload a playable clip to review your look before saving."}
              </p>
            )}
            <label className="flex items-start gap-2 text-xs text-muted-foreground">
              <Checkbox
                data-testid="look-reviewed-checkbox"
                checked={lookReviewed}
                disabled={!canReviewLook}
                onCheckedChange={(checked) => setReviewedLookKey(checked === true ? lookReviewKey : null)}
              />
              I&apos;ve reviewed the current hook &amp; end-card styling in the preview.
            </label>
            <div className="flex flex-wrap items-center gap-2">
              <input
                type="text"
                data-testid="look-preset-name-input"
                aria-label="Name your finished look"
                value={newLookName}
                onChange={(e) => setNewLookName(e.target.value)}
                placeholder="Name current look (e.g. Founder raw)"
                disabled={!canReviewLook}
                className={`${INPUT_CLASS} min-w-0 flex-1 basis-40 disabled:opacity-50`}
              />
              <Button
                type="button"
                variant="secondary"
                size="sm"
                data-testid="look-preset-save-btn"
                disabled={!canSaveLook}
                onClick={handleSaveLookPreset}
                className="shrink-0"
              >
                Save look
              </Button>
            </div>
            <p role="status" className="text-xs text-muted-foreground" data-testid="look-save-status">
              {savedLookNotice?.key === lookReviewKey ? `“${savedLookNotice.name}” saved above.` : ""}
            </p>
          </div>
        </EditorSection>

        {/* The TikTok spec used to live in an Output group of its own, but with
            a single upload-ready format there is nothing to choose: the Export
            button's title and the result card already carry the dimensions,
            frame rate and container, so a group just to restate them was a
            fifth stop on a panel that describes one clip. Rarely touched.
            Mockup height, screen position and crop live here
            because they are set once and then left alone; keeping them in the
            main groups is what made the panel taller than the preview it is
            meant to describe. */}
        <EditorSection title="Advanced" icon={SlidersHorizontal} open={openSections.advanced} onToggle={() => toggleSection("advanced")}>
          <p className="text-xs text-muted-foreground">Fine-tuning for mockup, placement, crop. Rarely needed.</p>
          <div className="space-y-2">
            <SubLabel>Mockup height</SubLabel>
            <div className="flex items-center gap-2">
              <Slider
                value={[mockupStretchY]}
                min={RANGES.mockupStretchY.min}
                max={RANGES.mockupStretchY.max}
                step={RANGES.mockupStretchY.step}
                onValueChange={([next]) => setMockupStretchY(next)}
                className="flex-1"
                aria-label="Mockup height"
              />
              <span className="w-12 shrink-0 text-right font-mono text-xs tabular-nums text-foreground">
                {Math.round(mockupStretchY * 100)}%
              </span>
              <ResetButton onClick={() => setMockupStretchY(1)}>Reset</ResetButton>
            </div>
          </div>
          {(viewMode === "hand" || (appendMeta && appendMode === "hand")) && (
            <div className="space-y-2" data-testid="screen-position-controls">
              <SubLabel>Screen position</SubLabel>
              {[
                ["Left", screenX, setScreenX, "left"],
                ["Top", screenY, setScreenY, "top"],
                ["Width", screenW, setScreenW, "width"],
                ["Height", screenH, setScreenH, "height"],
              ].map(([label, val, setter, key]) => (
                <div key={key} className="space-y-2">
                  <div className="flex items-baseline justify-between gap-2">
                    <FieldLabel>{label}</FieldLabel>
                    <span className="font-mono text-xs tabular-nums text-foreground">{(val * 100).toFixed(1)}</span>
                  </div>
                  <Slider
                    data-testid={`screen-${key}-slider`}
                    value={[val]}
                    min={RANGES.screen.min}
                    max={RANGES.screen.max}
                    step={RANGES.screen.step}
                    onValueChange={([next]) => setter(next)}
                  />
                </div>
              ))}
              <ResetButton testId="screen-reset-btn" onClick={() => { setScreenX(DEFAULT_SCREEN.x); setScreenY(DEFAULT_SCREEN.y); setScreenW(DEFAULT_SCREEN.w); setScreenH(DEFAULT_SCREEN.h); }}>
                Reset to photo screen
              </ResetButton>
            </div>
          )}
          {videoUrl && (
            <div className="space-y-2">
              <SubLabel>Video crop</SubLabel>
              <div className="flex items-center justify-between gap-2">
                <select value={videoFit} onChange={(e) => setVideoFit(e.target.value)} className={CONTROL_CLASS} aria-label="Video fit">
                  <option value="cover">Cover</option>
                  <option value="contain">Contain</option>
                  <option value="fill">Fill</option>
                </select>
                <ResetButton onClick={() => { setVideoFit("cover"); updateZoomDraft({ scale: 1, offX: 0, offY: 0 }); }}>Reset</ResetButton>
              </div>
              {/* What each mode actually does, and the source size it is doing it
                  to. "Fill" reads as a synonym for "Cover" until you have seen
                  them side by side, and picking Fill to remove a blank strip
                  used to change nothing at all. Naming the consequence is the
                  difference between a control and a guess. */}
              <p className="text-xs text-muted-foreground">
                {VIDEO_FIT_HINTS[videoFit] || VIDEO_FIT_HINTS.cover}
                {videoMeta ? ` Source ${videoMeta.w}×${videoMeta.h}.` : ""}
              </p>
              <ControlSlider label="Zoom" value={videoScale} min={RANGES.videoScale.min} max={RANGES.videoScale.max} step={RANGES.videoScale.step} onChange={(scale) => updateZoomDraft({ scale })} format={(v) => `${v.toFixed(2)}x`} />
              <ControlSlider label="H offset" value={videoOffsetX} min={RANGES.videoOffset.min} max={RANGES.videoOffset.max} step={RANGES.videoOffset.step} onChange={(v) => updateZoomDraft({ offX: Math.round(v) })} format={(v) => `${Math.round(v)}%`} />
              <ControlSlider label="V offset" value={videoOffsetY} min={RANGES.videoOffset.min} max={RANGES.videoOffset.max} step={RANGES.videoOffset.step} onChange={(v) => updateZoomDraft({ offY: Math.round(v) })} format={(v) => `${Math.round(v)}%`} />
            </div>
          )}
        </EditorSection>
        </div>
      </div>

      {/* Sticky on the COLUMN, not on the preview card inside it. A sticky card
          bounded by a column that also holds the player and the export bar has
          almost no travel, which is exactly the bug this replaces: the video
          scrolled off the top while the settings were still being adjusted.
          The column caps at the viewport and scrolls internally when its
          content (frame floor, player, export) exceeds it, so the frame never
          has to shrink below ~400px tall to keep everything on screen. */}
      {/* `demo-cta-column` carries the one width token the frame and the export
          button both resolve, so they cannot drift apart. `data-player` tells
          the stylesheet whether the player bar is in the column, because its
          104px comes out of the frame's height budget when it is. */}
      <div
        className="demo-cta-column demo-cta-panel-scroll min-w-0 space-y-3 lg:sticky lg:top-6 lg:max-h-[calc(100vh-12rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-1"
        data-player={videoUrl && videoMeta ? "on" : "off"}
      >
        
        {/* A fixed 9:16 frame rather than a box that grows to the canvas.
            Portrait output filled the width of a flexible card and left black
            bars either side; a real aspect frame makes the preview the shape
            the export will be, and the empty state can share it. Its width comes
            from `--demo-cta-frame-w`, which spends the column's leftover height
            on the video. */}
        <div
          className={`demo-cta-frame mx-auto flex items-center justify-center overflow-hidden rounded-xl border ${
            videoUrl ? "border-[color:var(--hairline)] bg-black" : "border-dashed border-[color:var(--hairline-strong)] bg-secondary/20"
          }`}
        >
          {videoUrl ? (
            <canvas
              ref={previewCanvasRef}
              role="img"
              aria-label="Styled video preview. Drag to adjust the framing, or use the zoom and position sliders."
              className="block h-full w-full cursor-grab touch-none active:cursor-grabbing"
              onPointerDown={handlePointerDown}
              onWheel={handleWheel}
            />
          ) : loadingSource ? (
            <div className="h-full w-full animate-pulse bg-secondary/40" role="status" aria-label="Loading the finished render">
              <span className="sr-only">Loading the finished render…</span>
            </div>
) : (
              // The whole empty box opens the picker: only the button did,
              // so clicks on the copy and padding fell on dead space. Button
              // clicks are excluded below so they drive the file input
              // instead — except the library shortcut, which opens the
              // History panel. Keyboard users keep the real buttons.
              <div
                className="cursor-pointer px-6 text-center"
                title="Upload a clip to style it"
                data-testid="demo-cta-frame-empty"
                onClick={(event) => {
                  if (event.target.closest("a, button")) return;
                  fileInputRef.current?.click();
                }}
              >
                <Button
                  type="button"
                  variant="accent"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  data-testid="demo-cta-frame-upload"
                >
                  <Upload className="h-3.5 w-3.5" />
                  Upload a clip
                </Button>
                <p className="mt-2 text-xs text-muted-foreground">Upload one clip to style it.</p>
                <p className="my-2 text-xs text-muted-foreground">or</p>
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => setHistoryOpen(true)}
                  data-testid="demo-cta-frame-history"
                >
                  Choose from library
                </Button>
              </div>
            )}
        </div>

        {/* The second door to base footage, beside the frame instead of in
            the settings: uploading a clip and picking a finished History
            render are one choice made where the clip lands, so they sit
            together. The toggle keeps its testid and panel wiring — only
            the address changed — and it stays mounted with a loaded clip
            so a base can still be swapped after it loads. */}
        <div className="space-y-2" data-testid="demo-cta-history-source">
          <Button
            type="button"
            variant="secondary"
            size="sm"
            className="h-10 w-full"
            onClick={() => setHistoryOpen((v) => !v)}
            aria-expanded={historyOpen}
            aria-controls={historyOpen ? historyPanelId : undefined}
            data-testid="history-source-toggle"
          >
            {historyOpen ? "Hide History" : "Choose from History"}
          </Button>
          {historyOpen && (
            <div id={historyPanelId} className="space-y-1.5" role="group" aria-label="History renders">
              {historyError && <p className="text-xs text-destructive">{historyError}</p>}
              {historyRows === null && !historyError && (
                <p className="flex items-center gap-2 text-xs text-muted-foreground">
                  <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading finished renders…
                </p>
              )}
              {historyRows !== null && historyRows.length === 0 && !historyError && (
                <p className="text-xs text-muted-foreground">No completed renders with a playable copy yet.</p>
              )}
              {historyRows !== null && historyRows.map((row) => (
                <button
                  key={row.id}
                  type="button"
                  onClick={() => attachHistoryVideo(row)}
                  disabled={attachingId !== null}
                  data-testid={`history-source-attach-${row.id}`}
                  className="focus-ring flex w-full items-center justify-between gap-2 rounded-xl border border-[color:var(--hairline)] px-3 py-2 text-left text-xs transition-colors hover:border-[color:var(--hairline-strong)] disabled:opacity-50"
                >
                  <span className="min-w-0 flex-1 truncate text-foreground">
                    {row.brand_name || "Untitled render"}{row.duration ? ` • ${Math.round(row.duration)}s` : ""}
                  </span>
                  <span className="shrink-0 text-muted-foreground">
                    {attachingId === row.id ? "Attaching…" : "Use as source"}
                  </span>
                </button>
              ))}
            </div>
          )}
        </div>

        {videoUrl && videoMeta && (
          /* A plain bar, not a card: the preview is chromeless, so a boxed
             player under a boxed preview was one box too many. It stays
             full-column — deliberately wider than the frame and the export
             button, which share a width with each other. overflow-x-clip trims
             the 8px the scrubber ticks and the seek knob bleed past 0%/100%:
             without it the column grows a horizontal bar under a player that
             otherwise fits. Tooltips are portalled, so clipping here cuts
             nothing interactive. */
          <div className="space-y-3 overflow-x-clip" data-testid="demo-cta-player" inert={recording ? true : undefined}>
              {/* Scrubber first: tick marks and zoom zones stay clickable but lose
                  their text labels — the readout lives once, beside the play
                  button — so the whole block is a compact strip above the one
                  control row instead of a tall timeline. */}
              <div className="space-y-1" data-testid="demo-cta-scrubber">
                <div className="relative h-3 select-none" role="group" aria-label="Seek to a time">
                  {ticks.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => handleSeek(t)}
                      title={formatTime(t)}
                      aria-label={`Seek to ${formatTime(t)}`}
                      className="focus-ring group absolute top-0 flex h-3 w-4 -translate-x-1/2 cursor-pointer items-start justify-center rounded"
                      style={{ left: `${(t / duration) * 100}%` }}
                    >
                      <span className="h-2 w-px bg-muted-foreground/30 transition group-hover:bg-muted-foreground/60" />
                    </button>
                  ))}
                </div>

                {/* Always rendered, even with no locks. The column spends a fixed
                    104px on the player bar when it sizes the frame, so a strip
                    that appeared and disappeared with the first keyframe would
                    silently resize the video the moment someone locked a zoom.
                    Empty, it is an 8px gap between two rules. */}
                <div
                  className="relative h-2 overflow-hidden rounded-full bg-secondary/60"
                  role="img"
                  aria-label={zoomKeyframes.length > 0 ? `${zoomKeyframes.length} zoom ${zoomKeyframes.length === 1 ? "lock" : "locks"}` : "No zoom locks yet"}
                >
                  {zoomKeyframes.length === 0 && <span className="sr-only">No zoom locks yet</span>}
                  {sortedKeyframes.map((seg, i, sorted) => {
                    const end = sorted[i + 1]?.time ?? duration;
                    return (
                      <div
                        key={seg.id}
                        className="absolute inset-y-0 border-l border-amber-400/40 bg-amber-400/20"
                        style={{
                          left: `${(seg.time / duration) * 100}%`,
                          width: `${((end - seg.time) / duration) * 100}%`,
                        }}
                        title={`${formatTime(seg.time)} → ${formatTime(end)}: ${describeFraming(viewMode, seg)} · ${seg.scale.toFixed(2)}x video`}
                      />
                    );
                  })}
                </div>

                {/* The strip is a real slider, not just a pointer surface:
                    ticks and transport buttons already seek, but a keyboard or
                    screen-reader user lands here for continuous scrubbing.
                    Arrows move a second (matching the −1s/+1s buttons), Home
                    and End jump to the clip ends. Space is left alone: the
                    global transport shortcut owns it and toggles playback. */}
                <div
                  className="group relative h-6 cursor-pointer"
                  role="slider"
                  tabIndex={0}
                  aria-label="Seek"
                  aria-valuemin={0}
                  aria-valuemax={duration > 0 ? duration : 0}
                  aria-valuenow={duration > 0 ? currentTime : 0}
                  aria-valuetext={`${formatTime(currentTime)} of ${formatTime(duration)}`}
                  onKeyDown={(e) => {
                    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
                    e.preventDefault();
                    if (e.key === "ArrowLeft") handleSeek(Math.max(0, currentTime - 1));
                    else if (e.key === "ArrowRight") handleSeek(Math.min(duration, currentTime + 1));
                    else if (e.key === "Home") handleSeek(0);
                    else handleSeek(duration);
                  }}
                  onPointerDown={(e) => {
                    const rect = e.currentTarget.getBoundingClientRect();
                    const pct = Math.max(0, Math.min(1, (e.clientX - rect.left) / rect.width));
                    handleSeek(pct * duration);
                    setIsSeeking(true);

                    const onMove = (ev) => {
                      const p = Math.max(0, Math.min(1, (ev.clientX - rect.left) / rect.width));
                      handleSeek(p * duration);
                    };
                    const onUp = () => {
                      setIsSeeking(false);
                      window.removeEventListener("pointermove", onMove);
                      window.removeEventListener("pointerup", onUp);
                    };
                    window.addEventListener("pointermove", onMove);
                    window.addEventListener("pointerup", onUp);
                  }}
                >
                  <div className="absolute left-0 right-0 top-1/2 h-2.5 -translate-y-1/2 rounded-full border border-[color:var(--hairline)] bg-secondary/60" />
                  <div
                    className="absolute left-0 top-1/2 h-2.5 -translate-y-1/2 rounded-full bg-[color:var(--brand-indigo)]"
                    style={{ width: `${duration > 0 ? (currentTime / duration) * 100 : 0}%` }}
                  />
                  {duration > 0 && zoomKeyframes.map((kf) => (
                    <div
                      key={kf.id}
                      className="pointer-events-none absolute top-1/2 z-10 h-3 w-3 -translate-y-1/2 rotate-45 rounded-sm border border-amber-500 bg-amber-400"
                      style={{ left: `calc(${(kf.time / duration) * 100}% - 6px)` }}
                    />
                  ))}
                  <div
                    className="pointer-events-none absolute top-1/2 z-20 h-4 w-4 -translate-y-1/2 rounded-full border-2 border-[color:var(--brand-indigo)] bg-background"
                    style={{ left: `calc(${duration > 0 ? (currentTime / duration) * 100 : 0}% - 8px)` }}
                  />
                </div>
              </div>

                {/* Single control row: transport group on the left, Export +
                    Lock + Clear buttons on the right. The time readout moved up here from below the
                    scrubber so nothing reads twice. Gaps are gap-x-3/gap-y-3 —
                    the header-action-row token — so the seven 44px targets stop
                    reading as one dense block; the buttons keep their measured
                    size. Wrap below xl so the row never overflows narrow
                    columns; nowrap at xl where the 650px column is measured to
                    hold it. */}
                <div className="flex flex-wrap items-center gap-x-3 gap-y-3 xl:flex-nowrap">
                  <div className="flex items-center gap-2" role="group" aria-label="Playback controls">
                    <TransportButton
                      label={isPlaying ? "Pause" : "Play"}
                      onClick={togglePlayPause}
                      testId="transport-play"
                    >
                      {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                    </TransportButton>
                    <TransportButton
                      label="Back 1 second"
                      onClick={() => handleSeek(Math.max(0, currentTime - 1))}
                      testId="transport-back-1s"
                    >
                      <span className="font-mono text-xs">−1s</span>
                    </TransportButton>
                    <TransportButton
                      label="Back 1 frame (1/30s)"
                      onClick={() => handleSeek(Math.max(0, currentTime - 1 / 30))}
                      testId="transport-back-frame"
                    >
                      <ChevronLeft className="h-4 w-4" />
                    </TransportButton>
                    <TransportButton
                      label="Forward 1 frame (1/30s)"
                      onClick={() => handleSeek(Math.min(duration, currentTime + 1 / 30))}
                      testId="transport-forward-frame"
                    >
                      <ChevronRight className="h-4 w-4" />
                    </TransportButton>
                    <TransportButton
                      label="Forward 1 second"
                      onClick={() => handleSeek(Math.min(duration, currentTime + 1))}
                      testId="transport-forward-1s"
                    >
                      <span className="font-mono text-xs">+1s</span>
                    </TransportButton>
                    <TransportButton
                      label={previewMuted ? "Unmute preview audio" : "Mute preview audio"}
                      onClick={togglePreviewMuted}
                      testId="transport-mute"
                    >
                      {previewMuted ? <VolumeX className="h-4 w-4" /> : <Volume2 className="h-4 w-4" />}
                    </TransportButton>
                  </div>
                  <div className="flex items-baseline gap-1.5 px-1">
                    <span className="font-mono text-sm font-semibold tabular-nums tracking-tight">
                      {formatTime(currentTime)}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">/</span>
                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                      {formatTime(duration)}
                    </span>
                  </div>
                  {/* Button-only cluster on the right: Export, + Lock, Clear.
                      No label or description — the timeline strip above and the
                      locked-segments disclosure below already say what locks
                      exist. w-full drops this cluster onto its own line below
                      xl; xl:w-auto rejoins the single row where the 650px
                      column holds it. */}
                  <div className="ml-auto flex min-w-0 flex-wrap w-full items-center justify-end gap-x-2 gap-y-2 xl:w-auto">
                    {/* Export lives here, not in a bar of its own. The primary
                        action beside the lock controls is where a decision gets
                        made — a separate bottom bar meant the column spent 44px
                        plus a gap on a button that could just as well sit in
                        the row it belongs to. */}
                    <Button
                      type="button"
                      variant="accent"
                      size="sm"
                      disabled={!videoUrl || !videoMeta || recording || saving || appendNotReady}
                      onClick={exportVideo}
                      data-testid="demo-cta-export"
                      className="shrink-0"
                      title="Export TikTok MP4 · 1080×1920 · 30 fps"
                    >
                      {recording ? (
                        <><Loader2 className="h-3.5 w-3.5 animate-spin" /> {Math.round(progress * 100)}%</>
                      ) : (
                        <><Smartphone className="h-3.5 w-3.5" /> Export</>
                      )}
                    </Button>
                    <Button type="button" variant="secondary" size="sm" className="shrink-0" onClick={handleCaptureZoomLock} title={`Lock the current zoom at ${formatTime(currentTime)}`}>
                      + Lock
                    </Button>
                    {zoomKeyframes.length > 0 && (
                      <Button type="button" variant="ghost" size="sm" onClick={handleClearZoomKeyframes}>
                        Clear
                      </Button>
                    )}
                  </div>
                </div>

                {/* Locked segments disclose below the row so the card stays one
                    scrubber plus one row until someone actually locks zooms. */}
                {sortedKeyframes.length > 0 && (
                  <details className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-1.5" data-testid="demo-cta-keyframes">
                    <summary className="flex cursor-pointer list-none items-center justify-between gap-2 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
                      <span>{sortedKeyframes.length} locked {sortedKeyframes.length === 1 ? "segment" : "segments"}</span>
                      <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180" />
                    </summary>
                    <div className="space-y-2 pb-1 pt-2">
                    {sortedKeyframes[0].time > 0.01 && (
                      <div className="flex items-center gap-2 rounded-lg border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2">
                        <span className="font-mono text-xs text-muted-foreground">0:00.0 → {formatTime(sortedKeyframes[0].time)} • default framing</span>
                      </div>
                    )}
                    {sortedKeyframes.map((kf, idx, sorted) => {
                      const nextTime = sorted[idx + 1]?.time ?? duration;
                      const isActive = currentTime >= kf.time && (sorted[idx + 1] ? currentTime < sorted[idx + 1].time : true);
                      return (
                        <div key={kf.id} className={`group flex items-center gap-2 rounded-lg border px-3 py-2 transition-all ${isActive ? "border-amber-400/30 bg-amber-500/[0.12]" : "border-amber-500/[0.08] bg-amber-500/[0.04]"}`}>
                          <button
                            type="button"
                            onClick={() => handleSeek(kf.time)}
                            className="focus-ring flex-1 rounded text-left font-mono text-xs tabular-nums text-muted-foreground transition hover:text-foreground"
                            title="Jump to this keyframe"
                          >
                            {formatTime(kf.time)} → {formatTime(nextTime)} • {describeFraming(viewMode, kf)} · {kf.scale.toFixed(2)}x video
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveZoomKeyframe(kf.id)}
                            className="focus-ring flex-shrink-0 rounded p-1.5 -m-1.5 text-muted-foreground/60 opacity-0 transition hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100"
                            title="Remove this keyframe"
                            aria-label="Remove this keyframe"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      );
                    })}
                    <p className="pt-0.5 text-xs text-muted-foreground">
                      Seek → adjust zoom → Lock. Adjustments pause the preview. Repeat at later times to zoom in or out; Play replays saved locks in preview and export.
                    </p>
                    </div>
                  </details>
                )}
          </div>
        )}

        {/* Export moved into the player row. What is left here is the progress
            and status that outlive the click — the button itself is gone, so
            this block is empty unless a recording is running or a save is in
            flight. It stays outside the row so a progress bar cannot reflow the
            nowrap transport row. */}
        <div className="space-y-2">
          {recording && <Progress value={Math.round(progress * 100)} />}
          {saving && (
            <p className="flex items-center gap-2 text-xs text-muted-foreground">
              <Loader2 className="h-3.5 w-3.5 animate-spin" /> Saving to History…
            </p>
          )}
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}<ExportFailureNote entry={latestExportError} /></AlertDescription>
            </Alert>
          )}
        </div>
        {/* Preview playback only. Export decodes the pinned source bytes directly,
            so this element's mute, volume and playback scheduler cannot alter the file. */}
        <video
          ref={videoRef}
          className="pointer-events-none absolute h-px w-px opacity-0"
          playsInline
          muted={previewMuted}
          loop={!appendUrl}
          autoPlay
        />
        {/* Second-segment playback; export decodes the original bytes. */}
        {appendUrl && (
          <video
            key={appendUrl}
            ref={appendVideoRef}
            src={appendUrl}
            onLoadedData={(event) => {
              const v = event.currentTarget;
              if (!(v.videoWidth > 0 && v.videoHeight > 0 && Number.isFinite(v.duration) && v.duration > 0)) {
                setAppendError("This added clip has no playable duration. Upload another MP4 or WebM.");
                return;
              }
              setAppendMeta((previous) => previous?.w === v.videoWidth && previous?.h === v.videoHeight && previous?.d === v.duration
                ? previous : { w: v.videoWidth, h: v.videoHeight, d: v.duration });
              setAppendError(null);
              dirtyRef.current = true;
              kickPreviewRef.current?.();
            }}
            onError={() => {
              setAppendMeta(null);
              setAppendError(`"${appendName}" couldn't be played. Upload a playable MP4 or WebM, or remove the added clip.`);
            }}
            data-testid="append-video"
            className="pointer-events-none absolute h-px w-px opacity-0"
            playsInline
            muted={previewMuted}
            preload="auto"
          />
        )}

        {result && (
          /* A plain wrapper because SectionCard is a function component and
             cannot receive a ref, and this card is the scroll target for the
             auto-scroll above. */
          <div ref={resultCardRef}>
            <SectionCard title="Export ready" icon={Download}>
              <div className="flex items-center justify-between text-xs text-muted-foreground">
                <span>MP4 · 1080×1920 · 30 fps • {(result.size / 1024 / 1024).toFixed(2)} MB</span>
                {saved ? (
                  <Badge variant="secondary"><Check className="mr-1 h-2.5 w-2.5" /> In History</Badge>
                ) : saving ? (
                  <span className="flex items-center gap-1"><Loader2 className="h-3 w-3 animate-spin" /> Saving…</span>
                ) : null}
              </div>
              <video key={result.url} src={result.url} controls loop playsInline preload="auto" className="w-full rounded-xl border border-[color:var(--hairline)] bg-black" />
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" size="sm" asChild>
                  <a
                    href={result.url}
                    download={result.name}
                    onClick={() => recordSignal("video_downloaded", "downloaded", {
                      brand_profile_id: generation?.brand_profile_id || "",
                      studio_project_id: generation?.studio_project_id || "",
                      generation_id: saved?.id || "",
                      template_id: generation?.template_id || "",
                    })}
                  >
                    <Download className="h-3.5 w-3.5" /> Download {result.name}
                  </a>
                </Button>
                {saved ? (
                  <Button variant="accent" size="sm" asChild>
                    <Link to={`/history#generation-${saved.id}`}>View in History</Link>
                  </Button>
                ) : (
                  <Button variant="secondary" size="sm" disabled={saving} onClick={() => result.blob && saveExport(result.blob, result.name)}>
                    <RotateCcw className="h-3.5 w-3.5" /> {saving ? "Saving…" : "Save to History"}
                  </Button>
                )}
              </div>
              {saveError && (
                <Alert variant="destructive">
                  <AlertTriangle className="h-4 w-4" />
                  <AlertDescription>{saveError}<ExportFailureNote entry={latestExportError} /></AlertDescription>
                </Alert>
              )}
              {saved && (
                <Alert>
                  <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                  <AlertDescription>
                    {generation ? "Saved beside the original clip in History. The original is untouched and still downloadable." : "Saved as a finished export in History. Download it here, then publish it yourself."}
                  </AlertDescription>
                </Alert>
              )}
              {/* Inherited kit from the save response; regenerate rewrites this export's own copy. */}
              {saved?.post_kit && (
                <PostKitSection postKit={saved.post_kit} generationId={saved.id} />
              )}
            </SectionCard>
          </div>
        )}
      </div>
    </div>
    </TooltipProvider>
  );
}

// Local drawPhone port lives with the other canvas math so the preview loop
// reads one module, not a second app.
// Frame color was removed as a control: every mockup renders the black frame.
// The "white" branches below used to exist and are deliberately gone rather
// than defaulted, so no future reader hunts for a control that sets them.
function drawPhone(ctx, x, y, w, h, dev, video, videoFit, videoScale, videoOffsetX, videoOffsetY, screenBase = "#000") {
  const radius = w * dev.radiusRatio;
  const bezel = w * dev.bezelRatio;

  const bodyColor = dev.body;
  const railColor = dev.rail;

  ctx.save();

  ctx.save();
  roundRect(ctx, x, y, w, h, radius);
  ctx.shadowColor = "rgba(0,0,0,0.55)";
  ctx.shadowBlur = w * 0.10;
  ctx.shadowOffsetY = w * 0.04;
  ctx.fillStyle = "#000";
  ctx.fill();
  ctx.restore();

  const railGrad = ctx.createLinearGradient(x, y, x + w, y);
  railGrad.addColorStop(0, shade(railColor, -25));
  railGrad.addColorStop(0.15, railColor);
  railGrad.addColorStop(0.5, shade(railColor, 20));
  railGrad.addColorStop(0.85, railColor);
  railGrad.addColorStop(1, shade(railColor, -25));
  roundRect(ctx, x, y, w, h, radius);
  ctx.fillStyle = railGrad;
  ctx.fill();

  const bx = x + w * 0.012;
  const by = y + w * 0.012;
  const bw = w - w * 0.024;
  const bh = h - w * 0.024;
  const br = Math.max(0, radius - w * 0.012);
  roundRect(ctx, bx, by, bw, bh, br);
  ctx.fillStyle = bodyColor;
  ctx.fill();

  ctx.save();
  roundRect(ctx, bx, by, bw, bh, br);
  ctx.clip();
  const hi = ctx.createLinearGradient(0, by, 0, by + bh * 0.25);
  hi.addColorStop(0, "rgba(255,255,255,0.10)");
  hi.addColorStop(1, "rgba(255,255,255,0)");
  ctx.fillStyle = hi;
  ctx.fillRect(bx, by, bw, bh * 0.25);
  ctx.restore();

  ctx.fillStyle = shade(railColor, -10);
  ctx.fillRect(x + w - w * 0.008, y + h * 0.18, w * 0.012, h * 0.06);
  ctx.fillRect(x - w * 0.004, y + h * 0.16, w * 0.012, h * 0.05);
  ctx.fillRect(x - w * 0.004, y + h * 0.235, w * 0.012, w * 0.06);

  const sx = bx + bezel;
  const sy = by + bezel;
  const sw = bw - bezel * 2;
  const sh = bh - bezel * 2;
  const sr = Math.max(0, br - bezel * 0.85);
  ctx.save();
  roundRect(ctx, sx, sy, sw, sh, sr);
  ctx.clip();
  // The screen behind the footage is the phone's wallpaper, not a void. It was
  // hard-coded to #000, so any strip the clip did not cover — Contain, a Zoom
  // below 1, an offset, or a source taller than this screen — rendered as a
  // black band that read as a broken picture rather than as deliberate. The
  // palette is what the founder chose for the surrounding canvas, so the screen
  // agreeing with it looks like one image instead of a video pasted on black.
  ctx.fillStyle = screenBase || "#000";
  ctx.fillRect(sx, sy, sw, sh);

  if (video instanceof HTMLCanvasElement || video.readyState >= 2) {
    // One shared fit implementation — see demoCta/fit.js. This used to be a
    // local `contain ? min : max`, which meant "fill" fell through to cover and
    // did nothing, while the hand-held phone's copy of the same arithmetic did
    // implement it. Same control, two behaviours.
    const box = fitVideoToScreen({
      fit: videoFit,
      videoW: video.videoWidth || video.width,
      videoH: video.videoHeight || video.height,
      screenW: sw,
      screenH: sh,
      scale: videoScale,
    });
    // No early return on a null box: the notch and the screen sheen below still
    // belong on a screen with nothing playing in it. Skipping the drawImage is
    // the whole of the degenerate case.
    if (box) {
      const { dw, dh } = box;
      const maxOffX = Math.max(0, (dw - sw) / 2);
      const maxOffY = Math.max(0, (dh - sh) / 2);
      const offX = (videoOffsetX / 100) * maxOffX;
      const offY = (videoOffsetY / 100) * maxOffY;
      const dx = sx + (sw - dw) / 2 + offX;
      const dy = sy + (sh - dh) / 2 + offY;
      ctx.drawImage(video, dx, dy, dw, dh);
    }
  }

  ctx.fillStyle = "#000";
  if (dev.camera === "punch-center") {
    const r = sw * 0.022;
    ctx.beginPath(); ctx.arc(sx + sw / 2, sy + r * 1.7, r, 0, Math.PI * 2); ctx.fill();
  } else if (dev.camera === "punch-left") {
    const r = sw * 0.022;
    ctx.beginPath(); ctx.arc(sx + sw * 0.12, sy + r * 1.7, r, 0, Math.PI * 2); ctx.fill();
  } else if (dev.camera === "notch-drop") {
    const r = sw * 0.028;
    roundRect(ctx, sx + sw / 2 - r, sy, r * 2, r * 1.6, r); ctx.fill();
  } else if (dev.camera === "notch-wide") {
    const nw = sw * 0.34; const nh = sh * 0.028;
    roundRect(ctx, sx + (sw - nw) / 2, sy, nw, nh, nh * 0.6); ctx.fill();
  }
  ctx.restore();

  ctx.save();
  roundRect(ctx, sx, sy, sw, sh, sr);
  ctx.clip();
  const sheen = ctx.createLinearGradient(sx, sy, sx + sw * 0.6, sy + sh * 0.6);
  sheen.addColorStop(0, "rgba(255,255,255,0.06)");
  sheen.addColorStop(0.4, "rgba(255,255,255,0)");
  ctx.fillStyle = sheen;
  ctx.fillRect(sx, sy, sw, sh);
  ctx.restore();

  ctx.restore();
}

function shade(hex, percent) {
  const h = String(hex).replace("#", "");
  const num = parseInt(h, 16);
  const r = Math.max(0, Math.min(255, (num >> 16) + percent));
  const g = Math.max(0, Math.min(255, ((num >> 8) & 0xff) + percent));
  const b = Math.max(0, Math.min(255, (num & 0xff) + percent));
  return `rgb(${r},${g},${b})`;
}

function roundRect(ctx, x, y, w, h, r) {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.lineTo(x + w - r, y);
  ctx.quadraticCurveTo(x + w, y, x + w, y + r);
  ctx.lineTo(x + w, y + h - r);
  ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
  ctx.lineTo(x + r, y + h);
  ctx.quadraticCurveTo(x, y + h, x, y + h - r);
  ctx.lineTo(x, y + r);
  ctx.quadraticCurveTo(x, y, x + r, y);
  ctx.closePath();
}

export default DemoCtaEditor;
