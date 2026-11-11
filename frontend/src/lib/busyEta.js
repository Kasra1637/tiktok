// Busy-button wait estimates (>=10s only).
//
// A busy button already paints the looping sweep on the button itself; the
// countdown below rides inside that same button (e.g. "Generating angles
// · 30s", ticking down to "· 0s") so no second narrator line appears beside
// it. The starting number is the typical completion for the underlying model
// call, not the client timeout: the endpoint answers on its own schedule, so
// a job that runs past its estimate holds at "· 0s" instead of going
// negative or restarting. Operations expected under 10s (saves, approvals,
// deletes, uploads, the free Shuffle) take no etaSeconds and keep the sweep
// alone. A button with no etaSeconds — the video render, whose wait is the
// polling progress bar with real position — takes no countdown at all.
//
// Values per operation, from backend/ai_service.py token/timeout budgets:
// - angles: 8000 tokens, timeout 90 → ~30s for six fielded angles.
// - goals: 4000 tokens, timeout 60 → ~20s for six ranked goals.
// - templates: 16384 tokens + possible top-up call → ~35s for 3 structures.
// - plan: 8000 tokens, timeout 120, up to 3 editorial attempts → ~30s typical.
// - strategy: 8192 tokens → ~30s typical.
// - research: page fetches (15s timeout each, sequential) + 8000-token draft
//   (timeout 90) → ~40s; refresh variants that also regenerate angles → ~45s.
// - postKit: 1500 tokens → ~12s for caption + 4–6 hashtags + cover.
// Excluded on purpose: render submit (a short submit whose wait is the
// polling progress bar with real position), Demo CTA export (real recording
// percentage on the button), and hook rewrite (400 tokens, fast).
export const BUSY_ETA_THRESHOLD_SECONDS = 10;

export const BUSY_ETA_SECONDS = {
  angles: 30,
  goals: 20,
  templates: 35,
  plan: 30,
  strategy: 30,
  research: 40,
  refresh: 45,
  postKit: 12,
};

/** Returns the countdown suffix for the seconds still to show (e.g. "· 30s"),
 * or null for a non-number. The Button owns the 10s threshold and the 0s
 * floor: this only formats what it is handed, so a job that runs past its
 * estimate still reads "· 0s" instead of disappearing mid-wait. */
export function formatBusyCountdown(seconds) {
  const n = Number(seconds);
  if (!Number.isFinite(n)) return null;
  return `· ${Math.max(0, Math.round(n))}s`;
}
