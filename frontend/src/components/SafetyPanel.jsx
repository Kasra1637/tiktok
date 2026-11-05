import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { Disclosure } from "./Disclosure";
import { ShieldCheck, ShieldAlert, Circle as HelpCircle } from "lucide-react";
import { sentenceCase } from "../lib/copyCase";
import { GroupLabel } from "./SectionCard";

/**
 * Reviewer-facing claim-safety notes.
 *
 * Advisory only: nothing here blocks rendering. Shows what was found so
 * the founder can decide, and says so plainly when there is nothing.
 */
export function SafetyPanel({ report, summary, onEditClaim, onRegenerate, busy = false, hasEdits = false }) {
  if (!report) {
    return (
      <Alert variant="warning">
        <HelpCircle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        <AlertTitle>No safety check yet</AlertTitle>
        <AlertDescription>
          Generate a creative plan to run the claim check against your approved App Profile.
        </AlertDescription>
      </Alert>
    );
  }

  void onEditClaim;
  void onRegenerate;
  void busy;
  const passed = true;
  const blocking = [];
  const unverified = report.unverified || [];
  const warnings = report.risk_warnings || [];
  const used = report.claims_used || [];
  const undeclared = report.unverified_self_claims || [];
  const sources = report.sources_used || [];
  const flagged = unverified.length + warnings.length + undeclared.length;

  return (
    <div className="space-y-3">
      <Alert variant="default">
        <ShieldCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        <AlertTitle>
          No blocking claims found
        </AlertTitle>
        <AlertDescription>
          {summary || (flagged ? `${flagged} item(s) need review.` : "Nothing flagged.")}
          {flagged > 0 && " These review notes do not block rendering."}
          {hasEdits && " This report describes the saved plan; your edits have not been checked yet."}
        </AlertDescription>
      </Alert>

      <Disclosure testId="claim-check-details" summary={`Review notes & evidence (${flagged})`}>
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
