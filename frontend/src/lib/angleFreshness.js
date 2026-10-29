/**
 * How old the visible angle set is, in founder words.
 *
 * The picker never shows this itself as a number: a timestamp is provenance,
 * not a choice, and the list is scanned by name. What the founder needs at
 * the Regenerate button is a one-line answer to "is this set stale?" — so
 * this returns the age of the NEWEST row (a regen rewrites every derived
 * row, which is exactly the refresh this dates), or null when no row
 * carries a parseable date, in which case the UI claims nothing rather
 * than dating the set off a guess.
 *
 * Pure (now is a parameter) so the wording is asserted in
 * scripts/check-frontend-logic.cjs instead of living untested behind a
 * render branch.
 */
export function angleSetAge(angles, now = Date.now()) {
  const times = (Array.isArray(angles) ? angles : [])
    .map((a) => Date.parse(a && a.created_at))
    .filter((t) => Number.isFinite(t));
  if (times.length === 0) return null;
  const elapsed = Math.max(0, now - Math.max(...times));
  const MINUTE = 60 * 1000;
  const HOUR = 60 * MINUTE;
  const DAY = 24 * HOUR;
  if (elapsed < MINUTE) return "just now";
  if (elapsed < HOUR) return `${Math.floor(elapsed / MINUTE)}m ago`;
  if (elapsed < DAY) return `${Math.floor(elapsed / HOUR)}h ago`;
  return `${Math.floor(elapsed / DAY)}d ago`;
}
