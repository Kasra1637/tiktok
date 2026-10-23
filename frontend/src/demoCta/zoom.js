/**
 * Native Product Demo + CTA zoom-keyframe helpers.
 *
 * Preview and export resolve the same timestamped locks. Only an explicit
 * paused edit auditions live framing before the user captures another lock.
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

const DEFAULT_LOCKED = { vScale: 1, vOffX: 0, vOffY: 0, hZoom: 1, hPanX: 0, hPanY: 0, phoneScale: 0.82 };

/**
 * Resolve the zoom in force at `videoTime`.
 *
 * - No keyframes: live sliders, always.
 * - Paused edits: live framing for preview only, until Lock, seek or playback.
 * - Before the first keyframe: defaults in preview and export alike.
 * - Past the last keyframe: the last lock holds, in both modes. The preview
 *   used to fall back to the live sliders here, which meant it showed a
 *   framing the export would not bake; the lock applies in preview and export
 *   alike so the two agree.
 * - Between locks: the active lock, rigidly.
 */
export function getEffectiveZoom({ keyframes, live, videoTime, isExporting = false, isEditing = false }) {
  const sorted = sortKeyframes(keyframes);
  const liveValues = {
    vScale: live.scale,
    vOffX: live.offX,
    vOffY: live.offY,
    hZoom: live.handZoom,
    hPanX: live.handPanX,
    hPanY: live.handPanY,
    phoneScale: live.phoneScale ?? DEFAULT_LOCKED.phoneScale,
  };
  if (sorted.length === 0 || (isEditing && !isExporting)) return liveValues;

  let active = null;
  for (let i = 0; i < sorted.length; i++) {
    if (sorted[i].time <= videoTime) {
      active = sorted[i];
    } else {
      break;
    }
  }
  if (!active) return { ...DEFAULT_LOCKED };
  // Keyframes carry the slider namespaces (scale/offX/offY, handZoom/handPanX/
  // handPanY); the returned object carries the canvas namespaces (vScale/vOffX/
  // vOffY, hZoom/hPanX/hPanY). Keep the two apart: reading active.hPanX here
  // yields undefined on every real keyframe and silently drops hand pan.
  return {
    vScale: active.scale,
    vOffX: active.offX,
    vOffY: active.offY,
    hZoom: active.handZoom,
    hPanX: active.handPanX,
    hPanY: active.handPanY,
    phoneScale: active.phoneScale ?? DEFAULT_LOCKED.phoneScale,
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
