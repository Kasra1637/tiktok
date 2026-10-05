import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  ArrowUp,
  Check,
  ChevronDown,
  ChevronLeft,
  ChevronRight,
  Download,
  Info,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  Smartphone,
  Upload,
  X,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Progress } from "../components/ui/progress";
import { Slider } from "../components/ui/slider";
import { Switch } from "../components/ui/switch";
import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "../components/ui/tooltip";
import { SectionCard } from "../components/SectionCard";
import { Chip } from "../components/Chip";
import { api, getErrorMessage } from "../lib/api";
import { recordSignal } from "../lib/feedback";
import {
  ANIMATIONS,
  BACKGROUNDS,
  BASE_PHONE_H,
  CAPTURE_FPS,
  COLOR_PALETTES,
  DEFAULT_SCREEN,
  DEFAULTS,
  DEVICES,
  ENVIRONMENTS,
  PRESETS,
  RANGES,
  ACCENT_SWATCHES,
  AUDIO_BITS_PER_SECOND,
  VIDEO_BITS_PER_SECOND,
  buildExportFilename,
  extensionForMime,
  formatTime,
  isPlausibleRecordingSize,
  sniffRecordingContainer,
  supportedExportMimes,
} from "./constants";
import { drawEndCard, drawHookOverlay, getEndCardBounds, getHookBounds, HOOK_FONT } from "./overlays";
import { drawHandView, preloadHandViewImages } from "./handView";
import { captureZoomLock, getEffectiveZoom, removeZoomKeyframe, sortKeyframes, tickInterval } from "./zoom";

const SECTIONS_KEY = "hookforge.demoCta.openSections.v3";

// Render order, which is also the order that decides which group wins when a
// stored value somehow has more than one open (older versions allowed it).
const SECTION_ORDER = ["source", "hook", "cta", "output", "advanced"];

/** The one-open shape: every key present, exactly one true (or none). */
function singleOpen(openKey) {
  return SECTION_ORDER.reduce((acc, key) => {
    acc[key] = key === openKey;
    return acc;
  }, {});
}

/**
 * Load a recorded blob into a throwaway video element and confirm it has a
 * real duration. This is the same check a player performs on open — metadata
 * parses, the container demuxes — so a blob that passes here opens in VLC,
 * QuickTime, and the in-app preview alike. A blob that fails never becomes a
 * download link or a History row.
 */
