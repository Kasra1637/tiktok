/**
 * Pure helpers for the influencer hook/extension lengths.
 *
 * Extracted from the panel because these were the exact decisions that broke:
 * a `=== 0` against a boolean that made a toggle inert, and a
 * `Number("target")` that turned "fill to target" into a silent 5s request.
 * Neither was caught by the Python suite or by the build, because both only
 * type-check and lint — nothing evaluated the comparison at runtime.
 *
 * So the rules live here, with no React and no DOM, and are asserted directly
 * by scripts/check-frontend-logic.cjs against this real source file.
 *
 * The length rules mirror video_providers.resolve_length() on the backend. The
 * backend still decides; this only predicts, so the UI can label an option
 * honestly before the render is paid for.
 */

// Must match video_providers.HOOK_LENGTH_CHOICES.
export const HOOK_LENGTHS = [2, 3, 4, 5, 6];
export const DEFAULT_HOOK = 4;

export const EXTEND_CHOICES = [3, 5, 8, 10];
export const DEFAULT_EXTEND = 5;

// Sentinel for the "fill to the remaining target" option. A string, because
// every <select> value is a string; a numeric sentinel here would invite the
// Number() coercion that broke this in the first place.
export const FILL_TO_TARGET = "target";

/**
 * Whether the founder has declared they intend to extend.
 *
 * The API returns a real boolean, so this must compare against `false` and NOT
 * against 0: `false === 0` is false, so an `=== 0` check silently reads "off"
 * as "on" and the toggle can never be turned off.
 *
 * Both shapes are accepted defensively. Every project endpoint currently
 * normalises through _public_project, so a row is always a boolean — but SQLite
 * has no boolean type, and a raw integer leaking through a future endpoint or a
 * cached payload would otherwise read as "on" no matter what the founder chose.
 */
export function readExtendIntent(project) {
  if (!project) return true;
  const value = project.extend_intent;
  if (value === false || value === 0 || value === "0" || value === "false") return false;
  return true;
}

/**
 * Resolve a wanted length against a provider's floor and ceiling.
 *
 * A wanted length below the floor is rendered at the floor and cut down, so it
 * is still delivered at the length asked for. A wanted length above the ceiling
 * cannot be recovered that way, which is why the backend refuses it instead.
 */
export function resolveLength(target, capability) {
  const floor = Number(capability?.min_duration ?? 4);
  const ceiling = Number(capability?.max_duration ?? 30);
  const want = Number(target) || 0;
  if (want < 1) return { target: want, render: floor, trimTo: 0 };
  const clamped = Math.min(want, ceiling);
  const render = Math.max(clamped, floor);
  return {
    target: clamped,
    render,
    trimTo: render > clamped ? clamped : 0,
  };
}

/**
 * Parse a <select> value into either a number of seconds or FILL_TO_TARGET.
 *
 * Anything unrecognised falls back to the default rather than becoming NaN: a
 * NaN here serialises to `null` on the wire, which the server reads as "no
 * preference" and answers with its own default — so a mis-parse turns into a
 * silently different request instead of a visible failure.
 */
export function parseExtendChoice(raw) {
  if (raw === FILL_TO_TARGET) return FILL_TO_TARGET;
  const n = Number(raw);
  if (!Number.isFinite(n) || n < 1) return DEFAULT_EXTEND;
  return n;
}

/** Whether "fill to the remaining target" can actually be requested. */
export function canFillToTarget(remaining, capability) {
  const left = Number(remaining) || 0;
  if (left <= 0) return false;
  const ceiling = Number(capability?.max_duration ?? 0);
  // No capability yet: do not offer it, because we cannot know it is possible.
  return ceiling > 0 && left <= ceiling;
}

/**
 * What the extend button should request, in seconds.
 *
 * Returns null when the choice cannot be honoured — the caller disables the
 * button rather than sending a request the server will refuse.
 */
export function resolveExtendRequest(choice, remaining, capability) {
  const parsed = parseExtendChoice(choice);
  if (parsed !== FILL_TO_TARGET) {
    const plan = resolveLength(parsed, capability);
    return { seconds: plan.trimTo || plan.render, trimTo: plan.trimTo };
  }
  const left = Number(remaining) || 0;
  if (!canFillToTarget(left, capability)) return null;
  const plan = resolveLength(left, capability);
  return { seconds: plan.trimTo || plan.render, trimTo: plan.trimTo };
}

/** How many more beats the plan can still produce, or null if unknown. */
export function plannedCoverage(segments, strategy) {
  const maxIndex = Number(strategy?.max_planned_index);
  if (!Number.isFinite(maxIndex) || maxIndex < 0) return null;
  const used = (segments || []).reduce(
    (max, s) => Math.max(max, Number(s?.segment_index) || 0),
    0
  );
  return Math.max(0, maxIndex - used);
}
