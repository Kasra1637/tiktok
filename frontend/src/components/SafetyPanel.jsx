import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { Badge } from "./ui/badge";
import { ShieldCheck, ShieldAlert, Ban, Circle as HelpCircle, Sparkles } from "lucide-react";
import { sentenceCase } from "../lib/copyCase";

/**
 * Reviewer-facing claim-safety report.
 *
 * Deliberately shows what was FOUND, not a reassuring summary. A clean plan
 * says so plainly; a flagged plan names every specific phrase so the founder
 * can decide, and a failed plan is impossible to miss because it blocks
 * generation.
 */
export function SafetyPanel({ report, summary }) {
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
          {passed ? "Claim check passed" : "Prohibited claim detected — generation blocked"}
        </AlertTitle>
        <AlertDescription>
          {summary || (flagged ? `${flagged} item(s) need review.` : "Nothing flagged.")}
        </AlertDescription>
      </Alert>

      {blocking.length > 0 && (
        <div className="rounded-xl border border-destructive/40 bg-destructive/5 p-4">
          <span className="eyebrow flex items-center gap-1.5 text-destructive">
            <Ban className="h-3 w-3" /> Never use — found in this script
          </span>
          <ul className="mt-2 space-y-1.5 text-sm">
            {blocking.map((b, i) => (
              <li key={i}>
                <span className="font-medium">&ldquo;{b.claim}&rdquo;</span>
                <span className="text-muted-foreground"> — {sentenceCase(b.reason)}</span>
              </li>
            ))}
          </ul>
        </div>
      )}

      {warnings.length > 0 && (
        <div className="rounded-xl border border-[color:var(--hairline-strong)] bg-secondary/25 p-4">
          <span className="eyebrow">Risk warnings</span>
          <ul className="mt-2 space-y-1.5 text-sm">
            {warnings.map((w, i) => (
              <li key={i} className="flex flex-wrap items-baseline gap-x-2">
                <span className="font-medium">&ldquo;{w.claim}&rdquo;</span>
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
        <div className="rounded-xl border border-[color:var(--hairline-strong)] bg-secondary/25 p-4">
          <span className="eyebrow">Declared but not in the script</span>
          <p className="mt-1 text-xs text-muted-foreground">
            The generator reported using these, but they do not appear in the text.
          </p>
          <ul className="mt-2 space-y-1 text-sm">
            {undeclared.map((c, i) => (
              <li key={i}>{c}</li>
            ))}
          </ul>
        </div>
      )}

      {unverified.length > 0 && (
        <div className="rounded-xl border border-[color:var(--hairline-strong)] bg-secondary/25 p-4">
          <span className="eyebrow">Needs verification</span>
          <ul className="mt-2 space-y-1 text-sm">
            {unverified.map((u, i) => (
              <li key={i}>{u.claim}</li>
            ))}
          </ul>
        </div>
      )}

      <div className="rounded-xl border border-[color:var(--hairline)] p-4">
        <span className="eyebrow flex items-center gap-1.5">
          <Sparkles className="h-3 w-3" /> Verified claims used ({used.length})
        </span>
        {used.length ? (
          <div className="mt-2 flex flex-wrap gap-1.5">
            {used.map((c, i) => (
              <Badge key={i} variant="secondary" className="text-xs">{c}</Badge>
            ))}
          </div>
        ) : (
          <p className="mt-1 text-sm text-muted-foreground">
            None of your approved claims appear in this script.
          </p>
        )}
      </div>

      {sources.length > 0 && (
        <p className="text-xs text-muted-foreground">
          Grounded in: {sources.map((s) => s.replace(/_/g, " ")).join(", ")}.
        </p>
      )}
    </div>
  );
}

export default SafetyPanel;
