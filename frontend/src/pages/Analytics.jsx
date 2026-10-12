import { useCallback, useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Button } from "../components/ui/button";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import { SectionCard } from "../components/SectionCard";
import { FactChip } from "../components/FactChip";
import { api, getErrorMessage } from "../lib/api";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import { TrendingUp, Loader2, AlertTriangle, Info, Activity } from "lucide-react";

/**
 * What happened as you worked, captured automatically.
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

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading analytics...
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
    <PageFrame className="space-y-6">
      {/* The header carries the testid rather than PageHeader: that component takes a
        fixed prop list and drops anything else, so a testid passed to it would
        silently never appear. */}
      <div data-testid="analytics-header">
        <PageHeader
          icon={TrendingUp}
          title="Analytics"
          description="What happened as you worked, captured automatically — facts about the workflow, not judgments about why."
          actions={
            <div className="flex flex-wrap items-center gap-2">
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
              Create an App Profile to get started.
            </span>
            <Button variant="secondary" size="sm" className="shrink-0" asChild>
              <Link to="/brand">Open App Profile</Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {selectedId && (
        <SignalCounts summary={feedback?.summary} />
      )}

      {selectedId && !feedback?.summary?.top_signals?.length && !loading && (
        <p className="text-sm text-muted-foreground">
          Nothing captured yet — signals appear here as you work with this app.
        </p>
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
    <SectionCard title="What happened" icon={Activity} className="space-y-2" data-testid="analytics-signals">
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
