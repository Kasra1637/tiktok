import { useCallback, useEffect, useRef, useState } from "react";
import { AlertTriangle, Check, Clock, Download, Info, Play, RotateCcw } from "lucide-react";
import { Button } from "../ui/button";
import { Badge } from "../ui/badge";
import { StatusBadge } from "../StatusBadge";
import { Alert, AlertTitle, AlertDescription } from "../ui/alert";
import { AppSelect } from "../AppSelect";
import { CONTROL_CLASS } from "../formControls";
import { GroupLabel } from "../SectionCard";
import { GenerateAnotherConfirmDialog } from "./GenerateAnotherConfirmDialog";
import { api, getErrorMessage, mediaUrl, downloadMediaUrl, durableMediaUrl } from "../../lib/api";
import { exceedsSinglePass, readPieceSeconds } from "../../lib/videoLength";

/**
 * The story render panel (ADR 0236): one frame, one render, modeled
 * on `GenerationPanel.jsx` and deliberately NOT that component — its
 * readiness gate is coupled to the wizard's strategy state, which a
 * story project does not have. A story's readiness is its plan
 * (ADR 0228): no plan, no render, plus the presenter photo the
 * identity is built from and the same model, resolution and
 * single-pass checks every submit makes. The gates are named in
 * words on the panel, never left to a click into a server refusal.
 *
 * The submit goes through the stories router's generate endpoint,
 * which renders the frame at its OWN seconds (exact duration —
 * a 5-second question frame renders and bills at 5, never at the
 * hook-video clamp's 8). Progress is the app's pattern: an
 * indeterminate bar, a stage checklist naming the real backend
 * phase, and the elapsed clock — never a percentage (ADR 0140).
 * The poll chain never retires a live render (ADR 0171): failures
 * stretch the interval and narrate themselves from the third.
 *
 * When the render lands, the finished clip stands here and the
 * story kit lands beside it (the page renders StoryKitPanel from
 * the same row): the kit is written at completion by a background
 * task, so a completed row without one is re-read a few times
 * before the panel settles.
 */
const STAGES = [
  "Sending your approved script",
  "Rendering your story frame",
  "Saving your finished video",
];

function stageIndexFor(status, persistInFlight) {
  if (status === "submitted") return 0;
  if (status === "generating") return persistInFlight ? 2 : 1;
  return 0;
}

function formatElapsed(ms) {
  const totalSeconds = Math.max(0, Math.floor(ms / 1000));
  const minutes = Math.floor(totalSeconds / 60);
  const seconds = String(totalSeconds % 60).padStart(2, "0");
  return `${minutes}:${seconds}`;
}

function StoryRenderProgress({ status, videoUrl, startedAt, persistInFlight = false }) {
  const hasUrl = Boolean(videoUrl);
  const isDone = status === "completed" || hasUrl;
  const stageIndex = isDone ? 3 : stageIndexFor(status, persistInFlight);
  const anchorRef = useRef(null);
  if (anchorRef.current === null) {
    const parsed = Date.parse(startedAt || "");
    anchorRef.current = Number.isFinite(parsed) ? parsed : Date.now();
  }
  const [now, setNow] = useState(() => Date.now());
  useEffect(() => {
    if (isDone) return undefined;
    const timer = setInterval(() => setNow(Date.now()), 1000);
    return () => clearInterval(timer);
  }, [isDone]);
  return (
    <div className="space-y-3" aria-live="polite" data-testid="story-render-progress">
      <div className="flex items-center gap-3">
        <div
          role="progressbar"
          aria-label="Story render progress"
          className="h-2 w-full flex-1 overflow-hidden rounded-full bg-[color:var(--indigo-8)]"
        >
          <div
            className={`h-full rounded-full bg-gradient-to-r from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] ${
              isDone ? "w-full" : "render-progress-fill"
            }`}
          />
        </div>
        {!isDone && (
          <span className="shrink-0 text-xs tabular-nums text-muted-foreground">
            {formatElapsed(now - anchorRef.current)} elapsed
          </span>
        )}
      </div>
      <ul className="space-y-1.5">
        {STAGES.map((label, i) => (
          <li
            key={label}
            className={`flex items-center gap-2 text-sm ${
              i < stageIndex
                ? "text-muted-foreground"
                : i === stageIndex
                  ? "font-semibold text-foreground"
                  : "text-muted-foreground"
            }`}
          >
            {i < stageIndex ? (
              <Check className="h-3.5 w-3.5 text-[color:var(--brand-indigo)]" />
            ) : (
              <span
                aria-hidden="true"
                className={`h-2 w-2 rounded-full ${
                  i === stageIndex
                    ? "bg-[color:var(--brand-indigo)]"
                    : "border border-current opacity-40"
                }`}
              />
            )}
            {label}
            {i === stageIndex && !isDone ? "…" : ""}
          </li>
        ))}
      </ul>
    </div>
  );
}

