import { Target } from "lucide-react";

/**
 * What has worked here, on one App Profile's own recorded results.
 *
 * This card used to live on the App Profile detail page and was moved out when
 * that page was reduced to collapsible research groups. It is resurrected here
 * rather than rewritten, because it is the only part of a profile that improves
 * with use: everything else was researched once and goes stale, while the
 * founder's own numbers say which openings actually carried views.
 *
 * Aggregate on purpose. Per-template counts only -- no video text, no caption,
 * no source URL -- and manual entries only, so a future automated import cannot
 * quietly become an input to generation.
 *
 * Both ends are shown. `bottom` is the half that used to be fetched and then
 * displayed nowhere: knowing which templates carried views is half the evidence,
 * because the next strategy has to avoid the ones that did not as well as repeat
 * the ones that did.
 */
export default function WhatWorksCard({ data }) {
  const hasSignal = Boolean(data?.has_signal);
  const videos = data?.videos ?? 0;

  return (
    <div className="surface space-y-3 rounded-2xl" data-testid="what-works">
      <span className="eyebrow flex items-center gap-1.5">
        <Target className="h-3 w-3" /> What has worked here
      </span>
      {!hasSignal ? (
        <p className="text-sm text-muted-foreground">
          Nothing recorded yet. Add view numbers to a finished video and the next strategy
          will know which of this app&apos;s openings actually carried them.
        </p>
      ) : (
        <>
          <p className="text-xs text-muted-foreground">
            Across {videos} recorded video{videos === 1 ? "" : "s"}. View counts only — not
            proof that one template is better.
          </p>
          <div className="grid gap-4 sm:grid-cols-2">
            <RankedList title="Carried the most views" rows={data?.top || []} />
            <RankedList title="Carried the least" rows={data?.bottom || []} muted />
          </div>
        </>
      )}
    </div>
  );
}

/**
 * One ranked end of the template table.
 *
 * The two ends sit in one row because they are read together: the fix is to
 * lean on the left column and stop reaching for the right one, which is not
 * visible from either list alone. A single end renders nothing rather than
 * opening a one-sided table, since one template has no "least".
 */
function RankedList({ title, rows, muted = false }) {
  if (!rows.length) return null;
  return (
    <div className="min-w-0">
      <span className="eyebrow block">{title}</span>
      <dl className="mt-2 space-y-1.5 text-sm">
        {rows.map((row) => (
          <div key={row.template_id} className="flex items-baseline justify-between gap-3">
            <dt className="min-w-0 truncate">{row.template_id}</dt>
            <dd className="shrink-0 text-muted-foreground">
              {row.views.toLocaleString()} views · save {Math.round(row.save_rate * 100)}%
            </dd>
          </div>
        ))}
      </dl>
      {muted && (
        <p className="mt-2 text-xs text-muted-foreground">
          Fewer views is not proof of a bad opening, only the absence of evidence for it.
        </p>
      )}
    </div>
  );
}