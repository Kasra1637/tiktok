/**
 * Remembers the founder's History view choice: the full cards or the
 * compact scan rows (ADR 0159).
 *
 * Same guarded pattern as currentApp.js. localStorage throws in
 * private-mode Safari and is absent entirely during server rendering,
 * and a preference that cannot be stored must never take the page down
 * with it — losing the memory costs the founder one click on the
 * toggle, and nothing else. Anything unreadable reads as the default,
 * the full cards.
 */

const KEY = "vocolens.historyView";

/** The stored view, or "full" when nothing valid is stored. */
export function readHistoryView() {
  try {
    if (typeof localStorage === "undefined") return "full";
    return localStorage.getItem(KEY) === "compact" ? "compact" : "full";
  } catch {
    return "full";
  }
}

export function rememberHistoryView(view) {
  try {
    if (typeof localStorage === "undefined") return;
    localStorage.setItem(KEY, view === "compact" ? "compact" : "full");
  } catch {
    // A preference that cannot be stored is not worth surfacing.
  }
}
