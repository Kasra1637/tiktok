import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { toast } from "sonner";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";
import { SectionCard } from "../components/SectionCard";
import { FactChip, FactList } from "../components/FactChip";
import WhatWorksCard from "../components/WhatWorksCard";
import { api, getErrorMessage } from "../lib/api";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import { TrendingUp, Loader2, AlertTriangle, Info, CircleCheck, CircleX, Copy } from "lucide-react";

/**
 * Recorded results, what the loop learned, and why logging pays off.
 *
 * The old Analytics page answered "what did this operator spend", which is why
 * it was retired: the product does not meter cost and that number was not a
 * decision a founder made. This one answers a different question the retired
 * page never asked — what did my own videos actually do, and what has the app
 * learned from that. Everything here is read from data the founder already
 * logged by hand, so the page carries no new instrumentation and needs no
 * backend work.
 *
 * Every figure is manual and unverified. There is no TikTok connection, nothing
 * is scraped, and no number here is presented as platform-verified. The page
 * says so once, at the bottom, rather than qualifying every row with it.
 */

/** A recorded verdict, in the words the founder chose it with. */
const VERDICT_COPY = {
  successful: { label: "Worked", tone: "text-success", Icon: CircleCheck },
  unsuccessful: { label: "Did not work", tone: "text-destructive", Icon: CircleX },
};

