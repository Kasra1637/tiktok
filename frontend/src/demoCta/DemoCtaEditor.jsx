import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import {
  AlertTriangle,
  Check,
  ChevronDown,
  Download,
  Info,
  Loader2,
  Pause,
  Play,
  RotateCcw,
  Smartphone,
  X,
} from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Progress } from "../components/ui/progress";
import { Slider } from "../components/ui/slider";
import { Switch } from "../components/ui/switch";
import { SectionCard } from "../components/SectionCard";
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
  selectExportMime,
} from "./constants";
import { drawEndCard, drawHookOverlay, getEndCardBounds, getHookBounds, HOOK_FONT } from "./overlays";
import { drawHandView, preloadHandViewImages } from "./handView";
import { captureZoomLock, getEffectiveZoom, removeZoomKeyframe, sortKeyframes, tickInterval } from "./zoom";

const SELECT_CLASS =
  "w-full appearance-none truncate rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2 text-sm outline-none transition focus:border-[color:var(--brand-indigo)]";

/**
 * One collapsible control group. The standalone app's sidebar sections map
 * one-to-one onto these; only the skin changed to the app's card language.
 */
function EditorSection({ title, defaultOpen = false, testId, children }) {
  const [open, setOpen] = useState(defaultOpen);
  return (
    <SectionCard
      className="!space-y-0 p-0"
      data-testid={testId}
    >
      <button
        type="button"
        onClick={() => setOpen((v) => !v)}
        aria-expanded={open}
        className="flex w-full items-center justify-between gap-2 px-3.5 py-2.5 text-left"
      >
        <span className="eyebrow">{title}</span>
        <ChevronDown className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform ${open ? "rotate-180" : ""}`} />
      </button>
      {open && <div className="space-y-2.5 px-3.5 pb-3.5">{children}</div>}
    </SectionCard>
  );
}

/** Small caps sub-label for blocks nested inside a group card. */
function SubLabel({ children }) {
  return (
    <p className="text-[11px] font-semibold uppercase tracking-wider text-muted-foreground">
      {children}
    </p>
  );
}

function FieldLabel({ children }) {
  return <span className="text-xs text-muted-foreground">{children}</span>;
}

function ControlSlider({ label, value, min, max, step, onChange, testId }) {
  return (
    <div className="space-y-1.5">
      <FieldLabel>{label}</FieldLabel>
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
      className="text-xs text-muted-foreground underline-offset-2 transition hover:text-foreground hover:underline"
    >
      {children || "Reset"}
    </button>
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
  const [videoUrl, setVideoUrl] = useState(null);
  const [sourceReplaced, setSourceReplaced] = useState(false);
  const [loadingSource, setLoadingSource] = useState(true);
  const [videoMeta, setVideoMeta] = useState(null);
  const [device, setDevice] = useState(DEFAULTS.device);
  const [frameColor, setFrameColor] = useState(DEFAULTS.frameColor);
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
    setSourceReplaced(true);
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
        drawPhone(ctx, 0, 0, drawW, drawH, dev, video, videoFit, ez.vScale, ez.vOffX, ez.vOffY, frameColor);
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
        drawPhone(ctx, x, y, drawW, drawH, dev, video, videoFit, ez.vScale, ez.vOffX, ez.vOffY, frameColor);
      }
      drawOverlays();
      rafRef.current = requestAnimationFrame(draw);
    };
    rafRef.current = requestAnimationFrame(draw);

    return () => {
      if (rafRef.current) cancelAnimationFrame(rafRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device, preset, scale, mockupStretchY, videoMeta, bg, anim, videoFit, videoScale, videoOffsetX, videoOffsetY, frameColor, viewMode, envBg, screenX, screenY, screenW, screenH, handZoom, handPanX, handPanY, hookEnabled, hookText, hookDuration, hookOffsetX, hookOffsetY, ctaEnabled, ctaHeadline, ctaHandle, ctaDuration, ctaOffsetX, ctaOffsetY, overlayAccent, zoomKeyframes]);

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
      const mime = selectExportMime({ transparent, exportFormat });
      if (!mime) throw new Error("Your browser does not support video recording.");
      const ext = extensionForMime(mime);

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

      const recorder = new MediaRecorder(stream, {
        mimeType: mime,
        videoBitsPerSecond: VIDEO_BITS_PER_SECOND,
        audioBitsPerSecond: AUDIO_BITS_PER_SECOND,
      });
      const chunks = [];
      recorder.ondataavailable = (e) => e.data.size && chunks.push(e.data);
      const done = new Promise((res) => {
        recorder.onstop = () => res(new Blob(chunks, { type: mime }));
      });

      await seekVideo(video, 0);
      await video.play();
      recorder.start();

      const duration = videoMeta.d;
      const start = performance.now();
      await new Promise((resolve) => {
        const tick = () => {
          const elapsed = (performance.now() - start) / 1000;
          setProgress(Math.min(1, elapsed / duration));
          if (video.ended || elapsed >= duration) resolve();
          else requestAnimationFrame(tick);
        };
        tick();
      });

      recorder.stop();
      video.pause();
      video.loop = true;
      video.muted = true;
      const blob = await done;
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

  return (
    <div className="grid gap-5 xl:grid-cols-[400px_minmax(0,1fr)]">
      <div className="min-w-0 space-y-3">
        <EditorSection title="Source & look" defaultOpen testId="demo-cta-source">
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
          <Button variant="secondary" size="sm" asChild className="w-full sm:w-auto">
            <label className="cursor-pointer">
              <span>{videoUrl ? "Replace video file" : "Choose a video"}</span>
              <input
                type="file"
                accept="video/*"
                data-testid="demo-cta-file-input"
                className="sr-only"
                onChange={(e) => e.target.files?.[0] && handleFile(e.target.files[0])}
              />
            </label>
          </Button>
          {sourceReplaced && generation && (
            <p className="text-xs text-muted-foreground">
              Source replaced for this edit. The export is still filed under the selected Hook + Middle.
            </p>
          )}
          <div className="grid grid-cols-2 gap-1.5 border-t border-[color:var(--hairline)] pt-2.5">
            {[
              ["floating", "Floating Phone"],
              ["hand", "Hand Holding"],
            ].map(([id, label]) => (
              <Button
                key={id}
                type="button"
                variant={viewMode === id ? "secondary" : "ghost"}
                size="sm"
                onClick={() => setViewMode(id)}
              >
                {label}
              </Button>
            ))}
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
                  <div className="px-0.5 py-1 text-center text-[10px] leading-tight text-muted-foreground">{env.label}</div>
                </button>
              ))}
            </div>
          )}
        </EditorSection>

        <EditorSection title="Framing">
          {viewMode === "floating" && (
            <div className="space-y-2">
              <SubLabel>Device</SubLabel>
              <select value={device} onChange={(e) => setDevice(e.target.value)} className={SELECT_CLASS} title={(DEVICES.find((d) => d.id === device) || {}).label} aria-label="Device frame">
                {DEVICES.map((d) => (
                  <option key={d.id} value={d.id}>{d.label}</option>
                ))}
              </select>
              <div className="flex items-center gap-2">
                <span className="text-xs text-muted-foreground">Frame color:</span>
                {[
                  ["black", "#0d0d10", "Black"],
                  ["white", "#f0f0f2", "White"],
                ].map(([id, color, title]) => (
                  <button
                    key={id}
                    type="button"
                    onClick={() => setFrameColor(id)}
                    title={title}
                    aria-label={title}
                    style={{ background: color }}
                    className={`h-6 w-6 rounded-full border-2 transition ${frameColor === id ? "border-[color:var(--brand-indigo)]" : "border-[color:var(--hairline)]"}`}
                  />
                ))}
              </div>
            </div>
          )}
          <div className="space-y-2">
            <SubLabel>Platform</SubLabel>
            <select value={preset} onChange={(e) => setPreset(e.target.value)} className={SELECT_CLASS} title={`${(PRESETS.find((p) => p.id === preset) || {}).label} — ${preset === "source" ? "auto" : `${(PRESETS.find((p) => p.id === preset) || {}).w}x${(PRESETS.find((p) => p.id === preset) || {}).h}`}`} aria-label="Platform preset">
              {PRESETS.map((p) => (
                <option key={p.id} value={p.id}>
                  {p.label} — {p.id === "source" ? "auto" : `${p.w}x${p.h}`}
                </option>
              ))}
            </select>
          </div>
          {viewMode === "floating" && (
            <div className="space-y-2">
              <SubLabel>Background</SubLabel>
              <div className="grid grid-cols-4 gap-1.5">
                {BACKGROUNDS.map((b) => (
                  <button
                    key={b.id}
                    type="button"
                    onClick={() => setBg(b.id)}
                    title={b.label}
                    aria-label={b.label}
                    className={`aspect-square overflow-hidden rounded-lg border transition ${
                      bg === b.id ? "border-[color:var(--brand-indigo)]" : "border-[color:var(--hairline)]"
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
          )}
          {viewMode === "floating" && (
            <div className="space-y-2">
              <SubLabel>Animation</SubLabel>
              <div className="grid grid-cols-2 gap-1.5">
                {ANIMATIONS.map((a) => (
                  <Button key={a.id} type="button" variant={anim === a.id ? "secondary" : "ghost"} size="sm" onClick={() => setAnim(a.id)}>
                    {a.label}
                  </Button>
                ))}
              </div>
            </div>
          )}
          {viewMode === "hand" && (
            <div className="space-y-2" data-testid="hand-transform-controls">
              <SubLabel>Hand framing</SubLabel>
              <p className="text-xs text-muted-foreground">Drag the preview to move • scroll to zoom</p>
              <ControlSlider label={`Zoom: ${handZoom.toFixed(2)}x`} value={handZoom} min={RANGES.handZoom.min} max={RANGES.handZoom.max} step={RANGES.handZoom.step} onChange={setHandZoom} testId="hand-zoom-slider" />
              <ControlSlider label={`H position: ${Math.round(handPanX * 100)}%`} value={handPanX} min={RANGES.handPan.min} max={RANGES.handPan.max} step={RANGES.handPan.step} onChange={setHandPanX} testId="hand-panx-slider" />
              <ControlSlider label={`V position: ${Math.round(handPanY * 100)}%`} value={handPanY} min={RANGES.handPan.min} max={RANGES.handPan.max} step={RANGES.handPan.step} onChange={setHandPanY} testId="hand-pany-slider" />
              <ResetButton testId="hand-transform-reset-btn" onClick={() => { setHandZoom(1); setHandPanX(0); setHandPanY(0); }}>
                Reset hand framing
              </ResetButton>
            </div>
          )}
          {viewMode === "hand" && (
            <div className="space-y-2" data-testid="screen-position-controls">
              <SubLabel>Screen position</SubLabel>
              {[
                ["Left", screenX, setScreenX, "left"],
                ["Top", screenY, setScreenY, "top"],
                ["Width", screenW, setScreenW, "width"],
                ["Height", screenH, setScreenH, "height"],
              ].map(([label, val, setter, key]) => (
                <div key={key} className="flex items-center gap-2">
                  <span className="w-11 shrink-0 text-xs text-muted-foreground">{label}</span>
                  <Slider
                    data-testid={`screen-${key}-slider`}
                    value={[val]}
                    min={RANGES.screen.min}
                    max={RANGES.screen.max}
                    step={RANGES.screen.step}
                    onValueChange={([next]) => setter(next)}
                    className="flex-1"
                  />
                  <span className="w-10 text-right font-mono text-[11px] text-muted-foreground">{(val * 100).toFixed(1)}</span>
                </div>
              ))}
              <ResetButton testId="screen-reset-btn" onClick={() => { setScreenX(DEFAULT_SCREEN.x); setScreenY(DEFAULT_SCREEN.y); setScreenW(DEFAULT_SCREEN.w); setScreenH(DEFAULT_SCREEN.h); }}>
                Reset to photo screen
              </ResetButton>
            </div>
          )}
          <div className="space-y-2">
            <SubLabel>Size</SubLabel>
            <ControlSlider label={`Phone size (${Math.round(scale * 100)}%)`} value={scale} min={RANGES.scale.min} max={RANGES.scale.max} step={RANGES.scale.step} onChange={setScale} />
          </div>
          <div className="space-y-2">
            <SubLabel>Height</SubLabel>
            <div className="flex items-center gap-2">
              <Slider value={[mockupStretchY]} min={RANGES.mockupStretchY.min} max={RANGES.mockupStretchY.max} step={RANGES.mockupStretchY.step} onValueChange={([next]) => setMockupStretchY(next)} className="flex-1" aria-label={`Mockup height (${Math.round(mockupStretchY * 100)}%)`} />
              <ResetButton onClick={() => setMockupStretchY(1)}>Reset</ResetButton>
            </div>
          </div>
          {videoUrl && (
            <div className="space-y-2">
              <SubLabel>Crop</SubLabel>
              <div className="flex items-center justify-between gap-2">
                <select value={videoFit} onChange={(e) => setVideoFit(e.target.value)} className={SELECT_CLASS} aria-label="Video fit">
                  <option value="cover">Cover</option>
                  <option value="contain">Contain</option>
                  <option value="fill">Fill</option>
                </select>
                <ResetButton onClick={() => { setVideoFit("cover"); setVideoScale(1); setVideoOffsetX(0); setVideoOffsetY(0); }}>Reset</ResetButton>
              </div>
              <ControlSlider label={`Zoom: ${videoScale.toFixed(2)}x`} value={videoScale} min={RANGES.videoScale.min} max={RANGES.videoScale.max} step={RANGES.videoScale.step} onChange={setVideoScale} />
              <ControlSlider label={`H offset: ${Math.round(videoOffsetX)}%`} value={videoOffsetX} min={RANGES.videoOffset.min} max={RANGES.videoOffset.max} step={RANGES.videoOffset.step} onChange={(v) => setVideoOffsetX(Math.round(v))} />
              <ControlSlider label={`V offset: ${Math.round(videoOffsetY)}%`} value={videoOffsetY} min={RANGES.videoOffset.min} max={RANGES.videoOffset.max} step={RANGES.videoOffset.step} onChange={(v) => setVideoOffsetY(Math.round(v))} />
            </div>
          )}
        </EditorSection>

        <EditorSection title="Hook text" defaultOpen testId="hook-controls">
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
            className="w-full resize-none rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2 text-xs leading-snug outline-none transition focus:border-[color:var(--brand-indigo)]"
          />
          <ControlSlider label={`On screen: ${hookDuration.toFixed(1)}s`} value={hookDuration} min={RANGES.hookDuration.min} max={RANGES.hookDuration.max} step={RANGES.hookDuration.step} onChange={setHookDuration} testId="hook-duration-slider" />
          {(hookOffsetX !== 0 || hookOffsetY !== 0) && (
            <ResetButton onClick={() => { setHookOffsetX(0); setHookOffsetY(0); }}>Reset position</ResetButton>
          )}
          <p className="text-xs italic text-muted-foreground">Drag the hook text on the preview to reposition</p>
        </EditorSection>

        <EditorSection title="End card" defaultOpen testId="cta-controls">
          <label className="flex items-center gap-2 text-xs text-muted-foreground">
            <Switch data-testid="cta-toggle" checked={ctaEnabled} onCheckedChange={setCtaEnabled} />
            Show lead-gen end card
          </label>
          <input
            data-testid="cta-headline-input"
            value={ctaHeadline}
            onChange={(e) => setCtaHeadline(e.target.value)}
            placeholder="Try it free — link in bio"
            className="w-full rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2 text-xs outline-none transition focus:border-[color:var(--brand-indigo)]"
          />
          <input
            data-testid="cta-handle-input"
            value={ctaHandle}
            onChange={(e) => setCtaHandle(e.target.value)}
            placeholder="@yourhandle"
            className="w-full rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2 text-xs outline-none transition focus:border-[color:var(--brand-indigo)]"
          />
          <ControlSlider label={`Last ${ctaDuration.toFixed(1)}s of the video`} value={ctaDuration} min={RANGES.ctaDuration.min} max={RANGES.ctaDuration.max} step={RANGES.ctaDuration.step} onChange={setCtaDuration} testId="cta-duration-slider" />
          {(ctaOffsetX !== 0 || ctaOffsetY !== 0) && (
            <ResetButton onClick={() => { setCtaOffsetX(0); setCtaOffsetY(0); }}>Reset position</ResetButton>
          )}
          <p className="text-xs italic text-muted-foreground">Drag the end card on the preview to reposition</p>
          <div className="flex items-center gap-2">
            <span className="text-xs text-muted-foreground">Accent</span>
            {ACCENT_SWATCHES.map((c) => (
              <button
                key={c}
                type="button"
                data-testid={`overlay-accent-${c.replace("#", "")}`}
                onClick={() => setOverlayAccent(c)}
                style={{ background: c }}
                aria-label={`Accent ${c}`}
                className={`h-5 w-5 rounded-full border-2 transition ${overlayAccent === c ? "border-[color:var(--brand-indigo)]" : "border-[color:var(--hairline)]"}`}
              />
            ))}
          </div>
          <p className="text-xs leading-snug text-muted-foreground">
            Laid out inside TikTok&apos;s safe area — clear of the right icon rail and bottom caption strip.
          </p>
        </EditorSection>

        <EditorSection title="Output" defaultOpen>
          <select
            value={bg === "transparent" ? "webm" : exportFormat}
            disabled={bg === "transparent"}
            onChange={(e) => setExportFormat(e.target.value)}
            className={`${SELECT_CLASS} disabled:opacity-50`}
            aria-label="Export format"
          >
            <option value="auto">Auto (MP4)</option>
            <option value="mp4">MP4</option>
            <option value="webm">WebM</option>
          </select>
          {bg === "transparent" && (
            <p className="text-xs text-muted-foreground">Transparent backgrounds export as WebM to keep the alpha channel.</p>
          )}
        </EditorSection>
      </div>

      <div className="min-w-0 space-y-3 order-first xl:order-none">
        <SectionCard title="Live preview" className="xl:sticky xl:top-6 xl:z-10">
          <div className="mb-2 flex items-center justify-between text-xs text-muted-foreground">
            <span>Live preview</span>
            <span>{(PRESETS.find((p) => p.id === preset) || {}).label}</span>
          </div>
          <div className="flex min-h-[280px] w-full items-center justify-center overflow-hidden rounded-xl border border-[color:var(--hairline)] bg-black p-2">
            {videoUrl ? (
              <canvas
                ref={previewCanvasRef}
                className="block h-auto w-auto max-h-[62vh] max-w-full cursor-grab touch-none active:cursor-grabbing xl:max-h-[54vh]"
                onPointerDown={handlePointerDown}
                onWheel={handleWheel}
              />
            ) : (
              <div className="text-sm text-muted-foreground">
                {loadingSource ? "Loading the finished render…" : "No video to preview"}
              </div>
            )}
          </div>
        </SectionCard>

        {videoUrl && videoMeta && (
          <SectionCard title="Player">
            <div className="space-y-3">
              <div className="space-y-1">
                <div className="relative h-4 select-none">
                  {ticks.map((t) => (
                    <button
                      key={t}
                      type="button"
                      onClick={() => handleSeek(t)}
                      className="group absolute top-0 flex cursor-pointer flex-col items-center"
                      style={{ left: `${(t / duration) * 100}%`, transform: "translateX(-50%)" }}
                    >
                      <div className="h-2 w-px bg-muted-foreground/30 transition group-hover:bg-muted-foreground/60" />
                      <span className="mt-0.5 font-mono text-[8px] tabular-nums leading-none text-muted-foreground/70 transition group-hover:text-muted-foreground">
                        {formatTime(t)}
                      </span>
                    </button>
                  ))}
                </div>

                {zoomKeyframes.length > 0 && (
                  <div className="relative h-3 overflow-hidden rounded-full bg-secondary/60">
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
                        >
                          <span className="pointer-events-none absolute inset-0 flex items-center justify-center font-mono text-[7px] text-amber-300/70">
                            {seg.scale.toFixed(1)}x
                          </span>
                        </div>
                      );
                    })}
                  </div>
                )}

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

                <div className="flex items-center justify-between px-0.5">
                  <span className="font-mono text-[9px] tabular-nums text-muted-foreground">0:00.0</span>
                  <span className="font-mono text-[9px] tabular-nums text-muted-foreground">{formatTime(duration)}</span>
                </div>
              </div>

              <div className="flex items-center gap-3 pt-1">
                <Button type="button" variant="secondary" size="icon" onClick={togglePlayPause} title={isPlaying ? "Pause" : "Play"}>
                  {isPlaying ? <Pause className="h-4 w-4" /> : <Play className="h-4 w-4" />}
                </Button>
                <div className="flex items-baseline gap-1.5">
                  <span className="font-mono text-[15px] font-medium tabular-nums tracking-tight">
                    {formatTime(currentTime)}
                  </span>
                  <span className="font-mono text-[11px] text-muted-foreground">/</span>
                  <span className="font-mono text-xs tabular-nums text-muted-foreground">
                    {formatTime(duration)}
                  </span>
                </div>
                <div className="ml-auto flex items-center gap-1.5">
                  <Button type="button" variant="ghost" size="sm" className="h-9 min-w-9 px-2.5 font-mono text-[11px]" onClick={() => handleSeek(Math.max(0, currentTime - 1))} title="Back 1 second">
                    −1s
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-9 min-w-9 px-2.5" onClick={() => handleSeek(Math.max(0, currentTime - 1 / 30))} title="Back 1 frame (1/30s)">
                    ‹
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-9 min-w-9 px-2.5" onClick={() => handleSeek(Math.min(duration, currentTime + 1 / 30))} title="Forward 1 frame (1/30s)">
                    ›
                  </Button>
                  <Button type="button" variant="ghost" size="sm" className="h-9 min-w-9 px-2.5 font-mono text-[11px]" onClick={() => handleSeek(Math.min(duration, currentTime + 1))} title="Forward 1 second">
                    +1s
                  </Button>
                </div>
              </div>

              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
                <div className="flex flex-wrap items-center gap-2">
                  <span className="eyebrow">Zoom Lock</span>
                  {zoomKeyframes.length > 0 && (
                    <span className="text-[11px] text-muted-foreground">
                      {zoomKeyframes.length} {zoomKeyframes.length === 1 ? "keyframe" : "keyframes"}
                    </span>
                  )}
                  <span className="ml-auto flex items-center gap-1.5">
                    <Button type="button" variant="secondary" size="sm" onClick={handleCaptureZoomLock}>
                      + Lock at {formatTime(currentTime)}
                    </Button>
                    {zoomKeyframes.length > 0 && (
                      <Button type="button" variant="ghost" size="sm" onClick={handleClearZoomKeyframes}>
                        Clear
                      </Button>
                    )}
                  </span>
                </div>
                {sortedKeyframes.length > 0 && (
                  <div className="space-y-1.5">
                    {sortedKeyframes[0].time > 0.01 && (
                      <div className="flex items-center gap-2 rounded-lg border border-[color:var(--hairline)] bg-secondary/40 px-3 py-2">
                        <span className="font-mono text-[11px] text-muted-foreground">0:00.0 → {formatTime(sortedKeyframes[0].time)} • default (1.00x)</span>
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
                            className="flex-1 text-left font-mono text-[11px] tabular-nums text-muted-foreground transition hover:text-foreground"
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
                    <p className="pt-0.5 text-[11px] text-muted-foreground">
                      Pause → seek to exact time → adjust zoom → Lock. Each segment displays its locked zoom in the preview and export.
                    </p>
                  </div>
                )}
              </div>
            </div>
          </SectionCard>
        )}

        <div className="fixed inset-x-0 bottom-0 z-40 border-t border-[color:var(--hairline)] bg-background/95 px-4 pb-[max(0.75rem,env(safe-area-inset-bottom))] pt-3 backdrop-blur xl:sticky xl:bottom-4 xl:rounded-2xl xl:border xl:bg-card/90 xl:px-4 xl:py-3">
          <Button
            type="button"
            variant="brand"
            className="w-full"
            disabled={!videoUrl || !videoMeta || recording || saving}
            onClick={exportVideo}
          >
            {recording ? (
              <><Loader2 className="h-3.5 w-3.5 animate-spin" /> Recording… {Math.round(progress * 100)}%</>
            ) : (
              <><Smartphone className="h-3.5 w-3.5" /> {bg === "transparent" ? "Export transparent WebM" : "Export MP4"}</>
            )}
          </Button>
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
        <div className="h-24 xl:hidden" aria-hidden="true" />

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
  );
}

// Local drawPhone port lives with the other canvas math so the preview loop
// reads one module, not a second app.
function drawPhone(ctx, x, y, w, h, dev, video, videoFit, videoScale, videoOffsetX, videoOffsetY, frameColor = "black") {
  const radius = w * dev.radiusRatio;
  const bezel = w * dev.bezelRatio;

  const bodyColor = frameColor === "white" ? "#f0f0f2" : dev.body;
  const railColor = frameColor === "white" ? "#d8d8dc" : dev.rail;

  ctx.save();

  ctx.save();
  roundRect(ctx, x, y, w, h, radius);
  ctx.shadowColor = frameColor === "white" ? "rgba(0,0,0,0.25)" : "rgba(0,0,0,0.55)";
  ctx.shadowBlur = w * 0.10;
  ctx.shadowOffsetY = w * 0.04;
  ctx.fillStyle = frameColor === "white" ? "#e0e0e4" : "#000";
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
