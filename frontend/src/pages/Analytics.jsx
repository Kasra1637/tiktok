import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import { SectionCard } from "../components/SectionCard";
import { AppPicker } from "../components/AppPicker";
import { EmptyState } from "../components/EmptyState";
import { Skeleton } from "../components/ui/skeleton";
import { FactChip } from "../components/FactChip";
import { api, getErrorMessage } from "../lib/api";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import { verdictFor } from "../lib/feedback";
import { nextTakeFor, pickNextTake } from "../lib/nextTake";
import { useVerifiedDraftIds } from "../hooks/useVerifiedDraftIds";
import { TrendingUp, AlertTriangle, Activity, Clapperboard, ListChecks, CalendarDays } from "lucide-react";

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
        <div className="surface space-y-4 rounded-2xl" aria-label="Loading analytics" data-testid="analytics-loading">
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
              <p className="text-xs text-muted-foreground">
                Showing {renders.length} most recent renders{selectedId ? " for this app" : " across all apps, including unassigned exports"} (up to 200). Activity below uses this same set.
              </p>
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

function ClipResults({ generations, profileId, pick, draftIds }) {
  const clips = generations
    .filter((row) => row.status === "completed" || row.status === "archived")
    .sort((a, b) => (b.tiktok_views ?? -1) - (a.tiktok_views ?? -1));
  const posted = clips.filter((row) => row.tiktok_url).length;
  const counted = clips.filter((row) => row.tiktok_views != null).length;
  const rated = clips.filter((row) => verdictFor(row.verdicts, "video") !== 0).length;
  const historyHref = profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history";
  const pickNext = pick ? nextTakeFor(pick, historyHref, draftIds) : null;
  return (
    <SectionCard title="Clip results" icon={TrendingUp} description="Compare reach & your judgment before choosing another take." data-testid="analytics-results">
      <p className="text-xs text-muted-foreground">{posted} posted · {counted} with recorded views · {rated} rated</p>
      <p className="text-xs text-muted-foreground">
        Views are manually recorded snapshots of reach, not installs, revenue, or conversions. Counts may come from different posting dates; this is not a controlled comparison.
        Your vote is your judgment. Winner still means thumbs up plus a posted link, never a view threshold.
      </p>
      {pick && pickNext && (
        <div data-testid="analytics-next-take" className="rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] px-3 py-2">
          <p className="text-sm font-semibold">Suggested next take: {clipName(pick)}</p>
          <p className="text-xs text-muted-foreground">
            Posted, {pick.tiktok_views.toLocaleString("en-US")} recorded views, rated Good — the highest reach among clips you rated Good.
            Past reach does not promise the next take repeats it.{" "}
            <Link to={pickNext.to} className="text-[color:var(--brand-indigo)] hover:underline">{pickNext.label}</Link> to test another take.
          </p>
        </div>
      )}
      {clips.length === 0 ? (
        <p className="text-base text-muted-foreground">No finished clips to compare yet.</p>
      ) : (
        <div className="overflow-x-auto">
          <table className="w-full text-left text-sm">
            <caption className="sr-only">Saved clips, highest recorded views first; missing counts last.</caption>
            <thead>
              <tr className="border-b border-[color:var(--hairline)] text-xs text-muted-foreground">
                {["Clip", "Posted", "Views", "Your vote", "Next take"].map((label) => <th key={label} scope="col" className="py-2 pr-4 font-semibold">{label}</th>)}
              </tr>
            </thead>
            <tbody>
              {clips.map((row) => {
                const vote = verdictFor(row.verdicts, "video");
                const next = nextTakeFor(row, historyHref, draftIds);
                return (
                  <tr key={row.id} data-testid={`result-${row.id}`} className="border-b border-[color:var(--hairline)] align-top">
                    <th scope="row" className="min-w-[180px] py-3 pr-4 font-normal">
                      <Link to={`${historyHref}#generation-${row.id}`} className="font-semibold text-[color:var(--brand-indigo)] hover:underline">
                        {clipName(row)}
                      </Link>
                      <span className="mt-1 block text-xs text-muted-foreground">{row.brand_name || "Unassigned app"}{row.objective ? ` · ${humanize(row.objective)}` : ""}</span>
                    </th>
                    <td className="py-3 pr-4 text-xs">
                      {row.tiktok_url ? <a href={row.tiktok_url} target="_blank" rel="noreferrer" className="text-[color:var(--brand-indigo)] hover:underline">Posted ↗</a> : "Not posted"}
                    </td>
                    <td className="whitespace-nowrap py-3 pr-4 font-mono text-xs">{row.tiktok_views == null ? "Not recorded" : row.tiktok_views.toLocaleString("en-US")}</td>
                    <td className="whitespace-nowrap py-3 pr-4 text-xs">{vote > 0 ? "Good" : vote < 0 ? "Not good" : "Not rated"}</td>
                    <td className="py-3 text-xs">
                      <Link to={next.to} className="text-[color:var(--brand-indigo)] hover:underline">{next.label}</Link>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      )}
      <p className="text-xs text-muted-foreground">Compare a high-reach clip you rated Good with the others, then reuse its draft to test another take. <Link to={historyHref} className="text-[color:var(--brand-indigo)] hover:underline">Record or update results in History</Link>.</p>
    </SectionCard>
  );
}

/**
 * The render funnel: every generation for this app, counted by status.
 *
 * Same rows History shows, so the counts here and the rows there can never
 * disagree. Archived renders keep their own row rather than folding into
 * completed — an archived clip was finished, but it is not on the shelf
 * anymore, and merging the two would overstate what is usable.
 */
function RenderFunnel({ generations = [], profileId = "" }) {
  const completed = generations.filter((g) => g?.status === "completed").length;
  const failed = generations.filter((g) => g?.status === "failed").length;
  const archived = generations.filter((g) => g?.status === "archived").length;
  const inProgress = generations.length - completed - failed - archived;
  const historyHref = profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history";
  const rows = [
    { label: "Completed", count: completed },
    { label: "Failed", count: failed },
    { label: "In progress", count: inProgress },
    { label: "Archived", count: archived },
  ];
  return (
    <SectionCard
      title="Renders"
      icon={Clapperboard}
      description="Loaded renders, counted by status."
      data-testid="analytics-funnel"
    >
      <ul className="divide-y divide-[color:var(--hairline)]">
        {rows.map((r) => (
          <li key={r.label} className="flex items-center justify-between gap-4 py-2 text-sm">
            <span className="min-w-0 truncate text-muted-foreground">{r.label}</span>
            <FactChip>{r.count}</FactChip>
          </li>
        ))}
      </ul>
      <p className="pt-2 text-xs text-muted-foreground">
        {generations.length} total ·{" "}
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
 * without a single render ever disappearing into a zero axis.
 */
function RenderActivity({ generations = [] }) {
  const buckets = weekBuckets(generations);
  if (!buckets.length) return null;
  const max = Math.max(...buckets.map((b) => b.count));
  return (
    <SectionCard
      title="Renders per week"
      icon={CalendarDays}
      description="Loaded render counts by week, newest first."
      data-testid="analytics-activity"
    >
      <ul className="space-y-2">
        {buckets.map((b) => (
          <li key={b.key} className="flex items-center gap-3 text-sm">
            <span className="w-28 shrink-0 truncate text-muted-foreground">{b.label}</span>
            <span className="flex h-2 min-w-0 flex-1 overflow-hidden rounded-full bg-[color:var(--hairline)]" aria-hidden="true">
              <span
                className="rounded-full bg-[color:var(--accent)]"
                style={{ width: `${max ? Math.max(6, Math.round((b.count / max) * 100)) : 0}%` }}
              />
            </span>
            <FactChip>{b.count}</FactChip>
          </li>
        ))}
      </ul>
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
      <ul className="divide-y divide-[color:var(--hairline)]">
        {signals.map((s) => {
          const genId = latestGenBySignal[s.signal];
          const href = genId
            ? `/history?profile=${encodeURIComponent(profileId)}#generation-${genId}`
            : (profileId ? `/history?profile=${encodeURIComponent(profileId)}` : "/history");
          return (
            <li key={s.signal} className="flex items-center justify-between gap-4 py-2 text-sm">
              <span className="min-w-0 truncate text-muted-foreground">{humanize(s.signal)}</span>
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
          <li key={r.reason} className="flex items-center justify-between gap-4 py-2 text-sm">
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
