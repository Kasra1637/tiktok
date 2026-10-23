import { useCallback, useEffect, useRef, useState } from "react";
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
import { api, getErrorMessage } from "../lib/api";
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
  HOOK_COPY_VARIANTS,
  CTA_COPY_VARIANTS,
  CTA_TIMING_PRESETS,
  BUILTIN_LOOK_PRESETS,
  buildExportFilename,
  formatTime,
  resolveCtaWindow,
  resolveStoryWindow,
  sniffRecordingContainer,
} from "./constants";
import { checkOverlaySafety, drawEndCard, drawHookOverlay, drawStoryOverlay, getEndCardBounds, getHookBounds } from "./overlays";
import { fitVideoToScreen } from "./fit";
import { exportTikTok, TIKTOK_EXPORT } from "./exportTikTok";
import { drawHandView, preloadHandViewImages, prepareHandViewImages } from "./handView";
import { getEffectiveZoom, tickInterval } from "./zoom";
import { useZoomKeyframes } from "./useZoomKeyframes";

const SECTIONS_KEY = "hookforge.demoCta.openSections.v3";

// Render order, which is also the order that decides which group wins when a
// stored value somehow has more than one open (older versions allowed it).
const SECTION_ORDER = ["source", "hook", "story", "cta", "advanced"];

// Remembered overlay taste: font, entrance and size for the hook + CTA
// overlays, plus the accent. Stored per app with a global fallback, so a
// founder's look survives reloads without one app imposing it on another.
// Empty storage yields DEFAULTS, which is what the smoke suite asserts.
const OVERLAY_PREFS_KEY = "hookforge.demoCta.overlayPrefs.v1";
function readOverlayPrefs() {
  try {
    const raw = window.localStorage.getItem(OVERLAY_PREFS_KEY);
    if (!raw) return {};
    const saved = JSON.parse(raw);
    return saved && typeof saved === "object" ? saved : {};
  } catch {
    return {};
  }
}
function prefFor(profileKey, field, fallback) {
  const all = readOverlayPrefs();
  const scoped = all?.byProfile?.[profileKey]?.[field];
  if (scoped !== undefined && scoped !== null && scoped !== "") return scoped;
  const global = all?.global?.[field];
  return global !== undefined && global !== null && global !== "" ? global : fallback;
}
function prefFont(profileKey, field, fallback) {
  const value = prefFor(profileKey, field, fallback);
  return OVERLAY_FONTS.some((f) => f.id === value) ? value : fallback;
}
function prefAnim(profileKey, field, fallback) {
  const value = prefFor(profileKey, field, fallback);
  return OVERLAY_ANIMS.some((a) => a.id === value) ? value : fallback;
}
function prefScale(profileKey, field, fallback) {
  const value = Number(prefFor(profileKey, field, fallback));
  return Number.isFinite(value) ? value : fallback;
}
function prefVariants(profileKey, field, fallbackList) {
  const value = prefFor(profileKey, field, null);
  if (Array.isArray(value) && value.length === fallbackList.length && value.every((v) => typeof v === "string")) {
    return value;
  }
  return [...fallbackList];
}
function prefLookPresets(profileKey) {
  const all = readOverlayPrefs();
  const scoped = all?.byProfile?.[profileKey]?.lookPresets;
  if (Array.isArray(scoped)) return scoped;
  const global = all?.global?.lookPresets;
  return Array.isArray(global) ? global : [];
}

/** The one-open shape: every key present, exactly one true (or none). */
function singleOpen(openKey) {
  return SECTION_ORDER.reduce((acc, key) => {
    acc[key] = key === openKey;
    return acc;
  }, {});
}

/**
 * Load a recorded blob into a throwaway video element and confirm it has a
 * decoded first frame, expected duration and full TikTok dimensions.
 * A blob that fails never becomes a download link or a History row.
 */
