import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import { FactChip } from "../components/FactChip";
import { SectionCard } from "../components/SectionCard";
import { BarChart3, Loader2, AlertTriangle, Info, TrendingUp } from "lucide-react";

function money(value) {
  if (value === null || value === undefined) return null;
  return `$${Number(value).toFixed(2)}`;
}

function pct(value) {
  return value == null ? "—" : `${Math.round(value * 100)}%`;
}

/**
 * One labelled set of rows, with the numbers in real columns.
 *
 * The three figures were bare spans inside a flex row, so nothing lined up:
 * counts and percentages sat wherever their labels ended, and the money column
 * was a `w-14` box that only lined up within a single card. Six of these sit side
 * by side, so misalignment read as the cards being different sizes rather than
 * as columns that needed widths. Fixed columns make the six cards comparable at
 * a glance, which is the entire point of a breakdown.
 */
function Breakdown({ title, rows, describeKey = "label", countKey = "count" }) {
  if (!rows?.length) return null;
  return (
    <SectionCard title={title}>
      <div className="space-y-1.5">
        {rows.slice(0, 8).map((row) => (
          <div
            key={row.key}
            className="grid grid-cols-[minmax(0,1fr)_2.5rem_3.5rem_4.5rem] items-center gap-2 text-sm"
          >
            <span className="min-w-0 truncate text-muted-foreground">
              {row[describeKey] || row.key}
            </span>
            <span className="text-right text-xs text-muted-foreground">{row[countKey]}</span>
            <span className="text-right text-xs">{pct(row.success_rate)}</span>
            <span className="text-right text-xs text-muted-foreground">
              {money(row.total_usd) || "$0"}
            </span>
          </div>
        ))}
      </div>
    </SectionCard>
  );
}

export default function Analytics() {
  const [report, setReport] = useState(null);
  const [profiles, setProfiles] = useState([]);
  const [filter, setFilter] = useState("");
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  const load = useCallback(async () => {
    setLoading(true);
    try {
      setReport(await api.getAnalytics(filter ? { brand_profile_id: filter } : {}));
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [filter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.getAppProfiles().then((d) => setProfiles(d.profiles || [])).catch(() => setProfiles([]));
  }, []);

  if (loading && !report) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading analytics...
      </p>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const t = report?.totals || {};
  const perf = report?.performance || {};
  const rework = report?.rework || {};
  const feedback = report?.feedback || {};

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <PageHeader
        icon={BarChart3}
        title="Analytics"
        description="Internal production metrics. Everything here is measured from this app's own history."
        actions={
          <select
            value={filter}
            onChange={(e) => setFilter(e.target.value)}
            aria-label="Filter by app"
            className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
          >
            <option value="">All apps</option>
            {profiles.map((p) => (
              <option key={p.id} value={p.id}>{p.brand_name}</option>
            ))}
          </select>
        }
      />

      {t.unpriced_runs > 0 && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>
            {t.unpriced_runs} run(s) reported no cost, so the spend figure above covers
            only the {t.priced_runs} priced run(s). Unpriced work is not treated as free.
          </AlertDescription>
        </Alert>
      )}

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4" data-testid="analytics-totals">
        {[
          ["Videos created", t.videos_created ?? 0, `${t.completed ?? 0} completed`],
          ["Success rate", pct(t.success_rate), `${t.failed ?? 0} failed`],
          ["Failure rate", pct(t.failure_rate), "of finished attempts"],
          ["Avg generation", t.avg_generation_seconds != null ? `${t.avg_generation_seconds}s` : "—", "submit to completion"],
          ["Known spend", money(t.total_usd) || "$0.00", `${t.priced_runs ?? 0} priced runs`],
          ["Regenerated", rework.regenerated ?? 0, "the same setup, rendered again"],
          ["Variations", rework.variations ?? 0, `max ${rework.max_variations_of_one_video ?? 0} of one video`],
          ["Approved videos", feedback.by_event?.video_approved ?? 0, "approved at review"],
        ].map(([label, value, hint]) => (
          <div key={label} className="surface rounded-2xl p-4">
            <span className="text-xs text-muted-foreground">{label}</span>
            <p className="mt-1 font-display text-xl font-bold">{value}</p>
            <p className="text-xs text-muted-foreground">{hint}</p>
          </div>
        ))}
      </div>

      <div className="grid grid-cols-1 gap-3 md:grid-cols-2" data-testid="analytics-breakdowns">
        <Breakdown title="By app" rows={report?.by_app} />
        <Breakdown title="By model" rows={report?.by_model} />
        <Breakdown title="By template" rows={report?.by_template} countKey="used" />
        <Breakdown title="By objective" rows={report?.by_objective} />
        <Breakdown title="By audience" rows={report?.by_audience} />
        <Breakdown title="By content angle" rows={report?.by_angle} />
      </div>

      <SectionCard
        title="TikTok performance (entered by hand)"
        icon={TrendingUp}
        className="space-y-3"
        data-testid="analytics-performance"
      >
        <div className="grid grid-cols-2 gap-3 sm:grid-cols-6">
          {[
            ["Entries", perf.entries ?? 0],
            ["Views", perf.views ?? 0],
            ["Likes", perf.likes ?? 0],
            ["Comments", perf.comments ?? 0],
            ["Shares", perf.shares ?? 0],
            ["Saves", perf.saves ?? 0],
          ].map(([label, value]) => (
            <div key={label}>
              <span className="text-xs text-muted-foreground">{label}</span>
              <p className="font-display text-base font-semibold">{value}</p>
            </div>
          ))}
        </div>
        {/* Facts about the source, not status: a badge reads as a state this
            thing is in, and none of these is a state. The two that matter most
            are the disclaimers, so they are chips like every other fact. */}
        <div className="flex flex-wrap items-center gap-2">
          <FactChip>Source: manual</FactChip>
          <FactChip>Not platform-verified</FactChip>
          <span className="text-xs text-muted-foreground">
            {perf.marked_successful ?? 0} marked worked · {perf.marked_unsuccessful ?? 0} did not
          </span>
        </div>
      </SectionCard>

      <div className="space-y-3" data-testid="analytics-feedback">
      {feedback.top_signals?.length > 0 && (
        <SectionCard title="What happened" className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Captured automatically as you worked. These are facts about the workflow, not
            opinions about why.
          </p>
          {feedback.top_signals.map((s) => (
            <div key={s.signal} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted-foreground">
                {String(s.signal).replace(/_/g, " ")}
              </span>
              {/* A count is a fact about the row, so it is a chip rather than a
                  badge — the same rule the breakdown columns follow. */}
              <FactChip>{s.count}</FactChip>
            </div>
          ))}
        </SectionCard>
      )}

      {feedback.top_reasons?.length > 0 && (
        <SectionCard title="Why work was rejected or redone" className="space-y-2">
          <p className="text-xs text-muted-foreground">
            Only the {feedback.explained ?? 0} of {feedback.total ?? 0} events you explained
            yourself. The rest are counted above without a stated reason.
          </p>
          {feedback.top_reasons.map((r) => (
            <div key={r.reason} className="flex items-center justify-between gap-3 text-sm">
              <span className="text-muted-foreground">
                {String(r.reason).replace(/_/g, " ")}
              </span>
              <FactChip>{r.count}</FactChip>
            </div>
          ))}
        </SectionCard>
      )}
      </div>

      <p className="text-xs text-muted-foreground">
        No TikTok account is connected and no platform data is scraped. Performance figures
        are whatever you typed in, and are never presented as verified.
      </p>
    </div>
  );
}
