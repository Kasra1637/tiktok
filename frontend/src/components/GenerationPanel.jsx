import { useCallback, useEffect, useRef, useState } from "react";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage } from "../lib/api";
import {
  Loader2, Clapperboard, AlertTriangle, Download, RefreshCw, RotateCcw,
  Play, Info, Clock,
} from "lucide-react";

/**
 * Produce and follow one complete video.
 *
 * The normal case is a single generation covering the hook and its
 * continuation. A second call is only ever made for the three justified
 * reasons the backend allows: a duration beyond the provider's single-pass
 * limit, an explicit extension, or a failed-segment replacement.
 */
const POLL_INTERVAL_MS = 6000;

function money(value) {
  if (value === null || value === undefined) return null;
  return `$${Number(value).toFixed(2)}`;
}

function StatusBadge({ status }) {
  const map = {
    submitted: ["Queued", "secondary"],
    generating: ["Generating", "indigo"],
    completed: ["Completed", "indigo"],
    failed: ["Failed", "destructive"],
    archived: ["Archived", "secondary"],
  };
  const [label, variant] = map[status] || [status, "secondary"];
  return <Badge variant={variant} className="text-xs">{label}</Badge>;
}

export function GenerationPanel({ project, onGenerationChange }) {
  const [models, setModels] = useState(null);
  const [selectedModel, setSelectedModel] = useState("");
  const [generation, setGeneration] = useState(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const timer = useRef(null);

  const projectId = project?.id;
  const ready = project?.status === "ready_for_generation";
  const blocked = project?.safety_report && project.safety_report.passed === false;

  useEffect(() => {
    let cancelled = false;
    api
      .getStudioVideoModels()
      .then((data) => {
        if (cancelled) return;
        setModels(data);
        setSelectedModel(data.default || "");
      })
      .catch(() => {
        if (!cancelled) setModels(null);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  // Adopt the newest generation for this project, and stop polling a
  // finished one so a completed video is not re-checked forever.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!projectId) return;
      try {
        const data = await api.getGenerations({ studio_project_id: projectId, limit: 1 });
        if (cancelled) return;
        const newest = data.generations?.[0] || null;
        setGeneration(newest);
        if (newest && (newest.status === "submitted" || newest.status === "generating")) {
          schedulePoll(newest.id);
        }
      } catch {
        /* a project with no generations yet is normal */
      }
    }
    load();
    return () => {
      cancelled = true;
      if (timer.current) clearTimeout(timer.current);
    };
  }, [projectId, schedulePoll]);

  const schedulePoll = useCallback((id) => {
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const updated = await api.pollGeneration(id);
        setGeneration(updated);
        onGenerationChange?.(updated);
        if (updated.status === "submitted" || updated.status === "generating") {
          schedulePoll(id);
        }
      } catch (err) {
        setError(getErrorMessage(err));
      }
    }, POLL_INTERVAL_MS);
  }, [onGenerationChange]);

  const handleGenerate = async () => {
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const created = await api.generateVideo(projectId, { model: selectedModel || undefined });
      setGeneration(created);
      onGenerationChange?.(created);
      if (created.duration_plan?.needs_extension) {
        setNotice(
          `${created.model} produces at most ${created.duration_plan.primary_seconds}s in one ` +
          `pass, so this video covers ${created.duration_plan.primary_seconds}s of your ` +
          `${created.duration_plan.requested_seconds}s. Extend it once it completes.`
        );
      }
      schedulePoll(created.id);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRetry = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.retryGeneration(generation.id);
      setGeneration(created);
      onGenerationChange?.(created);
      schedulePoll(created.id);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleExtend = async () => {
    setBusy(true);
    setError(null);
    try {
      const created = await api.extendGeneration(generation.id, { duration_seconds: 5 });
      setGeneration(created);
      onGenerationChange?.(created);
      schedulePoll(created.id);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const capability = models?.models?.find((m) => m.key === selectedModel);
  const inFlight = generation && (generation.status === "submitted" || generation.status === "generating");
  const cost = generation ? money(generation.cost_usd) : null;
  const downloadUrl = generation?.r2_url || generation?.video_url;

  return (
    <div className="space-y-3 rounded-2xl border border-[color:var(--hairline)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-display text-sm font-semibold">
          <Clapperboard className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          Produce the video
        </span>
        {generation && <StatusBadge status={generation.status} />}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {!ready && !generation && (
        <p className="text-sm text-muted-foreground">
          Mark the project ready for generation to enable production.
        </p>
      )}
      {blocked && (
        <Alert variant="destructive">
          <AlertTitle>Prohibited claim present</AlertTitle>
          <AlertDescription>
            Fix the flagged claim in the script above. Generation is blocked until the claim
            check passes.
          </AlertDescription>
        </Alert>
      )}

      {models && (
        <div className="space-y-1.5">
          <label htmlFor="gen-model" className="text-sm font-medium">Model</label>
          <select
            id="gen-model"
            value={selectedModel}
            onChange={(e) => setSelectedModel(e.target.value)}
            disabled={inFlight}
            className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            {models.models.map((m) => (
              <option key={m.key} value={m.key}>
                {m.name} — up to {m.max_duration}s per pass{m.key === models.default ? " (default)" : ""}
              </option>
            ))}
          </select>
          {capability && (
            <p className="text-xs text-muted-foreground">
              {capability.notes}
            </p>
          )}
        </div>
      )}

      <Button
        variant="brand"
        onClick={handleGenerate}
        disabled={busy || inFlight || !ready || blocked || !projectId}
      >
        {busy || inFlight ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {inFlight ? "Generating..." : generation ? "Generate another" : "Generate video"}
      </Button>

      {generation && (
        <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3 text-sm">
          <div className="flex flex-wrap items-center gap-2">
            {generation.model && <Badge variant="outline" className="text-[11px]">{generation.model}</Badge>}
            {generation.duration && (
              <Badge variant="outline" className="text-[11px]">
                <Clock className="mr-1 h-2.5 w-2.5" />{generation.duration}s
              </Badge>
            )}
            {generation.attempt > 1 && (
              <Badge variant="outline" className="text-[11px]">attempt {generation.attempt}</Badge>
            )}
            {cost && <Badge variant="secondary" className="text-[11px]">{cost}</Badge>}
            {generation.cost_source === "unavailable" && (
              <span className="text-[11px] text-muted-foreground">cost not reported by provider</span>
            )}
          </div>

          {generation.status === "completed" && downloadUrl && (
            <>
              <video
                src={downloadUrl}
                controls
                playsInline
                className="w-full max-w-[280px] rounded-xl border border-[color:var(--hairline)]"
              />
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" size="sm" asChild>
                  <a href={downloadUrl} download>
                    <Download className="h-3.5 w-3.5" /> Download MP4
                  </a>
                </Button>
                <Button variant="ghost" size="sm" onClick={handleExtend} disabled={busy}>
                  <RefreshCw className="h-3.5 w-3.5" /> Extend
                </Button>
              </div>
              <p className="text-xs text-muted-foreground">
                Post it yourself — this tool never publishes to any platform.
              </p>
            </>
          )}

          {generation.status === "failed" && (
            <div className="space-y-2">
              <p className="text-xs text-destructive">{generation.error}</p>
              {generation.retryable ? (
                <Button variant="secondary" size="sm" onClick={handleRetry} disabled={busy}>
                  <RotateCcw className="h-3.5 w-3.5" /> Replace failed segment
                </Button>
              ) : (
                <p className="text-xs text-muted-foreground">
                  This failure is not retryable — change the script or model and generate again.
                </p>
              )}
            </div>
          )}

          {inFlight && (
            <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
              <Loader2 className="h-3 w-3 animate-spin" /> Working — this page checks back on its own.
            </p>
          )}
        </div>
      )}
    </div>
  );
}

export default GenerationPanel;
