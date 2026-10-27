import { ChevronDown } from "lucide-react";

/**
 * The one closed disclosure in the app.
 *
 * Call sites own the label, the testid, and whatever sits inside.
 *
 * Not used for Fine-tune framing: the smoke suite matches that disclosure as
 * literal source text, so routing it through here would break the check.
 */
export function Disclosure({
  testId,
  summary,
  children,
  detailsClassName = "group rounded-xl border border-[color:var(--hairline)] bg-secondary/20 px-3 py-1.5",
  summaryClassName = "flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-sm font-semibold text-muted-foreground transition-colors group-hover:text-foreground [&::-webkit-details-marker]:hidden",
}) {
  return (
    <details className={detailsClassName} data-testid={testId}>
      <summary className={summaryClassName}>
        <span>{summary}</span>
        <ChevronDown className="h-4 w-4 shrink-0 transition-transform duration-200 group-open:rotate-180" />
      </summary>
      {children}
    </details>
  );
}
