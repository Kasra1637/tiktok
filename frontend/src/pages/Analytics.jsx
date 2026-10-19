import { useCallback, useEffect, useState } from "react";
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
import { TrendingUp, AlertTriangle, Activity, Clapperboard, ListChecks, CalendarDays } from "lucide-react";

/**
 * Facts about your work, captured automatically as you go.
 *
 * Manual result logging is gone, so this page no longer answers "what did my
 * videos do" — nothing is typed in, nothing is scraped, and no per-template
 * learning reads from here. What remains is the automatic half, in three
 * shapes that all stay counts, never judgments about why:
 *
 * - Renders: the generation funnel (completed, failed, in progress, archived)
 *   and renders per week, both read straight off the generations list.
 * - Signals: factual triggers (a template swapped, a video regenerated, a
 *   clip downloaded) counted as they happened.
 * - Reasons: the founder's own fixed-code explanations, plus how many of the
 *   captured signals carry one — so a thin list reads as "unexplained"
 *   rather than "no problem".
 */

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
  const [profiles, setProfiles] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [feedback, setFeedback] = useState(null);
  const [generations, setGenerations] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

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
          rows.some((p) => p.id === remembered) ? remembered : rows[0]?.id || ""
        );
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const loadProfileData = useCallback(async (profileId) => {
    if (!profileId) {
      setFeedback(null);
      setGenerations(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      // Signals only: the automatic triggers captured as the founder worked.
      // Manual result logging is gone, so there is no ledger, no verdicts
      // and no per-template learning left to fetch here.
      const fb = await api.getFeedback({ brand_profile_id: profileId, limit: 500 }).catch(() => null);
      setFeedback(fb);
      // The render funnel and weekly activity read straight off the
      // generations list — the same rows History shows, so the two pages can
      // never disagree. A failure here hides those two cards only; the
      // signals card below still renders from its own fetch.
      if (typeof api.getGenerations === "function") {
        try {
          const g = await api.getGenerations({ brand_profile_id: profileId, limit: 200 });
          setGenerations(g?.generations || []);
        } catch {
          setGenerations(null);
        }
      } else {
        setGenerations(null);
      }
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfileData(selectedId);
  }, [selectedId, loadProfileData]);

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
  const hasAnything = signals.length > 0 || reasons.length > 0 || (renders?.length || 0) > 0;

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={TrendingUp}
        title="Analytics"
        description="Facts about your work, captured automatically as you go."
        data-testid="analytics-header"
        actions={
          profiles.length > 1 ? (
            <AppPicker
              profiles={profiles}
              value={selectedId}
              onChange={selectProfile}
              testId="analytics-profile-picker"
            />
          ) : null
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        <div className="surface space-y-4 rounded-2xl" aria-label="Loading analytics" data-testid="analytics-loading">
          <Skeleton className="h-8 w-48" />
          <Skeleton className="h-4 w-full" />
          <Skeleton className="h-4 w-4/5" />
        </div>
      ) : !profiles.length ? (
        !error && (
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
        )
      ) : !hasAnything ? (
        <EmptyState
          icon={Activity}
          title="Nothing captured yet"
          description="Signals appear here as you work with this app."
        />
      ) : (
        <div className="space-y-6">
          {renders !== null && renders.length > 0 && (
            <RenderFunnel generations={renders} profileId={selectedId} />
          )}
          {renders !== null && renders.length > 0 && (
            <RenderActivity generations={renders} />
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
      description="Every clip for this app, counted by status."
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
      description="Clip counts by week, newest first."
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
