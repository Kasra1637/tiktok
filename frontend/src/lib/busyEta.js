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
// - angles: founder-measured 50s for six fielded angles (Nov 2026; the
//   budget-derived 30s ran short against the wait founders actually see).
// - goals: no entry — it completes under 10s in practice, so its button
//   keeps the sweep alone and never counts down.
// - templates: founder-measured 20s for 3 structures (Nov 2026).
// - plan: founder-measured 50s typical (Nov 2026; up to 3 editorial
//   attempts against the 120s timeout can still run past it, holding at 0s).
// - planStrategy: the one pass the Review step now makes — the plan's
//   founder-measured 50s plus the strategy's ~30s behind the same button,
//   so the countdown covers the whole wait the founder actually sits through.
// - strategy: 8192 tokens → ~30s typical.
// - research: page fetches (15s timeout each, sequential) + 8000-token draft
//   (timeout 90) → ~40s; refresh variants that also regenerate angles → ~45s.
// - postKit: 1500 tokens → ~12s for caption + 4–6 hashtags + cover.
// Excluded on purpose: render submit (a short submit whose wait is the
// polling progress bar with real position), Demo CTA export (real recording
// percentage on the button), and hook rewrite (400 tokens, fast).
export const BUSY_ETA_THRESHOLD_SECONDS = 10;

export const BUSY_ETA_SECONDS = {
  angles: 50,
  templates: 20,
  plan: 50,
  planStrategy: 80,
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
