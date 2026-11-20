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
// - angles: founder-dictated 40s (Nov 20 2026, ADR 0230) for the
//   four-angle set (ADR 0226), superseding the founder-measured 50s for
//   six fielded angles. The one entry drives both the Generate angles
//   and Regenerate angles countdowns.
// - goals: no entry — it completes under 10s in practice, so its button
//   keeps the sweep alone and never counts down.
// - templates: founder-measured 20s for 3 structures (Nov 2026).
// - plan: founder-measured 50s typical (Nov 2026; up to 3 editorial
//   attempts against the 120s timeout can still run past it, holding at 0s).
// - planStrategy: founder-dictated exactly 50s (Nov 19 2026, ADR 0214):
//   the whole plan-generation wait — plan and strategy behind the one
//   button — is declared at 50s, superseding the summed estimate (the
//   plan's 50s plus the strategy's ~30s). A run past it holds at 0s,
//   like every estimate here.
// - strategy: 8192 tokens → ~30s typical.
// - research: page fetches (15s timeout each, sequential) + 8000-token draft
//   (timeout 90) → ~40s; refresh variants that also regenerate angles → ~45s.
// - postKit: 1500 tokens → ~12s for caption + 4–6 hashtags + cover.
// Excluded on purpose: render submit (a short submit whose wait is the
// polling progress bar with real position), Demo CTA export (real recording
// percentage on the button), and hook rewrite (400 tokens, fast).
export const BUSY_ETA_THRESHOLD_SECONDS = 10;

export const BUSY_ETA_SECONDS = {
  angles: 40,
  templates: 20,
  plan: 50,
  planStrategy: 50,
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

/** Seconds left on a generation wait, derived from when the wait started.
 *
 * `startedAtMs` is the ms-epoch moment the caller recorded when the flight
 * began. Callers that outlive the button (a wizard page whose sections
 * unmount on a step change) keep it, so a remounted button resumes the
 * count where the wait actually is instead of restarting the estimate —
 * the wizard's plan flight is the case this exists for. Without a usable
 * start, the full estimate remains: the button's own countdown, unchanged.
 * Elapsed time floors to whole seconds and the result holds at 0, so a
 * wait that outruns its estimate reads "· 0s", never negative. */
export function busyRemainingSeconds(etaSeconds, startedAtMs, nowMs) {
  const eta = Number(etaSeconds);
  if (!Number.isFinite(eta)) return null;
  const started = Number(startedAtMs);
  if (!Number.isFinite(started)) return Math.max(0, Math.round(eta));
  const now = nowMs === undefined ? Date.now() : Number(nowMs);
  const elapsed = Number.isFinite(now)
    ? Math.max(0, Math.floor((now - started) / 1000))
    : 0;
  return Math.max(0, Math.round(eta) - elapsed);
}
