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
import { TrendingUp, AlertTriangle, Activity } from "lucide-react";

/**
 * Facts about your work, captured automatically as you go.
 *
 * Manual result logging is gone, so this page no longer answers "what did my
 * videos do" — nothing is typed in, nothing is scraped, and no per-template
 * learning reads from here. What remains is the automatic half: factual
 * triggers (a template swapped, a video regenerated, a clip downloaded)
 * counted as they happened, never judgments about why.
 */

/** Same vocabulary helper History uses, so a code reads identically on both. */
function humanize(value) {
  return String(value || "")
    .replace(/[-_]/g, " ")
    .replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function Analytics() {
  const [profiles, setProfiles] = useState([]);
  const [selectedId, setSelectedId] = useState("");
  const [feedback, setFeedback] = useState(null);
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
              <Button variant="brand" asChild>
                <Link to="/brand">Open App Profile</Link>
              </Button>
            }
          />
        )
      ) : feedback?.summary?.top_signals?.length ? (
        <SignalCounts summary={feedback.summary} />
      ) : (
        <EmptyState
          icon={Activity}
          title="Nothing captured yet"
          description="Signals appear here as you work with this app."
        />
      )}
    </PageFrame>
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
function SignalCounts({ summary }) {
  const signals = summary?.top_signals || [];
  if (!signals.length) return null;
  return (
    <SectionCard
      title="What happened"
      icon={Activity}
      description="Captured automatically as you worked."
      data-testid="analytics-signals"
    >
      <ul className="divide-y divide-[color:var(--hairline)]">
        {signals.map((s) => (
          <li key={s.signal} className="flex items-center justify-between gap-4 py-2 text-sm">
            <span className="min-w-0 truncate text-muted-foreground">{humanize(s.signal)}</span>
            <FactChip>{s.count}</FactChip>
          </li>
        ))}
      </ul>
    </SectionCard>
  );
}