function probeRecordingPlays(blob, expectedDuration) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const probe = document.createElement("video");
    const cleanup = () => {
      clearTimeout(timer);
      probe.onloadeddata = null;
      probe.onerror = null;
      URL.revokeObjectURL(url);
      probe.removeAttribute("src");
    };
    const fail = (message) => {
      cleanup();
      reject(new Error(message));
    };
    const timer = setTimeout(
      () => fail("The TikTok MP4 could not be decoded. Try exporting again in a current Chrome or Edge browser."),
      8000
    );
    probe.preload = "auto";
    probe.onloadeddata = () => {
      if (Number.isFinite(probe.duration) && Math.abs(probe.duration - expectedDuration) <= 0.1 &&
          probe.videoWidth === TIKTOK_EXPORT.width && probe.videoHeight === TIKTOK_EXPORT.height) {
        cleanup();
        resolve();
      } else {
        fail("The TikTok MP4 failed its duration or resolution check. Export again; this file will not be offered for download.");
      }
    };
    probe.onerror = () =>
      fail("The TikTok MP4 could not be decoded. Try exporting again in a current Chrome or Edge browser.");
    probe.src = url;
  });
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
  return (
    <SectionCard flush data-testid={testId}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="row-pad focus-ring flex w-full items-center justify-between gap-2 text-left transition duration-150 hover:bg-[color:var(--indigo-6)]"
      >
        <GroupLabel as="h2" icon={icon}>{title}</GroupLabel>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="space-y-5 px-5 pb-5">{children}</div>}
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
  return (
    <div className="space-y-2">
      <SubLabel>Customize</SubLabel>
      <details open={open} data-testid={testId} className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-1.5">
        <summary onClick={(event) => { event.preventDefault(); onToggle(); }} role="button" tabIndex={0} aria-expanded={open} className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
          <span>Animation · <span className="text-foreground">{currentLabel}</span></span>
          <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180" />
        </summary>
        <div className="space-y-5 pb-1 pt-3">
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
  return (
    <div className="space-y-2">
      <details open={open} data-testid={testId} className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-1.5">
        <summary onClick={(event) => { event.preventDefault(); onToggle(); }} role="button" tabIndex={0} aria-expanded={open} className="focus-ring flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
          <span>Font · <span className="text-foreground">{currentLabel}</span></span>
          <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180" />
        </summary>
        <div className="pb-1 pt-3" role="group" aria-label={groupLabel}>
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
/**
 * A browser network failure surfaces as the raw TypeError text "Failed to
 * fetch", which names the mechanism instead of the remedy. Say what happened
 * and what fixes it: the clip's link may have expired or the connection may
 * have dropped, and refreshing loads it fresh.
 */
function sourceErrorMessage(err, fallback) {
  const message = err?.message || "";
  if (/failed to fetch|network error/i.test(message)) {
    return "The clip couldn't be reached over the network. Check your connection, then refresh for a fresh link.";
  }
  return message || fallback;
}

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
  const [device, setDevice] = useState(DEFAULTS.device);
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
  const [overlayAccent, setOverlayAccent] = useState(() => prefFor(overlayScope, "overlayAccent", DEFAULTS.overlayAccent));
  const [captionFont, setCaptionFont] = useState(() => prefFont(overlayScope, "captionFont", DEFAULTS.captionFont));
  const [ctaFont, setCtaFont] = useState(() => prefFont(overlayScope, "ctaFont", DEFAULTS.ctaFont));
  const [captionAnim, setCaptionAnim] = useState(() => prefAnim(overlayScope, "captionAnim", DEFAULTS.captionAnim));
  const [ctaAnim, setCtaAnim] = useState(() => prefAnim(overlayScope, "ctaAnim", DEFAULTS.ctaAnim));
  const [captionScale, setCaptionScale] = useState(() => prefScale(overlayScope, "captionScale", DEFAULTS.captionScale));
  const [ctaScale, setCtaScale] = useState(() => prefScale(overlayScope, "ctaScale", DEFAULTS.ctaScale));
  const [hookVariants, setHookVariants] = useState(() => prefVariants(overlayScope, "hookVariants", HOOK_COPY_VARIANTS));
  const [activeHookVariant, setActiveHookVariant] = useState(0);
  const [ctaVariants, setCtaVariants] = useState(() => prefVariants(overlayScope, "ctaVariants", CTA_COPY_VARIANTS));
  const [activeCtaVariant, setActiveCtaVariant] = useState(0);
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
  const [customLookPresets, setCustomLookPresets] = useState(() => prefLookPresets(overlayScope));
  const [newLookName, setNewLookName] = useState("");
  const [reviewedLookKey, setReviewedLookKey] = useState(null);
  const [savedLookNotice, setSavedLookNotice] = useState(null);
  // Approval belongs to this clip and this exact reusable styling, not to
  // whichever choices happen to be selected after the next edit.
  const lookReviewKey = JSON.stringify([
    videoUrl, captionFont, ctaFont, captionAnim, ctaAnim,
    captionScale, ctaScale, overlayAccent,
  ]);
  const canReviewLook = !!videoUrl && Number.isFinite(videoMeta?.d) && videoMeta.d > 0 && !recording;
  const lookReviewed = reviewedLookKey === lookReviewKey;
  const canSaveLook = canReviewLook && lookReviewed && !!newLookName.trim();

  // Persist taste on change, per app with a global fallback. Convenience
  // only: private mode or quota failures must never break the editor.
  useEffect(() => {
    try {
      const all = readOverlayPrefs();
      const prefs = {
        overlayAccent,
        captionFont,
        ctaFont,
        captionAnim,
        ctaAnim,
        captionScale,
        ctaScale,
        hookVariants,
        ctaVariants,
        lookPresets: customLookPresets,
      };
      const next = {
        ...all,
        global: { ...(all.global || {}), ...prefs },
        byProfile: { ...(all.byProfile || {}), [overlayScope]: { ...((all.byProfile || {})[overlayScope] || {}), ...prefs } },
      };
      window.localStorage.setItem(OVERLAY_PREFS_KEY, JSON.stringify(next));
    } catch {
      // Nothing to do: persistence is a convenience, not the feature.
    }
  }, [overlayAccent, captionFont, ctaFont, captionAnim, ctaAnim, captionScale, ctaScale, hookVariants, ctaVariants, customLookPresets, overlayScope]);

  const selectHookVariant = (idx) => {
    setActiveHookVariant(idx);
    setHookText(hookVariants[idx] ?? "");
  };

  const updateHookText = (val) => {
    setHookText(val);
    setHookVariants((prev) => prev.map((v, i) => (i === activeHookVariant ? val : v)));
  };

  const selectCtaVariant = (idx) => {
    setActiveCtaVariant(idx);
    setCtaHeadline(ctaVariants[idx] ?? "");
  };

  const updateCtaHeadline = (val) => {
    setCtaHeadline(val);
    setCtaVariants((prev) => prev.map((v, i) => (i === activeCtaVariant ? val : v)));
  };

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

  const allLookPresets = [...BUILTIN_LOOK_PRESETS, ...customLookPresets];

  const isLookPresetActive = (look) =>
    captionFont === look.captionFont &&
    ctaFont === look.ctaFont &&
    captionAnim === look.captionAnim &&
    ctaAnim === look.ctaAnim &&
    Math.abs(captionScale - look.captionScale) < 1e-6 &&
    Math.abs(ctaScale - look.ctaScale) < 1e-6 &&
    overlayAccent.toLowerCase() === String(look.overlayAccent || "").toLowerCase();

  const applyLookPreset = (look) => {
    if (!look) return;
    setCaptionFont(look.captionFont);
    setCtaFont(look.ctaFont);
    setCaptionAnim(look.captionAnim);
    setCtaAnim(look.ctaAnim);
    setCaptionScale(look.captionScale);
    setCtaScale(look.ctaScale);
    setOverlayAccent(look.overlayAccent);
  };

  const handleSaveLookPreset = () => {
    const trimmed = newLookName.trim();
    if (!canSaveLook) return;
    const slug = trimmed.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || `look-${Date.now()}`;
    const entry = {
      id: `custom-${slug}`,
      name: trimmed,
      builtin: false,
      captionFont,
      ctaFont,
      captionAnim,
      ctaAnim,
      captionScale,
      ctaScale,
      overlayAccent,
    };
    setCustomLookPresets((prev) => {
      const filtered = prev.filter((p) => p.name.toLowerCase() !== trimmed.toLowerCase());
      return [...filtered, entry];
    });
    setNewLookName("");
    setReviewedLookKey(null);
    setSavedLookNotice({ name: trimmed, key: lookReviewKey });
  };

  const handleDeleteLookPreset = (id) => {
    setCustomLookPresets((prev) => prev.filter((p) => p.id !== id));
  };

  const [isPlaying, setIsPlaying] = useState(true);
  // Preview monitoring only: the source element stays muted so autoplay
  // never fights browser policy; the speaker toggle below unmutes on tap.
  // Export reads source samples directly; preview mute and volume never affect the file.
  const [previewMuted, setPreviewMuted] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isSeeking, setIsSeeking] = useState(false);

  const {
    zoomKeyframes,
    zoomKeyframesRef,
    sortedKeyframes,
    captureZoomKeyframe,
    removeZoomKeyframe,
    clearZoomKeyframes,
  } = useZoomKeyframes();

  const videoRef = useRef(null);
  // Scoped replay: hook/CTA style tweaks (accent, face, entrance, size)
  // restart playback inside that overlay's window only, then park at the
  // window end — never playing past it into the middle of the clip. The
  // ref holds the active window end; null means free transport. The video's
  // loop is switched off for the replay and restored when it parks or the
  // founder takes over transport, so a CTA replay ending at the clip end
  // cannot wrap to the top on its own.
  const scopedReplayRef = useRef(null);
  const cancelScopedReplay = useCallback(() => {
    scopedReplayRef.current = null;
    const video = videoRef.current;
    if (video) video.loop = true;
  }, []);
  const previewCanvasRef = useRef(null);
  // The one file input, referenced so the empty frame's upload button can
  // drive it. Two inputs would mean two sources of truth and a duplicate
  // `data-testid` for the same control.
  const fileInputRef = useRef(null);
  const rafRef = useRef(null);
  const paintFrameRef = useRef(null);
  // On-demand preview: `dirtyRef` marks a frame to paint, `kickPreviewRef`
  // restarts the parked loop from outside its effect (export finale).
  const dirtyRef = useRef(true);
  const kickPreviewRef = useRef(null);
  const exportAbortRef = useRef(null);
  useEffect(() => () => exportAbortRef.current?.abort(), []);
  const isExportingRef = useRef(false);
  const editingZoomRef = useRef(false);
  const liveZoomRef = useRef({
    scale: 1, offX: 0, offY: 0,
    handZoom: 1, handPanX: 0, handPanY: 0, phoneScale: DEFAULTS.scale,
  });
  const sourceObjectUrlRef = useRef(null);
  const resultObjectUrlRef = useRef(null);
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
        if (!cancelled) setError(sourceErrorMessage(e, "The finished render could not be loaded."));
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
    // State, not the prop: from the standalone route there is no pinned
    // sourceUrl, only a founder-supplied object URL in videoUrl.
    if (!videoUrl && !sourceUrl) return;
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
      refVideo.loop = true;
      refVideo.playsInline = true;
      refVideo.load();
      refVideo.play().catch(() => {});
      setIsPlaying(true);
      setCurrentTime(0);
    }
  }, [videoUrl, sourceFileName]);

  // Track current time from the video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const onTime = () => {
      if (!isSeeking) setCurrentTime(video.currentTime);
    };
    video.addEventListener("timeupdate", onTime);
    // The smoothing tick only runs while the clip plays. Paused seeks land
    // through `timeupdate`.
    let raf = 0;
    let lastReported = 0;
    const tick = () => {
      raf = 0;
      if (!video || video.paused) return;
      if (!isSeeking) {
        const t = video.currentTime;
        if (Math.abs(t - lastReported) >= 0.05) {
          lastReported = t;
          setCurrentTime(t);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    const onPlayTick = () => {
      editingZoomRef.current = false;
      if (!raf) raf = requestAnimationFrame(tick);
    };
    const onPauseTick = () => {
      if (raf) {
        cancelAnimationFrame(raf);
        raf = 0;
      }
      // Land the scrubber on the exact paused frame.
      if (!isSeeking) setCurrentTime(video.currentTime);
    };
    video.addEventListener("play", onPlayTick);
    video.addEventListener("pause", onPauseTick);
    raf = requestAnimationFrame(tick);
    return () => {
      video.removeEventListener("timeupdate", onTime);
      video.removeEventListener("play", onPlayTick);
      video.removeEventListener("pause", onPauseTick);
      cancelAnimationFrame(raf);
    };
  }, [isSeeking]);

  // Restart playback inside one overlay window so a style tweak replays
  // where it lands. Hook replays from frame 0 to the hook end; the end card
  // replays from its start to the clip end. With no loaded clip there is no
  // window, so this is a no-op and the on-demand paint carries the change.
  const startScopedPreview = useCallback((kind) => {
    if (isExportingRef.current) return;
    const video = videoRef.current;
    const dur = videoMeta?.d ?? 0;
    if (!video || !(dur > 0)) return;
    let start;
    let end;
    if (kind === "hook") {
      if (!hookEnabled) return;
      end = Math.min(hookDuration, dur * 0.45);
      start = 0;
    } else if (kind === "cta") {
      if (!ctaEnabled) return;
      const window = resolveCtaWindow(ctaDuration, dur, ctaTimingMode);
      end = dur;
      start = Math.max(0, dur - window);
    } else {
      return;
    }
    if (!(end > start)) return;
    scopedReplayRef.current = { end };
    video.loop = false;
    try {
      video.currentTime = start;
    } catch {
      // A seekable clip always accepts this; a transient failure leaves the
      // playhead where it is and the window guard still parks on time.
    }
    setCurrentTime(start);
    video.play().then(() => setIsPlaying(true)).catch(() => {});
  }, [videoMeta, hookEnabled, hookDuration, ctaEnabled, ctaDuration, ctaTimingMode]);

  // Continuous sliders fire dozens of changes per drag; restarting the
  // window on every tick would yank the playhead under the founder's hand.
  // If the clip already plays inside the window, just retarget the end and
  // let it run — otherwise restart it like a discrete pick.
  const ensureScopedPreview = useCallback((kind) => {
    const video = videoRef.current;
    const dur = videoMeta?.d ?? 0;
    if (!video || !(dur > 0)) return;
    let start;
    let end;
    if (kind === "hook") {
      if (!hookEnabled) return;
      end = Math.min(hookDuration, dur * 0.45);
      start = 0;
    } else if (kind === "cta") {
      if (!ctaEnabled) return;
      const window = resolveCtaWindow(ctaDuration, dur, ctaTimingMode);
      end = dur;
      start = Math.max(0, dur - window);
    } else {
      return;
    }
    if (!(end > start)) return;
    const t = video.currentTime;
    if (!video.paused && t >= start - 0.05 && t < end) {
      scopedReplayRef.current = { end };
      video.loop = false;
      return;
    }
    startScopedPreview(kind);
  }, [videoMeta, hookEnabled, hookDuration, ctaEnabled, ctaDuration, ctaTimingMode, startScopedPreview]);

  // Stable so the Space shortcut below subscribes once: it closes over the
  // video ref and a state setter only, so an empty dep array is complete.
  // An explicit press means free transport, so it always clears a scoped
  // window first — resuming from a parked hook end must play on past it.
  const togglePlayPause = useCallback(() => {
    if (isExportingRef.current) return;
    const video = videoRef.current;
    if (!video) return;
    cancelScopedReplay();
    editingZoomRef.current = false;
    if (video.paused) {
      video.play().catch(() => {});
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  }, [cancelScopedReplay]);

  const togglePreviewMuted = useCallback(() => {
    const video = videoRef.current;
    setPreviewMuted((was) => {
      const next = !was;
      if (video) {
        video.muted = next;
        if (!next) video.volume = 1;
      }
      return next;
    });
  }, []);

  useEffect(() => {
    if (videoRef.current) videoRef.current.muted = previewMuted;
  }, [previewMuted]);

  // Space toggles preview playback from anywhere that is not text entry, the
  // way every video editor answers it. A focused button or link already
  // answers Space with a click, so it is left to the native activation — a
  // second toggle here would undo the click. Sliders answer arrows, not
  // Space, so they keep the shortcut.
  useEffect(() => {
    const onKey = (event) => {
      if (event.code !== "Space" || event.metaKey || event.ctrlKey || event.altKey || event.repeat) return;
      const el = document.activeElement;
      const tag = el?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA" || tag === "SELECT" || el?.isContentEditable) return;
      if (tag === "BUTTON" || tag === "A" || tag === "SUMMARY") return;
      event.preventDefault();
      togglePlayPause();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [togglePlayPause]);

  const handleSeek = (time) => {
    const video = videoRef.current;
    if (!video) return;
    // Founder-driven seeks own the playhead, so a scoped window ends here.
    // (Scoped replays set currentTime directly and never call this.)
    cancelScopedReplay();
    editingZoomRef.current = false;
    showZoomValues(zoomValuesAt(time));
    video.currentTime = time;
    setCurrentTime(time);
    // No paint here: the `seeked` event repaints once the seek lands, so a
    // synchronous paint cannot show the stale pre-seek frame.
  };


  const showZoomValues = useCallback((values) => {
    liveZoomRef.current = values;
    setVideoScale(values.scale);
    setVideoOffsetX(values.offX);
    setVideoOffsetY(values.offY);
    setHandZoom(values.handZoom);
    setHandPanX(values.handPanX);
    setHandPanY(values.handPanY);
    setScale(values.phoneScale);
  }, []);

  const zoomValuesAt = useCallback((time) => {
    const ez = getEffectiveZoom({
      keyframes: zoomKeyframesRef.current, live: liveZoomRef.current, videoTime: time,
    });
    return {
      scale: ez.vScale, offX: ez.vOffX, offY: ez.vOffY,
      handZoom: ez.hZoom, handPanX: ez.hPanX, handPanY: ez.hPanY,
      phoneScale: ez.phoneScale,
    };
  }, [zoomKeyframesRef]);

  // Controls follow the lock under the playhead, rather than stale sliders
  // from the last edit. A paused draft stays visible until Lock or transport.
  useEffect(() => {
    if (editingZoomRef.current || isExportingRef.current) return;
    showZoomValues(zoomValuesAt(videoRef.current?.currentTime ?? currentTime));
  }, [currentTime, isPlaying, zoomKeyframes, showZoomValues, zoomValuesAt]);

  const updateZoomDraft = (patch) => {
    if (isExportingRef.current) return;
    const video = videoRef.current;
    const base = editingZoomRef.current ? liveZoomRef.current : zoomValuesAt(video?.currentTime ?? 0);
    cancelScopedReplay();
    video?.pause();
    setIsPlaying(false);
    editingZoomRef.current = true;
    showZoomValues({ ...base, ...(typeof patch === "function" ? patch(base) : patch) });
    dirtyRef.current = true;
    kickPreviewRef.current?.();
  };

  const handleCaptureZoomLock = () => {
    const video = videoRef.current;
    if (!video || !videoMeta || isExportingRef.current) return;
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

  // Preview loop
  useEffect(() => {
    const canvas = previewCanvasRef.current;
    const video = videoRef.current;
    if (!canvas || !video || !videoMeta) return undefined;
    const ctx = canvas.getContext("2d");
    if (!ctx) return undefined;

    const dev = DEVICES.find((d) => d.id === device) || DEVICES[0];
    const pre = PRESETS.find((p) => p.id === preset) || PRESETS[0];

    const phoneW = BASE_PHONE_H * dev.aspect;
    const phoneH = BASE_PHONE_H * mockupStretchY;

    let cw = pre.w;
    let ch = pre.h;
    if (pre.id === "source") {
      cw = Math.round(phoneW);
      ch = Math.round(phoneH);
    }
    canvas.width = cw;
    canvas.height = ch;

    const drawOverlays = (ctx, vt) => {
      const dur = videoMeta.d || 0;
      const hookWindow = dur > 0 ? Math.min(hookDuration, dur * 0.45) : hookDuration;
      const ctaWindow = resolveCtaWindow(ctaDuration, dur, ctaTimingMode);
      if (hookEnabled) {
        drawHookOverlay(ctx, cw, ch, vt, { text: hookText, duration: hookWindow, accent: overlayAccent, offsetX: hookOffsetX, offsetY: hookOffsetY, font: fontStack(captionFont), anim: captionAnim, scale: captionScale });
      }
      if (storyEnabled && storyAvailable) {
        drawStoryOverlay(ctx, cw, ch, vt, {
          text: storyText, start: storyStart, end: storyEnd,
          accent: overlayAccent, offsetY: storyOffsetY,
          font: fontStack(captionFont), anim: captionAnim, scale: captionScale,
        });
      }
      if (ctaEnabled && dur > 0) {
        drawEndCard(ctx, cw, ch, dur - vt, {
          headline: ctaHeadline,
          handle: ctaHandle,
          duration: ctaWindow,
          accent: overlayAccent,
          offsetX: ctaOffsetX,
          offsetY: ctaOffsetY,
          font: fontStack(ctaFont),
          anim: ctaAnim,
          scale: ctaScale,
        });
      }
    };

    // Preview and export call this exact painter with an explicit media timestamp.
    const paintFrame = (target, vt, frame) => {
      const ctx = target.getContext("2d");
      if (!ctx) throw new Error("Canvas drawing is unavailable. Reload the editor and try again.");
      ctx.clearRect(0, 0, cw, ch);
      const ez = getEffectiveZoom({
        keyframes: zoomKeyframesRef.current,
        live: liveZoomRef.current,
        videoTime: vt,
        isExporting: target !== canvas,
        isEditing: editingZoomRef.current,
      });

      // Hoisted above both renderer branches: each draws the phone, and each
      // needs the palette for the screen behind the footage. Left inside an
      // animation branch, the hand branch above referenced an identifier that
      // did not exist in its scope — and optional chaining does not save that,
      // it only guards a declared binding that happens to be nullish. A const
      // read before its declaration throws, killing the draw loop on the
      // first hand-mode frame and freezing the canvas.
      const palette = COLOR_PALETTES[bg] || COLOR_PALETTES.lavender;

      if (viewMode === "hand" && video) {
        const t = vt;
        drawHandView(ctx, cw, ch, frame, envBg, t, videoFit, ez.vScale, ez.vOffX, ez.vOffY, { x: screenX, y: screenY, w: screenW, h: screenH }, ez.hZoom, ez.hPanX, ez.hPanY, palette?.bg2);
        drawOverlays(ctx, vt);
        return;
      }

      const isFloat = bg !== "transparent";

      if (isFloat) {
        const t = vt;

        const bgGrad = ctx.createRadialGradient(cw * 0.5, ch * 0.4, 0, cw * 0.5, ch * 0.5, cw * 0.7);
        bgGrad.addColorStop(0, palette.bg2);
        bgGrad.addColorStop(1, palette.bg1);
        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, 0, cw, ch);

        const fit = Math.min(cw / phoneW, ch / phoneH) * ez.phoneScale * 0.85;
        const drawW = phoneW * fit;
        const drawH = phoneH * fit;
        const cx2 = cw / 2;
        const cy2 = ch / 2;

        const bobY = Math.sin(t * 1.2) * (ch * 0.012) + Math.sin(t * 2.8) * (ch * 0.004);
        const bobX = Math.sin(t * 0.8) * (cw * 0.003);
        const tiltX = Math.sin(t * 0.7) * 0.03;
        const tiltY = Math.sin(t * 1.1) * 0.02;
        const tiltZ = Math.sin(t * 0.5) * 0.008;
        const glowX = cx2 + bobX * 1.2;
        const glowY = cy2 + bobY * 0.8;
        const glowR = Math.max(drawW, drawH) * 0.85;

        if (anim === "breathe") {
          const breathPhase = t * 0.3;

          for (let i = 0; i < 3; i++) {
            const ringPhase = (breathPhase + i * 0.33) % 1;
            const ringR = glowR * (0.3 + ringPhase * 0.9);
            const ringAlpha = 0.2 * (1 - ringPhase);

            ctx.save();
            ctx.globalAlpha = ringAlpha;
            ctx.beginPath();
            ctx.arc(glowX, glowY, ringR, 0, Math.PI * 2);
            ctx.lineWidth = drawW * (0.04 - ringPhase * 0.03);
            ctx.strokeStyle = palette.glow.replace(/[\d.]+\)$/, "1)");
            ctx.stroke();
            ctx.globalAlpha = 1;
            ctx.restore();
          }

          ctx.save();
          const bAlpha = 0.18 + Math.sin(t * 0.5) * 0.08;
          ctx.globalAlpha = bAlpha;
          const bGrad = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR * 0.5);
          bGrad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          bGrad.addColorStop(0.5, palette.glow.replace(/[\d.]+\)$/, "0.4)"));
          bGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = bGrad;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "embers") {
          // Sparks rise on looped paths. Positions hash from the particle
          // index, never Math.random, so the export encodes the same sparks
          // the preview shows.
          ctx.save();
          ctx.globalAlpha = 0.30;
          const emberGlow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR);
          emberGlow.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          emberGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = emberGlow;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          for (let i = 0; i < 26; i++) {
            const hx = Math.sin(i * 127.1) * 43758.5453;
            const fx = hx - Math.floor(hx);
            const hy = Math.sin(i * 311.7 + 17.3) * 12578.1459;
            const fy = hy - Math.floor(hy);
            const speed = 0.05 + fy * 0.08;
            const ey = ch * (1 - ((fy + t * speed) % 1));
            const ex = cw * fx + Math.sin(t * 1.4 + i) * cw * 0.02;
            const tw = 0.4 + 0.6 * Math.abs(Math.sin(t * 2 + i * 1.7));
            ctx.globalAlpha = 0.5 * tw * (ey / ch + 0.2);
            ctx.fillStyle = i % 3 === 0 ? "#ffffff" : palette.glow.replace(/[\d.]+\)$/, "1)");
            ctx.beginPath();
            ctx.arc(ex, ey, Math.max(1.5, drawW * (0.004 + fy * 0.008)), 0, Math.PI * 2);
            ctx.fill();
          }
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "vortex") {
          // Two spiral arms rotate around the phone, trailing glow.
          for (let arm = 0; arm < 2; arm++) {
            ctx.save();
            ctx.globalAlpha = 0.16;
            ctx.strokeStyle = palette.glow.replace(/[\d.]+\)$/, "0.8)");
            ctx.lineWidth = Math.max(1.5, drawW * 0.02);
            ctx.beginPath();
            const vbase = t * 0.9 + arm * Math.PI;
            for (let s = 0; s <= 40; s++) {
              const p = s / 40;
              const va = vbase + p * 3.2;
              const vr = glowR * (0.25 + p * 0.65);
              const vx = cx2 + Math.cos(va) * vr;
              const vy = cy2 + Math.sin(va) * vr * 0.62;
              if (s === 0) ctx.moveTo(vx, vy);
              else ctx.lineTo(vx, vy);
            }
            ctx.stroke();
            ctx.globalAlpha = 1;
            ctx.restore();
          }
          ctx.save();
          ctx.globalAlpha = 0.14;
          const vortexGlow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR * 0.5);
          vortexGlow.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          vortexGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = vortexGlow;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "grid") {
          // A synthwave floor: lines converge past a horizon, horizontals rush
          // toward the viewer on a loop.
          const horizon = ch * 0.62;
          ctx.save();
          ctx.globalAlpha = 0.14;
          ctx.strokeStyle = palette.glow.replace(/[\d.]+\)$/, "0.8)");
          ctx.lineWidth = Math.max(1, cw * 0.002);
          for (let i = -8; i <= 8; i++) {
            ctx.beginPath();
            ctx.moveTo(cx2 + i * cw * 0.03, horizon);
            ctx.lineTo(cx2 + i * cw * 0.16, ch);
            ctx.stroke();
          }
          ctx.globalAlpha = 1;
          ctx.restore();
          ctx.save();
          for (let i = 0; i < 7; i++) {
            const gp = ((i / 7) + t * 0.3) % 1;
            const gy = horizon + Math.pow(gp, 2.2) * (ch - horizon);
            ctx.globalAlpha = 0.05 + gp * 0.14;
            ctx.strokeStyle = palette.glow.replace(/[\d.]+\)$/, "0.9)");
            ctx.lineWidth = Math.max(1, cw * 0.002 * (1 + gp * 2));
            ctx.beginPath();
            ctx.moveTo(0, gy);
            ctx.lineTo(cw, gy);
            ctx.stroke();
          }
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "comet") {
          // A comet arcs across the top third on a loop, fading tail behind it.
          ctx.save();
          ctx.globalAlpha = 0.12;
          const cometGlow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR * 0.6);
          cometGlow.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          cometGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = cometGlow;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();
          ctx.save();
          const cp = (t * 0.18) % 1;
          for (let k = 14; k >= 1; k--) {
            const pk = cp - k * 0.012;
            if (pk < 0) continue;
            const kx = cw * (1.1 - pk * 2.2);
            const ky = ch * (0.16 + Math.sin(pk * Math.PI) * 0.1);
            ctx.globalAlpha = 0.30 * (1 - k / 15);
            ctx.fillStyle = palette.glow.replace(/[\d.]+\)$/, "1)");
            ctx.beginPath();
            ctx.arc(kx, ky, Math.max(1.5, drawW * 0.02 * (1 - k / 18)), 0, Math.PI * 2);
            ctx.fill();
          }
          const hx0 = cw * (1.1 - cp * 2.2);
          const hy0 = ch * (0.16 + Math.sin(cp * Math.PI) * 0.1);
          ctx.globalAlpha = 0.9;
          const head = ctx.createRadialGradient(hx0, hy0, 0, hx0, hy0, drawW * 0.09);
          head.addColorStop(0, "#ffffff");
          head.addColorStop(0.4, palette.glow.replace(/[\d.]+\)$/, "1)"));
          head.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = head;
          ctx.fillRect(hx0 - drawW * 0.09, hy0 - drawW * 0.09, drawW * 0.18, drawW * 0.18);
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "tide") {
          // Three translucent sine bands drift at different speeds.
          for (let i = 0; i < 3; i++) {
            ctx.save();
            ctx.globalAlpha = 0.10 - i * 0.02;
            ctx.fillStyle = (i % 2 ? palette.accent : palette.glow).replace(/[\d.]+\)$/, "0.8)");
            ctx.beginPath();
            const tideBase = ch * (0.3 + i * 0.18);
            ctx.moveTo(0, ch);
            for (let gx = 0; gx <= cw; gx += cw / 48) {
              const wy = tideBase + Math.sin((gx / cw) * Math.PI * 2 + t * (0.6 + i * 0.25) + i * 2) * ch * 0.04;
              ctx.lineTo(gx, wy);
            }
            ctx.lineTo(cw, ch);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          }
        }

        if (anim === "prism") {
          // Three beams rotate slowly from behind the phone.
          for (let i = 0; i < 3; i++) {
            const pa = t * 0.25 + (i / 3) * Math.PI * 2;
            ctx.save();
            ctx.globalAlpha = 0.10;
            ctx.translate(glowX, glowY);
            ctx.rotate(pa);
            const beam = ctx.createLinearGradient(0, 0, glowR * 1.1, 0);
            beam.addColorStop(0, (i % 2 ? palette.accent : palette.glow).replace(/[\d.]+\)$/, "0.9)"));
            beam.addColorStop(1, "rgba(0,0,0,0)");
            ctx.fillStyle = beam;
            ctx.beginPath();
            ctx.moveTo(0, 0);
            ctx.lineTo(glowR * 1.1, -glowR * 0.16);
            ctx.lineTo(glowR * 1.1, glowR * 0.16);
            ctx.closePath();
            ctx.fill();
            ctx.restore();
          }
        }

        if (anim === "bloom") {
          // Petals of light open and close around the phone, very slow.
          for (let i = 0; i < 6; i++) {
            const ba = (i / 6) * Math.PI * 2 + t * 0.12;
            const blen = glowR * (0.55 + 0.25 * Math.sin(t * 0.5 + i));
            const bx = glowX + Math.cos(ba) * blen * 0.55;
            const by = glowY + Math.sin(ba) * blen * 0.4;
            ctx.save();
            ctx.globalAlpha = 0.10;
            const petal = ctx.createRadialGradient(bx, by, 0, bx, by, glowR * 0.32);
            petal.addColorStop(0, palette.accent.replace(/[\d.]+\)$/, "0.9)"));
            petal.addColorStop(1, "rgba(0,0,0,0)");
            ctx.fillStyle = petal;
            ctx.fillRect(bx - glowR * 0.32, by - glowR * 0.32, glowR * 0.64, glowR * 0.64);
            ctx.restore();
          }
        }

        if (anim === "meteor") {
          // Diagonal streaks fall fast across the frame on looped paths.
          ctx.save();
          for (let i = 0; i < 14; i++) {
            const mx = Math.sin(i * 197.3 + 3.1) * 36211.9271;
            const mfx = mx - Math.floor(mx);
            const my = Math.sin(i * 421.9 + 44.7) * 21134.7129;
            const mfy = my - Math.floor(my);
            const mp = (mfy + t * (0.35 + mfy * 0.3)) % 1;
            const sx = cw * (mfx * 1.4 - 0.2 + mp * 0.3);
            const sy = ch * mp;
            ctx.globalAlpha = 0.28 * (1 - mp);
            ctx.strokeStyle = i % 4 === 0 ? "#ffffff" : palette.glow.replace(/[\d.]+\)$/, "1)");
            ctx.lineWidth = Math.max(1, drawW * (0.003 + mfy * 0.004));
            ctx.lineCap = "round";
            ctx.beginPath();
            ctx.moveTo(sx, sy);
            ctx.lineTo(sx + cw * 0.03, sy + ch * 0.05);
            ctx.stroke();
          }
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        ctx.save();
        ctx.globalAlpha = 0.25;
        ctx.beginPath();
        const shadowY = cy2 + drawH * 0.52 + bobY * 0.3;
        const shadowW = drawW * 0.7 * (1 - Math.abs(tiltX) * 2);
        const shadowH = drawH * 0.06;
        ctx.ellipse(cx2 + bobX, shadowY, shadowW, shadowH, 0, 0, Math.PI * 2);
        ctx.fillStyle = "#000";
        ctx.filter = `blur(${Math.round(drawW * 0.08)}px)`;
        ctx.fill();
        ctx.filter = "none";
        ctx.globalAlpha = 1;
        ctx.restore();

        ctx.save();
        ctx.translate(cx2 + bobX, cy2 + bobY);
        ctx.rotate(tiltZ);

        const perspScale = 1 - Math.abs(tiltX) * 0.5;
        ctx.scale(1, perspScale);
        ctx.transform(1, tiltX * 0.8, tiltY * 0.6, 1, 0, 0);

        ctx.translate(-drawW / 2, -drawH / 2);
        drawPhone(ctx, 0, 0, drawW, drawH, dev, frame, videoFit, ez.vScale, ez.vOffX, ez.vOffY, palette?.bg2);
        ctx.restore();

        ctx.save();
        const vignette = ctx.createRadialGradient(
          cx2, cy2, Math.min(cw, ch) * 0.3,
          cx2, cy2, Math.max(cw, ch) * 0.7
        );
        vignette.addColorStop(0, "rgba(0, 0, 0, 0)");
        vignette.addColorStop(0.6, "rgba(0, 0, 0, 0)");
        vignette.addColorStop(0.85, "rgba(0, 0, 0, 0.25)");
        vignette.addColorStop(1, "rgba(0, 0, 0, 0.55)");
        ctx.fillStyle = vignette;
        ctx.fillRect(0, 0, cw, ch);
        ctx.restore();

      } else {
        const fit = Math.min(cw / phoneW, ch / phoneH) * ez.phoneScale;
        const drawW = phoneW * fit;
        const drawH = phoneH * fit;
        const x = (cw - drawW) / 2;
        const y = (ch - drawH) / 2;
        drawPhone(ctx, x, y, drawW, drawH, dev, frame, videoFit, ez.vScale, ez.vOffX, ez.vOffY, palette?.bg2);
      }
      drawOverlays(ctx, vt);
    };
    paintFrameRef.current = paintFrame;
    // On-demand preview. A paused clip with settled settings paints the same
    // frame forever, so an unconditional loop is pure GPU/battery burn: this
    // loop runs while the clip plays and paints exactly one frame per
    // settings change or seek while paused, then parks with no scheduled
    // work. `kick` restarts it; the video's own play/pause/seek events and
    // this effect's re-run (every setting lives in the deps below) are what
    // mark a frame dirty.
    const draw = () => {
      rafRef.current = null;
      if (isExportingRef.current) return;
      const v = videoRef.current;
      const playing = !!v && !v.paused;
      if (playing) editingZoomRef.current = false;
      if (playing || dirtyRef.current) {
        dirtyRef.current = false;
        paintFrame(canvas, v ? v.currentTime || 0 : 0, v);
      }
      // A scoped replay parks at its window end instead of playing past it:
      // pausing here lands the scrubber on the exact window frame, and the
      // loop restore below hands free transport back for the next press.
      const scoped = scopedReplayRef.current;
      if (playing && scoped && v && v.currentTime >= scoped.end - 0.08) {
        scopedReplayRef.current = null;
        v.pause();
        v.loop = true;
        setIsPlaying(false);
        setCurrentTime(v.currentTime);
        return;
      }
      if (playing) rafRef.current = requestAnimationFrame(draw);
    };
    const kick = () => {
      if (!rafRef.current) rafRef.current = requestAnimationFrame(draw);
    };
    kickPreviewRef.current = kick;
    // Play restarts the loop; a seek repaints once it lands. Pause needs no
    // paint: the last playing frame is already the paused frame.
    const onPlayPaint = () => kick();
    const onSeekedPaint = () => {
      dirtyRef.current = true;
      kick();
    };
    const previewVideo = videoRef.current;
    previewVideo?.addEventListener("play", onPlayPaint);
    previewVideo?.addEventListener("seeked", onSeekedPaint);
    // A CTA replay ending at the clip end fires `ended` instead of another
    // frame: clear the window and hand free transport back same as the
    // guarded park above.
    const onEndedScoped = () => {
      scopedReplayRef.current = null;
      if (previewVideo) previewVideo.loop = true;
      setIsPlaying(false);
    };
    previewVideo?.addEventListener("ended", onEndedScoped);
    dirtyRef.current = true;
    kick();

    return () => {
      paintFrameRef.current = null;
      kickPreviewRef.current = null;
      previewVideo?.removeEventListener("play", onPlayPaint);
      previewVideo?.removeEventListener("seeked", onSeekedPaint);
      previewVideo?.removeEventListener("ended", onEndedScoped);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device, preset, scale, mockupStretchY, videoMeta, bg, anim, videoFit, videoScale, videoOffsetX, videoOffsetY, viewMode, envBg, screenX, screenY, screenW, screenH, handZoom, handPanX, handPanY, hookEnabled, hookText, hookDuration, hookOffsetX, hookOffsetY, storyEnabled, storyAvailable, storyText, storyStart, storyEnd, storyOffsetY, ctaEnabled, ctaHeadline, ctaHandle, ctaDuration, ctaTimingMode, ctaOffsetX, ctaOffsetY, overlayAccent, captionFont, ctaFont, captionAnim, ctaAnim, captionScale, ctaScale, zoomKeyframes]);

  // Hook/CTA style picks replay their own window; everything else leaves the
  // playhead alone. Every overlay value is also in the preview loop's deps
  // above, so the canvas redraws with the new entrance, size or face on the
  // next frame even with no clip loaded — and pause-then-replay outside a
  // scoped window still resumes from that same spot. The playhead and the
  // play state otherwise stay with the transport (and the source-load
  // effect) alone.

  const saveExport = async (blob, name) => {
    setSaving(true);
    setSaveError(null);
    try {
      const savedRow = await api.saveDemoCtaExport(generation?.id, blob, name);
      setSaved(savedRow);
      recordSignal("video_downloaded", "demo_cta_exported", {
        brand_profile_id: generation?.brand_profile_id || "",
        studio_project_id: generation?.studio_project_id || "",
        generation_id: savedRow?.id || "",
        template_id: generation?.template_id || "",
      });
      onSaved?.(savedRow);
      return savedRow;
    } catch (err) {
      setSaveError(getErrorMessage(err));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const exportVideo = async () => {
    const video = videoRef.current;
    const paintFrame = paintFrameRef.current;
    if (!video || !paintFrame || !videoMeta || isExportingRef.current) return;
    const controller = new AbortController();
    exportAbortRef.current = controller;
    const resumePlayback = !video.paused;
    video.pause();
    setIsPlaying(false);
    setError(null);
    setSaveError(null);
    setSaved(null);
    setRecording(true);
    setProgress(0);
    setResult(null);
    isExportingRef.current = true;
    try {
      // Freeze settings, assets and fonts for the entire encode. Never capture a live RAF canvas.
      await Promise.all([document.fonts?.ready, ...[captionFont, ctaFont].map((id) =>
        document.fonts?.load(`100px ${fontStack(id)}`))]);
      if (viewMode === "hand") await prepareHandViewImages(envBg);
      const response = await fetch(videoUrl, { signal: controller.signal });
      if (!response.ok) throw new Error("The source clip could not be read. Reload it and export again.");
      const canvas = document.createElement("canvas");
      const { blob, duration } = await exportTikTok({
        source: await response.blob(), canvas, signal: controller.signal,
        drawFrame: (time, frame) => paintFrame(canvas, time, frame),
        onProgress: setProgress,
      });
      const head = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
      if (sniffRecordingContainer(head) !== "mp4") throw new Error("The encoder did not produce a valid MP4. Export again in Chrome or Edge.");
      await probeRecordingPlays(blob, duration);
      controller.signal.throwIfAborted();
      const url = URL.createObjectURL(blob);
      if (resultObjectUrlRef.current) URL.revokeObjectURL(resultObjectUrlRef.current);
      resultObjectUrlRef.current = url;
      const name = buildExportFilename({ device, preset: "tiktok", width: canvas.width, height: canvas.height, ext: "mp4" });
      const mime = "video/mp4";
      setResult({ url, name, size: blob.size, mime, blob });
      await saveExport(blob, name);
    } catch (e) {
      if (!controller.signal.aborted) setError(e?.message || "The TikTok MP4 export failed. Try again in Chrome or Edge.");
    } finally {
      isExportingRef.current = false;
      exportAbortRef.current = null;
      if (!controller.signal.aborted) {
        setRecording(false);
        setProgress(0);
        // The loop parks for the whole encode; repaint the live preview once
        // (the `play` event below re-kicks the loop when playback resumes).
        dirtyRef.current = true;
        kickPreviewRef.current?.();
        if (resumePlayback) video.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    }
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

    const video = videoRef.current;
    const vt = video ? video.currentTime : 0;
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
    const isHand = viewMode === "hand";
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
    updateZoomDraft((values) => viewMode === "hand"
      ? { handZoom: Math.max(RANGES.handZoom.min, Math.min(RANGES.handZoom.max, +(values.handZoom - e.deltaY * 0.0015).toFixed(3))) }
      : { phoneScale: Math.max(RANGES.scale.min, Math.min(RANGES.scale.max, +(values.phoneScale - e.deltaY * 0.0015).toFixed(3))) });
  };

  const duration = videoMeta?.d ?? 0;
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
  // `max-h-[calc(100vh-7rem)]` on the settings column is what makes the two
  // columns peers: the page itself stops growing, the panel scrolls inside its
  // own box, and the preview stays put no matter how long the panel gets.
  const settingsRef = useRef(null);

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
          className="demo-cta-panel-scroll space-y-3 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-2.5"
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
        <EditorSection title="Source & Look" icon={Film} open={openSections.source} onToggle={() => toggleSection("source")} testId="demo-cta-source">
          {generation ? (
            <>
              <p className="text-xs text-muted-foreground">
                This Hook + Story render is the source clip. Replace it with your own footage; one clip at a time.
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
              Upload one clip to start — your footage or a finished render. No generation needed; one clip at a time.
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
                  title="Remove this clip and go back to the finished render"
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
            <SubLabel>View style</SubLabel>
            <p className="text-xs text-muted-foreground">Floating phone or hand-held mockup. Drag preview to reframe; in hand mode, pick a scene.</p>
            <div className="grid grid-cols-2 gap-1 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 p-1">
              {[
                ["floating", "Floating Phone"],
                ["hand", "Hand Holding"],
              ].map(([id, label]) => (
                <button
                  key={id}
                  type="button"
                  onClick={() => setViewMode(id)}
                  aria-pressed={viewMode === id}
                  data-testid={`view-mode-${id}`}
                  className={`focus-ring h-8 rounded-lg text-xs font-semibold transition duration-150 ${
                    viewMode === id
                      ? "bg-[color:var(--brand-indigo)]/15 text-foreground shadow-[var(--shadow-xs)]"
                      : "text-muted-foreground hover:bg-secondary/50 hover:text-foreground"
                  }`}
                >
                  {label}
                </button>
              ))}
            </div>
          </div>
          {viewMode === "hand" && (
            <div className="grid grid-cols-5 gap-1.5">
              {ENVIRONMENTS.map((env) => (
                <button
                  key={env.id}
                  type="button"
                  onClick={() => setEnvBg(env.id)}
                  title={env.label}
                  className={`focus-ring overflow-hidden rounded-xl border text-xs transition ${
                    envBg === env.id ? "border-[color:var(--brand-indigo)]" : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                  }`}
                >
                  <img src={env.url} alt={env.label} className="aspect-[3/4] w-full object-cover" loading="lazy" crossOrigin="anonymous" />
                  <div className="px-0.5 py-1 text-center text-xs leading-tight text-muted-foreground">{env.label}</div>
                </button>
              ))}
            </div>
          )}
          {viewMode === "floating" && (
            <>
              <div className="space-y-2">
                <SubLabel>Device frame</SubLabel>
                <select
                  value={device}
                  onChange={(e) => setDevice(e.target.value)}
                  className={CONTROL_CLASS}
                  title={(DEVICES.find((d) => d.id === device) || {}).label}
                  aria-label="Device frame"
                  data-testid="device-frame-select"
                >
                  {DEVICES.map((d) => (
                    <option key={d.id} value={d.id}>{d.label}</option>
                  ))}
                </select>
              </div>
              <div className="space-y-2">
                <SubLabel>Background</SubLabel>
                <div className="flex flex-wrap items-center gap-2">
                  {BACKGROUNDS.map((b) => (
                    <button
                      key={b.id}
                      type="button"
                      onClick={() => setBg(b.id)}
                      title={b.label}
                      aria-label={b.label}
                      aria-pressed={bg === b.id}
                      data-testid={`background-${b.id}`}
                      className={`focus-ring h-10 w-10 shrink-0 overflow-hidden rounded-xl border transition duration-150 ${
                        bg === b.id
                          ? "border-[color:var(--brand-indigo)] ring-2 ring-[color:var(--indigo-45)]"
                          : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                      }`}
                      style={
                        b.preview === "transparent"
                          ? { backgroundImage: "linear-gradient(45deg,#666 25%,transparent 25%),linear-gradient(-45deg,#666 25%,transparent 25%),linear-gradient(45deg,transparent 75%,#666 75%),linear-gradient(-45deg,transparent 75%,#666 75%)", backgroundSize: "8px 8px", backgroundPosition: "0 0,0 4px,4px -4px,-4px 0", backgroundColor: "#222" }
                          : { background: b.preview }
                      }
                    />
                  ))}
                </div>
              </div>
              <div className="space-y-2">
                <SubLabel>Animation</SubLabel>
                {/* The app's own selectable pill rather than another hand-rolled
                    row of text buttons: this list is a segmented choice, which is
                    what `Chip` is for, and it carries the visible border, hover
                    state and indigo selected state the previous version lacked.
                    Even widths come from the grid, because `Chip` takes no
                    className. Three columns wherever the panel is full-width
                    (below lg) or wide (xl and up); two in the narrow lg–xl
                    column, where a third column leaves longer labels
                    about 92px and they wrap to two lines. */}
                <div
                  role="group"
                  aria-label="Animation"
                  data-testid="animation-group"
                  className="grid grid-cols-3 gap-1.5 lg:grid-cols-2 xl:grid-cols-3"
                >
                  {ANIMATIONS.map((a) => (
                    <Chip
                      key={a.id}
                      active={anim === a.id}
                      onClick={() => setAnim(a.id)}
                      testId={`animation-${a.id}`}
                      ariaLabel={a.label}
                    >
                      {a.label}
                    </Chip>
                  ))}
                </div>
              </div>
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
          <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3" data-testid="look-presets-block">
            <SubLabel>Named looks</SubLabel>
            <p className="text-xs text-muted-foreground">Start with a saved look. Save your finished styling in End Card CTA.</p>
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
                        className="focus-ring rounded-full p-1 text-muted-foreground transition-colors hover:text-foreground"
                      >
                        <X className="h-3 w-3" />
                      </button>
                    )}
                  </div>
                );
              })}
            </div>
          </div>
        </EditorSection>

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
                {hookVariants.map((_, idx) => (
                  <Chip
                    key={idx}
                    active={activeHookVariant === idx}
                    onClick={() => { selectHookVariant(idx); startScopedPreview("hook"); }}
                    testId={`hook-variant-${idx}`}
                    ariaLabel={`Hook variant ${idx + 1}`}
                  >
                    {`Option ${idx + 1}`}
                  </Chip>
                ))}
              </div>
            </div>
            <textarea
              data-testid="hook-text-input"
              aria-label="Text to show at the opening"
              value={hookText}
              onChange={(e) => updateHookText(e.target.value)}
              rows={3}
              placeholder="I built this so I'd stop journaling in Notes app"
              className={TEXTAREA_CLASS}
            />
          </div>
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
                {ctaVariants.map((_, idx) => (
                  <Chip
                    key={idx}
                    active={activeCtaVariant === idx}
                    onClick={() => { selectCtaVariant(idx); startScopedPreview("cta"); }}
                    testId={`cta-variant-${idx}`}
                    ariaLabel={`CTA variant ${idx + 1}`}
                  >
                    {`Option ${idx + 1}`}
                  </Chip>
                ))}
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
              {savedLookNotice?.key === lookReviewKey ? `“${savedLookNotice.name}” saved. Apply it from Named looks in Source & Look.` : ""}
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
          {viewMode === "hand" && (
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
        className="demo-cta-column demo-cta-panel-scroll min-w-0 space-y-3 lg:sticky lg:top-6 lg:max-h-[calc(100vh-3rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-1"
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
              <div className="px-6 text-center">
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
                        title={`${formatTime(seg.time)} → ${formatTime(end)}: ${viewMode === "hand" ? `${seg.handZoom.toFixed(2)}x hand` : `${Math.round((seg.phoneScale ?? DEFAULTS.scale) * 100)}% phone`} · ${seg.scale.toFixed(2)}x video`}
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
                      disabled={!videoUrl || !videoMeta || recording || saving}
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
                            {formatTime(kf.time)} → {formatTime(nextTime)} • {viewMode === "hand" ? `${kf.handZoom.toFixed(2)}x hand` : `${Math.round((kf.phoneScale ?? DEFAULTS.scale) * 100)}% phone`} · {kf.scale.toFixed(2)}x video
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveZoomKeyframe(kf.id)}
                            className="focus-ring flex-shrink-0 rounded text-muted-foreground/60 opacity-0 transition hover:text-destructive group-hover:opacity-100 focus-visible:opacity-100"
                            title="Remove this keyframe"
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
              <AlertDescription>{error}</AlertDescription>
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
          loop
          autoPlay
        />

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
                    <Link to="/history">View in History</Link>
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
                  <AlertDescription>{saveError}</AlertDescription>
                </Alert>
              )}
              {saved && (
                <Alert>
                  <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                  <AlertDescription>
                    Saved beside the original Hook + Story in History. The original is untouched and still downloadable.
                  </AlertDescription>
                </Alert>
              )}
              {/* The frozen kit the export inherited, already on the save response.
                  Regenerating here rewrites this export's own copy — the row
                  carries the parent's project, so the endpoint resolves. */}
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
