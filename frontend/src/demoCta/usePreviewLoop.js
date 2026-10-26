import { useCallback, useEffect, useRef, useState } from "react";
import {
  BASE_PHONE_H,
  COLOR_PALETTES,
  DEFAULTS,
  DEVICES,
  PRESETS,
  resolveCtaWindow,
  clipWindow,
} from "./constants";
import { drawEndCard, drawHookOverlay, drawStoryOverlay } from "./overlays";
import { transitionAt, easeInOut, hash01 } from "./transitions";
import { drawHandView } from "./handView";
import { fitVideoToScreen } from "./fit";
import { getEffectiveZoom } from "./zoom";

/**
 * Preview transport, scoped replay, and frame painting: one owner.
 *
 * The editor reads the playhead and calls the transport helpers; everything
 * that moves the playhead or paints the canvas lives here. Scene settings
 * arrive as one settings object (the loop effect's dependency array is the
 * contract the smoke suite pins), copy text stays editor-owned, and zoom
 * editing stays editor-owned except for the two refs the painter and the
 * lock-follow effect read.
 */
export function usePreviewLoop(settings) {
  const {
    device, preset, mockupStretchY, scale, videoMeta, bg, anim,
    baseStart = 0, appendStart = 0,
    videoFit, videoScale, videoOffsetX, videoOffsetY,
    viewMode, envBg, screenX, screenY, screenW, screenH,
    handZoom, handPanX, handPanY,
    appendUrl, appendMeta, appendMode, appendBg, appendAnim, appendEnv, appendVideoRef, appendOverlays,
    transition = "none",
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
  } = settings;
  const [isPlaying, setIsPlaying] = useState(true);
  // Preview monitoring only: the source element stays muted so autoplay
  // never fights browser policy; the speaker toggle below unmutes on tap.
  // Export reads source samples directly; preview mute and volume never affect the file.
  const [previewMuted, setPreviewMuted] = useState(true);
  const [currentTime, setCurrentTime] = useState(0);
  const [isSeeking, setIsSeeking] = useState(false);

  const videoRef = useRef(null);
  const activeVideoRef = useRef(null);
  // A start point moves the clip's own clock: overlays, windows and zoom locks
  // are timed from the first used frame, and the export decodes from that same
  // frame. Both lengths below are the used run, never the source length.
  const baseWindow = clipWindow(videoMeta?.d, baseStart);
  const appendWindow = clipWindow(appendMeta?.d, appendStart);
  const baseDuration = baseWindow.duration;
  const appendDuration = appendWindow.duration;
  const sequence = !!appendMeta;
  const sequenceRef = useRef(null);
  sequenceRef.current = {
    enabled: sequence,
    baseDuration,
    appendDuration,
    baseStart: baseWindow.start,
    appendStart: appendWindow.start,
  };
  const activeVideo = useCallback(() => activeVideoRef.current || videoRef.current, []);
  // Media time → timeline time. The base opens on its in point, so a timeline
  // position is the offset from the first used frame rather than from frame 0.
  const timelineTime = useCallback((video) => {
    if (!video) return 0;
    const config = sequenceRef.current;
    const added = video === appendVideoRef?.current;
    const local = (video.currentTime || 0) - (added ? config.appendStart : config.baseStart);
    return Math.max(0, local + (added ? config.baseDuration : 0));
  }, [appendVideoRef]);
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
    if (video) video.loop = !sequenceRef.current.enabled;
  }, []);
  const previewCanvasRef = useRef(null);
  const rafRef = useRef(null);
  const paintFrameRef = useRef(null);
  // On-demand preview: `dirtyRef` marks a frame to paint, `kickPreviewRef`
  // restarts the parked loop from outside its effect (export finale).
  const dirtyRef = useRef(true);
  const kickPreviewRef = useRef(null);
  const isExportingRef = useRef(false);
  const editingZoomRef = useRef(false);
  const liveZoomRef = useRef({
    scale: 1, offX: 0, offY: 0,
    handZoom: 1, handPanX: 0, handPanY: 0, phoneScale: DEFAULTS.scale,
  });

  // Track the active segment on a single global playhead.
  useEffect(() => {
    const video = videoRef.current;
    const added = appendVideoRef?.current;
    if (!video) return undefined;
    const elements = [video, added].filter(Boolean);
    const onTime = () => {
      if (!isSeeking) setCurrentTime(timelineTime(activeVideo()));
    };
    elements.forEach((el) => el.addEventListener("timeupdate", onTime));
    // The smoothing tick only runs while the clip plays. Paused seeks land
    // through `timeupdate`.
    let raf = 0;
    let lastReported = 0;
    const tick = () => {
      raf = 0;
      const video = activeVideo();
      if (!video || video.paused) return;
      if (!isSeeking) {
        const t = timelineTime(video);
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
      if (!isSeeking) setCurrentTime(timelineTime(activeVideo()));
    };
    elements.forEach((el) => {
      el.addEventListener("play", onPlayTick);
      el.addEventListener("pause", onPauseTick);
    });
    raf = requestAnimationFrame(tick);
    return () => {
      elements.forEach((el) => {
        el.removeEventListener("timeupdate", onTime);
        el.removeEventListener("play", onPlayTick);
        el.removeEventListener("pause", onPauseTick);
      });
      cancelAnimationFrame(raf);
    };
  }, [isSeeking, appendUrl, appendMeta, appendVideoRef, activeVideo, timelineTime]);

  // Restart playback inside one overlay window so a style tweak replays
  // where it lands. Hook replays from frame 0 to the hook end; the end card
  // replays from its start to the clip end. With no loaded clip there is no
  // window, so this is a no-op and the on-demand paint carries the change.
  const startScopedPreview = useCallback((kind) => {
    if (isExportingRef.current) return;
    const video = videoRef.current;
    const dur = baseDuration;
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
    appendVideoRef?.current?.pause();
    activeVideoRef.current = video;
    scopedReplayRef.current = { end };
    video.loop = false;
    try {
      video.currentTime = start + baseStart;
    } catch {
      // A seekable clip always accepts this; a transient failure leaves the
      // playhead where it is and the window guard still parks on time.
    }
    setCurrentTime(start);
    video.play().then(() => setIsPlaying(true)).catch(() => {});
  }, [baseDuration, baseStart, hookEnabled, hookDuration, ctaEnabled, ctaDuration, ctaTimingMode, appendVideoRef]);

  // Continuous sliders fire dozens of changes per drag; restarting the
  // window on every tick would yank the playhead under the founder's hand.
  // If the clip already plays inside the window, just retarget the end and
  // let it run — otherwise restart it like a discrete pick.
  const ensureScopedPreview = useCallback((kind) => {
    const video = videoRef.current;
    const dur = baseDuration;
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
    const t = timelineTime(video);
    if (!video.paused && t >= start - 0.05 && t < end) {
      scopedReplayRef.current = { end };
      video.loop = false;
      return;
    }
    startScopedPreview(kind);
  }, [baseDuration, baseStart, hookEnabled, hookDuration, ctaEnabled, ctaDuration, ctaTimingMode, startScopedPreview, timelineTime]);

  // Stable so the Space shortcut below subscribes once: it closes over the
  // video ref and a state setter only, so an empty dep array is complete.
  // An explicit press means free transport, so it always clears a scoped
  // window first — resuming from a parked hook end must play on past it.
  const togglePlayPause = useCallback(() => {
    if (isExportingRef.current) return;
    const video = activeVideo();
    if (!video) return;
    cancelScopedReplay();
    editingZoomRef.current = false;
    if (video.paused) {
      if (video.ended) {
        const base = videoRef.current;
        activeVideoRef.current = base;
        base.currentTime = baseStart;
        base.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
      } else video.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
    } else {
      video.pause();
      setIsPlaying(false);
    }
  }, [cancelScopedReplay, activeVideo, baseStart]);

  const togglePreviewMuted = useCallback(() => {
    const video = videoRef.current;
    setPreviewMuted((was) => {
      const next = !was;
      [video, appendVideoRef?.current].filter(Boolean).forEach((el) => {
        el.muted = next;
        if (!next) el.volume = 1;
      });
      return next;
    });
  }, [appendVideoRef]);

  // Per-clip mute rides on top of the monitor mute: a muted segment stays
  // silent even after the founder unmutes preview, and export reads the
  // same flags from the editor rather than this element state.
  useEffect(() => {
    const base = videoRef.current;
    const added = appendVideoRef?.current;
    if (base) {
      base.muted = previewMuted || !!baseMuted;
      if (!base.muted) base.volume = 1;
    }
    if (added) {
      added.muted = previewMuted || !!appendMuted;
      if (!added.muted) added.volume = 1;
    }
  }, [previewMuted, baseMuted, appendMuted, appendUrl, appendVideoRef]);

  // Space toggles preview playback from anywhere that is not text entry, the
  // way every video editor answers it. A focused button or link already
  // answers Space with a click, so it is left to the native activation — a
  // second toggle there would undo the click. Sliders answer arrows, not
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
    const config = sequenceRef.current;
    const next = config.enabled && time >= config.baseDuration ? appendVideoRef.current : video;
    const previous = activeVideo();
    const playing = previous && !previous.paused;
    if (previous !== next) previous?.pause();
    activeVideoRef.current = next;
    // Both directions add the segment's own in point, so a timeline position
    // lands on the media frame the export uses for that same position.
    next.currentTime = next === video
      ? config.baseStart + Math.max(0, time)
      : config.appendStart + Math.min(config.appendDuration, Math.max(0, time - config.baseDuration));
    if (playing && next.paused) next.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
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
  }, [setVideoScale, setVideoOffsetX, setVideoOffsetY, setHandZoom, setHandPanX, setHandPanY, setScale]);

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
    // Locks are keyed to the timeline, not to media time: with a start point
    // the base's own clock runs ahead of the frame the lock was set on.
    showZoomValues(zoomValuesAt(activeVideo() ? timelineTime(activeVideo()) : currentTime));
  }, [currentTime, isPlaying, zoomKeyframes, showZoomValues, zoomValuesAt, activeVideo, timelineTime]);

  // Only one segment plays at a time. No looping, mixing or retiming at the cut.
  useEffect(() => {
    const base = videoRef.current;
    const added = appendVideoRef?.current;
    if (!base) return undefined;
    added?.pause();
    activeVideoRef.current = base;
    base.loop = !sequence;
    setCurrentTime(timelineTime(base));
    setIsPlaying(!base.paused);
    const advance = () => {
      if (!sequence || scopedReplayRef.current || isExportingRef.current) return;
      activeVideoRef.current = added;
      added.currentTime = appendStart;
      setCurrentTime(baseDuration);
      added.play().then(() => setIsPlaying(true)).catch(() => setIsPlaying(false));
    };
    const finish = () => {
      setCurrentTime(baseDuration + appendDuration);
      setIsPlaying(false);
    };
    base.addEventListener("ended", advance);
    added?.addEventListener("ended", finish);
    return () => {
      base.removeEventListener("ended", advance);
      added?.removeEventListener("ended", finish);
      added?.pause();
    };
  }, [appendUrl, appendMeta, videoMeta, appendStart, baseDuration, appendDuration, timelineTime, viewMode, sequence, appendVideoRef]);

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

    const drawOverlays = (ctx, vt, dur = baseDuration) => {
      const hookWindow = dur > 0 ? Math.min(hookDuration, dur * 0.45) : hookDuration;
      const ctaWindow = resolveCtaWindow(ctaDuration, dur, ctaTimingMode);
      if (hookEnabled) {
        drawHookOverlay(ctx, cw, ch, vt, { text: hookText, duration: hookWindow, accent: overlayAccent, offsetX: hookOffsetX, offsetY: hookOffsetY, font: fontStack(captionFont), anim: captionAnim, scale: captionScale, textStyle });
      }
      if (storyEnabled && storyAvailable) {
        drawStoryOverlay(ctx, cw, ch, vt, {
          text: storyText, start: storyStart, end: storyEnd,
          accent: overlayAccent, offsetY: storyOffsetY,
          font: fontStack(captionFont), anim: captionAnim, scale: captionScale,
          textStyle,
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
          textStyle,
        });
      }
    };

    // Joint transition between the base and added clips: a post-effect on
    // the painted frame, so every look (realistic, hand, floating) carries
    // the same motion and the export — which calls this same painter per
    // decoded frame — records exactly the preview frame. A pure function of
    // timeline time, like the overlay entrances.
    let jointScratch = null;
    const paintJointTransition = (target, vt) => {
      if (!sequence) return;
      const t = transitionAt(vt, baseDuration, appendDuration, transition);
      if (!t.active) return;
      const ctx = target.getContext("2d");
      const w = target.width;
      const h = target.height;
      if (!jointScratch) jointScratch = document.createElement("canvas");
      if (jointScratch.width !== w || jointScratch.height !== h) {
        jointScratch.width = w;
        jointScratch.height = h;
      }
      const sctx = jointScratch.getContext("2d");
      sctx.clearRect(0, 0, w, h);
      sctx.drawImage(target, 0, 0);
      // Peak energy exactly at the cut: 0 on the window edges, 1 at the join.
      const q = t.side === "out" ? easeInOut(t.progress * 2) : easeInOut((1 - t.progress) * 2);
      const frameIdx = Math.round(vt * 30);
      ctx.save();
      if (transition === "whip") {
        const dx = q * w;
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(jointScratch, dx, 0, w, h);
        ctx.drawImage(jointScratch, dx - w, 0, w, h);
        ctx.fillStyle = `rgba(255, 255, 255, ${(q * 0.16).toFixed(3)})`;
        for (let i = 0; i < 12; i += 1) {
          ctx.fillRect(0, hash01(frameIdx * 7 + i * 13) * h, w, 2);
        }
      } else if (transition === "zoom") {
        const s = 1 + q * 0.35;
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(jointScratch, (w - w * s) / 2, (h - h * s) / 2, w * s, h * s);
        ctx.fillStyle = `rgba(255, 255, 255, ${(Math.sin(t.progress * Math.PI) * 0.28).toFixed(3)})`;
        ctx.fillRect(0, 0, w, h);
      } else if (transition === "spin") {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, w, h);
        ctx.translate(w / 2, h / 2);
        ctx.rotate(q * 0.5);
        const s = 1 + q * 0.25;
        ctx.drawImage(jointScratch, (-w * s) / 2, (-h * s) / 2, w * s, h * s);
      } else if (transition === "glitch") {
        const slices = 10;
        const sh = h / slices;
        for (let i = 0; i < slices; i += 1) {
          const off = (hash01(frameIdx * 13 + i) - 0.5) * q * w * 0.15;
          if (off) ctx.drawImage(jointScratch, 0, i * sh, w, sh + 1, off, i * sh, w, sh + 1);
        }
        if (hash01(frameIdx * 3) > 1 - q * 0.5) {
          ctx.fillStyle = overlayAccent || "#c8ff2e";
          ctx.globalAlpha = 0.12;
          ctx.fillRect(0, 0, w, h);
          ctx.globalAlpha = 1;
        }
      } else if (transition === "swipe") {
        // A panel sweeps in and back out, fully covering the join at the cut.
        const half = t.progress < 0.5 ? t.progress * 2 : (1 - t.progress) * 2;
        const edgeX = (-0.05 + easeInOut(half) * 1.1) * w;
        const dx = (t.side === "out" ? -t.progress : 1 - t.progress) * w * 0.12;
        ctx.clearRect(0, 0, w, h);
        ctx.drawImage(jointScratch, dx, 0, w, h);
        if (edgeX > 0) {
          ctx.fillStyle = "#0b0b10";
          ctx.fillRect(0, 0, Math.min(edgeX, w), h);
          ctx.fillStyle = overlayAccent || "#c8ff2e";
          ctx.fillRect(Math.max(0, edgeX - 10), 0, 10, h);
        }
      }
      ctx.restore();
    };

    // Preview and export call this exact painter with an explicit media timestamp.
    // The fourth argument identifies the base or added segment.
    const paintFrame = (target, vt, frame, segment = 0) => {
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
      // read before its declaration would throw, killing the draw loop on the
      // first hand-mode frame and freezing the canvas.
      const mode = segment ? appendMode : viewMode;
      // Each segment carries its own look: the added clip starts from the
      // same defaults but diverges independently, so a calm base can flow
      // into an energetic upload. Only the selected branch's values are
      // read — a realistic segment never touches palettes or environments.
      const lookBg = segment ? (appendBg ?? bg) : bg;
      const lookAnim = segment ? (appendAnim ?? anim) : anim;
      const lookEnv = segment ? (appendEnv ?? envBg) : envBg;
      const palette = COLOR_PALETTES[lookBg] || COLOR_PALETTES.lavender;

      if (mode === "hand" && video) {
        const t = vt;
        drawHandView(ctx, cw, ch, frame, lookEnv, t, videoFit, ez.vScale, ez.vOffX, ez.vOffY, { x: screenX, y: screenY, w: screenW, h: screenH }, ez.hZoom, ez.hPanX, ez.hPanY, palette?.bg2);
        if (!segment || appendOverlays) drawOverlays(ctx, segment ? vt - baseDuration : vt, segment ? appendDuration : baseDuration);
        paintJointTransition(target, vt);
        return;
      }

      // Real Video: the actual clip full-bleed, no phone and no scene — the
      // same Video-crop zoom and offsets as the phone screen, applied to the
      // whole canvas, so the crop controls keep working and the export (which
      // calls this same painter per decoded frame) records exactly this.
      // The added segment uses its own uncoupled framing and overlay window.
      if (mode === "realistic") {
        ctx.fillStyle = "#000";
        ctx.fillRect(0, 0, cw, ch);
        if (mediaReady(frame)) {
          const vw = frame.videoWidth || frame.width;
          const vh = frame.videoHeight || frame.height;
          const box = fitVideoToScreen({ fit: segment ? "cover" : videoFit, videoW: vw, videoH: vh, screenW: cw, screenH: ch, scale: segment ? 1 : ez.vScale });
          if (box) {
            const maxOffX = Math.max(0, (box.dw - cw) / 2);
            const maxOffY = Math.max(0, (box.dh - ch) / 2);
            ctx.drawImage(frame, (cw - box.dw) / 2 + (segment ? 0 : ez.vOffX / 100) * maxOffX, (ch - box.dh) / 2 + (segment ? 0 : ez.vOffY / 100) * maxOffY, box.dw, box.dh);
          }
        }
        if (!segment || appendOverlays) drawOverlays(ctx, segment ? vt - baseDuration : vt, segment ? appendDuration : baseDuration);
        paintJointTransition(target, vt);
        return;
      }

      const isFloat = lookBg !== "transparent";

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

        if (lookAnim === "breathe") {
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
          ctx.restore();
        }

        if (lookAnim === "embers") {
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

        if (lookAnim === "vortex") {
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

        if (lookAnim === "grid") {
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

        if (lookAnim === "comet") {
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

        if (lookAnim === "tide") {
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

        if (lookAnim === "prism") {
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

        if (lookAnim === "bloom") {
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

        if (lookAnim === "meteor") {
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
      if (!segment || appendOverlays) drawOverlays(ctx, segment ? vt - baseDuration : vt, segment ? appendDuration : baseDuration);
      paintJointTransition(target, vt);
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
      const v = activeVideo();
      const playing = !!v && !v.paused;
      // A looping base wraps to frame 0, which sits before the start point. Park
      // it back on the in point before the skipped run is painted; the seek
      // marks the next frame dirty.
      if (playing && v === videoRef.current && v.currentTime < baseStart - 0.02) {
        v.currentTime = baseStart;
        dirtyRef.current = true;
        rafRef.current = requestAnimationFrame(draw);
        return;
      }
      if (playing) editingZoomRef.current = false;
      if (playing || dirtyRef.current) {
        dirtyRef.current = false;
        paintFrame(canvas, timelineTime(v), v, v === appendVideoRef?.current ? 1 : 0);
      }
      // A scoped replay parks at its window end instead of playing past it:
      // pausing here lands the scrubber on the exact window frame, and the
      // loop restore below hands free transport back for the next press.
      const scoped = scopedReplayRef.current;
      if (playing && scoped && v && timelineTime(v) >= scoped.end - 0.08) {
        scopedReplayRef.current = null;
        v.pause();
        v.loop = !sequence;
        setIsPlaying(false);
        setCurrentTime(timelineTime(v));
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
    const previewElements = [previewVideo, appendVideoRef?.current].filter(Boolean);
    previewElements.forEach((el) => {
      el.addEventListener("play", onPlayPaint);
      el.addEventListener("seeked", onSeekedPaint);
    });
    // A CTA replay ending at the clip end fires `ended` instead of another
    // frame: clear the window and hand free transport back same as the
    // guarded park above.
    const onEndedScoped = () => {
      const wasScoped = !!scopedReplayRef.current;
      scopedReplayRef.current = null;
      if (previewVideo) previewVideo.loop = !sequence;
      if (!sequence || wasScoped) setIsPlaying(false);
    };
    previewVideo?.addEventListener("ended", onEndedScoped);
    dirtyRef.current = true;
    kick();

    return () => {
      paintFrameRef.current = null;
      kickPreviewRef.current = null;
      previewElements.forEach((el) => {
        el.removeEventListener("play", onPlayPaint);
        el.removeEventListener("seeked", onSeekedPaint);
      });
      previewVideo?.removeEventListener("ended", onEndedScoped);
      if (rafRef.current) {
        cancelAnimationFrame(rafRef.current);
        rafRef.current = null;
      }
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [device, preset, scale, mockupStretchY, videoMeta, bg, anim, videoFit, videoScale, videoOffsetX, videoOffsetY, viewMode, appendMode, appendBg, appendAnim, appendEnv, envBg, screenX, screenY, screenW, screenH, handZoom, handPanX, handPanY, appendUrl, appendMeta, appendOverlays, hookEnabled, hookText, hookDuration, hookOffsetX, hookOffsetY, storyEnabled, storyAvailable, storyText, storyStart, storyEnd, storyOffsetY, ctaEnabled, ctaHeadline, ctaHandle, ctaDuration, ctaTimingMode, ctaOffsetX, ctaOffsetY, overlayAccent, captionFont, ctaFont, captionAnim, ctaAnim, captionScale, ctaScale, textStyle, zoomKeyframes, baseStart, appendStart, baseDuration, appendDuration, timelineTime, transition]);

  return {
    videoRef, activeVideoRef, previewCanvasRef,
    isPlaying, setIsPlaying,
    previewMuted, setPreviewMuted, togglePreviewMuted,
    currentTime, setCurrentTime,
    isSeeking, setIsSeeking,
    startScopedPreview, ensureScopedPreview,
    togglePlayPause, handleSeek,
    cancelScopedReplay, dirtyRef,
    showZoomValues, zoomValuesAt,
    editingZoomRef, liveZoomRef,
    paintFrameRef, kickPreviewRef, isExportingRef,
  };
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

// A frame is drawable when it has decoded pixels: a live element past
// HAVE_CURRENT_DATA, or a decoded export canvas (an HTMLCanvasElement).
// One guard for the base and the overlay, so the preview never draws a
// layer the export would skip.
function mediaReady(f) {
  if (!f) return false;
  const w = f.videoWidth || f.width || 0;
  const h = f.videoHeight || f.height || 0;
  if (!(w > 0 && h > 0)) return false;
  return f instanceof HTMLCanvasElement || f.readyState >= 2;
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
