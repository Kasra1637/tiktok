import { useCallback, useEffect, useMemo, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";
import { SectionCard } from "../components/SectionCard";
import { FactChip } from "../components/FactChip";
import WhatWorksCard from "../components/WhatWorksCard";
import { api, getErrorMessage } from "../lib/api";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import { TrendingUp, Loader2, AlertTriangle, Info, CircleCheck, CircleX } from "lucide-react";

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

export default function Analytics() {
  const [profiles, setProfiles] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [whatWorks, setWhatWorks] = useState(null);
  const [generations, setGenerations] = useState([]);
  const [feedback, setFeedback] = useState(null);
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

  const selectProfile = (id) => {
    setSelectedId(id);
    // Persisted so returning here is one click, not a re-pick. Same key the
    // rest of the app uses, so an app chosen here is the app the Asset Library
    // opens on.
    rememberCurrentAppId(id);
  };

  // Completed rows only. A failed render has nothing to record results against,
  // and listing it here would invite the founder to enter numbers for a clip
  // that was never produced.
  const ledger = useMemo(
    () => generations.filter((g) => g.status === "completed"),
    [generations]
  );
  const recorded = useMemo(() => ledger.filter((g) => g.performance), [ledger]);
  const unrecorded = useMemo(() => ledger.filter((g) => !g.performance), [ledger]);

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
            profiles.length > 1 ? (
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
            ) : null
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
    return (
      <div
        className="flex items-center justify-between gap-3 rounded-xl border border-dashed border-[color:var(--hairline)] px-3 py-2"
        data-testid={`analytics-nudge-${row.id}`}
      >
        <span className="min-w-0 truncate text-sm text-muted-foreground">
          {row.hook_line || row.template_id || "Finished video"} — nothing logged yet
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