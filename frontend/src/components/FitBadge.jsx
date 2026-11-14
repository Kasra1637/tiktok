import { Tooltip, TooltipContent, TooltipProvider, TooltipTrigger } from "./ui/tooltip";

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
 *
 * The basis rides the shared tooltip, not a native `title`: titles never
 * appear for keyboard or touch users, and these two picks (angle, template)
 * are the most consequential in Step 2 (audit 2026-11-14, finding 8). The
 * pill is focusable so the explanation is reachable by every input, the
 * same pattern the craft tiles use — one way of explaining a score.
 */
export function FitBadge({ score, basis, testId }) {
  return (
    <TooltipProvider delayDuration={200}>
      <Tooltip>
        <TooltipTrigger asChild>
          <span
            data-testid={testId}
            tabIndex={0}
            aria-label={`Fit ${score} out of 10. ${basis}`}
            className="rounded-full border border-[color:var(--hairline)] px-2 py-0.5 text-xs font-semibold text-muted-foreground"
          >
            Fit {score}/10
          </span>
        </TooltipTrigger>
        <TooltipContent>{basis}</TooltipContent>
      </Tooltip>
    </TooltipProvider>
  );
}
