/**
 * Remembers which App Profile the founder is working on.
 *
 * Why this exists: the app you select in "Your app" lives in that page's React
 * state, so nothing else in the app can see it. The Asset Library, opened from
 * the sidebar at a plain `/assets`, therefore had no idea an app had been
 * chosen and dead-ended on "Choose an App Profile first". Storing the selection
 * here is what makes "the app I already picked" mean something outside the page
 * that picked it.
 *
 * Every access is guarded. localStorage throws in private-mode Safari and is
 * absent entirely during server rendering, and a preference that cannot be
 * stored must never take the page down with it — losing the memory costs the
 * user their default selection and nothing else.
 */

const KEY = "vocolens.currentAppProfileId";

/** A candidate id that is safe to write: non-empty, and short enough to be an id. */
function isSaneId(value) {
  return typeof value === "string" && value.trim().length > 0 && value.length <= 128;
}

export function readCurrentAppId() {
  try {
    if (typeof localStorage === "undefined") return "";
    const raw = localStorage.getItem(KEY);
    return isSaneId(raw) ? raw.trim() : "";
  } catch {
    return "";
  }
}

export function rememberCurrentAppId(id) {
  try {
    if (typeof localStorage === "undefined" || !isSaneId(id)) return;
    localStorage.setItem(KEY, id.trim());
  } catch {
    // A preference that cannot be stored is not worth surfacing.
  }
}

export function forgetCurrentAppId() {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.removeItem(KEY);
  } catch {
    // Same as above.
  }
}
