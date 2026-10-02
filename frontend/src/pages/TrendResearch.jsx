import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import {
  Radar, Loader2, AlertTriangle, Search, ShieldCheck, Sparkles, XCircle,
} from "lucide-react";

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

export default function TrendResearch() {
  const [kind, setKind] = useState("keyword");
  const [query, setQuery] = useState("");
  const [appContext, setAppContext] = useState("");
  const [running, setRunning] = useState(false);
  const [error, setError] = useState(null);
  const [result, setResult] = useState(null);
  const [runs, setRuns] = useState([]);
  const [expandedId, setExpandedId] = useState(null);
  const [publishBusyId, setPublishBusyId] = useState("");
  const [publishedIds, setPublishedIds] = useState(() => new Set());

  const loadRuns = useCallback(() => {
    api.getResearchRuns().then((d) => setRuns(d.runs || [])).catch(() => setRuns([]));
  }, []);

  useEffect(() => {
    loadRuns();
  }, [loadRuns]);

  const scan = async (e) => {
    e?.preventDefault();
    if (!query.trim()) {
      setError("Enter a keyword, hashtag, or category to research.");
      return;
    }
    setRunning(true);
    setError(null);
    setResult(null);
    try {
      const data = await api.runResearchScan({
        kind,
        query: query.trim(),
        limit: 15,
        app_context: appContext.trim() || undefined,
      });
      setResult(data);
      loadRuns();
    } catch (err) {
      setError(getErrorMessage(err));
      loadRuns();
    } finally {
      setRunning(false);
    }
  };

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Radar}
        title="Trend Research"
        description="Reads public trend data to find recurring hook mechanics, and turns them into reviewable template drafts."
      />

      <Alert>
        <ShieldCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        <AlertDescription>
          Research extracts reusable mechanics only. It never copies a creator's identity,
          gestures, voice, or music, and no source video is kept or needed to use a
          resulting template. Every draft must be reviewed and published before it can be
          used in a video.
        </AlertDescription>
      </Alert>

      <form onSubmit={scan} className="surface space-y-3 rounded-2xl p-4">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[auto_1fr_auto]">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            aria-label="Research type"
            className="rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            <option value="keyword">Keyword</option>
            <option value="hashtag">Hashtag</option>
          </select>
          <Input
            value={query}
            onChange={(e) => setQuery(e.target.value)}
            placeholder={kind === "hashtag" ? "e.g. journaling" : "e.g. journaling app"}
            aria-label="Search term"
          />
          <Button type="submit" variant="brand" disabled={running}>
            {running ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
            Scan
          </Button>
        </div>
        <Input
          value={appContext}
          onChange={(e) => setAppContext(e.target.value)}
          placeholder="Optional: which app are you promoting? (biases the drafts)"
          aria-label="App context"
        />
      </form>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Research did not run</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {result && (
        <div className="space-y-3">
          <Alert>
            <AlertTitle>
              {result.sources_found} public source(s) scanned, {result.drafts.length} draft(s) proposed
            </AlertTitle>
            <AlertDescription>{result.note}</AlertDescription>
          </Alert>

          {result.drafts.length > 0 && (
            <div className="space-y-2">
              {result.drafts.map((d) => {
                const published = publishedIds.has(d.id);
                const expanded = expandedId === d.id;
                return (
                <div key={d.id} className="surface rounded-2xl p-4">
                  <div className="flex flex-wrap items-center justify-between gap-2">
                    <span className="font-display text-sm font-semibold">{d.name}</span>
                    <span className="flex items-center gap-2">
                      <Badge variant="secondary" className="text-[11px]">{humanize(d.category)}</Badge>
                      <Badge variant="outline" className="text-[11px]">
                        {published ? "published" : "unpublished"}
                      </Badge>
                    </span>
                  </div>
                  {expanded && (
                    <dl className="mt-3 space-y-2 text-sm">
                      {[
                        ["Opening", d.opening_structure],
                        // `middle_structure` replaced `continuation_structure`
                        // and a separate `cta_pattern`: a research draft used
                        // to describe a chain with a closing beat, and the
                        // middle is now where the story goes — up to the moment
                        // the viewer reaches for the app. The retired name is
                        // read as a fallback for drafts written before the
                        // change, and the CTA pattern is not shown at all
                        // because this product does not generate a close.
                        ["Middle", d.middle_structure || d.continuation_structure],
                        ["Hook mechanic", d.hook_mechanic],
                      ].map(([label, value]) => value ? (
                        <div key={label}>
                          <dt className="text-[11px] font-medium uppercase tracking-wide text-muted-foreground">{label}</dt>
                          <dd className="mt-0.5">{value}</dd>
                        </div>
                      ) : null)}
                    </dl>
                  )}
                  <div className="mt-2 flex flex-wrap gap-2">
                    <Button
                      variant="secondary"
                      size="sm"
                      onClick={() => setExpandedId(expanded ? null : d.id)}
                    >
                      {expanded ? "Hide detail" : "Review"}
                    </Button>
                    {published ? (
                      <Button variant="brand" size="sm" asChild>
                        <a href="/create">Use in the studio</a>
                      </Button>
                    ) : (
                      <Button
                        variant="brand"
                        size="sm"
                        disabled={publishBusyId === d.id}
                        onClick={async () => {
                          setPublishBusyId(d.id);
                          setError(null);
                          try {
                            await api.publishTemplate(d.id);
                            setPublishedIds((prev) => new Set(prev).add(d.id));
                          } catch (err) {
                            setError(getErrorMessage(err));
                          } finally {
                            setPublishBusyId("");
                          }
                        }}
                      >
                        {publishBusyId === d.id ? (
                          <Loader2 className="h-3.5 w-3.5 animate-spin" />
                        ) : null}
                        Publish
                      </Button>
                    )}
                  </div>
                </div>
                );
              })}
            </div>
          )}

          {(result.rejected || []).length > 0 && (
            <div className="space-y-2">
              <h3 className="flex items-center gap-1.5 font-display text-sm font-semibold">
                <XCircle className="h-4 w-4 text-muted-foreground" />
                Rejected by the safety guard ({result.rejected.length})
              </h3>
              {result.rejected.map((r, i) => (
                <p key={i} className="rounded-xl border border-[color:var(--hairline)] p-3 text-xs text-muted-foreground">
                  <span className="font-medium text-foreground">{r.name || "(unnamed)"}</span>
                  {" — "}{r.reason}
                </p>
              ))}
              <p className="text-xs text-muted-foreground">
                Anything describing a specific creator, their gestures or voice, or
                copyrighted audio is dropped rather than published.
              </p>
            </div>
          )}
        </div>
      )}

      <div className="space-y-2">
        <h2 className="font-display text-base font-semibold">Previous runs</h2>
        {runs.length === 0 ? (
          <EmptyState
            icon={Sparkles}
            title="No research yet"
            description="Scan a keyword or hashtag to find recurring hook mechanics."
          />
        ) : (
          <div className="space-y-1.5">
            {runs.map((r) => (
              <div
                key={r.id}
                className="flex flex-wrap items-center gap-2 rounded-xl border border-[color:var(--hairline)] p-3 text-sm"
              >
                <Badge variant="secondary" className="text-[11px]">{humanize(r.kind)}</Badge>
                <span className="min-w-0 flex-1 truncate">{r.query || r.niche}</span>
                <span className="text-xs text-muted-foreground">
                  {r.sources_found} source(s)
                </span>
                <Badge
                  variant={r.status === "completed" ? "indigo" : "destructive"}
                  className="text-[11px]"
                >
                  {r.status}
                </Badge>
                <span className="text-xs text-muted-foreground">
                  {new Date(r.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