/** Same vocabulary helper History uses, so a code reads identically on both. */
function humanize(value) {
  return String(value || "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * One ratio the platforms reward, computed only over a real denominator.
 *
 * Views are what the founder typed in and can be 0, null, or missing. A rate
 * over nothing is not 0% — rendering it as a number would turn "no data" into
 * "bad data", which is exactly the direction a low-views keeper must not read.
 */
function rateText(part, whole) {
  const w = Number(whole);
  if (!Number.isFinite(w) || w <= 0) return "—";
  return `${(((Number(part) || 0) / w) * 100).toFixed(1)}%`;
}

/** Short counts for lead lines and the copied summary: 2400 -> "2.4k". */
function compact(n) {
  const v = Number(n) || 0;
  if (v < 1000) return String(Math.round(v));
  const k = v / 1000;
  return `${k >= 100 ? Math.round(k) : k.toFixed(1).replace(/\.0$/, "")}k`;
}

/**
 * How long a finished clip has waited to be logged.
 *
 * Completed rows stay listed as nudges until the founder records them, and a
 * three-week-old nudge is a different urgency from a three-hour-old one. The
 * input prefers completed_at (when the clip was actually produced) and falls
 * back to created_at.
 */
function finishedAgeLabel(iso) {
  const t = new Date(iso).getTime();
  if (!Number.isFinite(t)) return "";
  const days = Math.floor((Date.now() - t) / 86400000);
  if (days < 1) return "finished today";
  if (days === 1) return "finished yesterday";
  if (days < 7) return `finished ${days}d ago`;
  const weeks = Math.floor(days / 7);
  if (weeks < 5) return `finished ${weeks}w ago`;
  return `finished ${new Date(t).toLocaleDateString()}`;
}

/** Median, because one 500k outlier must not be allowed to define a bucket. */
function median(nums) {
  const xs = (nums || []).filter((n) => Number.isFinite(n)).sort((a, b) => a - b);
  if (!xs.length) return null;
  const mid = Math.floor(xs.length / 2);
  return xs.length % 2 ? xs[mid] : Math.round((xs[mid - 1] + xs[mid]) / 2);
}

/**
 * How many logged videos a bucket needs before it may be compared.
 *
 * Named, not a bare literal, because this number is a judgment call rather
 * than a fact: it is the smallest n at which a median of logged views starts
 * to say anything, and raising it later must not require finding every place
 * a "3" happens to appear.
 */
const COMPARABLE_AT = 3;

/**
 * Group recorded rows by a free-form dimension (objective, audience).
 *
 * Buckets with zero view counts are shown but refuse to produce a median: a
 * bucket whose rows carry no views has nothing to rank on, and inventing a
 * zero median would read as a measured failure rather than missing data.
 */
function bucketDimension(rows, key) {
  const map = new Map();
  for (const row of rows || []) {
    const raw = row?.[key];
    const label = typeof raw === "string" && raw.trim() ? raw.trim() : "(none)";
    if (!map.has(label)) map.set(label, []);
    map.get(label).push(row);
  }
  return [...map.entries()].map(([label, members]) => {
    const counted = members
      .map((m) => Number(m.performance?.views))
      .filter((v) => Number.isFinite(v) && v > 0);
    return {
      label,
      n: members.length,
      views: counted.reduce((a, b) => a + b, 0),
      med: median(counted),
      comparable: members.length >= COMPARABLE_AT,
    };
  });
}

/**
 * The bucket a breakdown may name as leading: comparable, with view counts,
 * and the highest median. Anything else is a candidate the data cannot vouch
 * for, so a null return means the card shows counts and waits.
 */
function leadBucket(buckets) {
  const pool = (buckets || []).filter((b) => b.comparable && b.med != null);
  if (!pool.length) return null;
  return pool.reduce((a, b) => (b.med > a.med ? b : a));
}

export default function Analytics() {
  const [profiles, setProfiles] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [whatWorks, setWhatWorks] = useState(null);
  const [generations, setGenerations] = useState([]);
  const [feedback, setFeedback] = useState(null);
  // Objective outcome copy ("Gets them naming the problem out loud") lives in
  // /templates/facets and is fetched once: it is global, not per profile, and
  // the breakdown must still render when it fails, falling back to labels.
  const [facets, setFacets] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);

  // The profile list first, because it decides what everything else is scoped
  // to. A remembered selection is only honoured when it still names a profile
  // that exists -- an id from a deleted app would otherwise pin the page to an
  // empty ledger forever.
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
      setWhatWorks(null);
      setGenerations([]);
      setFeedback(null);
      setLoading(false);
      return;
    }
    setLoading(true);
    setError(null);
    try {
      const [works, history, fb] = await Promise.all([
        api.getProfileWhatWorks(profileId).catch(() => null),
        api.getGenerationHistory({ brand_profile_id: profileId, limit: 200 }).catch(() => ({ generations: [] })),
        api.getFeedback({ brand_profile_id: profileId, limit: 500 }).catch(() => null),
      ]);
      setWhatWorks(works);
      setGenerations(history.generations || []);
      setFeedback(fb);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    loadProfileData(selectedId);
  }, [selectedId, loadProfileData]);

  useEffect(() => {
    api.getTemplateFacets().then(setFacets).catch(() => setFacets(null));
  }, []);

  const selectProfile = (id) => {
    setSelectedId(id);
    // Persisted so returning here is one click, not a re-pick. Same key the
    // rest of the app uses, so an app chosen here is the app the Asset Library
    // opens on.
    rememberCurrentAppId(id);
  };

  // The learning leaves the browser: one plain block with the ledger, the
  // verdicts and the breakdowns, for a doc or a collaborator. Built from the
  // same derived structures the cards render, so the copy can never disagree
  // with the page.
  const copySummary = async () => {
    const profile = profiles.find((p) => p.id === selectedId);
    const text = buildAnalyticsSummaryText({
      profileName: profile?.brand_name || "Untitled app",
      generatedAt: new Date().toLocaleDateString(),
      recorded,
      tallies,
      whatWorks,
      objectiveOutcomes: facets?.objective_outcomes || null,
      signals: feedback?.summary?.top_signals || [],
    });
    try {
      if (navigator?.clipboard?.writeText) {
        await navigator.clipboard.writeText(text);
      } else {
        // Older contexts with no async clipboard: a transient textarea is the
        // only copy path that works everywhere.
        const ta = document.createElement("textarea");
        ta.value = text;
        document.body.appendChild(ta);
        ta.select();
        document.execCommand("copy");
        document.body.removeChild(ta);
      }
      toast.success("Summary copied.");
    } catch {
      toast.error("Could not copy the summary.");
    }
  };

  // Completed rows only. A failed render has nothing to record results against,
  // and listing it here would invite the founder to enter numbers for a clip
  // that was never produced.
  const ledger = useMemo(
    () => generations.filter((g) => g.status === "completed"),
    [generations]
  );
  const recorded = useMemo(() => ledger.filter((g) => g.performance), [ledger]);
  // Nudges run oldest first: the clip that has waited longest to be logged is
  // the one the loop is losing first, so it goes on top rather than wherever
  // creation order happened to leave it.
  const unrecorded = useMemo(
    () =>
      ledger
        .filter((g) => !g.performance)
        .sort(
          (a, b) =>
            new Date(a.completed_at || a.created_at).getTime() -
            new Date(b.completed_at || b.created_at).getTime()
        ),
    [ledger]
  );

  // Views over time, logged videos only. A row with no view count carries no
  // trend evidence, so it is skipped rather than plotted as a zero that would
  // read as a collapse. Renders nothing when there is nothing to plot.
  const trendPoints = useMemo(
    () =>
      recorded
        .map((r) => ({
          t: new Date(r.performance?.created_at || r.created_at).getTime(),
          views: Number(r.performance?.views),
        }))
        .filter((p) => Number.isFinite(p.t) && Number.isFinite(p.views) && p.views > 0)
        .sort((a, b) => a.t - b.t),
    [recorded]
  );

  const objectiveBuckets = useMemo(() => bucketDimension(recorded, "objective"), [recorded]);
  const audienceBuckets = useMemo(() => bucketDimension(recorded, "audience"), [recorded]);

  const tallies = useMemo(
  () => tallyVerdicts(recorded, feedback?.summary),
  [recorded, feedback]
);

  if (loading && !ledger.length) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading results...
      </p>
    );
  }

  if (error && !profiles.length) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  return (
    <div className="mx-auto w-full max-w-5xl space-y-6">
      {/* The header carries the testid rather than PageHeader: that component takes a
        fixed prop list and drops anything else, so a testid passed to it would
        silently never appear. */}
      <div data-testid="analytics-header">
        <PageHeader
          icon={TrendingUp}
          title="Analytics"
          description="Every result you have logged, and what the app has learned from it."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {selectedId ? (
                <Button
                  variant="secondary"
                  size="sm"
                  onClick={copySummary}
                  data-testid="analytics-copy-summary"
                  title="Copy this app's results as plain text"
                >
                  <Copy className="h-3.5 w-3.5" /> Copy summary
                </Button>
              ) : null}
              {profiles.length > 1 ? (
                <select
                  value={selectedId}
                  onChange={(e) => selectProfile(e.target.value)}
                  aria-label="Select App Profile"
                  data-testid="analytics-profile-picker"
                  className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
                >
                  {profiles.map((p) => (
                    <option key={p.id} value={p.id}>
                      {p.brand_name || "Untitled app"}
                    </option>
                  ))}
                </select>
              ) : null}
            </div>
          }
        />
      </div>

      {!profiles.length && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription className="flex flex-col justify-between gap-3 sm:flex-row sm:items-center">
            <span className="text-muted-foreground">
              Create an App Profile and render a video to start recording results.
            </span>
            <Button variant="secondary" size="sm" className="shrink-0" asChild>
              <Link to="/brand">Open App Profile</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {selectedId && <WhatWorksCard data={whatWorks} />}

      {/* The one question the ledger alone cannot answer: is this app getting
          better or worse. Chronological logged views, nothing invented — a row
          with no view count is skipped, not plotted as a zero. */}
      {selectedId && <TrendSpark points={trendPoints} />}

      {/* The ledger is the page. What Has Worked Here is the aggregate of these
          rows; the rows are the evidence, and each one links to the History row
          that owns the clip so the founder can act on it without hunting. */}
      <SectionCard
        title="Recorded results"
        className="space-y-3"
        data-testid="analytics-ledger"
      >
        {!ledger.length ? (
          <p className="text-sm text-muted-foreground">
            No finished videos for this app yet. Every video you complete appears here,
            recorded or not.
          </p>
        ) : (
          <div className="space-y-2">
            {recorded.map((row) => (
              <LedgerRow key={row.id} row={row} />
            ))}
            {/* Unrecorded completions are listed rather than hidden: a finished
                clip with no numbers is a video the loop is learning nothing from,
                and that is only obvious if it is visible. Compact, because this
                list can be long and none of these rows carries a result yet. */}
            {unrecorded.map((row) => (
              <LedgerRow key={row.id} row={row} nudge />
            ))}
          </div>
        )}
      </SectionCard>

      {selectedId && (
        <VerdictTallies tallies={tallies} total={recorded.length} />
      )}

      {/* Which video goal to pick next, read off the founder's own logged
          results. Counts are always shown; a comparison only appears once a
          bucket clears COMPARABLE_AT. Descriptions, never promises — the same
          rule the outcome copy follows. */}
      {selectedId && (
        <DimensionBreakdown
          title="By objective"
          testid="analytics-by-objective"
          buckets={objectiveBuckets}
          formatKey={humanize}
          noneLabel="No objective set"
          copy={facets?.objective_outcomes || null}
        />
      )}
      {selectedId && (
        <DimensionBreakdown
          title="By audience"
          testid="analytics-by-audience"
          buckets={audienceBuckets}
          formatKey={(v) => v}
          noneLabel="No audience set"
          copy={null}
        />
      )}

      {selectedId && (
        <SignalCounts summary={feedback?.summary} />
      )}

      <p className="text-xs text-muted-foreground">
        No TikTok account is connected and no platform data is scraped. Every figure here
        is what you typed in, and is never presented as verified. Logged results feed your
        next strategy.
      </p>
    </div>
  );
}

