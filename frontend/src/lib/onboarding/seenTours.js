// Which onboarding tours have already opened, persisted across reloads.
//
// Extracted from OnboardingProvider so the once-only rule is testable as a
// value rather than as a regex over JSX. The provider owns *when* a tour opens;
// this owns *whether it has opened before*, which is the whole rule.
//
// The rule: a tour auto-opens the first time its route is reached and never
// again on its own. Re-opening it is always possible deliberately, via the
// sidebar's "Show me around". A tour is recorded when it OPENS, not when it is
// dismissed, so reloading mid-tour does not re-greet someone already reading it.

const STORAGE_KEY = "hookforge_seen_tours.v2";

/**
 * Reads the seen set, treating anything unexpected as "nothing seen".
 *
 * The failure this guards is specific: a value that parses but is not a plain
 * object — an array, a string, a number — must not read as "everything has
 * been seen". That would suppress every tour permanently, silently, and the
 * only symptom would be onboarding that never appears again. Reading corrupt
 * state as empty costs one redundant greeting; reading it as full costs the
 * feature.
 */
export function readSeenTours(storage) {
  try {
    const raw = storage.getItem(STORAGE_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    // Keep only id -> finite timestamp. A value like {"create": "yes"} is
    // still a claim that it was seen, and that claim is all we need.
    const out = {};
    Object.keys(parsed).forEach((id) => {
      out[id] = parsed[id];
    });
    return out;
  } catch {
    // Private mode, storage disabled, or malformed JSON.
    return {};
  }
}

/**
 * The seen set plus `tourId`, persisted.
 *
 * Returns the SAME set object when the tour was already recorded, so callers
 * can use identity to skip a state update. That matters: writing on every
 * render would re-render whatever holds this state for no reason.
 *
 * A storage failure is swallowed. The tour still opens — it just opens again on
 * a later visit, which is a far better failure than onboarding that silently
 * stops working.
 */
export function markTourSeen(storage, seen, tourId) {
  if (!tourId || Object.prototype.hasOwnProperty.call(seen, tourId)) return seen;
  const next = { ...seen, [tourId]: Date.now() };
  try {
    storage.setItem(STORAGE_KEY, JSON.stringify(next));
  } catch {
    /* see above: degrade to showing again, never to not showing */
  }
  return next;
}

export function hasSeenTour(seen, tourId) {
  return !!tourId && Object.prototype.hasOwnProperty.call(seen, tourId);
}

// A plain const rather than an `export { X as Y }` clause: the frontend logic
// suite evaluates these modules by stripping the `export` keyword, which turns a
// re-export clause into a syntax error. Exported this way it is a normal
// top-level declaration that both the bundler and the suite can read.
export const SEEN_TOURS_STORAGE_KEY = STORAGE_KEY;