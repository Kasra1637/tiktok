import { useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import { SectionCard } from "../components/SectionCard";
import { AppPicker } from "../components/AppPicker";
import { EmptyState } from "../components/EmptyState";
import { AnalyticsEmptyArt, AppProfileEmptyArt } from "../components/EmptyStateArt";
import { Skeleton } from "../components/ui/skeleton";
import { FactChip, FactList } from "../components/FactChip";
import { api, getErrorMessage } from "../lib/api";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import { useReducedMotionPreference } from "../lib/reducedMotion";
import { isWinnerRow, nextTakeFor, pickNextTake } from "../lib/nextTake";
import { useVerifiedDraftIds } from "../hooks/useVerifiedDraftIds";
import { useTourEligibility } from "../components/onboarding/OnboardingProvider";
import TourStartLink from "../components/onboarding/TourStartLink";
import { TrendingUp, AlertTriangle, Activity, ListChecks, CalendarDays, ThumbsUp, ThumbsDown, Minus, Crown, Download, RotateCcw, LayoutTemplate, PenLine, CopyPlus, ChevronDown } from "lucide-react";

// Compare the same saved results History displays; activity stays separate
// from reach, and neither views nor workflow signals imply conversions.

/** Same vocabulary helper History uses, so a code reads identically on both. */
function humanize(value) {
  return String(value || "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * Weekly render counts, newest week first, capped at six.
 *
 * Rows without a parseable created_at are skipped rather than bucketed: a
 * week labelled from a guess would be inventing a fact, and the funnel card
 * already counts every row regardless of date.
 */
function weekBuckets(rows) {
  const buckets = new Map();
  for (const row of rows || []) {
    const t = Date.parse(row?.created_at);
    if (Number.isNaN(t)) continue;
    const d = new Date(t);
    const monday = new Date(d);
    monday.setDate(d.getDate() - ((d.getDay() + 6) % 7));
    monday.setHours(0, 0, 0, 0);
    const key = monday.getTime();
    buckets.set(key, (buckets.get(key) || 0) + 1);
  }
  const now = new Date();
  const thisMonday = new Date(now);
  thisMonday.setDate(now.getDate() - ((now.getDay() + 6) % 7));
  thisMonday.setHours(0, 0, 0, 0);
  return [...buckets.entries()]
    .sort((a, b) => b[0] - a[0])
    .slice(0, 6)
    .map(([key, count]) => ({
      key,
      count,
      label:
        key === thisMonday.getTime()
          ? "This week"
          : `Week of ${new Date(key).toLocaleDateString(undefined, { month: "short", day: "numeric" })}`,
    }));
}

// The skeleton fade's length, shared with the .skeleton-leaving
// animation in index.css (ADR 0166): the leaving state must lift
// exactly when the fade completes.
const SKELETON_FADE_MS = 250;

export default function Analytics() {
  const [profiles, setProfiles] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [generations, setGenerations] = useState(null);
  const [verdictSummary, setVerdictSummary] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryVersion, setRetryVersion] = useState(0);

  // Skeleton resolve (ADR 0166): when loading ends, the skeleton stays
  // mounted for one fade while the content mounts in the same grid
  // cell beneath it, so the handoff is a crossfade rather than the old
  // hard cut. Reduced motion never enters the leaving state — the
  // swap stays instant, the JS belt to the CSS no-preference gate on
  // .skeleton-leaving.
  const reduceMotion = useReducedMotionPreference();
  const [skeletonLeaving, setSkeletonLeaving] = useState(false);
  const wasLoading = useRef(false);
  useEffect(() => {
    if (loading) {
      wasLoading.current = true;
      setSkeletonLeaving(false);
      return undefined;
    }
    if (!wasLoading.current || reduceMotion) {
      wasLoading.current = false;
      setSkeletonLeaving(false);
      return undefined;
    }
    wasLoading.current = false;
    setSkeletonLeaving(true);
    const timer = setTimeout(() => setSkeletonLeaving(false), SKELETON_FADE_MS);
    return () => clearTimeout(timer);
  }, [loading, reduceMotion]);

  // First-run help (ADR 0118): the tour may auto-open only once the page
  // has loaded cleanly and no verdict has been cast yet. The summary's
  // verdict count is the "the founder has started judging videos"
  // signal; past zero the tour would interrupt someone already in the loop.
  useTourEligibility(
    "analytics",
    !loading && !error && generations !== null && (verdictSummary?.total ?? 0) === 0
  );

  // The profile list first, because it decides what everything else is scoped
  // to. A remembered selection is only honoured when it still names a profile
  // that exists -- an id from a deleted app would otherwise pin the page to an
  // empty state forever.
  useEffect(() => {
    let cancelled = false;
    api
      .getAppProfiles()
      .then((d) => {
        if (cancelled) return;
        const rows = d.profiles || [];
        setProfiles(rows);
        const remembered = readCurrentAppId();
        setSelectedId(
          rows.some((p) => p.id === remembered) ? remembered : ""
        );
      })
      .catch((err) => {
        if (!cancelled) {
          setError(getErrorMessage(err));
          setLoading(false);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [retryVersion]);

  useEffect(() => {
    if (profiles === null) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    setFeedback(null);
    setGenerations(null);
    setVerdictSummary(null);
    const scope = selectedId ? { brand_profile_id: selectedId } : {};
    Promise.all([
      api.getFeedback({ ...scope, limit: 500 }),
      api.getGenerationHistory({ ...scope, limit: 200 }),
    ]).then(([fb, history]) => {
      if (cancelled) return;
      setFeedback(fb);
      setGenerations(history.generations || []);
      setVerdictSummary(history.verdict_summary || null);
    }).catch((err) => {
      if (!cancelled) setError(getErrorMessage(err));
    }).finally(() => {
      if (!cancelled) setLoading(false);
    });
    return () => { cancelled = true; };
  }, [selectedId, profiles, retryVersion]);

  const selectProfile = (id) => {
    setSelectedId(id);
    // Persisted so returning here is one click, not a re-pick. Same key the
    // rest of the app uses, so an app chosen here is the app the Asset Library
    // opens on.
    rememberCurrentAppId(id);
  };

  const signals = feedback?.summary?.top_signals || [];
  const reasons = feedback?.summary?.top_reasons || [];
  const renders = Array.isArray(generations) ? generations : null;
  const takePick = pickNextTake(renders);
  const draftIds = useVerifiedDraftIds(selectedId, takePick?.studio_project_id);
  const hasFeedback = (feedback?.summary?.total || 0) > 0 || (feedback?.feedback?.length || 0) > 0;
  const hasAnything = hasFeedback || signals.length > 0 || reasons.length > 0 || (renders?.length || 0) > 0;

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={TrendingUp}
        title="Analytics"
        description="Your recent renders and how they performed."
        data-testid="analytics-header"
        actions={
          profiles?.length > 0 ? (
            <AppPicker
              profiles={profiles}
              value={selectedId}
              onChange={selectProfile}
              allLabel="All apps"
              testId="analytics-profile-picker"
              align="end"
            />
          ) : null
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>{error}</span>
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setRetryVersion((v) => v + 1)}
              data-testid="analytics-retry"
            >
              Try again
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* The skeleton and the content it gives way to share one grid
          cell (.skeleton-stack, ADR 0166): for the length of the fade
          both are mounted in the same cell, so the resolve cannot
          shift the layout, and the skeleton lifts exactly when its
          fade completes. */}
      <div className="skeleton-stack">
        {(loading || skeletonLeaving) && (
          <div
            className={`surface space-y-4${skeletonLeaving ? " skeleton-leaving" : ""}`}
            aria-label="Loading analytics"
            aria-hidden={skeletonLeaving || undefined}
            data-testid="analytics-loading"
          >
            <Skeleton className="h-8 w-48" />
            <Skeleton className="h-4 w-full" />
            <Skeleton className="h-4 w-4/5" />
          </div>
        )}
        {loading ? null : error ? null : !profiles?.length && !hasAnything ? (
          <EmptyState
            illustration={<AppProfileEmptyArt />}
            title="No app yet"
            description="Create an App Profile to get started. Signals appear here as you work with it."
            action={
              <Button variant="accent" asChild>
                <Link to="/brand">Open App Profile</Link>
              </Button>
            }
          />
      ) : !hasAnything ? (
        <EmptyState
          illustration={<AnalyticsEmptyArt />}
          title="No posted results yet"
          description="Create a clip, then add its posted link, views, and your vote in History."
          action={
            <div className="flex flex-col items-center gap-3">
              <Button variant="accent" asChild>
                <Link to={selectedId ? `/create?profile=${encodeURIComponent(selectedId)}` : "/create"}>Create Video</Link>
              </Button>
              <TourStartLink tourId="analytics" />
            </div>
          }
        />
      ) : (
        <div className="page-content-enter space-y-6">
          <p data-testid="analytics-scope" className="text-sm text-muted-foreground">
            Your {renders?.length ?? 0} newest renders{selectedId ? " for this app" : " across all apps, unassigned exports included"}. Everything below uses this same set.
          </p>
          {/* Clip results stands alone at full width — a wide read,
              like the weekly chart below. It used to share the desktop
              width two-across with the Renders funnel card, the pair
              stretched to one height (ADR 0159); Kasra removed the
              Renders section (ADR 0272), so the pairing grid went
              with it and the ledger keeps the whole row. */}
          {renders?.length > 0 && (
            <ClipResults generations={renders} profileId={selectedId} pick={takePick} draftIds={draftIds} verdictSummary={verdictSummary} />
          )}
          {renders !== null && renders.length > 0 && (
            <RenderActivity generations={renders} />
          )}
          {hasFeedback && !signals.length && !reasons.length && !renders?.length && (
            <p className="text-base text-muted-foreground" role="status">
              Feedback is saved. No renders or automatic workflow signals are in this loaded set yet.
              Ratings inform future suggestions; they are not conversions or proof that a clip works.
            </p>
          )}
          {hasFeedback && (
            <p className="text-sm text-muted-foreground">Repeated ratings are events, not unique clips or measured outcomes.</p>
          )}
          {(signals.length > 0 || reasons.length > 0) && (
            <div className={`grid items-start gap-6 ${signals.length > 0 && reasons.length > 0 ? "lg:grid-cols-2" : ""}`}>
              {signals.length > 0 && (
                <SignalCounts summary={feedback.summary} events={feedback.feedback || []} profileId={selectedId} />
              )}
              {reasons.length > 0 && (
                <SignalReasons summary={feedback.summary} events={feedback.feedback || []} profileId={selectedId} />
              )}
            </div>
          )}
        </div>
        )}
      </div>
    </PageFrame>
  );
}

function clipName(row) {
  return row.hook_line || `${row.segment_role === "demo_cta" ? "Demo + CTA export" : "Render"} · ${row.id.slice(0, 8)}`;
}

// Three rows is the card's opening glance: the ranked top of the list under
// its own count line. Ten rows pushed the cards below out of view and read as
// a spreadsheet rather than a comparison; the rest stay one click away.
const LEADERBOARD_PAGE_SIZE = 3;

/**
 * The one headline line about the founder's whole-video verdicts, or
 * the honest not-yet state. Mirrors feedback.summarize_video_verdicts
 * on the server: counts of worked / didn't-work verdicts, and — at 3+,
 * the same threshold generation steering uses — what the worked
 * bundles share. Below 3 verdicts there is no pattern to name, and
 * the line says so (ADR 0124). Posted metrics and craft scores stay
 * on the rows as the record; since ADR 0124 they headline nothing,
 * because neither can say which element made a video work.
 */
function verdictSummaryLine(summary) {
  const total = summary?.total || 0;
  const up = summary?.up || 0;
  const down = summary?.down || 0;
  if (total === 0) {
    return "No verdicts yet — judge a finished video in History, one call on the whole clip, and new plans start learning from what worked.";
  }
  if (!summary?.ready) {
    return `${total} ${total === 1 ? "verdict" : "verdicts"} so far (${up} worked, ${down} didn't) — the loop starts learning at 3 verdicts, and patterns firm up around 5–7.`;
  }
  const shared = summary.shared || {};
  const traits = [
    ...(shared.templates || []).length ? ["the same opening template"] : [],
    ...(shared.angle_kinds || []).map((kind) => `the ${humanize(kind)} angle`),
    ...(shared.objectives || []).map((objective) => `the ${humanize(objective)} goal`),
  ];
  const base = `Across ${total} rated videos (${up} worked, ${down} didn't): `;
  const body = traits.length
    ? `the ones that worked share ${traits.join(", ")}.`
    : "no single trait runs through all the ones that worked yet.";
  return base + body + (total < 5 ? " Patterns firm up around 5–7 verdicts." : "");
}

/** The real numbers from a clip's latest results snapshot, as one line. */
function snapshotFacts(snapshot) {
  if (!snapshot) return [];
  return [
    snapshot.retention_3s_pct != null ? `${Number(snapshot.retention_3s_pct)}% past 3s` : null,
    snapshot.avg_watch_pct != null ? `${Number(snapshot.avg_watch_pct)}% avg watch` : null,
    snapshot.saves != null ? `${Number(snapshot.saves).toLocaleString("en-US")} saves` : null,
    snapshot.shares != null ? `${Number(snapshot.shares).toLocaleString("en-US")} shares` : null,
  ].filter(Boolean);
}

/** A short, local date for the renders inside a status group. */
// Craft scores read on the honest 0-10 scale (ADR 0300). The
// server fills score10 into stored reports on read; the fallback
// divides by the true 95-point ceiling for any report that still
// carries points only.
function craftScore10Label(report) {
  const value = typeof report?.score10 === "number"
    ? report.score10
    : Math.round(((Number(report?.total) || 0) / 95) * 100) / 10;
  return Number.isInteger(value) ? String(value) : value.toFixed(1);
}

function shortDate(value) {
  const t = Date.parse(value);
  if (Number.isNaN(t)) return "";
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function ClipResults({ generations, profileId, pick, draftIds, verdictSummary }) {
  const clips = generations
    .filter((row) => row.status === "completed" || row.status === "archived")
    .sort((a, b) => (b.tiktok_views ?? -1) - (a.tiktok_views ?? -1));
  const [expanded, setExpanded] = useState(false);
  // The card opens on its first three rows: enough to show the ranking and
  // the scale between them, with the full ledger a deliberate second step.
  // The card itself never collapses (ADR 0166): like History's sections
  // (ADR 0151) it stands open, and this show-all control is the only
  // disclosure it carries.
  const visible = expanded ? clips : clips.slice(0, LEADERBOARD_PAGE_SIZE);
  const posted = clips.filter((row) => row.tiktok_url).length;
  const counted = clips.filter((row) => row.tiktok_views != null).length;
  const rated = clips.filter((row) => row.video_verdict).length;
  const historyHref = profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history";
  const pickNext = pick ? nextTakeFor(pick, historyHref, draftIds) : null;
  // Bars scale to the highest recorded count, so the leader reads full and
  // every other clip reads relative to it. A recorded zero still earns a
  // sliver; an unrecorded count earns no bar and no guess.
  const maxViews = Math.max(0, ...clips.map((row) => row.tiktok_views ?? 0));
  const barWidth = (views) => `${views > 0 && maxViews > 0 ? Math.max(6, Math.round((views / maxViews) * 100)) : views === 0 ? 6 : 0}%`;
  return (
    <SectionCard
      title="Clip results"
      icon={TrendingUp}
      description="Compare reach & your judgment before choosing another take."
      data-testid="analytics-results"
    >
      <FactList aria-label="Clip totals">
        <FactChip>{posted} posted</FactChip>
        <FactChip>{counted} with recorded views</FactChip>
        <FactChip>{rated} rated</FactChip>
      </FactList>
      <p className="text-sm text-muted-foreground" data-testid="analytics-performance-summary">
        {verdictSummaryLine(verdictSummary)}
      </p>
      <div className="space-y-5">
        <details className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/20 px-3 py-1.5 transition-colors hover:border-[color:var(--hairline-strong)]">
          <summary className="flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-sm text-muted-foreground [&::-webkit-details-marker]:hidden">
            <span>Why these numbers</span>
            <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-open:rotate-180" />
          </summary>
          <div className="space-y-2 pb-2 text-sm text-muted-foreground">
            <p>
              Views are manually recorded snapshots of reach, not installs, revenue, or conversions. Counts may come from different posting dates; this is not a controlled comparison.
              Your verdict is your judgment. Winner still means a worked verdict plus a posted link, never a view threshold.
            </p>
            <p>Compare a high-reach clip you said worked with the others, then reuse its draft to test another take. <Link to={historyHref} className="text-[color:var(--brand-indigo)] hover:underline">Record or update results in History</Link>.</p>
          </div>
        </details>
        {pick && pickNext && (
          <div data-testid="analytics-next-take" className="flex items-start gap-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] px-4 py-3">
            <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[color:var(--indigo-35)] bg-[color:var(--indigo-10)]">
              <ThumbsUp aria-hidden="true" className="h-3 w-3 text-[color:var(--brand-indigo)]" />
            </span>
            <div className="min-w-0 space-y-1">
            <p className="text-sm font-semibold text-foreground">Suggested next take: {clipName(pick)}</p>
            <p className="text-sm text-muted-foreground">
              Posted, {pick.tiktok_views.toLocaleString("en-US")} recorded views, rated worked — the highest reach among clips you said worked.
              Past reach does not promise the next take repeats it.{" "}
              <Link to={pickNext.to} className="text-[color:var(--brand-indigo)] hover:underline">{pickNext.label}</Link> to test another take.
            </p>
            </div>
          </div>
        )}
        {clips.length === 0 ? (
          <p className="text-base text-muted-foreground">No finished clips to compare yet.</p>
        ) : (
          <div
            data-testid="analytics-results-table"
            className={`rounded-xl border border-[color:var(--hairline)] bg-secondary/10 ${expanded ? "clips-scroll-region" : ""}`}
          >
            {/* Stacked entries, not a table (ADR 0209, superseding ADR
                0159's fixed-layout column template): the card is paired
                at half width on desktop and full width below it, and at
                neither width could seven percentage columns hold their
                content — the clip title wrapped to four lines, the
                posted state wrapped under its dot, the craft grade
                split at its middot, the verdict pill wrapped inside
                itself and the rank crown overflowed its cell into the
                title's. Each clip is now one entry in the page's own
                ledger language: rank and title on their own line, the
                facts as a wrapping row of labelled items beneath, and
                every short field — posted state, views count, craft
                grade, verdict pill, next-take link — on one line by
                construction (whitespace-nowrap), wrapping only as
                whole items. Expanded, the region still scrolls inside
                the ADR 0160 bound in index.css instead of growing the
                card past its pair; collapsed, no height bound exists,
                so the first entries always stand whole. */}
            <ul aria-label="Saved clips, highest recorded views first; missing counts last." className="divide-y divide-[color:var(--hairline)]">
              {visible.map((row, index) => {
                const vote = row.video_verdict === "up" ? 1 : row.video_verdict === "down" ? -1 : 0;
                const next = nextTakeFor(row, historyHref, draftIds);
                const winner = isWinnerRow(row);
                return (
                  <li key={row.id} data-testid={`result-${row.id}`} className="space-y-2 px-3 py-3 transition-colors hover:bg-secondary/20">
                    <div className="flex items-start gap-2.5">
                      <span data-testid={`result-rank-${row.id}`} className="flex shrink-0 items-center gap-1.5 pt-0.5 text-xs text-muted-foreground">
                        <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[color:var(--hairline-strong)] bg-secondary/40 font-mono tabular-nums">{index + 1}</span>
                        {winner && <Crown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />}
                      </span>
                      <div className="min-w-0">
                        <Link to={`${historyHref}#generation-${row.id}`} className="text-sm font-semibold text-[color:var(--brand-indigo)] hover:underline">
                          {clipName(row)}
                        </Link>
                        <span className="mt-0.5 block text-xs text-muted-foreground">{row.brand_name || "Unassigned app"}{row.objective ? ` · ${humanize(row.objective)}` : ""}</span>
                      </div>
                    </div>
                    <div className="flex flex-wrap items-center gap-x-4 gap-y-2 pl-[34px] text-xs">
                      {row.tiktok_url ? (
                        <a href={row.tiktok_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 whitespace-nowrap text-[color:var(--brand-indigo)] hover:underline">
                          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-[color:var(--brand-indigo)]" />
                          Posted ↗
                        </a>
                      ) : (
                        <span className="inline-flex items-center gap-1.5 whitespace-nowrap text-muted-foreground">
                          <span aria-hidden="true" className="h-1.5 w-1.5 shrink-0 rounded-full bg-muted-foreground/30" />
                          Not posted
                        </span>
                      )}
                      <span className="inline-flex items-center gap-1.5 whitespace-nowrap">
                        <span className="text-muted-foreground">Views</span>
                        {row.tiktok_views == null ? (
                          <span className="text-muted-foreground">Not recorded</span>
                        ) : (
                          <span className="inline-flex items-center gap-1.5">
                            <span className="h-2 w-16 shrink-0 overflow-hidden rounded-full bg-secondary/50" aria-hidden="true">
                              <span data-testid={`result-views-bar-${row.id}`} className="block h-full rounded-full bg-[color:var(--accent)] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.18)]" style={{ width: barWidth(row.tiktok_views) }} />
                            </span>
                            <span className="font-mono tabular-nums">{row.tiktok_views.toLocaleString("en-US")}{row.tiktok_views_at && shortDate(row.tiktok_views_at) ? ` · Recorded ${shortDate(row.tiktok_views_at)}` : ""}</span>
                          </span>
                        )}
                      </span>
                      <span className="inline-flex items-center gap-1.5 whitespace-nowrap" data-testid={`result-craft-${row.id}`}>
                        <span className="text-muted-foreground">Craft</span>
                        {row.quality_report ? (
                          <span className="font-mono tabular-nums">{row.quality_report.grade} · {craftScore10Label(row.quality_report)}</span>
                        ) : (
                          <span className="text-muted-foreground">Not scored</span>
                        )}
                      </span>
                      <span data-testid={`result-vote-${row.id}`} className="inline-flex">
                        <span className={`inline-flex items-center gap-1.5 whitespace-nowrap rounded-full border px-2 py-0.5 ${vote > 0 ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-10)] text-foreground" : "border-[color:var(--hairline)] bg-secondary/20 text-muted-foreground"}`}>
                          {vote > 0 ? (
                            <ThumbsUp aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
                          ) : vote < 0 ? (
                            <ThumbsDown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          ) : (
                            <Minus aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-muted-foreground" />
                          )}
                          {vote > 0 ? "Worked" : vote < 0 ? "Didn't work" : "Not rated"}
                        </span>
                      </span>
                      <Link to={next.to} className="whitespace-nowrap text-[color:var(--brand-indigo)] hover:underline">{next.label}</Link>
                    </div>
                    {snapshotFacts(row.performance_snapshot).length > 0 && (
                      <p className="pl-[34px] text-xs text-muted-foreground" data-testid={`result-results-${row.id}`}>
                        {snapshotFacts(row.performance_snapshot).join(" · ")}
                      </p>
                    )}
                  </li>
                );
              })}
            </ul>
          </div>
        )}
        {clips.length > LEADERBOARD_PAGE_SIZE && (
          <div className="flex justify-center pt-1">
            <Button
              variant="secondary"
              size="sm"
              onClick={() => setExpanded((current) => !current)}
              aria-expanded={expanded}
              data-testid="analytics-results-show-more"
            >
              {expanded ? "Show less" : `Show all ${clips.length}`}
            </Button>
          </div>
        )}
        <p className="border-t border-[color:var(--hairline)] pt-3 text-sm text-muted-foreground">
          Ranked by recorded views; missing counts sort last.
        </p>
      </div>
    </SectionCard>
  );
}

/** Week counts as words, for the busiest-week sentence (ADR 0160). */
const WEEK_COUNT_WORDS = ["", "", "two", "three", "four", "five", "six"];

/**
 * One plain sentence naming the busiest week shown (ADR 0160).
 *
 * Buckets arrive newest first, so the first bucket at the maximum is
 * the most recent of any tie — the honest name to give. This week
 * speaks in the second person, because it is the founder's own output,
 * still warm; an older week is simply named. With nothing counted,
 * the sentence stays neutral rather than crowning an empty week.
 */
function activitySummary(buckets) {
  if (!buckets.length) return "No renders in the weeks shown yet.";
  const max = Math.max(...buckets.map((b) => b.count));
  if (max <= 0) return "No renders in the weeks shown yet.";
  const top = buckets.find((b) => b.count === max);
  const noun = top.count === 1 ? "render" : "renders";
  if (top.label === "This week") {
    const span =
      buckets.length > 1
        ? ` — the busiest of the last ${WEEK_COUNT_WORDS[buckets.length] || buckets.length} weeks.`
        : ".";
    return `You made ${top.count} ${noun} this week${span}`;
  }
  return `Busiest week: ${top.label.charAt(0).toLowerCase()}${top.label.slice(1)}, with ${top.count} ${noun}.`;
}

/**
 * Renders per week: clip counts in Monday-start buckets, newest first.
 *
 * One row per week (ADR 0160), replacing the bar chart Kasra rejected
 * — a digit floating over a scaled column was neither countable nor
 * comparable at a glance. The week is now a ledger row: its label at a
 * fixed width, one dot for every render in it, and the count written
 * out as words, under one plain sentence naming the busiest week, so
 * the section reads before it is studied. The dots are decoration for
 * the eye; the label and the written count carry the fact, and they
 * are what assistive tech reads.
 */
function RenderActivity({ generations = [] }) {
  const buckets = weekBuckets(generations);
  if (!buckets.length) return null;
  const max = Math.max(...buckets.map((b) => b.count));
  return (
    <SectionCard
      title="Renders per week"
      icon={CalendarDays}
      description={activitySummary(buckets)}
      data-testid="analytics-activity"
    >
      <ul className="divide-y divide-[color:var(--hairline)]">
        {buckets.map((b, i) => (
          <li
            key={b.key}
            data-testid={`activity-row-${i}`}
            title={`${b.label}: ${b.count} ${b.count === 1 ? "render" : "renders"}`}
            className="flex items-center gap-4 py-3 first:pt-0 last:pb-0"
          >
            <span className="w-32 shrink-0 text-sm text-foreground/90">{b.label}</span>
            <span className="flex min-w-0 flex-1 flex-wrap items-center gap-1.5" aria-hidden="true">
              {Array.from({ length: b.count }, (_, d) => (
                <span
                  key={d}
                  data-testid="activity-dot"
                  className="h-2.5 w-2.5 shrink-0 rounded-full bg-[color:var(--accent)]"
                />
              ))}
            </span>
            <span className={`shrink-0 text-sm tabular-nums ${b.count === max ? "font-semibold text-foreground" : "text-muted-foreground"}`}>
              {b.count} {b.count === 1 ? "render" : "renders"}
            </span>
          </li>
        ))}
      </ul>
      <p className="text-sm text-muted-foreground">
        Same {generations.length} {generations.length === 1 ? "render" : "renders"} as above, in the {buckets.length} {buckets.length === 1 ? "week" : "weeks"} shown.
      </p>
    </SectionCard>
  );
}

/**
 * Automatic signals, counts only.
 *
 * These are factual triggers captured as the founder worked -- a template
 * swapped, a video regenerated, a clip downloaded. They are not judgments about
 * why, and pairing them with a reason would be inventing one, so this card
 * stays a count list.
 */
/** One icon per automatic trigger, so the timeline reads at a glance. */
function signalIcon(signal) {
  switch (signal) {
    case "template_changed":
      return LayoutTemplate;
    case "script_edited_heavy":
    case "script_edited_light":
      return PenLine;
    case "regenerated":
      return RotateCcw;
    case "downloaded":
      return Download;
    case "open_plan":
      return CopyPlus;
    default:
      return Activity;
  }
}

function SignalCounts({ summary, events = [], profileId = "" }) {
  const signals = summary?.top_signals || [];
  if (!signals.length) return null;
  // Rows arrive newest-first, so the first generation_id seen per signal is
  // the latest render behind it. Counts stay counts; the link just answers
  // "which clip" without inventing a mapping the backend never stored.
  const latestGenBySignal = {};
  for (const row of events) {
    const sig = row?.signal;
    const gen = row?.generation_id;
    if (sig && gen && !latestGenBySignal[sig]) latestGenBySignal[sig] = gen;
  }
  return (
    <SectionCard
      title="What happened"
      icon={Activity}
      description="Captured automatically as you worked."
      data-testid="analytics-signals"
    >
      <div className="relative">
        {/* One continuous rail behind the markers, so the list reads as a
            timeline rather than four indented rows with floating dots. */}
        <span
          aria-hidden="true"
          className="absolute inset-y-3 left-[11px] w-px bg-[color:var(--hairline)]"
        />
        <ul className="space-y-0.5">
          {signals.map((s) => {
            const genId = latestGenBySignal[s.signal];
            const href = genId
              ? `/history?profile=${encodeURIComponent(profileId)}#generation-${genId}`
              : (profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history");
            const Icon = signalIcon(s.signal);
            return (
            <li
              key={s.signal}
              className="relative flex items-center justify-between gap-4 rounded-xl py-2.5 pl-10 pr-2 transition-colors hover:bg-secondary/20"
            >
              <span
                data-testid={`analytics-signal-icon-${s.signal}`}
                aria-hidden="true"
                className="absolute left-2 top-1/2 flex h-6 w-6 -translate-y-1/2 items-center justify-center rounded-full border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)]"
              >
                  <Icon aria-hidden="true" className="h-3 w-3 text-[color:var(--brand-indigo)]" />
                </span>
                <span className="min-w-0 truncate text-sm text-foreground">{humanize(s.signal)}</span>
                <span className="flex shrink-0 items-center gap-2">
                  <FactChip>{s.count}</FactChip>
                  <Link
                    to={href}
                    data-testid={`analytics-signal-${s.signal}`}
                    title={genId ? "Open the latest render behind this signal" : "Open this app in History"}
                    className="shrink-0 text-xs text-muted-foreground underline-offset-2 transition hover:text-foreground hover:underline"
                  >
                    {genId ? "View render" : "View in History"}
                  </Link>
                </span>
              </li>
            );
          })}
        </ul>
      </div>
    </SectionCard>
  );
}

/**
 * The founder's own explanations, in the backend's fixed codes.
 *
 * These are the only judgments on this page, and every one was typed by the
 * founder — the page never infers or defaults one. The explained-of-total
 * line is what keeps a thin list honest: rework that nobody explained is a
 * different problem from a specific, repeatable complaint.
 */
function SignalReasons({ summary, events = [], profileId = "" }) {
  const reasons = summary?.top_reasons || [];
  if (!reasons.length) return null;
  const explained = summary?.explained ?? reasons.reduce((n, r) => n + (r.count || 0), 0);
  const total = summary?.total ?? 0;
  const latestGenByReason = {};
  for (const row of events) {
    const code = row?.reason;
    const gen = row?.generation_id;
    if (code && gen && !latestGenByReason[code]) latestGenByReason[code] = gen;
  }
  const historyHref = profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history";
  return (
    <SectionCard
      title="What you liked & disliked"
      icon={ListChecks}
      description="Your own codes on past rework."
      data-testid="analytics-reasons"
    >
      <ul className="divide-y divide-[color:var(--hairline)]">
        {reasons.map((r) => {
          const genId = latestGenByReason[r.reason];
          const href = genId ? `${historyHref}#generation-${genId}` : historyHref;
          return (
            <li key={r.reason} className="flex items-center justify-between gap-4 rounded-lg px-2 py-2 text-sm transition-colors hover:bg-secondary/20">
              <span className="min-w-0 truncate text-muted-foreground">{humanize(r.reason)}</span>
              <span className="flex shrink-0 items-center gap-2">
                <FactChip>{r.count}</FactChip>
                <Link
                  to={href}
                  data-testid={`analytics-reason-${r.reason}`}
                  title={genId ? "Open the latest render behind this reason" : "Open this app in History"}
                  className="shrink-0 text-xs text-muted-foreground underline-offset-2 transition hover:text-foreground hover:underline"
                >
                  {genId ? "View render" : "View in History"}
                </Link>
              </span>
            </li>
          );
        })}
      </ul>
      {total > 0 && (
        <p className="pt-2 text-sm text-muted-foreground">
          {explained} of {total} signals explained.
        </p>
      )}
    </SectionCard>
  );
}
