import { useEffect, useId, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import { SectionCard } from "../components/SectionCard";
import { AppPicker } from "../components/AppPicker";
import { EmptyState } from "../components/EmptyState";
import { Skeleton } from "../components/ui/skeleton";
import { FactChip, FactList } from "../components/FactChip";
import { api, getErrorMessage } from "../lib/api";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import { verdictFor } from "../lib/feedback";
import { isWinnerRow, nextTakeFor, pickNextTake } from "../lib/nextTake";
import { useVerifiedDraftIds } from "../hooks/useVerifiedDraftIds";
import { TrendingUp, AlertTriangle, Activity, Clapperboard, ListChecks, CalendarDays, ThumbsUp, ThumbsDown, Minus, Crown, Download, RotateCcw, LayoutTemplate, PenLine, CopyPlus, ChevronDown, ChevronRight } from "lucide-react";

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

export default function Analytics() {
  const [profiles, setProfiles] = useState(null);
  const [selectedId, setSelectedId] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [generations, setGenerations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retryVersion, setRetryVersion] = useState(0);

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
    const scope = selectedId ? { brand_profile_id: selectedId } : {};
    Promise.all([
      api.getFeedback({ ...scope, limit: 500 }),
      api.getGenerationHistory({ ...scope, limit: 200 }),
    ]).then(([fb, history]) => {
      if (cancelled) return;
      setFeedback(fb);
      setGenerations(history.generations || []);
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
        description="Compare posted clips, recorded views & your own ratings."
        data-testid="analytics-header"
        actions={
          profiles?.length > 0 ? (
            <AppPicker
              profiles={profiles}
              value={selectedId}
              onChange={selectProfile}
              allLabel="All apps"
              testId="analytics-profile-picker"
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

      {loading ? (
        <div className="surface space-y-4" aria-label="Loading analytics" data-testid="analytics-loading">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ) : error ? null : !profiles?.length && !hasAnything ? (
          <EmptyState
            icon={TrendingUp}
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
          icon={Activity}
          title="Nothing captured yet"
          description="Create a clip, then add its posted link, views, and your vote in History."
          action={
            <Button variant="accent" asChild>
              <Link to={selectedId ? `/create?profile=${encodeURIComponent(selectedId)}` : "/create"}>Create Video</Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-6">
          {renders?.length > 0 && (
            <>
              <ClipResults generations={renders} profileId={selectedId} pick={takePick} draftIds={draftIds} />
            </>
          )}
          {renders !== null && renders.length > 0 && (
            <RenderFunnel generations={renders} profileId={selectedId} />
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
            <p className="text-xs text-muted-foreground">Feedback below uses up to 500 most recent saved events{selectedId ? " for this app" : " across all apps"}. Repeated ratings are events, not unique clips or measured outcomes.</p>
          )}
          {signals.length > 0 && (
            <SignalCounts summary={feedback.summary} events={feedback.feedback || []} profileId={selectedId} />
          )}
          {reasons.length > 0 && (
            <SignalReasons summary={feedback.summary} />
          )}
        </div>
      )}
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

/** A short, local date for the renders inside a status group. */
function shortDate(value) {
  const t = Date.parse(value);
  if (Number.isNaN(t)) return "";
  return new Date(t).toLocaleDateString(undefined, { month: "short", day: "numeric" });
}

function ClipResults({ generations, profileId, pick, draftIds }) {
  const clips = generations
    .filter((row) => row.status === "completed" || row.status === "archived")
    .sort((a, b) => (b.tiktok_views ?? -1) - (a.tiktok_views ?? -1));
  const [expanded, setExpanded] = useState(false);
  // The card opens on its first three rows: enough to show the ranking and
  // the scale between them, with the full ledger a deliberate second step.
  const [open, setOpen] = useState(true);
  const panelId = useId();
  const visible = expanded ? clips : clips.slice(0, LEADERBOARD_PAGE_SIZE);
  const posted = clips.filter((row) => row.tiktok_url).length;
  const counted = clips.filter((row) => row.tiktok_views != null).length;
  const rated = clips.filter((row) => verdictFor(row.verdicts, "video") !== 0).length;
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
      actions={
        <Button
          variant="ghost"
          size="sm"
          aria-expanded={open}
          aria-controls={open ? panelId : undefined}
          onClick={() => setOpen((current) => !current)}
          data-testid="analytics-results-toggle"
        >
          <ChevronDown
            aria-hidden="true"
            className={`transition-transform duration-200 ${open ? "rotate-180" : ""}`}
          />
          <span>{open ? "Collapse" : "Expand"}</span>
        </Button>
      }
    >
      <FactList aria-label="Clip totals">
        <FactChip>{posted} posted</FactChip>
        <FactChip>{counted} with recorded views</FactChip>
        <FactChip>{rated} rated</FactChip>
      </FactList>
      {open && (
        <div id={panelId} className="space-y-5">
          <details className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/20 px-3 py-1.5 transition-colors hover:border-[color:var(--hairline-strong)]">
            <summary className="flex cursor-pointer list-none items-center justify-between gap-2 py-1 text-xs text-muted-foreground [&::-webkit-details-marker]:hidden">
              <span>Why these numbers</span>
              <ChevronDown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-open:rotate-180" />
            </summary>
            <div className="space-y-2 pb-2 text-xs text-muted-foreground">
              <p>
                Views are manually recorded snapshots of reach, not installs, revenue, or conversions. Counts may come from different posting dates; this is not a controlled comparison.
                Your vote is your judgment. Winner still means thumbs up plus a posted link, never a view threshold.
              </p>
              <p>Compare a high-reach clip you rated Good with the others, then reuse its draft to test another take. <Link to={historyHref} className="text-[color:var(--brand-indigo)] hover:underline">Record or update results in History</Link>.</p>
            </div>
          </details>
          {pick && pickNext && (
            <div data-testid="analytics-next-take" className="flex items-start gap-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] px-4 py-3">
              <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[color:var(--indigo-35)] bg-[color:var(--indigo-10)]">
                <ThumbsUp aria-hidden="true" className="h-3 w-3 text-[color:var(--brand-indigo)]" />
              </span>
              <div className="min-w-0 space-y-1">
              <p className="text-sm font-semibold text-foreground">Suggested next take: {clipName(pick)}</p>
              <p className="text-xs text-muted-foreground">
                Posted, {pick.tiktok_views.toLocaleString("en-US")} recorded views, rated Good — the highest reach among clips you rated Good.
                Past reach does not promise the next take repeats it.{" "}
                <Link to={pickNext.to} className="text-[color:var(--brand-indigo)] hover:underline">{pickNext.label}</Link> to test another take.
              </p>
              </div>
            </div>
          )}
          {clips.length === 0 ? (
            <p className="text-base text-muted-foreground">No finished clips to compare yet.</p>
          ) : (
            <div className="overflow-x-auto rounded-xl border border-[color:var(--hairline)] bg-secondary/10">
              <table className="w-full text-left text-sm">
                <caption className="sr-only">Saved clips, highest recorded views first; missing counts last.</caption>
                <thead>
                  <tr className="bg-secondary/20 text-xs text-muted-foreground">
                    {["Rank", "Clip", "Posted", "Views", "Your vote", "Next take"].map((label) => <th key={label} scope="col" className="whitespace-nowrap px-3 py-2 font-semibold">{label}</th>)}
                  </tr>
                </thead>
                <tbody>
                  {visible.map((row, index) => {
                    const vote = verdictFor(row.verdicts, "video");
                    const next = nextTakeFor(row, historyHref, draftIds);
                    const winner = isWinnerRow(row);
                    return (
                      <tr key={row.id} data-testid={`result-${row.id}`} className="border-t border-[color:var(--hairline)] align-top transition-colors first:border-t-0 hover:bg-secondary/20">
                        <td data-testid={`result-rank-${row.id}`} className="px-3 py-3 text-xs text-muted-foreground">
                          <span className="inline-flex items-center gap-1.5">
                            <span className="flex h-6 w-6 items-center justify-center rounded-full border border-[color:var(--hairline-strong)] bg-secondary/40 font-mono tabular-nums">{index + 1}</span>
                            {winner && <Crown aria-hidden="true" className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />}
                          </span>
                        </td>
                        <th scope="row" className="min-w-[180px] px-3 py-3 font-normal">
                          <Link to={`${historyHref}#generation-${row.id}`} className="font-semibold text-[color:var(--brand-indigo)] hover:underline">
                            {clipName(row)}
                          </Link>
                          <span className="mt-1 block text-xs text-muted-foreground">{row.brand_name || "Unassigned app"}{row.objective ? ` · ${humanize(row.objective)}` : ""}</span>
                        </th>
                        <td className="whitespace-nowrap px-3 py-3 text-xs">
                          {row.tiktok_url ? (
                            <a href={row.tiktok_url} target="_blank" rel="noreferrer" className="inline-flex items-center gap-1.5 text-[color:var(--brand-indigo)] hover:underline">
                              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-[color:var(--brand-indigo)]" />
                              Posted ↗
                            </a>
                          ) : (
                            <span className="inline-flex items-center gap-1.5 text-muted-foreground">
                              <span aria-hidden="true" className="h-1.5 w-1.5 rounded-full bg-muted-foreground/30" />
                              Not posted
                            </span>
                          )}
                        </td>
                        <td className="px-3 py-3 text-xs">
                          {row.tiktok_views == null ? (
                            "Not recorded"
                          ) : (
                            <span className="flex items-center gap-2">
                              <span className="h-2 w-24 shrink-0 overflow-hidden rounded-full bg-secondary/50" aria-hidden="true">
                                <span data-testid={`result-views-bar-${row.id}`} className="block h-full rounded-full bg-[color:var(--accent)] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.18)]" style={{ width: barWidth(row.tiktok_views) }} />
                              </span>
                              <span className="whitespace-nowrap font-mono tabular-nums">{row.tiktok_views.toLocaleString("en-US")}</span>
                            </span>
                          )}
                        </td>
                        <td data-testid={`result-vote-${row.id}`} className="whitespace-nowrap px-3 py-3 text-xs">
                          <span className={`inline-flex items-center gap-1.5 rounded-full border px-2 py-0.5 ${vote > 0 ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-10)] text-foreground" : "border-[color:var(--hairline)] bg-secondary/20 text-muted-foreground"}`}>
                            {vote > 0 ? (
                              <ThumbsUp aria-hidden="true" className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
                            ) : vote < 0 ? (
                              <ThumbsDown aria-hidden="true" className="h-3.5 w-3.5 text-muted-foreground" />
                            ) : (
                              <Minus aria-hidden="true" className="h-3.5 w-3.5 text-muted-foreground" />
                            )}
                            {vote > 0 ? "Good" : vote < 0 ? "Not good" : "Not rated"}
                          </span>
                        </td>
                        <td className="px-3 py-3 text-xs">
                          <Link to={next.to} className="whitespace-nowrap text-[color:var(--brand-indigo)] hover:underline">{next.label}</Link>
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
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
          <p className="border-t border-[color:var(--hairline)] pt-3 text-xs text-muted-foreground">
            Showing {generations.length} most recent renders{profileId ? " for this app" : " across all apps, including unassigned exports"} (up to 200). Activity below uses this same set.
          </p>
        </div>
      )}
    </SectionCard>
  );
}

/** One render inside a status group: its identity and landing day, both
 * linking to the History row that owns it. */
function StatusRenderRow({ row, historyHref }) {
  const date = shortDate(row.created_at);
  return (
    <li className="flex items-baseline justify-between gap-3 rounded-lg px-2 py-1.5 transition-colors hover:bg-secondary/20">
      <Link
        to={`${historyHref}#generation-${row.id}`}
        className="min-w-0 truncate text-sm text-[color:var(--brand-indigo)] hover:underline"
      >
        {clipName(row)}
      </Link>
      {date && <span className="shrink-0 font-mono text-xs tabular-nums text-muted-foreground">{date}</span>}
    </li>
  );
}

// How many renders a status shows before pointing at History for the rest.
const STATUS_LIST_LIMIT = 6;

/**
 * The render funnel: every generation for this app, counted by status and
 * openable to the renders behind each count.
 *
 * Same rows History shows, so the counts here and the rows there can never
 * disagree. Archived renders keep their own group rather than folding into
 * completed — an archived clip was finished, but it is not on the shelf
 * anymore, and merging the two would overstate what is usable.
 *
 * The first status with rows opens on arrival: a count you can expand is only
 * worth reading if the expansion is visible, and one group open keeps the card
 * shorter than the four lists it stands for.
 */
function RenderFunnel({ generations = [], profileId = "" }) {
  const byStatus = {
    completed: generations.filter((g) => g?.status === "completed"),
    failed: generations.filter((g) => g?.status === "failed"),
    archived: generations.filter((g) => g?.status === "archived"),
    active: generations.filter((g) => !["completed", "failed", "archived"].includes(g?.status)),
  };
  const groups = [
    { key: "completed", label: "Completed" },
    { key: "failed", label: "Failed" },
    { key: "active", label: "In progress" },
    { key: "archived", label: "Archived" },
  ];
  const [openStatus, setOpenStatus] = useState(
    () => groups.find((group) => byStatus[group.key].length)?.key || null
  );
  const historyHref = profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history";
  return (
    <SectionCard
      title="Renders"
      icon={Clapperboard}
      description="Open a status to see the renders behind it."
      data-testid="analytics-funnel"
    >
      <ul className="divide-y divide-[color:var(--hairline)]">
        {groups.map((group) => {
          const rows = byStatus[group.key];
          if (!rows.length) {
            return (
              <li key={group.key} data-testid={`analytics-status-${group.key}`} className="flex items-center justify-between gap-4 rounded-lg px-2 py-2 text-sm">
                <span className="min-w-0 truncate text-muted-foreground">{group.label}</span>
                <FactChip>0</FactChip>
              </li>
            );
          }
          const isOpen = openStatus === group.key;
          const panelId = `analytics-status-panel-${group.key}`;
          const shown = rows.slice(0, STATUS_LIST_LIMIT);
          return (
            <li key={group.key} data-testid={`analytics-status-${group.key}`}>
              <button
                type="button"
                aria-expanded={isOpen}
                aria-controls={isOpen ? panelId : undefined}
                onClick={() => setOpenStatus((current) => (current === group.key ? null : group.key))}
                data-testid={`analytics-status-toggle-${group.key}`}
                className="focus-ring flex w-full items-center justify-between gap-4 rounded-xl px-2 py-2 text-left text-sm transition-colors hover:bg-secondary/20 hover:text-foreground"
              >
                <span className="flex min-w-0 items-center gap-2.5">
                  <span aria-hidden="true" className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full border border-[color:var(--hairline)] bg-secondary/30">
                    <ChevronRight
                      className={`h-3.5 w-3.5 text-muted-foreground transition-transform duration-150 ${isOpen ? "rotate-90" : ""}`}
                    />
                  </span>
                  <span className="truncate text-muted-foreground">{group.label}</span>
                </span>
                <FactChip>{rows.length}</FactChip>
              </button>
              {isOpen && (
                <div id={panelId} className="ml-3 space-y-1 border-l border-[color:var(--hairline)] py-1 pl-3">
                  <ul className="space-y-0.5 text-xs">
                    {shown.map((row) => <StatusRenderRow key={row.id} row={row} historyHref={historyHref} />)}
                  </ul>
                  {rows.length > shown.length && (
                    <Link
                      to={historyHref}
                      className="inline-block px-2 text-xs text-muted-foreground underline-offset-2 transition hover:text-foreground hover:underline"
                    >
                      +{rows.length - shown.length} more in History
                    </Link>
                  )}
                </div>
              )}
            </li>
          );
        })}
      </ul>
      <p className="flex items-center justify-between gap-4 border-t border-[color:var(--hairline)] pt-3 text-xs text-muted-foreground">
        <span>{generations.length} total</span>
        <Link
          to={historyHref}
          data-testid="analytics-funnel-history"
          title="Open this app in History"
          className="underline-offset-2 transition hover:text-foreground hover:underline"
        >
          View in History
        </Link>
      </p>
    </SectionCard>
  );
}

/**
 * Renders per week: clip counts in Monday-start buckets, newest first.
 *
 * Bars are scaled to the busiest week shown, so a quiet week reads quiet
 * without a single render ever disappearing into a zero axis. Each bar sits
 * in a hairline well, the same inset the app uses for a recessed surface: the
 * column height is the data, the well is the scale it is read against.
 */
function RenderActivity({ generations = [] }) {
  const buckets = weekBuckets(generations);
  if (!buckets.length) return null;
  const max = Math.max(...buckets.map((b) => b.count));
  const shown = buckets.reduce((sum, b) => sum + b.count, 0);
  return (
    <SectionCard
      title="Renders per week"
      icon={CalendarDays}
      description="Loaded render counts by week, newest first."
      data-testid="analytics-activity"
    >
      <ul className="flex items-end gap-3 sm:gap-4">
        {buckets.map((b) => (
        <li
          key={b.key}
          title={`${b.label}: ${b.count} ${b.count === 1 ? "render" : "renders"}`}
          className="group flex min-w-0 flex-1 flex-col items-center gap-2"
        >
          <FactChip className={b.count === max ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-10)] text-foreground" : undefined}>{b.count}</FactChip>
          <span
            className="flex h-24 w-full max-w-20 items-end justify-center overflow-hidden rounded-xl border border-[color:var(--hairline)] bg-secondary/25 transition-colors group-hover:border-[color:var(--hairline-strong)]"
            aria-hidden="true"
          >
              <span
                data-testid="activity-bar"
                className="block w-full rounded-t-md bg-[color:var(--accent)] shadow-[inset_0_1px_0_0_rgba(255,255,255,0.18)]"
                style={{ height: `${max ? Math.max(6, Math.round((b.count / max) * 100)) : 0}%` }}
              />
            </span>
            <span className="w-full truncate text-center text-xs text-muted-foreground">{b.label}</span>
          </li>
        ))}
      </ul>
      <p className="text-xs text-muted-foreground">
        {shown} {shown === 1 ? "render" : "renders"} across the {buckets.length} {buckets.length === 1 ? "week" : "weeks"} shown.
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
function SignalReasons({ summary }) {
  const reasons = summary?.top_reasons || [];
  if (!reasons.length) return null;
  const explained = summary?.explained ?? reasons.reduce((n, r) => n + (r.count || 0), 0);
  const total = summary?.total ?? 0;
  return (
    <SectionCard
      title="Reasons you gave"
      icon={ListChecks}
      description="Your own codes on past rework."
      data-testid="analytics-reasons"
    >
      <ul className="divide-y divide-[color:var(--hairline)]">
        {reasons.map((r) => (
          <li key={r.reason} className="flex items-center justify-between gap-4 rounded-lg px-2 py-2 text-sm transition-colors hover:bg-secondary/20">
            <span className="min-w-0 truncate text-muted-foreground">{humanize(r.reason)}</span>
            <FactChip>{r.count}</FactChip>
          </li>
        ))}
      </ul>
      {total > 0 && (
        <p className="pt-2 text-xs text-muted-foreground">
          {explained} of {total} signals explained.
        </p>
      )}
    </SectionCard>
  );
}
