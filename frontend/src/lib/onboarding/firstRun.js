// First-run wayfinding state: the three-step path is Create Video,
// then Demo + CTA, then Export. The card shows until the founder's
// first Demo + CTA export is saved to History, or until dismissed.
//
// Extracted as pure storage helpers (like seenTours) so the once-only
// rule is testable as a value rather than as JSX. The checklist owns
// *when* it shows; this owns *whether the run is over*, which is the
// whole rule.
//
// A failed read degrades to "still first run": showing the card again
// costs nothing, while reading corrupt state as done would retire the
// guide for someone who never finished it.

const DONE_KEY = "hookforge_first_export_done.v1";
const DISMISSED_KEY = "hookforge_first_run_dismissed.v1";

function readFlag(storage, key) {
  try {
    return storage.getItem(key) === "1";
  } catch {
    return false;
  }
}

function writeFlag(storage, key) {
  try {
    storage.setItem(key, "1");
  } catch {
    // Private mode / storage disabled: the card simply shows again
    // next visit, which is the safe failure.
  }
}

export function isFirstRunDone(storage) {
  if (!storage) return false;
  return readFlag(storage, DONE_KEY);
}

export function markFirstRunDone(storage) {
  if (!storage) return;
  writeFlag(storage, DONE_KEY);
}

export function isFirstRunDismissed(storage) {
  if (!storage) return false;
  return readFlag(storage, DISMISSED_KEY);
}

export function dismissFirstRun(storage) {
  if (!storage) return;
  writeFlag(storage, DISMISSED_KEY);
}

/** The card shows while the first export is unsaved and not dismissed. */
export function shouldShowChecklist(storage) {
  if (!storage) return true;
  return !readFlag(storage, DONE_KEY) && !readFlag(storage, DISMISSED_KEY);
}

// Plain consts rather than `export { X as Y }` clauses: the frontend
// logic suite evaluates these modules by stripping the `export` keyword,
// which turns a re-export clause into a syntax error.
export const FIRST_RUN_DONE_KEY = DONE_KEY;
export const FIRST_RUN_DISMISSED_KEY = DISMISSED_KEY;
