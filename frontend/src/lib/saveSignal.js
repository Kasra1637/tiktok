/**
 * The one app-wide saved signal (Kasra's order, Nov 27 2026).
 *
 * The pages' autosaves keep working exactly as they always have —
 * same writes, same timing, same failure handling — but their
 * status text is gone from every page: no "Saving…", no "All
 * changes saved" standing anywhere. In its place a single green
 * check in the app chrome says the work is saved, and it is driven
 * by the saves themselves: each page calls `signalSaved()` at the
 * exact moment its autosave completes (the moment it used to set
 * the saved text), and the one indicator listens here and shows
 * the check, pulsing anew on every save. No save logic lives in
 * this module — it only carries the news from the save to the
 * chrome.
 */
export const SAVED_EVENT = "hookforge:autosaved";

export function signalSaved() {
  try {
    window.dispatchEvent(new CustomEvent(SAVED_EVENT));
  } catch {
    /* no window (a test harness without one) — no signal to send */
  }
}

export function onSaved(handler) {
  window.addEventListener(SAVED_EVENT, handler);
  return () => window.removeEventListener(SAVED_EVENT, handler);
}