/**
 * One recorded video: the five numbers, the verdict, and the way back to it.
 *
 * Fixed number columns rather than a flex row of spans, so two videos can be
 * compared by scanning down instead of by reading both sentences. The verdict
 * sits beside them as the thing the whole row exists to state.
 */
function LedgerRow({ row, nudge = false }) {
  const perf = row.performance;
  const verdict = perf?.outcome ? VERDICT_COPY[perf.outcome] : null;

  if (nudge) {
    const age = finishedAgeLabel(row.completed_at || row.created_at);
    return (
      <div
        className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-[color:var(--hairline)] px-3 py-2"
        data-testid={`analytics-nudge-${row.id}`}
      >
        <span className="min-w-0 truncate text-sm text-muted-foreground">
          {row.hook_line || row.template_id || "Finished video"} — nothing logged yet
          {age ? ` · ${age}` : ""}
        </span>
        {/* `?generation=` is the same deep link History reads to open the record
            form, so this lands on the form rather than on the row. */}
        <Button variant="ghost" size="sm" asChild className="shrink-0">
          <Link to={`/history?generation=${encodeURIComponent(row.id)}`}>
            Record results
          </Link>
        </Button>
      </div>
    );
  }

  return (
    <div
      className="rounded-xl border border-[color:var(--hairline)] p-3"
      data-testid={`analytics-row-${row.id}`}
    >
      <div className="flex flex-wrap items-baseline justify-between gap-x-3 gap-y-1">
        <span className="min-w-0 truncate text-sm font-medium">
          {row.hook_line || row.template_id || "Finished video"}
        </span>
        <span className="flex shrink-0 items-center gap-1.5 text-xs">
          {verdict ? (
            <span className={`inline-flex items-center gap-1 font-medium ${verdict.tone}`}>
              <verdict.Icon className="h-3.5 w-3.5" />
              {verdict.label}
            </span>
          ) : (
            <span className="text-muted-foreground">No verdict</span>
          )}
          <span className="text-muted-foreground">
            · {new Date(row.created_at).toLocaleDateString()}
          </span>
        </span>
      </div>

      <div className="mt-2 grid grid-cols-3 gap-2 sm:grid-cols-5">
        {["views", "likes", "comments", "shares", "saves"].map((k) => (
          <div key={k}>
            <span className="text-[11px] text-muted-foreground">{humanize(k)}</span>
            <p className="text-sm font-semibold tabular-nums">
              {perf[k] == null ? "—" : perf[k].toLocaleString()}
            </p>
          </div>
        ))}
      </div>

      {/* The row's template, so a result connects to the ranking it feeds. The
          What Has Worked Here card names templates in aggregate; this chip is
          what lets the founder see that this 12k-view row IS the
          confession-open the top list is talking about. */}
      {row.template_id ? (
        <FactList className="mt-1.5">
          <FactChip>template {row.template_id}</FactChip>
        </FactList>
      ) : null}

      {/* The two ratios worth comparing. A low-view video with a strong save
          rate is a keeper; the raw counts above cannot say that, and the
          top-list ranking by views actively argues against it. */}
      <div className="mt-1.5 flex flex-wrap items-center gap-x-4 gap-y-1 text-xs text-muted-foreground">
        <span>
          save rate{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {rateText(perf.saves, perf.views)}
          </span>
        </span>
        <span>
          share rate{" "}
          <span className="font-semibold tabular-nums text-foreground">
            {rateText(perf.shares, perf.views)}
          </span>
        </span>
      </div>

      {/* The reason is the only part of a verdict the founder supplied, so it is
          shown verbatim and kept short. It is what makes a rejection countable
          later instead of a bare no. */}
      {perf.notes ? (
        <p className="mt-2 text-xs text-muted-foreground">{perf.notes}</p>
      ) : null}

      <div className="mt-2">
        <Button variant="ghost" size="sm" asChild>
          <Link to={`/history?generation=${encodeURIComponent(row.id)}`}>
            Open in History
          </Link>
        </Button>
      </div>
    </div>
  );
}

/**
 * Logged views over time, as a sparkline with a written equivalent.
 *
 * Hand-rolled SVG rather than a chart dependency: this is one polyline with
 * dots and no interactivity, and a dependency would buy tooltips nobody asked
 * for. The muted line under it states the same first-to-last movement in
 * words, so the trend is readable without parsing the shape — and so a screen
 * reader gets the conclusion instead of a silent image.
 */
function TrendSpark({ points }) {
  if (!points.length) return null;
  const W = 100;
  const H = 34;
  const P = 5;
  const max = Math.max(...points.map((p) => p.views), 1);
  const x = (i) => (points.length === 1 ? W / 2 : P + (i * (W - 2 * P)) / (points.length - 1));
  const y = (v) => H - P - (v / max) * (H - 2 * P);
  const first = points[0];
  const last = points[points.length - 1];
  return (
    <SectionCard title="Views over time" className="space-y-2" data-testid="analytics-trend">
      <svg
        viewBox={`0 0 ${W} ${H}`}
        className="h-10 w-full text-[color:var(--brand-indigo)]"
        role="img"
        aria-label={`Logged views across ${points.length} videos`}
      >
        {points.length > 1 && (
          <polyline
            points={points.map((p, i) => `${x(i)},${y(p.views)}`).join(" ")}
            fill="none"
            stroke="currentColor"
            strokeWidth="1.5"
            strokeLinejoin="round"
            strokeLinecap="round"
          />
        )}
        {points.map((p, i) => (
          <circle key={i} cx={x(i)} cy={y(p.views)} r="2" fill="currentColor" />
        ))}
      </svg>
      <p className="text-xs text-muted-foreground">
        {points.length === 1
          ? `${compact(last.views)} views · 1 logged video`
          : `${compact(first.views)} → ${compact(last.views)} · ${points.length} logged videos`}
      </p>
    </SectionCard>
  );
}

/**
 * Recorded results by one dimension, with the count always shown and the
 * comparison earned.
 *
 * Every bucket renders its n and its total views — those are facts about what
 * was logged. But a lead line only appears when a bucket clears COMPARABLE_AT
 * with view counts to rank on, and it names its own n so the claim carries its
 * evidence. Below that the bucket is listed and explicitly unranked, which is
 * the honest middle between hiding thin data and ranking it.
 */
function DimensionBreakdown({ title, testid, buckets, formatKey, noneLabel, copy }) {
  if (!buckets.length) return null;
  const leader = leadBucket(buckets);
  const anyComparable = buckets.some((b) => b.comparable);
  return (
    <SectionCard title={title} className="space-y-3" data-testid={testid}>
      {leader && (
        <p className="text-sm">
          {leader.label === "(none)" ? noneLabel : formatKey(leader.label)} leads —{" "}
          {compact(leader.med)} median views across {leader.n} logged videos.
        </p>
      )}
      <div className="space-y-2.5">
        {buckets.map((b) => (
          <div key={b.label}>
            <div className="flex items-center justify-between gap-3 text-sm">
              <span className="min-w-0 truncate">
                {b.label === "(none)" ? noneLabel : formatKey(b.label)}
              </span>
              <FactChip>{b.n} logged</FactChip>
            </div>
            <p className="mt-0.5 text-xs text-muted-foreground">
              {compact(b.views)} views total
              {b.med != null ? ` · median ${compact(b.med)}` : " · no view counts logged"}
              {!b.comparable ? " · not enough logged videos to compare" : ""}
            </p>
            {copy?.[b.label] ? (
              <p className="text-xs text-muted-foreground">{copy[b.label]}</p>
            ) : null}
          </div>
        ))}
      </div>
      {!anyComparable && (
        <p className="text-xs text-muted-foreground">
          The counts above are real; the ranking waits. A comparison needs
          enough logged videos in one bucket to mean anything.
        </p>
      )}
    </SectionCard>
  );
}

/**
 * The whole page as plain text, for a doc or a collaborator.
 *
 * Exported (rather than kept inside the click handler) so the shape is
 * assertable without mocking the clipboard: the smoke gate reads the built
 * text directly and checks that the verdicts, the templates and the loop line
 * all survived the trip out of the browser.
 */
export function buildAnalyticsSummaryText({
  profileName,
  generatedAt,
  recorded,
  tallies,
  whatWorks,
  objectiveOutcomes,
  signals,
}) {
  const lines = [];
  lines.push(`HookForge Analytics — ${profileName || "Untitled app"} (${generatedAt})`);
  const rows = recorded || [];
  const totalViews = rows.reduce((a, r) => a + (Number(r.performance?.views) || 0), 0);
  lines.push(`Logged videos: ${rows.length} · total views logged: ${totalViews.toLocaleString()}`);
  if (tallies) {
    lines.push(
      `Verdicts: ${tallies.successful} worked, ${tallies.unsuccessful} did not work, ${tallies.undecided} no verdict`
    );
  }
  const top = whatWorks?.top || [];
  const bottom = whatWorks?.bottom || [];
  if (top.length || bottom.length) lines.push("");
  if (top.length) {
    lines.push("Carried the most views:");
    for (const t of top) {
      lines.push(
        `- ${t.template_id} — ${Number(t.views).toLocaleString()} views, save ${Math.round((t.save_rate || 0) * 100)}%`
      );
    }
  }
  if (bottom.length) {
    lines.push("Carried the least:");
    for (const b of bottom) {
      lines.push(
        `- ${b.template_id} — ${Number(b.views).toLocaleString()} views, save ${Math.round((b.save_rate || 0) * 100)}%`
      );
    }
  }
  const buckets = bucketDimension(rows, "objective");
  if (buckets.length) {
    lines.push("");
    lines.push("By objective:");
    const leader = leadBucket(buckets);
    for (const b of buckets) {
      const label = b.label === "(none)" ? "Unset" : humanize(b.label);
      const marked = leader && b.label === leader.label ? " (leads)" : "";
      lines.push(
        `- ${label} — ${b.n} logged, median ${b.med != null ? compact(b.med) : "—"} views${marked}${
          !b.comparable ? " (not enough to compare)" : ""
        }`
      );
    }
  }
  const sigs = signals || [];
  if (sigs.length) {
    lines.push("");
    lines.push("What happened (automatic):");
    for (const s of sigs) lines.push(`- ${humanize(s.signal)} — ${s.count}`);
  }
  lines.push("");
  lines.push(
    "Logged results feed your next strategy. Every figure typed in by hand; nothing scraped or verified."
  );
  return lines.join("\n");
}

/**
 * Verdict counts, plus the reasons behind the rejections.
 *
 * Counts alone answer "how often" and not "why", and only the why can change
 * what the app recommends. The reason list is therefore the substance of this
 * card and the counts are the frame around it.
 */
function VerdictTallies({ tallies, total }) {
  if (!total) return null;
  return (
    <SectionCard title="Verdicts" className="space-y-3" data-testid="analytics-tallies">
      <div className="flex flex-wrap items-center gap-2">
        <FactChip className="border-green-500/25 text-green-300">
          {tallies.successful} worked
        </FactChip>
        <FactChip className="border-red-500/25 text-destructive">
          {tallies.unsuccessful} did not work
        </FactChip>
        <FactChip>{tallies.undecided} no verdict</FactChip>
      </div>

      {tallies.reasons.length > 0 ? (
        <div>
          <span className="eyebrow block">Reasons you gave</span>
          <div className="mt-2 space-y-1.5">
            {tallies.reasons.map((r) => (
              <div
                key={r.reason}
                className="flex items-center justify-between gap-3 text-sm"
              >
                <span className="min-w-0 truncate text-muted-foreground">
                  {r.reason === "poor_performance"
                    ? "Did not carry"
                    : "Carried"}
                </span>
                <FactChip>{r.count}</FactChip>
              </div>
            ))}
          </div>
        </div>
      ) : (
        <p className="text-xs text-muted-foreground">
          No reasons recorded yet. A rejection with a reason is what makes the next
          strategy different from this one.
        </p>
      )}
    </SectionCard>
  );
}

/**
 * Automatic signals, counts only.
 *
 * These are factual triggers captured as the founder worked -- a template
 * swapped, a video regenerated, a clip downloaded. They are not judgments about
 * why, and pairing them with a reason would be inventing one, so this card
 * stays a count list and the reasons live in the verdict card above.
 */
function SignalCounts({ summary }) {
  const signals = summary?.top_signals || [];
  if (!signals.length) return null;
  return (
    <SectionCard title="What happened" className="space-y-2" data-testid="analytics-signals">
      <p className="text-xs text-muted-foreground">
        Captured automatically as you worked. These are facts about the workflow, not
        opinions about why.
      </p>
      {signals.map((s) => (
        <div key={s.signal} className="flex items-center justify-between gap-3 text-sm">
          <span className="min-w-0 truncate text-muted-foreground">
            {humanize(s.signal)}
          </span>
          <FactChip>{s.count}</FactChip>
        </div>
      ))}
    </SectionCard>
  );
}

/**
 * Count verdicts.
 *
 * The counts come from performance_entries because that is where a verdict was
 * recorded. The reasons do not: performance_entries has no reason column, and
 * the founder's stated reason is captured as a feedback event instead. So the
 * two halves are read from the two stores that actually hold them rather than
 * from whichever row happens to be in hand.
 */
function tallyVerdicts(rows, summary) {
  const successful = rows.filter((r) => r.performance?.outcome === "successful").length;
  const unsuccessful = rows.filter((r) => r.performance?.outcome === "unsuccessful").length;
  return {
    successful,
    unsuccessful,
    undecided: rows.length - successful - unsuccessful,
    // Only reasons that came with an explicit verdict. A reason attached to
    // something else (a template swap, a regenerate) is not an answer to
    // "why did this video not work", and counting it as one would put words in
    // the founder's mouth.
    reasons: (summary?.top_reasons || [])
      .filter((r) => r.reason === "poor_performance" || r.reason === "good_performance")
      .map((r) => ({ reason: r.reason, count: r.count })),
  };
}