const POLL_INTERVAL_MS = 6000;

function modelStorageKey(projectId) {
  return `story-video-model:${projectId}`;
}

function resolutionStorageKey(projectId) {
  return `story-video-resolution:${projectId}`;
}

export default function StoryRenderPanel({
  project, generation, onGenerationChange, hasUnsavedEdits = false, autosaving = false,
}) {
  const [models, setModels] = useState(null);
  const [modelError, setModelError] = useState(null);
  const [modelRetry, setModelRetry] = useState(0);
  const [selectedModel, setSelectedModel] = useState("");
  const [selectedResolution, setSelectedResolution] = useState("");
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [previewBroken, setPreviewBroken] = useState(false);
  const [retryingStorage, setRetryingStorage] = useState(false);
  const [pollStalled, setPollStalled] = useState(false);
  const [rerollConfirm, setRerollConfirm] = useState(false);
  const rerollConfirmResolveRef = useRef(null);
  const timer = useRef(null);
  const pollFailures = useRef(0);
  const pollingId = useRef(null);
  const intentKey = useRef(null);
  const generationRef = useRef(null);
  useEffect(() => { generationRef.current = generation; }, [generation]);

  const projectId = project?.id;
  const settleRerollConfirm = (answer) => {
    const resolve = rerollConfirmResolveRef.current;
    rerollConfirmResolveRef.current = null;
    setRerollConfirm(false);
    resolve?.(answer);
  };
  useEffect(() => () => {
    rerollConfirmResolveRef.current?.(false);
    rerollConfirmResolveRef.current = null;
  }, []);

  // The story's gates, each named in words on the panel. Order is
  // the founder's order: the plan first (it is the readiness), then
  // the photo the identity is built from, then the save state —
  // the render reads the SAVED plan, never unsaved text.
  const hasPlan = Boolean(
    String(project?.hook_line || "").trim() && String(project?.script || "").trim()
  );
  const hasPhoto = (project?.assets || []).some(
    (a) => String(a?.kind || "").trim().toLowerCase() === "character_reference"
  );
  const gate = !hasPlan
    ? "Generate the story plan first — a frame renders its plan's words, and there is no plan yet."
    : !hasPhoto
      ? "Add your presenter photo in the direction section — the render is built from it, and without one the model would invent a presenter."
      : hasUnsavedEdits || autosaving
        ? "Your edits are still saving — the render uses the saved plan, so it waits for the save to land."
        : null;

  useEffect(() => {
    let cancelled = false;
    setModels(null);
    setModelError(null);
    api
      .getStudioVideoModels()
      .then((data) => {
        if (cancelled) return;
        setModels(data);
        let saved = "";
        try {
          saved = projectId ? window.localStorage.getItem(modelStorageKey(projectId)) || "" : "";
        } catch {
          saved = "";
        }
        const offered = (data.models || []).some((m) => m.key === saved);
        const nextModel = offered ? saved : data.default || "";
        setSelectedModel(nextModel);
        try {
          if (projectId) {
            const resSaved = window.localStorage.getItem(resolutionStorageKey(projectId)) || "";
            const caps = (data.models || []).find((m) => m.key === nextModel);
            if ((caps?.supported_resolutions || []).includes(resSaved)) {
              setSelectedResolution(resSaved);
            }
          }
        } catch {
          /* a choice that does not persist is still a choice for this render */
        }
      })
      .catch((err) => {
        if (!cancelled) setModelError(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, [projectId, modelRetry]);

  const onPollSettled = useCallback((updated) => {
    onGenerationChange?.(updated);
    return updated.status === "submitted" || updated.status === "generating";
  }, [onGenerationChange]);

  const pollOnce = useCallback(async (id) => {
    try {
      const updated = await api.pollGeneration(id);
      pollFailures.current = 0;
      setPollStalled(false);
      if (onPollSettled(updated)) {
        schedulePollRef.current?.(id);
      }
    } catch {
      // Never retire a live render (ADR 0171): the chain keeps
      // firing at a slower cadence, and from the third consecutive
      // failure the stall notice says checks are being slowed.
      pollFailures.current += 1;
      if (pollFailures.current >= 3) setPollStalled(true);
      schedulePollRef.current?.(id);
    }
  }, [onPollSettled]);

  const schedulePoll = useCallback((id) => {
    if (pollingId.current !== id) {
      pollingId.current = id;
      pollFailures.current = 0;
      setPollStalled(false);
    }
    if (timer.current) clearTimeout(timer.current);
    const delay = pollFailures.current >= 3 ? POLL_INTERVAL_MS * 2 : POLL_INTERVAL_MS;
    timer.current = setTimeout(() => {
      pollOnce(id);
    }, delay);
  }, [pollOnce]);

  const schedulePollRef = useRef(schedulePoll);
  schedulePollRef.current = schedulePoll;

  // A backgrounded tab throttles timers to minutes; on return, poll
  // at once rather than leaving a frozen stage (ADR 0171's rule).
  useEffect(() => {
    const resumePolling = () => {
      if (document.visibilityState !== "visible") return;
      const current = generationRef.current;
      if (!current || (current.status !== "submitted" && current.status !== "generating")) return;
      pollOnce(current.id);
    };
    document.addEventListener("visibilitychange", resumePolling);
    return () => document.removeEventListener("visibilitychange", resumePolling);
  }, [pollOnce]);

  // Adopt the newest generation for THIS project, and keep watching
  // one that is still in flight.
  useEffect(() => {
    let cancelled = false;
    async function load() {
      if (!projectId) return;
      try {
        const data = await api.getGenerations({ studio_project_id: projectId, limit: 1 });
        if (cancelled) return;
        const newest = data.generations?.[0] || null;
        if (newest && newest.studio_project_id && newest.studio_project_id !== projectId) return;
        if (newest) {
          onGenerationChange?.(newest);
          if (newest.status === "submitted" || newest.status === "generating") {
            schedulePoll(newest.id);
          }
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
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectId]);

  // The kit is written by a background task at completion, so a
  // completed row can land a breath before its kit does: re-read
  // the row a few times while the kit is missing, then settle —
  // the kit panel's own Regenerate covers a kit that never comes.
  const kitWatchId = generation?.status === "completed" && !generation?.story_kit
    ? generation.id
    : null;
  useEffect(() => {
    if (!kitWatchId) return undefined;
    let cancelled = false;
    let attempts = 0;
    const tick = async () => {
      attempts += 1;
      try {
        const fresh = await api.getGeneration(kitWatchId);
        if (cancelled) return;
        if (fresh?.story_kit) {
          onGenerationChange?.(fresh);
          return;
        }
      } catch {
        /* best-effort: the kit panel's regenerate is the recovery */
      }
      if (!cancelled && attempts < 6) {
        timer.current = setTimeout(tick, 5000);
      }
    };
    const first = setTimeout(tick, 5000);
    return () => {
      cancelled = true;
      clearTimeout(first);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [kitWatchId]);

  const trackedGenerationId = generation?.id || "";
  useEffect(() => {
    setPreviewBroken(false);
  }, [trackedGenerationId]);

  const handleGenerate = async () => {
    // A second render on a frame the founder has already seen asks
    // first, in the branded dialog (ADR 0212) — the click waits on
    // the promise the dialog settles, so the ask itself spends
    // nothing. One click when there is nothing to lose.
    if (Boolean(generation)) {
      const confirmed = await new Promise((resolve) => {
        rerollConfirmResolveRef.current = resolve;
        setRerollConfirm(true);
      });
      if (!confirmed) return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      if (!intentKey.current) {
        intentKey.current =
          typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
            ? crypto.randomUUID()
            : `story-render-${projectId}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      }
      const created = await api.generateStory(projectId, {
        model: selectedModel || undefined,
        resolution: selectedResolution || undefined,
        // The frame's own seconds (ADR 0228): the endpoint renders
        // exactly this length, so the pick the founder made is the
        // length that bills.
        duration_seconds: Number(project?.duration_seconds) || undefined,
        idempotency_key: intentKey.current,
      });
      intentKey.current = null;
      onGenerationChange?.(created);
      schedulePoll(created.id);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRetry = async () => {
    if (!generation) return;
    setBusy(true);
    setError(null);
    try {
      const created = await api.retryGeneration(generation.id);
      onGenerationChange?.(created);
      schedulePoll(created.id);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRetryStorage = async () => {
    if (!generation) return;
    setRetryingStorage(true);
    setError(null);
    try {
      const saved = await api.retryGenerationStorage(generation.id);
      const fresh = await api.getGeneration(generation.id);
      onGenerationChange?.(fresh);
      const degraded = saved?.storage_error || fresh?.storage_error || "";
      setNotice(
        degraded
          ? `Saved, but not durably: ${degraded}`
          : "Durable copy saved."
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setRetryingStorage(false);
    }
  };

  const capability = models?.models?.find((m) => m.key === selectedModel);
  const inFlight = generation && (generation.status === "submitted" || generation.status === "generating");
  const pieceSeconds = readPieceSeconds(project, null);
  const tooLong = exceedsSinglePass(pieceSeconds, capability);
  const downloadUrl = generation ? durableMediaUrl(generation) : null;
  const saveUrl = generation ? downloadMediaUrl(generation) || downloadUrl : null;
  const posterUrl = generation?.poster_url ? mediaUrl(generation.poster_url) : null;
  const generateLabel = generation ? "Generate another" : "Generate the story";

  return (
    <div className="space-y-3" data-testid="story-render-panel">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={Play}>Render the frame</GroupLabel>
        {generation && <StatusBadge status={generation.status} />}
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="break-words whitespace-pre-wrap">{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert variant="warning">
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {gate && (
        <p role="status" className="text-base text-muted-foreground" data-testid="story-render-gate">
          {gate}
        </p>
      )}

      {models && (
        <div className="space-y-2">
          <label htmlFor="story-gen-model" className="text-sm font-semibold">Model</label>
          <AppSelect
            id="story-gen-model"
            testId="story-gen-model"
            block
            value={selectedModel}
            onChange={(next) => {
              setSelectedModel(next);
              setSelectedResolution("");
              try {
                if (projectId) {
                  window.localStorage.setItem(modelStorageKey(projectId), next);
                  window.localStorage.removeItem(resolutionStorageKey(projectId));
                }
              } catch {
                /* a choice that does not persist is still a choice for this render */
              }
            }}
            disabled={Boolean(inFlight)}
            className={CONTROL_CLASS}
            options={models.models.map((m) => ({
              value: m.key,
              label: `${m.name} — one render, up to ${m.max_duration}s${m.key === models.default ? " (default)" : ""}`,
            }))}
          />
          {(capability?.supported_resolutions || []).length > 0 && (
            <div className="space-y-2 pt-1">
              <label htmlFor="story-gen-resolution" className="text-sm font-semibold">Resolution</label>
              <AppSelect
                id="story-gen-resolution"
                testId="story-gen-resolution"
                block
                value={selectedResolution}
                onChange={(next) => {
                  setSelectedResolution(next);
                  try {
                    if (projectId) {
                      if (next) window.localStorage.setItem(resolutionStorageKey(projectId), next);
                      else window.localStorage.removeItem(resolutionStorageKey(projectId));
                    }
                  } catch {
                    /* a choice that does not persist is still a choice for this render */
                  }
                }}
                disabled={Boolean(inFlight)}
                className={CONTROL_CLASS}
                options={[
                  { value: "", label: `${capability?.resolution || ""} (default)` },
                  ...(capability.supported_resolutions || [])
                    .filter((r) => r !== capability?.resolution)
                    .map((r) => ({ value: r, label: r })),
                ]}
              />
            </div>
          )}
        </div>
      )}

      {!models && (
        <div role={modelError ? "alert" : "status"} className="space-y-2 text-base text-muted-foreground" data-testid="story-render-model-status">
          <p>{modelError ? `Video models could not load: ${modelError}` : "Loading video models before rendering…"}</p>
          {modelError && (
            <Button variant="secondary" size="sm" onClick={() => setModelRetry((value) => value + 1)}>
              Retry loading models
            </Button>
          )}
        </div>
      )}

      <Button
        variant="accent"
        onClick={handleGenerate}
        disabled={busy || Boolean(inFlight) || !models || Boolean(gate) || tooLong || !projectId}
        busy={busy || Boolean(inFlight)}
        data-testid="story-render-generate"
      >
        <Play className="h-4 w-4" />
        {inFlight || busy ? "Generating story" : generateLabel}
      </Button>

      {tooLong && (
        <p role="status" className="text-base text-muted-foreground">
          Choose a model above that supports {pieceSeconds}s, or pick a shorter frame length.
        </p>
      )}

      {pollStalled && inFlight && (
        <div
          role="status"
          data-testid="story-render-poll-stalled"
          className="flex flex-wrap items-center gap-2 text-base text-muted-foreground"
        >
          <p>
            Still rendering — status checks are being slowed down right now, so this
            panel is checking less often. It has not stopped: the finished frame
            will appear here.
          </p>
          <Button
            variant="secondary"
            size="sm"
            onClick={() => {
              const current = generationRef.current;
              if (current) pollOnce(current.id);
            }}
          >
            Check again now
          </Button>
        </div>
      )}

      {(busy || inFlight || (generation && (generation.playback_url || generation.r2_url || generation.video_url))) && (
        <StoryRenderProgress
          status={generation?.status || "submitted"}
          videoUrl={generation?.playback_url || generation?.r2_url || generation?.video_url}
          startedAt={generation?.created_at}
          persistInFlight={Boolean(generation?.persist_in_flight)}
        />
      )}

      {generation?.status === "failed" && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>This render did not finish</AlertTitle>
          <AlertDescription>
            {generation.error_message || generation.error || "The provider did not return a video."}
            <div className="mt-2">
              <Button variant="secondary" size="sm" onClick={handleRetry} disabled={busy} busy={busy}>
                <RotateCcw className="h-3.5 w-3.5" />
                Retry render
              </Button>
            </div>
          </AlertDescription>
        </Alert>
      )}

      {generation && generation.status === "completed" && (
        <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3 text-base">
          <div className="flex flex-wrap items-center gap-2">
            {generation.model && <Badge variant="outline" className="text-xs">{generation.model}</Badge>}
            {generation.duration && (
              <Badge variant="outline" className="text-xs">
                <Clock className="mr-1 h-2.5 w-2.5" />{generation.duration}s
              </Badge>
            )}
          </div>

          {generation.storage_error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Durable copy missing — download this video now</AlertTitle>
              <AlertDescription>
                The render finished, but saving a permanent copy failed
                ({generation.storage_error}). What plays below is the
                provider's temporary copy and it expires — download it now so
                you keep the video either way, then retry the durable save.
                <div className="mt-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRetryStorage}
                    disabled={retryingStorage}
                    busy={retryingStorage}
                  >
                    Retry durable save
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {downloadUrl && (
            <div className="w-full max-w-[280px] space-y-2">
              {previewBroken ? (
                <div className="w-full space-y-2 rounded-xl border border-dashed border-[color:var(--hairline-strong)] p-3">
                  <p className="text-sm text-muted-foreground">
                    Preview unavailable — download it to view.
                  </p>
                </div>
              ) : (
                <video
                  key={`${generation.id}-${downloadUrl}`}
                  src={downloadUrl}
                  controls
                  playsInline
                  controlsList="nodownload noremoteplayback"
                  disablePictureInPicture
                  preload="none"
                  poster={posterUrl || undefined}
                  onError={() => setPreviewBroken(true)}
                  className="w-full rounded-xl border border-[color:var(--hairline)]"
                  data-testid="story-render-video"
                />
              )}
              {saveUrl && (
                <Button variant="secondary" size="sm" asChild>
                  <a href={saveUrl} download>
                    <Download className="h-3.5 w-3.5" />
                    Download MP4
                  </a>
                </Button>
              )}
            </div>
          )}
        </div>
      )}

      <GenerateAnotherConfirmDialog
        confirm={rerollConfirm}
        onCancel={() => settleRerollConfirm(false)}
        onConfirm={() => settleRerollConfirm(true)}
      />
    </div>
  );
}
