/**
 * Native Product Demo + CTA zoom-keyframe helpers.
 *
 * Ported faithfully from the standalone app. These are pure functions so the
 * preview/export split — live sliders during preview, locked values during
 * export — can be unit-tested without a canvas.
 */

export function sortKeyframes(list) {
  return [...(list || [])].sort((a, b) => a.time - b.time);
}

export function makeKeyframeId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

/**
 * Capture the current slider settings as a keyframe at time `t`. A keyframe
 * within 0.05s is updated in place instead of duplicated.
 */
export function captureZoomLock(prev, t, snapshot) {
  const list = Array.isArray(prev) ? prev : [];
  const existingIdx = list.findIndex((k) => Math.abs(k.time - t) < 0.05);
  if (existingIdx !== -1) {
    const next = [...list];
    next[existingIdx] = { ...next[existingIdx], ...snapshot, time: t };
    return next;
  }
  return [...list, { id: makeKeyframeId(), time: t, ...snapshot }];
}

export function removeZoomKeyframe(prev, id) {
  return (Array.isArray(prev) ? prev : []).filter((k) => k.id !== id);
}

const DEFAULT_LOCKED = { vScale: 1, vOffX: 0, vOffY: 0, hZoom: 1, hPanX: 0, hPanY: 0 };

/**
 * Resolve the zoom in force at `videoTime`.
 *
 * - No keyframes: live sliders, always.
 * - Before the first keyframe: locked defaults during export (so the export is
 *   deterministic), live sliders during preview (so adjustments show).
 * - Past the last keyframe: same split — live during preview, last lock baked
 *   during export.
 * - Between locks: the active lock, rigidly.
 */
export function getEffectiveZoom({ keyframes, live, videoTime, isExporting }) {
  const sorted = sortKeyframes(keyframes);
  const liveValues = {
    vScale: live.scale,
    vOffX: live.offX,
    vOffY: live.offY,
    hZoom: live.handZoom,
    hPanX: live.handPanX,
    hPanY: live.handPanY,
  };
  if (sorted.length === 0) return liveValues;

  let active = null;
  let hasNextKeyframe = false;
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i].time <= videoTime) {
      active = sorted[i];
    } else {
      hasNextKeyframe = true;
      break;
    }
  }
  if (!active) {
    if (isExporting) return { ...DEFAULT_LOCKED };
    return liveValues;
  }
  void hasNextKeyframe;
  return {
    vScale: active.scale,
    vOffX: active.offX,
    vOffY: active.offY,
    hZoom: active.handZoom,
    hPanX: active.hPanX,
    hPanY: active.hPanY,
  };
}

/** Timeline tick interval: aims for roughly 6–10 visible ticks. */
export function tickInterval(duration) {
  const dur = Number(duration) || 0;
  if (dur > 60) return 10;
  if (dur > 30) return 5;
  if (dur > 10) return 2;
  if (dur > 5) return 1;
  return 0.5;
}
