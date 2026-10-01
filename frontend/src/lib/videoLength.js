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

// The hook length is computed from the strategy, recommended and locked —
// there is no selector and therefore no list of choices. DEFAULT_HOOK is
// the provisional value before any strategy exists.
export const DEFAULT_HOOK = 4;

/**
 * The locked extension length for the next segment.
 *
 * Computed, recommended, locked: the next uncovered planned beat's seconds,
 * resolved against the provider floor/ceiling so the delivered number is
 * honest. When the remaining target is smaller than the planned beat, the
 * remainder wins — that is the fill case, reached automatically rather than
 * offered as a choice. Returns null when there is nothing to extend by, so
 * the caller disables the button instead of sending a request the server
 * will refuse. A remainder beyond one pass is likewise null: it needs two
 * steps, not a guess.
 */

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

export function resolveExtendLock(plannedSeconds, remainingToTarget, capability) {
  const planned = Number(plannedSeconds) || 0;
  const remaining = Number(remainingToTarget) || 0;
  const ceiling = Number(capability?.max_duration ?? 30);
  const want = planned > 0
    ? (remaining > 0 ? Math.min(planned, remaining) : planned)
    : remaining;
  if (want <= 0) return null;
  if (want > ceiling) return null;
  const plan = resolveLength(want, capability);
  return {
    seconds: plan.trimTo || plan.render,
    planned: want,
    render: plan.render,
    trimTo: plan.trimTo,
  };
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