function probeRecordingPlays(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const probe = document.createElement("video");
    const cleanup = () => {
      URL.revokeObjectURL(url);
      probe.removeAttribute("src");
    };
    const fail = (message) => {
      cleanup();
      reject(new Error(message));
    };
    const timer = setTimeout(
      () => fail("The recording would not play back. Try again, or switch Export format to WebM in Output."),
      8000
    );
    probe.preload = "auto";
    probe.onloadedmetadata = () => {
      clearTimeout(timer);
      if (Number.isFinite(probe.duration) && probe.duration > 0) {
        cleanup();
        resolve();
      } else {
        fail("The recording has no playable duration. Try again, or switch Export format to WebM in Output.");
      }
    };
    probe.onerror = () =>
      fail("The recording would not play back. Try again, or switch Export format to WebM in Output.");
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
const CONTROL_CLASS =
  "h-10 w-full appearance-none rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 text-sm text-foreground shadow-[var(--shadow-xs)] transition-colors outline-none hover:border-[color:var(--hairline-strong)] focus-visible:border-[color:var(--indigo-35)] focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)] disabled:cursor-not-allowed disabled:opacity-50";

const INPUT_CLASS =
  "h-10 w-full rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3.5 py-1 text-sm shadow-[var(--shadow-xs)] transition-colors placeholder:text-muted-foreground hover:border-[color:var(--hairline-strong)] focus-visible:border-[color:var(--indigo-35)] focus-visible:bg-secondary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)]";

const TEXTAREA_CLASS =
  "w-full resize-none rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3.5 py-2 text-sm leading-snug shadow-[var(--shadow-xs)] transition-colors placeholder:text-muted-foreground hover:border-[color:var(--hairline-strong)] focus-visible:border-[color:var(--indigo-35)] focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)]";

/**
 * One collapsible control group.
 *
 * `.surface` is un-layered CSS with its own 24px padding, so the padding here
 * has to be important to win — without `!p-0` every group carried 24px of dead
 * space around a 32px header, which is most of what made the old panel feel
 * bloated. Content padding is 16px to match the rest of the app's card rhythm.
 *
 * `open`/`onToggle` are lifted so the parent can persist which groups are open.
 */
function EditorSection({ title, open, onToggle, testId, children }) {
  return (
    <SectionCard className="!space-y-0 !p-0" data-testid={testId}>
      <button
        type="button"
        onClick={onToggle}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-4 py-3 text-left transition duration-150 hover:bg-[color:var(--indigo-6)]"
      >
        <span className="eyebrow">{title}</span>
        <ChevronDown
          className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 ${open ? "rotate-180" : ""}`}
        />
      </button>
      {open && <div className="space-y-3 px-4 pb-4">{children}</div>}
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

function ResetButton({ onClick, children, testId }) {
  return (
    <button
      type="button"
      data-testid={testId}
      onClick={onClick}
      className="text-xs text-muted-foreground underline-offset-2 transition duration-150 hover:text-foreground hover:underline"
    >
      {children || "Reset"}
    </button>
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
 *   Hook + Middle it is a fallback that swaps the source for this edit; entered
 *   from the sidebar with no generation it is the whole input, and the export
 *   is saved standalone. Either way it never creates a Hook + Middle.
 */
export function DemoCtaEditor({ generation = null, sourceUrl = null, onSaved }) {
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
  const [preset, setPreset] = useState(DEFAULTS.preset);
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
  const [exportFormat, setExportFormat] = useState(DEFAULTS.exportFormat);
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
  const [overlayAccent, setOverlayAccent] = useState(DEFAULTS.overlayAccent);

  const [isPlaying, setIsPlaying] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isSeeking, setIsSeeking] = useState(false);

  const [zoomKeyframes, setZoomKeyframes] = useState([]);

  const videoRef = useRef(null);
  const previewCanvasRef = useRef(null);
  // The one file input, referenced so the empty frame's upload button can
  // drive it. Two inputs would mean two sources of truth and a duplicate
  // `data-testid` for the same control.
  const fileInputRef = useRef(null);
  const rafRef = useRef(null);
  const audioCtxRef = useRef(null);
  const audioSrcRef = useRef(null);
  const audioDestRef = useRef(null);
  const isExportingRef = useRef(false);
  const zoomKeyframesRef = useRef([]);
  const liveZoomRef = useRef({
    scale: 1, offX: 0, offY: 0,
    handZoom: 1, handPanX: 0, handPanY: 0,
  });
  const sourceObjectUrlRef = useRef(null);
  const resultObjectUrlRef = useRef(null);

  useEffect(() => {
    preloadHandViewImages();
  }, []);

  useEffect(() => {
    if (document.fonts?.load) {
      document.fonts.load(`700 100px ${HOOK_FONT}`).catch(() => {});
    }
  }, []);

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
        if (!res.ok) throw new Error(`The finished render returned ${res.status}. Reload to get a fresh link.`);
        const blob = await res.blob();
        if (cancelled) return;
        const url = URL.createObjectURL(blob);
        sourceObjectUrlRef.current = url;
        setVideoUrl(url);
        setSourceReplaced(false);
      } catch (e) {
        if (!cancelled) setError(e?.message || "The finished render could not be loaded.");
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
    setResult(null);
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
   */
  const clearSource = () => {
    if (!generation || !sourceUrl) return;
    setSourceFileName("");
    setSourceReplaced(false);
    setError(null);
    setLoadingSource(true);
    (async () => {
      try {
        const res = await fetch(sourceUrl);
        if (!res.ok) throw new Error(`The finished render returned ${res.status}. Reload to get a fresh link.`);
        const blob = await res.blob();
        if (sourceObjectUrlRef.current) URL.revokeObjectURL(sourceObjectUrlRef.current);
        const url = URL.createObjectURL(blob);
        sourceObjectUrlRef.current = url;
        setVideoUrl(url);
      } catch (e) {
        setError(e?.message || "The finished render could not be reloaded.");
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
    const refVideo = videoRef.current;
    if (refVideo) {
      refVideo.src = videoUrl;
      refVideo.muted = true;
      refVideo.loop = true;
      refVideo.playsInline = true;
      refVideo.load();
      refVideo.play().catch(() => {});
      setIsPlaying(true);
      setCurrentTime(0);
    }
  }, [videoUrl]);

  // Track current time from the video element
  useEffect(() => {
    const video = videoRef.current;
    if (!video) return undefined;
    const onTime = () => {
      if (!isSeeking) setCurrentTime(video.currentTime);
    };
    video.addEventListener("timeupdate", onTime);
    let raf = 0;
    let lastReported = 0;
    const tick = () => {
      if (!isSeeking && video && !video.paused) {
        const t = video.currentTime;
        if (Math.abs(t - lastReported) >= 0.05) {
          lastReported = t;
          setCurrentTime(t);
        }
      }
      raf = requestAnimationFrame(tick);
    };
    raf = requestAnimationFrame(tick);
    return () => {
      video.removeEventListener("timeupdate", onTime);
      cancelAnimationFrame(raf);
    };
  }, [isSeeking]);

  const togglePlayPause = () => {
    const video = videoRef.current;
    if (!video) return;
    if (video.paused) {
      video.play().catch(() => {});
      setIsPlaying(true);
    } else {
      video.pause();
      setIsPlaying(false);
    }
  };

  const handleSeek = (time) => {
    const video = videoRef.current;
    if (!video) return;
    video.currentTime = time;
    setCurrentTime(time);
  };

  useEffect(() => {
    zoomKeyframesRef.current = sortKeyframes(zoomKeyframes);
  }, [zoomKeyframes]);

  useEffect(() => {
    liveZoomRef.current = {
      scale: videoScale, offX: videoOffsetX, offY: videoOffsetY,
      handZoom, handPanX, handPanY,
    };
  }, [videoScale, videoOffsetX, videoOffsetY, handZoom, handPanX, handPanY]);

  const handleCaptureZoomLock = () => {
    const video = videoRef.current;
    const t = video ? video.currentTime : 0;
    setZoomKeyframes((prev) =>
      captureZoomLock(prev, t, {
        scale: videoScale,
        offX: videoOffsetX,
        offY: videoOffsetY,
        handZoom,
        handPanX,
        handPanY,
      })
    );
  };

  const handleRemoveZoomKeyframe = (id) => {
    setZoomKeyframes((prev) => removeZoomKeyframe(prev, id));
  };

  const handleClearZoomKeyframes = () => setZoomKeyframes([]);

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

    const drawOverlays = () => {
      const vt = video.currentTime || 0;
      const dur = videoMeta.d || 0;
      const hookWindow = dur > 0 ? Math.min(hookDuration, dur * 0.45) : hookDuration;
      const ctaWindow = dur > 0 ? Math.min(ctaDuration, dur * 0.45) : ctaDuration;
      if (hookEnabled) {
        drawHookOverlay(ctx, cw, ch, vt, { text: hookText, duration: hookWindow, accent: overlayAccent, offsetX: hookOffsetX, offsetY: hookOffsetY });
      }
      if (ctaEnabled && dur > 0) {
        drawEndCard(ctx, cw, ch, dur - vt, {
          headline: ctaHeadline,
          handle: ctaHandle,
          duration: ctaWindow,
          accent: overlayAccent,
          offsetX: ctaOffsetX,
          offsetY: ctaOffsetY,
        });
      }
    };

    const draw = () => {
      ctx.clearRect(0, 0, cw, ch);

      const vt = video.currentTime || 0;
      const ez = getEffectiveZoom({
        keyframes: zoomKeyframesRef.current,
        live: liveZoomRef.current,
        videoTime: vt,
        isExporting: isExportingRef.current,
      });

      if (viewMode === "hand" && video) {
        const t = performance.now() / 1000;
        drawHandView(ctx, cw, ch, video, envBg, t, videoFit, ez.vScale, ez.vOffX, ez.vOffY, { x: screenX, y: screenY, w: screenW, h: screenH }, ez.hZoom, ez.hPanX, ez.hPanY);
        drawOverlays();
        rafRef.current = requestAnimationFrame(draw);
        return;
      }

      const isFloat = bg !== "transparent";

      if (isFloat) {
        const t = performance.now() / 1000;
        const palette = COLOR_PALETTES[bg] || COLOR_PALETTES.lavender;

        const bgGrad = ctx.createRadialGradient(cw * 0.5, ch * 0.4, 0, cw * 0.5, ch * 0.5, cw * 0.7);
        bgGrad.addColorStop(0, palette.bg2);
        bgGrad.addColorStop(1, palette.bg1);
        ctx.fillStyle = bgGrad;
        ctx.fillRect(0, 0, cw, ch);

        const fit = Math.min(cw / phoneW, ch / phoneH) * scale * 0.85;
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

        if (anim === "float") {
          ctx.save();
          const glowAlpha = 0.30 + Math.sin(t * 0.4) * 0.10;
          ctx.globalAlpha = glowAlpha;
          const glowGrad = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR * 1.1);
          glowGrad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          glowGrad.addColorStop(0.3, palette.glow.replace(/[\d.]+\)$/, "0.7)"));
          glowGrad.addColorStop(0.6, palette.glow);
          glowGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = glowGrad;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "pulse") {
          const pulsePhase = Math.sin(t * 0.5);
          const pulseR = glowR * (0.7 + pulsePhase * 0.3);
          const pulseAlpha = 0.25 + pulsePhase * 0.12;

          ctx.save();
          ctx.globalAlpha = pulseAlpha;
          const pulseGrad = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, pulseR);
          pulseGrad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          pulseGrad.addColorStop(0.35, palette.glow.replace(/[\d.]+\)$/, "0.6)"));
          pulseGrad.addColorStop(0.7, palette.accent.replace(/[\d.]+\)$/, "0.3)"));
          pulseGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = pulseGrad;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = 0.08 + pulsePhase * 0.04;
          ctx.beginPath();
          ctx.arc(glowX, glowY, pulseR * 1.1, 0, Math.PI * 2);
          ctx.lineWidth = drawW * 0.02;
          ctx.strokeStyle = palette.glow.replace(/[\d.]+\)$/, "0.5)");
          ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "orbit") {
          const orbitAngle = t * 0.6;
          const orbitR = glowR * 0.65;

          ctx.save();
          ctx.globalAlpha = 0.08;
          ctx.beginPath();
          ctx.ellipse(cx2, cy2, orbitR, orbitR * 0.35, 0.2, 0, Math.PI * 2);
          ctx.lineWidth = drawW * 0.015;
          ctx.strokeStyle = palette.glow.replace(/[\d.]+\)$/, "0.6)");
          ctx.stroke();
          ctx.globalAlpha = 1;
          ctx.restore();

          const dotX = cx2 + Math.cos(orbitAngle) * orbitR;
          const dotY = cy2 + Math.sin(orbitAngle) * orbitR * 0.35;
          const dotR = drawW * 0.06;

          ctx.save();
          ctx.globalAlpha = 0.4;
          const dotGrad = ctx.createRadialGradient(dotX, dotY, 0, dotX, dotY, dotR * 3);
          dotGrad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          dotGrad.addColorStop(0.3, palette.glow.replace(/[\d.]+\)$/, "0.5)"));
          dotGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = dotGrad;
          ctx.fillRect(dotX - dotR * 3, dotY - dotR * 3, dotR * 6, dotR * 6);
          ctx.globalAlpha = 1;
          ctx.restore();

          const dot2X = cx2 + Math.cos(orbitAngle + Math.PI) * orbitR;
          const dot2Y = cy2 + Math.sin(orbitAngle + Math.PI) * orbitR * 0.35;
          ctx.save();
          ctx.globalAlpha = 0.2;
          const dot2Grad = ctx.createRadialGradient(dot2X, dot2Y, 0, dot2X, dot2Y, dotR * 2);
          dot2Grad.addColorStop(0, palette.accent.replace(/[\d.]+\)$/, "1)"));
          dot2Grad.addColorStop(0.4, palette.accent.replace(/[\d.]+\)$/, "0.4)"));
          dot2Grad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = dot2Grad;
          ctx.fillRect(dot2X - dotR * 2, dot2Y - dotR * 2, dotR * 4, dotR * 4);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = 0.12;
          const centerGlow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR * 0.5);
          centerGlow.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          centerGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = centerGlow;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();
        }

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

        if (anim === "rays") {
          ctx.save();
          ctx.globalAlpha = 0.12;
          const rGlow = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, glowR);
          rGlow.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          rGlow.addColorStop(0.4, palette.glow);
          rGlow.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = rGlow;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = 0.07;
          const rayCount = 8;
          const rayBaseAngle = t * 0.15;
          for (let i = 0; i < rayCount; i++) {
            const angle = rayBaseAngle + (i / rayCount) * Math.PI * 2;
            const rayLen = Math.max(cw, ch) * 0.8;
            const rayWidth = 0.08 + Math.sin(t * 0.3 + i * 1.7) * 0.03;
            ctx.beginPath();
            ctx.moveTo(glowX, glowY);
            ctx.lineTo(glowX + Math.cos(angle - rayWidth) * rayLen, glowY + Math.sin(angle - rayWidth) * rayLen);
            ctx.lineTo(glowX + Math.cos(angle + rayWidth) * rayLen, glowY + Math.sin(angle + rayWidth) * rayLen);
            ctx.closePath();
            const rayGrad = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, rayLen);
            rayGrad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
            rayGrad.addColorStop(0.4, palette.glow);
            rayGrad.addColorStop(1, "rgba(0, 0, 0, 0)");
            ctx.fillStyle = rayGrad;
            ctx.fill();
          }
          ctx.globalAlpha = 1;
          ctx.restore();
        }

        if (anim === "aurora") {
          ctx.save();
          ctx.globalAlpha = 0.14;
          const w1Y = ch * 0.35 + Math.sin(t * 0.4) * ch * 0.08;
          const w1Grad = ctx.createRadialGradient(cw * 0.3 + Math.sin(t * 0.3) * cw * 0.1, w1Y, 0, cw * 0.3, w1Y, cw * 0.5);
          w1Grad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          w1Grad.addColorStop(0.4, palette.glow);
          w1Grad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = w1Grad;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = 0.10;
          const w2Y = ch * 0.5 + Math.sin(t * 0.35 + 1.5) * ch * 0.06;
          const w2Grad = ctx.createRadialGradient(cw * 0.7 + Math.sin(t * 0.25 + 2) * cw * 0.08, w2Y, 0, cw * 0.7, w2Y, cw * 0.45);
          w2Grad.addColorStop(0, palette.accent.replace(/[\d.]+\)$/, "1)"));
          w2Grad.addColorStop(0.4, palette.accent);
          w2Grad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = w2Grad;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          const w3Alpha = 0.10 + Math.sin(t * 0.5) * 0.04;
          ctx.globalAlpha = w3Alpha;
          const w3Grad = ctx.createRadialGradient(glowX, glowY, 0, glowX, glowY, drawH * 0.7);
          w3Grad.addColorStop(0, palette.glow.replace(/[\d.]+\)$/, "1)"));
          w3Grad.addColorStop(0.5, palette.glow);
          w3Grad.addColorStop(1, "rgba(0, 0, 0, 0)");
          ctx.fillStyle = w3Grad;
          ctx.fillRect(0, 0, cw, ch);
          ctx.globalAlpha = 1;
          ctx.restore();

          ctx.save();
          ctx.globalAlpha = 0.04;
          for (let i = 0; i < 4; i++) {
            const sY = ch * (0.25 + i * 0.18) + Math.sin(t * 0.2 + i * 0.8) * ch * 0.03;
            const sGrad = ctx.createLinearGradient(0, sY - ch * 0.015, 0, sY + ch * 0.015);
            sGrad.addColorStop(0, "rgba(0,0,0,0)");
            sGrad.addColorStop(0.5, palette.glow.replace(/[\d.]+\)$/, "0.8)"));
            sGrad.addColorStop(1, "rgba(0,0,0,0)");
            ctx.fillStyle = sGrad;
            ctx.fillRect(0, sY - ch * 0.015, cw, ch * 0.03);
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
        drawPhone(ctx, 0, 0, drawW, drawH, dev, video, videoFit, ez.vScale, ez.vOffX, ez.vOffY);
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
        const fit = Math.min(cw / phoneW, ch / phoneH) * scale;
        const drawW = phoneW * fit;
        const drawH = phoneH * fit;
        const x = (cw - drawW) / 2;
        const y = (ch - drawH) / 2;
        drawPhone(ctx, x, y, drawW, drawH, dev, video, videoFit, ez.vScale, ez.vOffX, ez.vOffY);
      }
      drawOverlays();
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device, preset, scale, mockupStretchY, videoMeta, bg, anim, videoFit, videoScale, videoOffsetX, videoOffsetY, viewMode, envBg, screenX, screenY, screenW, screenH, handZoom, handPanX, handPanY, hookEnabled, hookText, hookDuration, hookOffsetX, hookOffsetY, ctaEnabled, ctaHeadline, ctaHandle, ctaDuration, ctaOffsetX, ctaOffsetY, overlayAccent, zoomKeyframes]);

  const seekVideo = (video, time) => new Promise((resolve) => {
    const done = () => { video.removeEventListener("seeked", done); resolve(); };
    video.addEventListener("seeked", done, { once: true });
    video.currentTime = time;
    if (Math.abs(video.currentTime - time) < 0.02) requestAnimationFrame(done);
  });

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
    const canvas = previewCanvasRef.current;
    if (!video || !canvas || !videoMeta) return;
    if (typeof MediaRecorder === "undefined" || typeof canvas.captureStream !== "function") {
      setError("This browser cannot record video here. Download the finished render and export it elsewhere.");
      return;
    }

    setError(null);
    setSaveError(null);
    setSaved(null);
    setRecording(true);
    setProgress(0);
    setResult(null);
    isExportingRef.current = true;

    try {
      const transparent = viewMode !== "hand" && bg === "transparent";
      const mimes = supportedExportMimes({ transparent, exportFormat });
      if (!mimes.length) throw new Error("Your browser does not support video recording.");

      // Pre-flight: an instant stop — zero duration, a canvas that never sized —
      // produces a valid-looking empty file that no player opens. Fail here with
      // words instead of offering that file with a confident filename.
      if (!Number.isFinite(videoMeta.d) || videoMeta.d <= 0) {
        throw new Error("The clip has no playable duration, so there is nothing to record.");
      }
      if (!canvas.width || !canvas.height) {
        throw new Error("The preview has no size yet. Wait for it to appear, then export again.");
      }

      const stream = canvas.captureStream(CAPTURE_FPS);
      video.loop = false;
      video.muted = false;
      video.volume = 1;
      let audioTrackAdded = false;

      try {
        const capturableVideo = video;
        const sourceStream = (capturableVideo.captureStream ?? capturableVideo.mozCaptureStream)?.call(video);
        const audioTracks = sourceStream?.getAudioTracks() ?? [];
        for (const track of audioTracks) {
          stream.addTrack(track);
          audioTrackAdded = true;
        }
      } catch (captureErr) {
        console.warn("Native audio capture failed:", captureErr);
      }

      try {
        if (!audioTrackAdded && !audioCtxRef.current) {
          const Ctx = window.AudioContext || window.webkitAudioContext;
          audioCtxRef.current = new Ctx();
        }
        if (!audioTrackAdded && audioCtxRef.current) {
          const ac = audioCtxRef.current;
          if (ac.state === "suspended") await ac.resume();
          if (!audioSrcRef.current) {
            audioSrcRef.current = ac.createMediaElementSource(video);
          }
          if (!audioDestRef.current) {
            audioDestRef.current = ac.createMediaStreamDestination();
            audioSrcRef.current.connect(audioDestRef.current);
            audioSrcRef.current.connect(ac.destination);
          }
          for (const track of audioDestRef.current.stream.getAudioTracks()) {
            stream.addTrack(track);
            audioTrackAdded = true;
          }
        }
      } catch (audioErr) {
        console.warn("Audio capture failed:", audioErr);
      }

      // One attempt per supported MIME. A recorder-level failure — the encoder
      // rejecting a configuration `isTypeSupported` passed, which is exactly
      // what "configuration is not supported" means — advances to the next
      // candidate instead of failing the export. Validation failures below do
      // NOT retry: an empty capture is environmental, and every candidate would
      // produce the same nothing at the cost of another full recording pass.
      const recordAttempt = async (candidateMime) => {
        const recorder = new MediaRecorder(stream, {
          mimeType: candidateMime,
          videoBitsPerSecond: VIDEO_BITS_PER_SECOND,
          audioBitsPerSecond: AUDIO_BITS_PER_SECOND,
        });
        const chunks = [];
        recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
        const done = new Promise((res, rej) => {
          // Without this, a mid-record mux failure resolves the blob anyway and
          // the partial file is offered as a download. Rejecting here routes it
          // to the fallback below like any other recorder failure.
          recorder.onerror = (e) => {
            const detail = e?.error?.message || e?.error?.name || "unknown recorder error";
            const err = new Error(`The recording failed mid-capture (${detail}). Trying the next format.`);
            err.retryableRecorderError = true;
            rej(err);
          };
          recorder.onstop = () => res(new Blob(chunks, { type: candidateMime }));
        });

        await seekVideo(video, 0);
        await video.play();
        setProgress(0);
        try {
          // A 250ms timeslice: same accumulated output, but chunks flow during
          // the capture instead of arriving only at stop, so a stalled recorder
          // shows itself earlier.
          recorder.start(250);
        } catch (e) {
          const err = new Error(`This format was rejected before recording started (${e?.message || e}). Trying the next one.`);
          err.retryableRecorderError = true;
          throw err;
        }

        const duration = videoMeta.d;
        const start = performance.now();
        const finished = new Promise((resolve) => {
          const tick = () => {
            const elapsed = (performance.now() - start) / 1000;
            setProgress(Math.min(1, elapsed / duration));
            if (video.ended || elapsed >= duration) resolve();
            else requestAnimationFrame(tick);
          };
          tick();
        });
        try {
          // If the recorder dies mid-capture, `done` rejects and this aborts
          // the wait instead of sitting out the full duration for a dead take.
          await Promise.race([finished, done]);
        } finally {
          // Guarded: stopping an already-inactive recorder throws
          // InvalidStateError and masks the real failure with noise.
          if (recorder.state !== "inactive") {
            try {
              recorder.stop();
            } catch {
              // Already handled through `done`.
            }
          }
          video.pause();
        }
        return done;
      };

      let blob = null;
      let mime = null;
      let encoderError = null;
      for (const candidate of mimes) {
        try {
          blob = await recordAttempt(candidate);
          mime = candidate;
          encoderError = null;
          break;
        } catch (e) {
          if (e && e.retryableRecorderError) {
            encoderError = e;
            continue;
          }
          throw e;
        }
      }
      if (!blob) {
        throw encoderError ?? new Error("Your browser does not support video recording.");
      }
      video.loop = true;
      video.muted = true;
      const ext = extensionForMime(mime);

      // Post-record validation. Everything below is about refusing to offer a
      // broken download: a file that fails here never gets a URL, a filename,
      // or a History row.
      if (!isPlausibleRecordingSize(blob.size)) {
        throw new Error("The recording came out empty — nothing was captured. Try again, or switch Export format to WebM in Output.");
      }
      const head = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
      const container = sniffRecordingContainer(head);
      if (!container) {
        throw new Error("The recording is damaged and would not play. Try again, or switch Export format to WebM in Output.");
      }
      if ((ext === "mp4") !== (container === "mp4")) {
        throw new Error("The recording is not the format it claims to be. Try again, or switch Export format to WebM in Output.");
      }
      await probeRecordingPlays(blob);

      const url = URL.createObjectURL(blob);
      if (resultObjectUrlRef.current) URL.revokeObjectURL(resultObjectUrlRef.current);
      resultObjectUrlRef.current = url;
      const pre = PRESETS.find((p) => p.id === preset) || PRESETS[0];
      const name = buildExportFilename({ device, preset: pre.id, width: canvas.width, height: canvas.height, ext });
      setResult({ url, name, size: blob.size, mime, blob });
      // Saved straight into History, beside the original. The download below
      // stays as a secondary action, never the only path.
      await saveExport(blob, name);
    } catch (e) {
      setError(e?.message || "The export could not be recorded.");
    } finally {
      isExportingRef.current = false;
      if (video) { video.loop = true; video.muted = true; }
      setRecording(false);
      setProgress(0);
    }
  };

  const handlePointerDown = (e) => {
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
    const ctaWindow = ctaDuration + 0.4;
    const hookVisible = hookEnabled && vt <= hookWindow;
    const ctaVisible = ctaEnabled && dur > 0 && (dur - vt) <= ctaWindow && (dur - vt) >= 0;

    let dragTarget = "video";
    if (hookVisible) {
      const hb = getHookBounds(canvasW, canvasH, hookText, hookOffsetX, hookOffsetY);
      if (hb && cx >= hb.x && cx <= hb.x + hb.w && cy >= hb.y && cy <= hb.y + hb.h) {
        dragTarget = "hook";
      }
    }
    if (ctaVisible && dragTarget === "video") {
      const cb = getEndCardBounds(canvasW, canvasH, ctaHeadline, ctaHandle, ctaOffsetX, ctaOffsetY);
      if (cb && cx >= cb.x && cx <= cb.x + cb.w && cy >= cb.y && cy <= cb.y + cb.h) {
        dragTarget = "cta";
      }
    }

    const startHookX = hookOffsetX;
    const startHookY = hookOffsetY;
    const startCtaX = ctaOffsetX;
    const startCtaY = ctaOffsetY;
    const isHand = viewMode === "hand";
    const startOffX = isHand ? handPanX : videoOffsetX;
    const startOffY = isHand ? handPanY : videoOffsetY;

    const move = (ev) => {
      const dx = (ev.clientX - startX) / rect.width;
      const dy = (ev.clientY - startY) / rect.height;
      if (dragTarget === "hook") {
        setHookOffsetX(startHookX + dx);
        setHookOffsetY(startHookY + dy);
      } else if (dragTarget === "cta") {
        setCtaOffsetX(startCtaX + dx);
        setCtaOffsetY(startCtaY + dy);
      } else if (isHand) {
        setHandPanX(startOffX + dx);
        setHandPanY(startOffY + dy);
      } else {
        setVideoOffsetX(Math.max(-100, Math.min(100, Math.round(startOffX + dx * 200))));
        setVideoOffsetY(Math.max(-100, Math.min(100, Math.round(startOffY + dy * 200))));
      }
    };
    const up = () => { window.removeEventListener("pointermove", move); window.removeEventListener("pointerup", up); };
    window.addEventListener("pointermove", move);
    window.addEventListener("pointerup", up);
  };

  const handleWheel = (e) => {
    e.preventDefault();
    if (viewMode === "hand") {
      setHandZoom((z) => Math.max(0.4, Math.min(3, +(z - e.deltaY * 0.0015).toFixed(3))));
    } else {
      setVideoScale((s) => Math.max(0.5, Math.min(3, +(s - e.deltaY * 0.002).toFixed(2))));
    }
  };

  const duration = videoMeta?.d ?? 0;
  const sortedKeyframes = sortKeyframes(zoomKeyframes);
  const interval = tickInterval(duration);
  const ticks = [];
  if (duration > 0) {
    for (let t = 0; t <= duration; t += interval) ticks.push(t);
    if (ticks[ticks.length - 1] < duration - interval * 0.3) ticks.push(duration);
  }

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
    <div className="grid items-start gap-6 lg:grid-cols-[minmax(0,1fr)_minmax(0,1.15fr)] xl:grid-cols-[minmax(0,1fr)_740px]">
      <div className="relative min-w-0">
        {/* Back to top. Deliberately outside the scrolling panel and to its
            left, so it can never sit over the sticky preview. */}
        <button
          type="button"
          onClick={() => settingsRef.current?.scrollTo({ top: 0, behavior: "smooth" })}
          aria-label="Back to top of settings"
          title="Back to top"
          className="absolute -left-1 top-0 z-20 hidden h-9 w-9 -translate-x-full items-center justify-center rounded-full border border-[color:var(--hairline)] bg-card text-muted-foreground transition duration-150 hover:border-[color:var(--brand-indigo)] hover:text-foreground hover:bg-[color:var(--indigo-8)] focus:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--brand-indigo)]/40 lg:flex"
        >
          <ArrowUp className="h-4 w-4" />
        </button>

        {/* Own scroll container, own slim scrollbar, and enough right padding that a
            6px bar never sits over a card edge. */}
        <div
          ref={settingsRef}
          className="demo-cta-panel-scroll space-y-3 lg:max-h-[calc(100vh-7rem)] lg:overflow-y-auto lg:overscroll-contain lg:pr-2.5"
        >
        <EditorSection title="Source & Look" open={openSections.source} onToggle={() => toggleSection("source")} testId="demo-cta-source">
          {generation ? (
            <>
              <p className="text-xs text-muted-foreground">
                This finished render is the input. Nothing is downloaded or uploaded to get it here.
              </p>
              <div className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="secondary">Hook + Middle</Badge>
                {videoMeta && <span className="text-muted-foreground">{videoMeta.w}x{videoMeta.h} • {videoMeta.d.toFixed(1)}s</span>}
              </div>
              {loadingSource && (
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <Loader2 className="h-3 w-3 animate-spin" /> Loading the finished render…
                </p>
              )}
            </>
          ) : (
            <p className="text-xs text-muted-foreground">
              Bring your own footage. Drop a clip in to use Demo + CTA on its own,
              without generating a hook first.
            </p>
          )}
          <div className="flex flex-wrap items-center gap-2">
            {/* No picker button here. The frame carries the upload action in
                both routes, so a second button in this group was two doors to
                the same input. The input itself stays — the frame's button
                drives it by ref — unwrapped and named, since a `sr-only`
                input with no label is invisible to assistive tech too. */}
            <input
              ref={fileInputRef}
              type="file"
              accept="video/*"
              aria-label="Choose a video file"
              data-testid="demo-cta-file-input"
              className="sr-only"
              onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
            />
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
              Source replaced for this edit. The export is still filed under the selected Hook + Middle.
            </p>
          )}
          <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
            <SubLabel>View style</SubLabel>
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
                  className={`h-8 rounded-lg text-xs font-medium transition duration-150 ${
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
                  className={`overflow-hidden rounded-xl border text-xs transition ${
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
                      className={`h-10 w-10 shrink-0 overflow-hidden rounded-xl border transition duration-150 ${
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
                    className. Two columns below xl — "Breathing Pulse" does not
                    fit the ~92px a third column leaves at that width. */}
                <div
                  role="group"
                  aria-label="Animation"
                  data-testid="animation-group"
                  className="grid grid-cols-2 gap-1.5 xl:grid-cols-3"
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
              <ControlSlider label="Phone size" value={scale} min={RANGES.scale.min} max={RANGES.scale.max} step={RANGES.scale.step} onChange={setScale} testId="phone-size-slider" format={(v) => `${Math.round(v * 100)}%`} />
            </>
          )}
          {viewMode === "hand" && (
            <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
              <SubLabel>Hand size &amp; position</SubLabel>
              <p className="text-xs text-muted-foreground">Drag the preview to move • scroll to zoom</p>
              <ControlSlider label="Zoom" value={handZoom} min={RANGES.handZoom.min} max={RANGES.handZoom.max} step={RANGES.handZoom.step} onChange={setHandZoom} testId="hand-zoom-slider" format={(v) => `${v.toFixed(2)}x`} />
              <ControlSlider label="H position" value={handPanX} min={RANGES.handPan.min} max={RANGES.handPan.max} step={RANGES.handPan.step} onChange={setHandPanX} testId="hand-panx-slider" format={(v) => `${Math.round(v * 100)}%`} />
              <ControlSlider label="V position" value={handPanY} min={RANGES.handPan.min} max={RANGES.handPan.max} step={RANGES.handPan.step} onChange={setHandPanY} testId="hand-pany-slider" format={(v) => `${Math.round(v * 100)}%`} />
              <ResetButton testId="hand-transform-reset-btn" onClick={() => { setHandZoom(1); setHandPanX(0); setHandPanY(0); }}>
                Reset hand framing
              </ResetButton>
            </div>
          )}
        </EditorSection>

        <EditorSection title="Hook Text" open={openSections.hook} onToggle={() => toggleSection("hook")} testId="hook-controls">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid="hook-toggle" checked={hookEnabled} onCheckedChange={setHookEnabled} />
            Show punch-in hook on frame 1
          </label>
          <textarea
            data-testid="hook-text-input"
            value={hookText}
            onChange={(e) => setHookText(e.target.value)}
            rows={3}
            placeholder="I built this so I'd stop journaling in Notes app"
            className={TEXTAREA_CLASS}
          />
          <ControlSlider label="On screen" value={hookDuration} min={RANGES.hookDuration.min} max={RANGES.hookDuration.max} step={RANGES.hookDuration.step} onChange={setHookDuration} testId="hook-duration-slider" format={(v) => `${v.toFixed(1)}s`} />
          {(hookOffsetX !== 0 || hookOffsetY !== 0) && (
            <ResetButton onClick={() => { setHookOffsetX(0); setHookOffsetY(0); }}>Reset position</ResetButton>
          )}
          <p className="text-xs italic text-muted-foreground">Drag the hook text on the preview to reposition</p>
        </EditorSection>

        <EditorSection title="End Card CTA" open={openSections.cta} onToggle={() => toggleSection("cta")} testId="cta-controls">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid="cta-toggle" checked={ctaEnabled} onCheckedChange={setCtaEnabled} />
            Show lead-gen end card
          </label>
          <input
            data-testid="cta-headline-input"
            value={ctaHeadline}
            onChange={(e) => setCtaHeadline(e.target.value)}
            placeholder="Try it free — link in bio"
            className={INPUT_CLASS}
          />
          <input
            data-testid="cta-handle-input"
            value={ctaHandle}
            onChange={(e) => setCtaHandle(e.target.value)}
            placeholder="@yourhandle"
            className={INPUT_CLASS}
          />
          <ControlSlider label="Visible for" value={ctaDuration} min={RANGES.ctaDuration.min} max={RANGES.ctaDuration.max} step={RANGES.ctaDuration.step} onChange={setCtaDuration} testId="cta-duration-slider" format={(v) => `${v.toFixed(1)}s`} />
          {(ctaOffsetX !== 0 || ctaOffsetY !== 0) && (
            <ResetButton onClick={() => { setCtaOffsetX(0); setCtaOffsetY(0); }}>Reset position</ResetButton>
          )}
          <p className="text-xs italic text-muted-foreground">Drag the end card on the preview to reposition</p>
          <div className="space-y-2">
            <SubLabel>Accent</SubLabel>
            <div className="flex flex-wrap items-center gap-2">
              {ACCENT_SWATCHES.map((c) => (
                <button
                  key={c}
                  type="button"
                  data-testid={`overlay-accent-${c.replace("#", "")}`}
                  onClick={() => setOverlayAccent(c)}
                  style={{ background: c }}
                  aria-label={`Accent ${c}`}
                  aria-pressed={overlayAccent === c}
                  className={`h-10 w-10 shrink-0 rounded-full border-2 transition duration-150 ${
                    overlayAccent === c
                      ? "border-[color:var(--brand-indigo)] ring-2 ring-[color:var(--indigo-45)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                  }`}
                />
              ))}
            </div>
          </div>
          <p className="text-xs leading-snug text-muted-foreground">
            Laid out inside TikTok&apos;s safe area — clear of the right icon rail and bottom caption strip.
          </p>
        </EditorSection>

        <EditorSection title="Output" open={openSections.output} onToggle={() => toggleSection("output")}>
          {/* Platform preset as a two-line list rather than a native select:
              "TikTok / Reels / Shorts" as the value and "1080×1920" beneath it.
              A select truncates both into one clipped line at 420px, and the
              dimensions are the part you actually check before exporting. */}
          <div className="space-y-2">
            <SubLabel>Platform preset</SubLabel>
            <div
              role="radiogroup"
              aria-label="Platform preset"
              data-testid="platform-preset-group"
              className="space-y-1.5"
            >
              {PRESETS.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  role="radio"
                  aria-checked={preset === p.id}
                  onClick={() => setPreset(p.id)}
                  title={`${p.label} — ${p.id === "source" ? "auto" : `${p.w}x${p.h}`}`}
                  className={`flex w-full items-center justify-between gap-3 rounded-xl border px-3 py-2 text-left transition duration-150 ${
                    preset === p.id
                      ? "border-[color:var(--brand-indigo)] bg-[color:var(--brand-indigo)]/10"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)] hover:bg-secondary/40"
                  }`}
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground">{p.label}</span>
                  <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">
                    {p.id === "source" ? "auto" : `${p.w}x${p.h}`}
                  </span>
                </button>
              ))}
            </div>
          </div>
          <div className="space-y-2">
            <SubLabel>Export format</SubLabel>
            <select
              value={bg === "transparent" ? "webm" : exportFormat}
              disabled={bg === "transparent"}
              onChange={(e) => setExportFormat(e.target.value)}
              className={CONTROL_CLASS}
              aria-label="Export format"
            >
              <option value="auto">Auto (MP4)</option>
              <option value="mp4">MP4</option>
              <option value="webm">WebM</option>
            </select>
            {bg === "transparent" && (
              <p className="text-xs text-muted-foreground">Transparent backgrounds export as WebM to keep the alpha channel.</p>
            )}
          </div>
        </EditorSection>

        {/* Rarely touched. Mockup height, screen position and crop live here
            because they are set once and then left alone; keeping them in the
            main groups is what made the panel taller than the preview it is
            meant to describe. */}
        <EditorSection title="Advanced" open={openSections.advanced} onToggle={() => toggleSection("advanced")}>
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
                <div key={key} className="space-y-1.5">
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
                <ResetButton onClick={() => { setVideoFit("cover"); setVideoScale(1); setVideoOffsetX(0); setVideoOffsetY(0); }}>Reset</ResetButton>
              </div>
              <ControlSlider label="Zoom" value={videoScale} min={RANGES.videoScale.min} max={RANGES.videoScale.max} step={RANGES.videoScale.step} onChange={setVideoScale} format={(v) => `${v.toFixed(2)}x`} />
              <ControlSlider label="H offset" value={videoOffsetX} min={RANGES.videoOffset.min} max={RANGES.videoOffset.max} step={RANGES.videoOffset.step} onChange={(v) => setVideoOffsetX(Math.round(v))} format={(v) => `${Math.round(v)}%`} />
              <ControlSlider label="V offset" value={videoOffsetY} min={RANGES.videoOffset.min} max={RANGES.videoOffset.max} step={RANGES.videoOffset.step} onChange={(v) => setVideoOffsetY(Math.round(v))} format={(v) => `${Math.round(v)}%`} />
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
              className="block h-full w-full cursor-grab touch-none active:cursor-grabbing"
              onPointerDown={handlePointerDown}
              onWheel={handleWheel}
            />
          ) : loadingSource ? (
            <div className="h-full w-full animate-pulse bg-secondary/40" role="status" aria-label="Loading the finished render">
              <span className="sr-only">Loading the finished render…</span>
            </div>
) : (
              /* An actual control, not a sentence. "Upload a clip to preview"
                 read as a caption; the one thing you can do here is pick a
                 file, so the frame says so with a button that opens the
                 picker. Deliberately `secondary`, not coral: the Export button
                 is this screen's one primary action (design_guidelines.md:174),
                 and two coral buttons would make neither the primary one. */
              /* One control, and the label the frame used to carry above it.
                 "Live preview" lived in a caption row above the video, which
                 cost 16px plus a gap and said nothing while the frame was
                 empty — the dashed border and this copy both say it. With the
                 platform label gone the row held one word, which is not worth
                 a row of the column's height. */
              <div className="px-6 text-center">
                <Button
                  type="button"
                  variant="secondary"
                  size="sm"
                  onClick={() => fileInputRef.current?.click()}
                  data-testid="demo-cta-frame-upload"
                >
                  <Upload className="h-3.5 w-3.5" />
                  Upload a clip
                </Button>
                <p className="mt-2 text-xs text-muted-foreground">Live preview</p>
              </div>
            )}
        </div>

        {videoUrl && videoMeta && (
          /* A plain bar, not a card: the preview is chromeless, so a boxed
             player under a boxed preview was one box too many. It stays
             full-column — deliberately wider than the frame and the export
             button, which share a width with each other. */
          <div className="space-y-2" data-testid="demo-cta-player">
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
                      className="group absolute top-0 flex h-3 w-4 -translate-x-1/2 cursor-pointer items-start justify-center"
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
                        title={`${formatTime(seg.time)} → ${formatTime(end)}: ${seg.scale.toFixed(2)}x`}
                      />
                    );
                  })}
                </div>

                <div
                  className="group relative h-6 cursor-pointer"
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

                {/* Single control row: transport on the left, Zoom Lock on the
                    right. The time readout moved up here from below the
                    scrubber so nothing reads twice. Wrap below xl so the row
                    never overflows narrow columns; nowrap at xl where the
                    650px column is measured to hold it. */}
                <div className="flex flex-wrap items-center gap-x-1.5 gap-y-2 xl:flex-nowrap">
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
                  <div className="flex items-baseline gap-1.5 px-1">
                    <span className="font-mono text-sm font-medium tabular-nums tracking-tight">
                      {formatTime(currentTime)}
                    </span>
                    <span className="font-mono text-xs text-muted-foreground">/</span>
                    <span className="font-mono text-xs tabular-nums text-muted-foreground">
                      {formatTime(duration)}
                    </span>
                  </div>
                  <div className="ml-auto flex items-center gap-1.5">
                    {/* Export lives here, not in a bar of its own. The primary
                        action beside the Zoom Lock controls is where a decision
                        gets made — a separate bottom bar meant the column spent
                        44px plus a gap on a button that could just as well sit
                        in the row it belongs to. */}
                    <Button
                      type="button"
                      variant="brand"
                      size="sm"
                      disabled={!videoUrl || !videoMeta || recording || saving}
                      onClick={exportVideo}
                      data-testid="demo-cta-export"
                      title={(() => {
                        const pre = PRESETS.find((p) => p.id === preset) || PRESETS[0];
                        return `Export at ${pre.id === "source" ? "the phone's own size" : `${pre.w}x${pre.h}`}`;
                      })()}
                    >
                      {recording ? (
                        <><Loader2 className="h-3.5 w-3.5 animate-spin" /> {Math.round(progress * 100)}%</>
                      ) : (
                        <><Smartphone className="h-3.5 w-3.5" /> {bg === "transparent" ? "Export WebM" : "Export MP4"}</>
                      )}
                    </Button>
                    <span aria-hidden="true" className="text-muted-foreground/40">|</span>
                    <span className="eyebrow">Zoom Lock</span>
                    {zoomKeyframes.length > 0 && (
                      <span className="text-xs tabular-nums text-muted-foreground">
                        {zoomKeyframes.length}
                      </span>
                    )}
                    <Button type="button" variant="secondary" size="sm" onClick={handleCaptureZoomLock} title={`Lock the current zoom at ${formatTime(currentTime)}`}>
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
                    <div className="space-y-1.5 pb-1 pt-2">
                    {sortedKeyframes[0].time > 0.01 && (
                      <div className="flex items-center gap-2 rounded-lg border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2">
                        <span className="font-mono text-xs text-muted-foreground">0:00.0 → {formatTime(sortedKeyframes[0].time)} • default (1.00x)</span>
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
                            className="flex-1 text-left font-mono text-xs tabular-nums text-muted-foreground transition hover:text-foreground"
                            title="Jump to this keyframe"
                          >
                            {formatTime(kf.time)} → {formatTime(nextTime)} • {kf.scale.toFixed(2)}x zoom
                          </button>
                          <button
                            type="button"
                            onClick={() => handleRemoveZoomKeyframe(kf.id)}
                            className="flex-shrink-0 text-muted-foreground/60 opacity-0 transition hover:text-destructive group-hover:opacity-100"
                            title="Remove this keyframe"
                          >
                            <X className="h-3 w-3" />
                          </button>
                        </div>
                      );
                    })}
                    <p className="pt-0.5 text-xs text-muted-foreground">
                      Pause → seek to exact time → adjust zoom → Lock. Each segment displays its locked zoom in the preview and export.
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
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Saving to History…
            </p>
          )}
          {error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertDescription>{error}</AlertDescription>
            </Alert>
          )}
        </div>
        <video ref={videoRef} className="hidden" playsInline muted loop autoPlay />

        {result && (
          <SectionCard title="Export ready">
            <div className="flex items-center justify-between text-xs text-muted-foreground">
              <span>{result.mime.includes("mp4") ? "MP4" : "WebM"} • {(result.size / 1024 / 1024).toFixed(2)} MB</span>
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
                <Button variant="brand" size="sm" asChild>
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
                  Saved beside the original Hook + Middle in History. The original is untouched and still downloadable.
                </AlertDescription>
              </Alert>
            )}
          </SectionCard>
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
function drawPhone(ctx, x, y, w, h, dev, video, videoFit, videoScale, videoOffsetX, videoOffsetY) {
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
  ctx.fillStyle = "#000";
  ctx.fillRect(sx, sy, sw, sh);

  if (video.readyState >= 2) {
    const vw = video.videoWidth;
    const vh = video.videoHeight;
    let baseScale;
    if (videoFit === "contain") baseScale = Math.min(sw / vw, sh / vh);
    else baseScale = Math.max(sw / vw, sh / vh);
    const s = baseScale * videoScale;
    const dw = vw * s;
    const dh = vh * s;
    const maxOffX = Math.max(0, (dw - sw) / 2);
    const maxOffY = Math.max(0, (dh - sh) / 2);
    const offX = (videoOffsetX / 100) * maxOffX;
    const offY = (videoOffsetY / 100) * maxOffY;
    const dx = sx + (sw - dw) / 2 + offX;
    const dy = sy + (sh - dh) / 2 + offY;
    ctx.drawImage(video, dx, dy, dw, dh);
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
