// Which onboarding tours have been completed, persisted across reloads —
// and which were dismissed early. The two outcomes together decide whether
// a tour offers itself again.
//
// Extracted from OnboardingProvider so the once-only rule is testable as a
// value rather than as a regex over JSX. The provider owns *when* a tour opens;
// this owns *whether it may open again*, which is the whole rule.
//
// The rule (audit 2026-11-14, finding 13): a tour is recorded as seen when
// it is COMPLETED, not when it opens. It used to be recorded on open, so a
// tour dismissed in its first second — mid-task, meaning to return — was
// gone forever. A dismissal is recorded as a dismissal instead: the tour
// re-offers itself ONCE on the next eligible visit, and a second dismissal
// ends the offers. Re-opening by hand is always possible deliberately, via
// the sidebar's "Show me around", whatever either ledger says.

const STORAGE_KEY = "hookforge_seen_tours.v2";
const DISMISSED_KEY = "hookforge_dismissed_tours.v1";

// How many early dismissals a tour gets before it stops offering itself:
// the first earns exactly one re-offer; the second ends the offers.
const MAX_TOUR_DISMISSALS = 2;

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

/**
 * Reads the dismissal ledger, with the same defensive shape as the seen
 * set: anything unexpected reads as "never dismissed", never as "always
 * dismissed" — reading corrupt state as full would suppress every tour
 * permanently, silently. Values are counts, so they are coerced: only a
 * positive finite number survives, floored.
 */
export function readDismissedTours(storage) {
  try {
    const raw = storage.getItem(DISMISSED_KEY);
    if (!raw) return {};
    const parsed = JSON.parse(raw);
    if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) return {};
    const out = {};
    Object.keys(parsed).forEach((id) => {
      const count = Math.floor(Number(parsed[id]));
      if (Number.isFinite(count) && count > 0) out[id] = count;
    });
    return out;
  } catch {
    return {};
  }
}

/**
 * The dismissal ledger plus one more early dismissal of `tourId`,
 * persisted. Returns the SAME ledger once the cap is reached, so callers
 * can use identity to skip a state update — past the cap the count no
 * longer matters, only that the offers have ended.
 *
 * A storage failure is swallowed, like the seen set's: the tour simply
 * offers itself again on a later visit.
 */
export function markTourDismissed(storage, dismissed, tourId) {
  if (!tourId) return dismissed;
  const count = Number(dismissed?.[tourId]) || 0;
  if (count >= MAX_TOUR_DISMISSALS) return dismissed;
  const next = { ...dismissed, [tourId]: count + 1 };
  try {
    storage.setItem(DISMISSED_KEY, JSON.stringify(next));
  } catch {
    /* see above: degrade to offering again, never to not offering */
  }
  return next;
}

export function tourDismissalCount(dismissed, tourId) {
  return tourId ? Number(dismissed?.[tourId]) || 0 : 0;
}

/**
 * Whether a tour may auto-open on this visit: never once completed, and
 * only until its early dismissals run out — one dismissal earns exactly
 * one re-offer, the second ends the offers.
 */
export function shouldAutoOpenTour(seen, dismissed, tourId) {
  if (!tourId || hasSeenTour(seen, tourId)) return false;
  return tourDismissalCount(dismissed, tourId) < MAX_TOUR_DISMISSALS;
}

// A plain const rather than an `export { X as Y }` clause: the frontend logic
// suite evaluates these modules by stripping the `export` keyword, which turns a
// re-export clause into a syntax error. Exported this way it is a normal
// top-level declaration that both the bundler and the suite can read.
export const SEEN_TOURS_STORAGE_KEY = STORAGE_KEY;
export const DISMISSED_TOURS_STORAGE_KEY = DISMISSED_KEY;