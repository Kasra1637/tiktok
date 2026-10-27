/**
 * Transitions between the base clip and the added second clip.
 *
 * Four TikTok-native trends, each a pure function of timeline time: the
 * painter reads `transitionAt` and the export records exactly what the
 * preview showed, the same contract the overlay entrances keep (see
 * ADR 0007). No WebGL, no new dependencies — Canvas 2D transforms and
 * slice copies only, applied as a post-effect on the painted frame.
 *
 * The window is centered on the cut (`baseDuration ± D/2`) and capped by
 * the shorter clip, so a 0.5s clip is never eaten by a 0.45s spin. The
 * total timeline never grows: the transition borrows the tail of the base
 * and the head of the added clip, and the audio join is untouched.
 */

export const TRANSITIONS = [
  { id: "whip", label: "Whip pan", duration: 0.35, description: "Slings sideways with motion streaks." },
  { id: "zoom", label: "Zoom punch", duration: 0.3, description: "Punches in, flashes through the cut." },
  { id: "spin", label: "Spin", duration: 0.45, description: "Twirls into the next clip." },
  { id: "glitch", label: "Glitch", duration: 0.25, description: "Slices shift and flicker." },
];

export const TRANSITION_IDS = TRANSITIONS.map((t) => t.id);

export function transitionDef(id) {
  return TRANSITIONS.find((t) => t.id === id) || null;
}

/**
 * Deterministic 0..1 hash per frame index. The glitch slices need
 * randomness that is identical for an identical timeline time, so the
 * export paints what the preview showed instead of a fresh dice roll.
 */
export function hash01(n) {
  const x = Math.sin(Math.floor(n) * 127.1 + 311.7) * 43758.5453;
  return x - Math.floor(x);
}

/**
 * Where the transition window sits on the joined timeline, in seconds.
 * Zero means no window: unknown id, hard cut, or no room to borrow.
 */
export function transitionWindow(baseDuration, appendDuration, id) {
  const def = transitionDef(id);
  if (!def || !def.duration) return 0;
  if (!(baseDuration > 0) || !(appendDuration > 0)) return 0;
  const room = Math.min(baseDuration, appendDuration);
  if (room < 0.24) return 0;
  return Math.min(def.duration, room);
}

/**
 * The transition state at one timeline time. Outside the window (or for a
 * hard cut) the painter is untouched: `{ active: false }`.
 *
 * Inside, `side` names which segment is on screen and `progress` runs 0→1
 * across the whole window, so both halves peak exactly at the cut.
 */
export function transitionAt(vt, baseDuration, appendDuration, id) {
  const span = transitionWindow(baseDuration, appendDuration, id);
  if (!span) return { active: false, side: null, progress: 0, span: 0 };
  const start = baseDuration - span / 2;
  const t = Number(vt) || 0;
  if (t < start || t > start + span) return { active: false, side: null, progress: 0, span };
  const progress = Math.min(1, Math.max(0, (t - start) / span));
  return { active: true, side: t < baseDuration ? "out" : "in", progress, span };
}

/**
 * Reduced-motion resolution: every trend parks as a cut.
 *
 * "none" is the internal cut token, not a picker choice: no animation, no
 * luminance strobe. Unknown ids pass through so a stale saved value (hard
 * cut, flash, fade) still resolves to no window downstream.
 */
export function effectiveTransition(id, reduceMotion) {
  if (!reduceMotion) return id;
  return "none";
}

/** Ease both halves toward the cut so the motion lands, never drifts. */
export function easeInOut(p) {
  const t = Math.min(1, Math.max(0, p));
  return t < 0.5 ? 4 * t * t * t : 1 - Math.pow(-2 * t + 2, 3) / 2;
}
