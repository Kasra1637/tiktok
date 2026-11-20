import { Check, X } from "lucide-react";

/**
 * The story craft check, displayed (ADR 0236): phase 2's fixed
 * four-check list (`assess_story_quality`, ADR 0228) recomputed on
 * every project read and carried on the payload as `story_quality`.
 *
 * Display only — the check is advisory, refuses nothing and gates
 * no render, and this component holds no scoring of its own: it
 * prints the server's checks, their evidence, and the next step
 * each failing check names. The four checks are the format's fixed
 * demands (first-second hook, screen text standing alone muted,
 * one idea per frame, sticker plan present) — never calibrated
 * against outcomes, under Kasra's standing ruling for both craft
 * checks.
 */
export default function StoryCraftCheck({ report }) {
  if (!report || !report.checks) return null;
  const checks = Object.values(report.checks);
  if (!checks.length) return null;
  const passed = Number(report.passed) || 0;
  const total = Number(report.total) || checks.length;

  return (
    <div className="inset-panel space-y-3" data-testid="story-craft-check">
      <div className="flex flex-wrap items-baseline justify-between gap-2">
        <p className="text-sm font-semibold">Story craft check</p>
        <p className="text-sm text-muted-foreground">
          {passed} of {total} checks passing
        </p>
      </div>
      <ul className="space-y-2">
        {checks.map((check) => (
          <li
            key={check.key}
            data-testid="story-craft-check-row"
            data-check={check.key}
            data-passed={check.passed ? "true" : "false"}
            className="flex items-start gap-2"
          >
            {check.passed ? (
              <Check className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />
            ) : (
              <X className="mt-0.5 h-4 w-4 shrink-0 text-destructive-text" />
            )}
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-semibold">{check.label}</p>
              {(check.evidence || []).map((line, i) => (
                <p key={i} className="text-sm text-muted-foreground">{line}</p>
              ))}
              {!check.passed && check.next_step && (
                <p className="text-sm text-muted-foreground">Next: {check.next_step}</p>
              )}
            </div>
          </li>
        ))}
      </ul>
    </div>
  );
}
