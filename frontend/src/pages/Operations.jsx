import { useCallback, useEffect, useState } from "react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import { api, getErrorMessage } from "../lib/api";
import {
  Settings2, Loader2, AlertTriangle, CheckCircle2, XCircle, RotateCcw,
  Cpu, Database, Cloud, Film, ShieldCheck,
} from "lucide-react";

function IntegrationRow({ icon: Icon, label, configured, detail }) {
  return (
    <div className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] p-3">
      {configured ? (
        <CheckCircle2 className="h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />
      ) : (
        <XCircle className="h-4 w-4 shrink-0 text-muted-foreground" />
      )}
      <Icon className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 flex-1">
        <span className="text-sm font-medium">{label}</span>
        {detail && <p className="text-xs text-muted-foreground">{detail}</p>}
      </div>
      <Badge variant={configured ? "indigo" : "secondary"} className="shrink-0 text-[11px]">
        {configured ? "Configured" : "Not set"}
      </Badge>
    </div>
  );
}

export default function Operations() {
  const [ops, setOps] = useState(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [retrying, setRetrying] = useState(null);

  const load = useCallback(() => {
    setLoading(true);
    api
      .getOperations()
      .then(setOps)
      .catch((err) => setError(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    load();
    const timer = setInterval(load, 30000);
    return () => clearInterval(timer);
  }, [load]);

  if (loading && !ops) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading operations...
      </p>
    );
  }

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertTitle>Could not load operations</AlertTitle>
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  const jobs = ops?.jobs || {};
  const config = ops?.config || {};
  const cost = ops?.cost || {};
  const modelRequests = ops?.model_requests || {};
  const modalityEntries = Object.entries(modelRequests.by_modality || {});
  const modelEntries = Object.entries(modelRequests.by_model || {});

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Settings2}
        title="Operations"
        description="What is running, what failed and can be retried, what it cost, and what each integration is doing."
        actions={
          <Button variant="secondary" size="sm" onClick={load} disabled={loading}>
            {loading ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
            Refresh
          </Button>
        }
      />

      <div className="grid grid-cols-2 gap-3 lg:grid-cols-5">
        {[
          ["Total jobs", jobs.total ?? 0],
          ["In flight", jobs.in_flight ?? 0],
          ["Completed", jobs.completed ?? 0],
          ["Failed", jobs.failed ?? 0],
          ["Known spend", cost.total_usd != null ? `$${cost.total_usd.toFixed(2)}` : "$0.00"],
        ].map(([label, value]) => (
          <div key={label} className="surface rounded-2xl p-4">
            <span className="text-xs text-muted-foreground">{label}</span>
            <p className="mt-1 font-display text-xl font-bold">{value}</p>
          </div>
        ))}
      </div>

      <div className="space-y-2">
        <h2 className="font-display text-base font-semibold">Video providers</h2>
        <div className="surface space-y-2 rounded-2xl p-4">
          {(ops?.providers || []).map((p) => (
            <div key={p.key} className="flex flex-wrap items-center gap-2 border-b border-[color:var(--hairline)] pb-2 last:border-0 last:pb-0">
              <Cpu className="h-4 w-4 shrink-0 text-muted-foreground" />
              <span className="text-sm font-medium">{p.name}</span>
              {p.is_default && <Badge variant="indigo" className="text-[11px]">default</Badge>}
              {!p.allowed && <Badge variant="outline" className="text-[11px]">not allowed</Badge>}
              {!p.studio_eligible && (
                <Badge variant="outline" className="text-[11px]">editor only — not usable here</Badge>
              )}
              <span className="ml-auto text-xs text-muted-foreground">
                up to {p.max_single_pass_seconds}s per pass
                {p.supports_native_audio ? " · native audio" : ""}
              </span>
            </div>
          ))}
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="font-display text-base font-semibold">Integrations</h2>
        <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
          <IntegrationRow icon={Cpu} label="OpenRouter (text, vision, video)" configured={config.ai_configured} />
          <IntegrationRow icon={Cloud} label="Apify (trend research)" configured={config.apify_configured} />
          <IntegrationRow icon={Database} label="Cloudflare R2 (video storage)" configured={config.r2_configured} />
          <IntegrationRow icon={Database} label="Turso (cloud database)" configured={config.turso_configured} />
          <IntegrationRow icon={Film} label="ffmpeg (overlays)" configured={!!config.overlay_font} detail={config.overlay_font} />
        </div>
      </div>

      <div className="space-y-2">
        <h2 className="font-display text-base font-semibold">Model requests</h2>
        <div className="surface space-y-3 rounded-2xl p-4">
          <p className="text-xs text-muted-foreground">
            {modelRequests.total ?? 0} tracked · {modelRequests.completed ?? 0} completed ·{" "}
            {modelRequests.failed ?? 0} failed ·{" "}
            {modelRequests.total_usd != null ? `$${modelRequests.total_usd.toFixed(4)} reported` : "no reported cost"}
            {modelRequests.unpriced_runs ? ` · ${modelRequests.unpriced_runs} unpriced` : ""}
          </p>
          {modalityEntries.length > 0 && (
            <div className="flex flex-wrap gap-1.5">
              {modalityEntries.map(([modality, entry]) => (
                <Badge key={modality} variant="secondary" className="text-[11px]">
                  {modality}: {entry.completed}/{entry.total}
                  {entry.failed ? ` · ${entry.failed} failed` : ""}
                </Badge>
              ))}
            </div>
          )}
          {modelEntries.length > 0 && (
            <div className="space-y-1.5">
              {modelEntries.map(([model, entry]) => (
                <div key={model} className="flex flex-wrap items-center gap-2 text-xs">
                  <Cpu className="h-3.5 w-3.5 text-muted-foreground" />
                  <span className="font-medium">{model}</span>
                  <span className="text-muted-foreground">
                    {entry.completed}/{entry.total} completed
                    {entry.failed ? ` · ${entry.failed} failed` : ""}
                    {entry.priced_runs ? ` · $${entry.total_usd.toFixed(4)}` : ""}
                  </span>
                </div>
              ))}
            </div>
          )}
          {(ops?.failed_model_requests || []).length > 0 && (
            <div className="space-y-1.5">
              {(ops.failed_model_requests || []).map((r) => (
                <div key={r.id} className="flex flex-wrap items-center gap-2 text-xs">
                  <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                  <span className="font-medium">{r.operation}</span>
                  <span className="text-muted-foreground">{r.modality} · {r.model}</span>
                  <span className="min-w-0 flex-1 truncate text-destructive">{r.error || "Unknown error"}</span>
                </div>
              ))}
            </div>
          )}
        </div>
      </div>

      {(ops?.research_runs || []).length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Research jobs</h2>
          <div className="surface space-y-2 rounded-2xl p-4">
            {ops.research_runs.map((run) => (
              <div key={run.id} className="flex flex-wrap items-center gap-2 text-xs">
                <Badge variant="outline" className="text-[11px]">{run.status}</Badge>
                <span className="font-medium">{run.kind}: {run.query || run.niche || "research"}</span>
                {run.sources_found != null && (
                  <span className="text-muted-foreground">{run.sources_found} source(s)</span>
                )}
                {run.error && (
                  <span className="min-w-0 flex-1 truncate text-destructive">{run.error}</span>
                )}
                <span className="ml-auto text-muted-foreground">
                  {new Date(run.created_at).toLocaleString()}
                </span>
              </div>
            ))}
          </div>
        </div>
      )}

      {(ops?.asset_events || []).length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Asset failures</h2>
          <div className="surface space-y-2 rounded-2xl p-4">
            {ops.asset_events.map((event) => (
              <div key={event.id} className="flex flex-wrap items-center gap-2 text-xs">
                <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
                <span className="font-medium">{String(event.kind).replace(/_/g, " ")}</span>
                {event.asset_kind && <span className="text-muted-foreground">{event.asset_kind}</span>}
                <span className="min-w-0 flex-1 truncate text-destructive">{event.reason}</span>
                <span className="ml-auto text-muted-foreground">
                  {new Date(event.created_at).toLocaleString()}
                </span>
              </div>
            ))}
            <p className="text-xs text-muted-foreground">
              Rejected uploads and composition assets stay visible here. Successful uploads need no event.
            </p>
          </div>
        </div>
      )}

      {(ops?.storage_failures || []).length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Durable-storage failures</h2>
          {ops.storage_failures.map((f) => (
            <div
              key={f.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-3"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
              <span className="min-w-0 flex-1 truncate text-xs">{f.storage_error || "Durable copy failed."}</span>
              <Badge variant="outline" className="text-[11px]">{f.model}</Badge>
              <Button
                variant="secondary"
                size="sm"
                disabled={retrying === `storage:${f.id}`}
                onClick={async () => {
                  setRetrying(`storage:${f.id}`);
                  try {
                    await api.retryGenerationStorage(f.id);
                    load();
                  } catch (err) {
                    setError(getErrorMessage(err));
                  } finally {
                    setRetrying(null);
                  }
                }}
              >
                {retrying === `storage:${f.id}` ? (
                  <Loader2 className="h-3.5 w-3.5 animate-spin" />
                ) : (
                  <RotateCcw className="h-3.5 w-3.5" />
                )}
                Retry storage
              </Button>
            </div>
          ))}
          <p className="text-xs text-muted-foreground">
            The rendered video is intact; only its durable R2/local copy failed.
          </p>
        </div>
      )}

      {(ops?.failures || []).length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Failed generations</h2>
          {ops.failures.map((f) => (
            <div
              key={f.id}
              className="flex flex-wrap items-center gap-2 rounded-xl border border-destructive/40 bg-destructive/5 p-3"
            >
              <AlertTriangle className="h-3.5 w-3.5 shrink-0 text-destructive" />
              <span className="min-w-0 flex-1 truncate text-xs">{f.error || "Unknown error"}</span>
              <Badge variant="outline" className="text-[11px]">{f.model}</Badge>
              <Badge variant="outline" className="text-[11px]">
                {new Date(f.created_at).toLocaleString()}
              </Badge>
              {f.retryable ? (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={retrying === f.id}
                  onClick={async () => {
                    setRetrying(f.id);
                    try {
                      await api.retryGeneration(f.id);
                      load();
                    } catch (err) {
                      setError(getErrorMessage(err));
                    } finally {
                      setRetrying(null);
                    }
                  }}
                >
                  {retrying === f.id ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3.5 w-3.5" />
                  )}
                  Retry
                </Button>
              ) : (
                <Badge variant="outline" className="text-[11px]">not retryable</Badge>
              )}
            </div>
          ))}
        </div>
      )}

      {(ops?.overlay_jobs?.errors || []).length > 0 && (
        <div className="space-y-2">
          <h2 className="font-display text-base font-semibold">Video processing failures</h2>
          {ops.overlay_jobs.errors.map((e, i) => (
            <p key={i} className="truncate rounded-xl border border-[color:var(--hairline)] p-3 text-xs text-destructive">
              {e}
            </p>
          ))}
          <p className="text-xs text-muted-foreground">
            An overlay failure never loses the video: the un-composited clip is kept.
          </p>
        </div>
      )}

      <div className="surface flex items-start gap-2 rounded-2xl p-4">
        <ShieldCheck className="mt-0.5 h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]" />
        <p className="text-sm text-muted-foreground">{ops?.manual_publishing}</p>
      </div>
    </div>
  );
}
