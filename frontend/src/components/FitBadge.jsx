/**
 * One shared 0–10 fit badge for every ranked choice in the studio: the
 * picked angle, each video goal, each template card. Same pill, same words,
 * same contract everywhere — `Fit N/10` up front, the counts or reasons
 * behind it in the tooltip — so a founder never has to relearn what a
 * score means from one list to the next.
 *
 * A match score, never an outcome promise: it says how well the option fits
 * the app and the angle, not what any video will do. The basis string names
 * what went into the number (counts, rank, or the server's matched factors)
 * and must always be supplied — a bare number with no provenance is exactly
 * the false precision this badge exists to prevent.
 */
export function FitBadge({ score, basis, testId }) {
  return (
    <span
      data-testid={testId}
      title={basis}
      aria-label={`Fit ${score} out of 10. ${basis}`}
      className="rounded-full border border-[color:var(--hairline)] px-2 py-0.5 text-xs font-semibold text-muted-foreground"
    >
      Fit {score}/10
    </span>
  );
}
