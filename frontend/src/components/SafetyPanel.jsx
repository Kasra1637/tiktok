import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Button } from "./ui/button";
import { Disclosure } from "./Disclosure";
import { ShieldCheck, ShieldAlert, Ban, Circle as HelpCircle } from "lucide-react";
import { sentenceCase } from "../lib/copyCase";
import { GroupLabel } from "./SectionCard";

/**
 * Reviewer-facing claim-safety report.
 *
 * Deliberately shows what was FOUND, not a reassuring summary. A clean plan
 * says so plainly; a flagged plan names every specific phrase so the founder
 * can decide, and a failed plan is impossible to miss because it blocks
 * generation.
 */
export function SafetyPanel({ report, summary, onEditClaim, onRegenerate, busy = false, hasEdits = false }) {
  if (!report) {
    return (
      <Alert>
        <HelpCircle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        <AlertTitle>No safety check yet</AlertTitle>
        <AlertDescription>
          Generate a creative plan to run the claim check against your approved App Profile.
        </AlertDescription>
      </Alert>
    );
  }

  const passed = report.passed !== false;
  const blocking = report.blocking || [];
  const unverified = report.unverified || [];
  const warnings = report.risk_warnings || [];
  const used = report.claims_used || [];
  const undeclared = report.unverified_self_claims || [];
  const sources = report.sources_used || [];
  const flagged = blocking.length + unverified.length + warnings.length + undeclared.length;

  return (
    <div className="space-y-3">
      <Alert variant={passed ? "default" : "destructive"}>
        {passed ? (
          <ShieldCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        ) : (
          <ShieldAlert className="h-4 w-4" />
        )}
        <AlertTitle>
          {passed ? "No blocking claims found" : "Fix the flagged wording before rendering"}
        </AlertTitle>
        <AlertDescription>
          {summary || (flagged ? `${flagged} item(s) need review.` : "Nothing flagged.")}
          {passed && flagged > 0 && " These review notes do not block rendering."}
          {!passed && " Edit the affected text and save to recheck, or regenerate the plan for review."}
          {hasEdits && " This report describes the saved plan; your edits have not been checked yet."}
        </AlertDescription>
      </Alert>

      {blocking.length > 0 && (
        <div className="inset-panel inset-panel-strong">
          <GroupLabel icon={Ban} className="text-destructive">Blocks rendering</GroupLabel>
          <ul className="mt-2 space-y-2 text-base">
            {blocking.map((b, i) => (
              <li key={i}>
                <span className="font-semibold">&ldquo;{b.claim}&rdquo;</span>
                <span className="text-muted-foreground"> — {sentenceCase(b.reason)}</span>
                {onEditClaim && (
                  <Button variant="secondary" size="sm" className="ml-2" disabled={busy}
                    data-testid={`safety-edit-${i}`} onClick={() => onEditClaim(b.claim)}>
                    Edit affected text
                  </Button>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {!passed && onRegenerate && (
        <Button variant="secondary" size="sm" disabled={busy} onClick={onRegenerate} data-testid="safety-regenerate">
          Regenerate plan for review
        </Button>
      )}

      <Disclosure testId="claim-check-details" summary={`Review notes & evidence (${flagged - blocking.length})`}>
      <div className="mt-3 space-y-3">
      <p className="text-sm text-muted-foreground">These are app checks, not provider or TikTok approval. Review notes do not block rendering.</p>
      {warnings.length > 0 && (
        <div className="inset-panel inset-panel-strong">
          <GroupLabel icon={ShieldAlert}>Nonblocking warnings</GroupLabel>
          <ul className="mt-2 space-y-2 text-base">
            {warnings.map((w, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-semibold">&ldquo;{w.claim}&rdquo;</span>
                <span className="text-muted-foreground">{sentenceCase(w.reason)}</span>
                {w.disclosure_missing && (
                  <Badge variant="outline" className="text-xs">no disclosure</Badge>
                )}
              </li>
            ))}
          </ul>
        </div>
      )}

      {undeclared.length > 0 && (
        <div className="inset-panel inset-panel-strong">
          <GroupLabel icon={HelpCircle}>Declared but not in the script</GroupLabel>
          <p className="mt-1 text-sm text-muted-foreground">
            The generator reported using these, but they do not appear in the text.
          </p>
          <ul className="mt-2 space-y-1 text-base">
            {undeclared.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {unverified.length > 0 && (
        <div className="inset-panel inset-panel-strong">
          <GroupLabel icon={ShieldCheck}>Needs verification</GroupLabel>
          <ul className="mt-2 space-y-1 text-base">
            {unverified.map((u, i) => (
              <li key={i}>{u.claim}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="inset-panel">
        <GroupLabel icon={ShieldCheck}>Approved claims found ({used.length})</GroupLabel>
        {used.length ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {used.map((c, i) => (
              <Badge key={i} variant="secondary" className="text-xs">{c}</Badge>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-base text-muted-foreground">
            None of your approved claims appear in this script.
          </p>
        )}
      </div>

      {sources.length > 0 && (
        <p className="text-sm text-muted-foreground">
          Grounded in: {sources.map((s) => s.replace(/_/g, " ")).join(", ")}.
        </p>
      )}
      </div>
      </Disclosure>
    </div>
  );
}

export default SafetyPanel;
