import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage, mediaUrl, downloadMediaUrl } from "../lib/api";
import { recordSignal } from "../lib/feedback";
import { RecordResultsNudge } from "./RecordResultsNudge";
import {
  exceedsSinglePass, readPieceSeconds, singlePassCeiling,
} from "../lib/videoLength";
import {
  Loader2, Clapperboard, AlertTriangle, Download, RotateCcw,
  Play, Info, Clock, Smartphone,
} from "lucide-react";

/**
 * The render. One request, one job, one file.
 *
 * A video is a hook and a middle in a single pass. There is no second job, no
 * extension and nothing to join, so this panel has one button and one output —
 * where it used to offer a second render for a length the model could not
 * reach in one pass. That path is gone from the server as well: a request past
 * the ceiling is refused with a 400 rather than split, because handing back a
 * file that is not the video the plan describes is worse than refusing it.
 * What is left for the founder is the demo they record and the close they add,
 * and saying so is part of this panel's job.
 *
 * The claim gate and the ready gate both stay. They are the two things standing
 * between an unreviewed plan and the render, and nothing about making the
 * render a single job weakened either one.
 *
 * A third thing stands there now, and it is built here rather than asked for:
 * the strategy. Without one the render falls back to a generic take with a name
 * in it, and nothing on screen said so — the founder would only find out from
 * the log. It is built automatically on the way to the render they actually
 * asked for, and the panel above shows the result for reading either before or
 * after.
 *
 * If that build fails, the render does NOT proceed. Sending a less specific
 * video than the founder believes they are getting, without being told, is the
 * same dishonesty as silently shortening the piece — which this panel already
 * refuses to do.
 */
const POLL_INTERVAL_MS = 6000;

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

/** localStorage key holding one project's chosen video model. */
function modelStorageKey(projectId) {
  return `studio-video-model:${projectId}`;
}

export function GenerationPanel({ project, onGenerationChange, onProjectChange }) {
  const [models, setModels] = useState(null);
  const [selectedModel, setSelectedModel] = useState("");  const [generation, setGeneration] = useState(null);
  const [busy, setBusy] = useState(false);
  // Set when the finished clip cannot be played inline, so the panel replaces a
  // dead-looking player with the truth instead of leaving a dead control.
  const [previewBroken, setPreviewBroken] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [retryingStorage, setRetryingStorage] = useState(false);
  const timer = useRef(null);

  const projectId = project?.id;
  const ready = project?.status === "ready_for_generation";
  const claimBlocked = project?.safety_report && project.safety_report.passed === false;
  // The render gate refuses words that cannot be spoken in the piece's seconds,
  // and that verdict is recomputed from the live plan — so the button has to
  // answer to it too. Without this the founder clicks an enabled Generate into
  // a 409, which is the gate working and the UI lying about it.
  const overflowBlocked = (project?.spoken_overflow?.dropped_chars || 0) > 0;
  const blocked = claimBlocked || overflowBlocked;
  // A render follows the strategy, so one must exist and must match the plan it
  // was built from. Both checks are the same ones the server makes, so the
  // button is disabled for the real reason instead of letting the founder click
  // into a 409 and wondering what they did wrong.
  //
  // Presence is judged by CONTENT, not by the object's truthiness: the server
  // sends an empty object rather than null for a project with no strategy, and
  // {} is truthy in JS, so `!project.strategy` is false for exactly the
  // projects that need one.
  const hasStrategy = Boolean(project?.strategy?.hook_line);
  const staleStrategy = hasStrategy && project?.strategy_is_current === false;
  // The angle is required: the strategy and the render are built around it.
  // Judged on the saved project, matching the server — the wizard's picked
  // value reaches the row through the normal save before anything here runs.
  const noAngle = !project?.content_angle_id;
  // Same drift the strategy panel names: strategy_is_current only tracks plan
  // versions, so an angle change after the build would otherwise render a
  // strategy describing the wrong video.
  const angleStale =
    hasStrategy &&
    (project?.strategy?.content_angle_id || "") !== (project?.content_angle_id || "");
  const strategyReady = hasStrategy && !staleStrategy && !angleStale;

  // The presenter must be the founder's own face. Judged by the asset KIND on
  // what is attached, matching the server: a project can legitimately hold other
  // rows, and an attached photo of the wrong kind is still no presenter.
  const noPhoto = !(project?.assets || []).some(
    (a) => String(a?.kind || "").trim().toLowerCase() === "character_reference"
  );

  // One click, one render. The key identifies a single INTENT to render and is
  // reused for every retry of that intent, then cleared the moment a render
  // lands so "Generate another" gets a fresh one and can still bill.
  //
  // This is the half that matters: the server refusing a repeat only helps if
  // the repeat carries the same key. Minting a new one per click would close the
  // network-retry hole and leave the double-tap wide open, which is the one a
  // founder actually hits.
  const intentKey = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getStudioVideoModels()
      .then((data) => {
        if (cancelled) return;
        setModels(data);
        // The choice survives a reload, per project. A comparison run on H3 Max
        // used to revert to the H3 default on refresh, so the founder could pay
        // for a clip on a model they had already switched away from. A saved
        // key the server no longer offers falls back to the default rather than
        // sticking the select on a model that cannot render.
        let saved = "";
        try {
          saved = projectId ? window.localStorage.getItem(modelStorageKey(projectId)) || "" : "";
        } catch {
          saved = "";
        }
        const offered = (data.models || []).some((m) => m.key === saved);
        setSelectedModel(offered ? saved : data.default || "");
      })
      .catch(() => {
        if (!cancelled) setModels(null);
      });
    return () => {
      cancelled = true;
    };
  }, [projectId]);

  // schedulePoll is declared BEFORE the effect that depends on it. A dependency
  // array is evaluated during render, so listing this effect above the `const`
  // read the binding in its temporal dead zone and threw a ReferenceError on
  // every mount — which the app-wide ErrorBoundary turned into a blank screen
  // on every route. scripts/check-render-smoke.cjs mounts this component, so
  // that class of ordering mistake fails the gate instead of shipping.
  // Consecutive poll failures and the generation they belong to. One failed
  // poll used to kill the loop outright: a single 502 during a container
  // restart left "Generating..." frozen beside a message promising the page
  // checks back on its own — while nothing checked anything. Transient
  // failures now stay silent and keep polling; only a sustained outage (five
  // in a row) escalates to the error banner. The id guard resets the count
  // when tracking moves to a different generation, so an old outage cannot
  // spend a new render's tolerance.
  const pollFailures = useRef(0);
  const pollingId = useRef(null);
  const MAX_POLL_FAILURES = 5;
  const schedulePoll = useCallback((id) => {
    if (pollingId.current !== id) {
      pollingId.current = id;
      pollFailures.current = 0;
    }
    if (timer.current) clearTimeout(timer.current);
    timer.current = setTimeout(async () => {
      try {
        const updated = await api.pollGeneration(id);
        pollFailures.current = 0;
        setGeneration(updated);
        onGenerationChange?.(updated);
        if (updated.status === "submitted" || updated.status === "generating") {
          schedulePoll(id);
        }
      } catch (err) {
        pollFailures.current += 1;
        if (pollFailures.current >= MAX_POLL_FAILURES) {
          setError(getErrorMessage(err));
        } else {
          schedulePoll(id);
        }
      }
    }, POLL_INTERVAL_MS);
  }, [onGenerationChange]);

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


const handleGenerate = async () => {
    // "Generate another" runs a second render on a video the founder has
    // already seen. Idempotency stops accidental duplicates of one click, not a
    // deliberate click the founder did not mean, so a re-roll asks first. Same
    // window.confirm pattern as the strategy rebuild: one click when there is
    // nothing to lose, two when there is work on it.
    if (Boolean(generation)) {
      const ok =
        typeof window === "undefined" || typeof window.confirm !== "function"
          ? true
          : window.confirm(
              "Generate another video from this plan? This runs a second render. " +
              "The video you already have stays in history."
            );
      if (!ok) return;
    }
    setBusy(true);
    setError(null);
    setNotice(null);
    // "Generate another" re-rolls a video the founder has already seen, which
    // is the rework signal. A first generation is not rework, and a retry is a
    // recovery from a failure rather than a judgment about the result, so
    // neither is recorded.
    const isReroll = Boolean(generation);
    try {
      if (!intentKey.current) {
        intentKey.current =
          typeof crypto !== "undefined" && typeof crypto.randomUUID === "function"
            ? crypto.randomUUID()
            : `render-${projectId}-${Date.now()}-${Math.random().toString(36).slice(2)}`;
      }
      // No strategy is built here. This path used to build one and render in
      // the same click, which made the "read the strategy" copy above cosmetic:
      // the founder never got a chance to see it before the render went.
      // Building is a separate, text-only action on HookContinuityPanel
      // directly above this one, and the button below stays disabled until a
      // current strategy exists, so the review is a real step rather than a
      // race the founder loses.
      //
      // No duration is sent. The length is computed from the template, the
      // project carries it, and the response has no plan to return because
      // there is no second pass to arrange - so there is nothing here to
      // reconcile afterwards and nothing to warn about.
      const created = await api.generateVideo(projectId, {
        model: selectedModel || undefined,
        idempotency_key: intentKey.current,
      });
      // The intent is spent. A later deliberate re-roll mints its own key, so
      // this only ever suppresses a genuine duplicate of THIS render.
      intentKey.current = null;
      setGeneration(created);
      onGenerationChange?.(created);
      if (isReroll) {
        recordSignal("video_regenerated", "regenerated", {
          studio_project_id: projectId,
          generation_id: created.id,
          template_id: created.template_id,
          brand_profile_id: created.brand_profile_id,
        });
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

  const handleRetryStorage = async () => {
    if (!generation) return;
    setRetryingStorage(true);
    setError(null);
    try {
      const saved = await api.retryGenerationStorage(generation.id);
      // The endpoint returns only the save result, so re-read the row: the
      // alert above keys off storage_error, and only a fresh read clears it.
      const fresh = await api.getGeneration(generation.id);
      setGeneration(fresh);
      onGenerationChange?.(fresh);
      // "Durable copy saved." was a lie in one case. When the cloud upload fails
      // the server falls back to serving the local file, and on this host local
      // means the container's ephemeral disk -- so the clip plays now and is
      // gone on the next deploy. That is not a durable save, and the founder
      // has to be the one who decides whether to spend a retry on it.
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
  const downloadUrl = generation ? mediaUrl(generation.r2_url || generation.video_url) : null;
  // The save must originate same-origin: the playback href above is a raw
  // cross-origin R2 locator whenever the durable copy sits in R2, and browsers
  // ignore `download` there — the button opened an R2 error page instead of
  // saving. downloadMediaUrl splices the signed same-origin /download route,
  // whose signature is minted fresh by the server on every read. Falls back
  // to the playback href only when no same-origin source exists at all.
  const saveUrl = generation ? downloadMediaUrl(generation) || downloadUrl : null;
  // Preview through the fresh signed same-origin route for the same reason:
  // a raw R2 href fails on play (masked until then by preload="none").
  const previewUrl = generation?.playback_url ? mediaUrl(generation.playback_url) : downloadUrl;
  const posterUrl = generation?.poster_url ? mediaUrl(generation.poster_url) : null;
  // The length this project will render at, and whether the selected model can
  // do it in one pass. Shown before the click because the endpoint refuses
  // anything longer with a 400: the founder should read that here rather than
  // spend a click to meet a raw error body. It is a prediction, not the
  // guarantee — the endpoint still decides.
  const pieceSeconds = readPieceSeconds(project, null);
  const ceiling = singlePassCeiling(capability);
  const tooLong = exceedsSinglePass(pieceSeconds, capability);

  return (
    <div className="space-y-3 rounded-2xl border border-[color:var(--hairline)] p-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="flex items-center gap-2 font-display text-sm font-semibold">
          <Clapperboard className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          Render your Hook + Story
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

      {/* No photograph attached. Named here rather than left to the server's
          409, because this is the panel where the founder decides to generate:          telling them before the click is the difference between a rule they
          have not met yet and an app that appears to have broken. */}
      {noPhoto && (
        <Alert variant="destructive">
          <AlertTitle>No photo attached</AlertTitle>
          <AlertDescription>
            Add a clear photo of the person you want on camera on the Template &amp; photo step. The video model uses it as a presenter reference; without it, the presenter may be invented.
          </AlertDescription>
        </Alert>
      )}
      {!ready && !noPhoto && (
        <p className="text-sm text-muted-foreground">
          Review and save your script plan first. A saved plan is checked before rendering.
        </p>
      )}
      {claimBlocked && (
        <Alert variant="destructive">
          <AlertTitle>Prohibited claim present</AlertTitle>
          <AlertDescription>
            Fix the flagged claim in the script above. Generation is blocked until the claim
            check passes.
          </AlertDescription>
        </Alert>
      )}
      {overflowBlocked && (
        <Alert variant="destructive" data-testid="generate-overflow-blocked">
          <AlertTitle>Script too long for this piece</AlertTitle>
          <AlertDescription>
            Your approved script has {project.spoken_overflow.dropped_chars} characters that do not
            fit in the {project.spoken_overflow.middle_seconds}s middle. A generated plan is trimmed
            to fit on arrival, so this is your own edit above — shorten it, or press Regenerate plan
            on the Review step, then rebuild the strategy and generate.
          </AlertDescription>
        </Alert>
      )}

      {models && (
        <div className="space-y-1.5">
          <label htmlFor="gen-model" className="text-sm font-medium">Model</label>
          <select
            id="gen-model"
            value={selectedModel}
            onChange={(e) => {
              const next = e.target.value;
              setSelectedModel(next);
              try {
                if (projectId) window.localStorage.setItem(modelStorageKey(projectId), next);
              } catch {
                /* a choice that does not persist is still a choice for this render */
              }
            }}
            disabled={inFlight}
            className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            {models.models.map((m) => (
              <option key={m.key} value={m.key}>
                {m.name} — one render, up to {m.max_duration}s{m.key === models.default ? " (default)" : ""}
              </option>
            ))}
          </select>
        </div>
      )}

      <Button
        variant="brand"
        onClick={handleGenerate}
        disabled={
          busy || inFlight || !ready || blocked || tooLong || !projectId || !strategyReady || noPhoto || noAngle
        }
      >
        {busy || inFlight ? <Loader2 className="h-4 w-4 animate-spin" /> : <Play className="h-4 w-4" />}
        {inFlight
          ? "Generating..."
          : generation
            ? "Generate another"
            : "Generate the video"}
      </Button>

      {noAngle && (
        <Alert variant="destructive">
          <AlertTitle>No audience angle picked</AlertTitle>
          <AlertDescription>
            Pick one on the Audience &amp; goal step. The strategy and the render are built around
            it — without one the piece falls back to generic framing.
          </AlertDescription>
        </Alert>
      )}

      {!strategyReady && (
        <p className="text-sm text-muted-foreground">
          {angleStale
            ? "The audience angle changed after this strategy was built. Rebuild it for the angle now picked, then render."
            : staleStrategy
              ? "The plan changed after this strategy was built. Rebuild it so it matches your saved plan, then render."
              : "Read the app-specific strategy above, then generate. It guides the Hook + Story clip and is separate from your filmed product demo."}
        </p>
      )}

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
          </div>

          {/* A storage failure used to be a muted line here, so a video that would
              not load later looked like a playback bug rather than a failed
              upload. It is now the loudest thing on the panel, because the
              stakes are expiry: the clip above is the provider's temporary
              copy, and once it lapses with no durable copy the render is gone. The
              retry endpoint existed but no UI called it, so the only recovery
              was one the founder could not reach. */}
          {generation.storage_error && (
            <Alert variant="destructive">
              <AlertTriangle className="h-4 w-4" />
              <AlertTitle>Durable copy missing — download this video now</AlertTitle>
              <AlertDescription>
                The render finished, but saving a permanent copy failed
                ({generation.storage_error}). What plays above is the
                provider's temporary copy and it expires — download it now so
                you keep the video either way, then retry the durable save.
                <div className="mt-2">
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleRetryStorage}
                    disabled={retryingStorage}
                  >
                    {retryingStorage && <Loader2 className="mr-1 h-3 w-3 animate-spin" />}
                    Retry durable save
                  </Button>
                </div>
              </AlertDescription>
            </Alert>
          )}

          {generation.status === "completed" && downloadUrl && (
            <>
              {/* Says so when the clip cannot be played here. A player that
                  renders its first frame and then does nothing on click looks
                  like a broken app; the truth is usually a source the browser
                  cannot stream (an expired provider link), and the download is
                  the way through either way. */}
              {previewBroken ? (
                <p className="w-full max-w-[280px] rounded-xl border border-dashed border-[color:var(--hairline-strong)] p-3 text-xs text-muted-foreground">
                  Preview unavailable — download it to view.
                </p>
              ) : (
                <video
                  src={previewUrl}
                  controls
                  playsInline
                  preload="none"
                  poster={posterUrl || undefined}
                  onError={() => setPreviewBroken(true)}
                  className="w-full max-w-[280px] rounded-xl border border-[color:var(--hairline)]"
                />
              )}
              <div className="flex flex-wrap gap-2">
                <Button variant="secondary" size="sm" asChild>
                  <a
                    href={saveUrl}
                    download
                    onClick={() => recordSignal("video_downloaded", "downloaded", {
                      brand_profile_id: generation?.brand_profile_id || "",
                      studio_project_id: generation?.studio_project_id || "",
                      generation_id: generation?.id || "",
                      template_id: generation?.template_id || "",
                    })}
                  >
                    <Download className="h-3.5 w-3.5" /> Download MP4
                  </a>
                </Button>
              </div>
              {/* What they got, and what is still theirs to do. The old copy here
                  promised a call to action on an end card, which made this file
                  look finished. It is not: the middle deliberately ends where
                  the presenter would reach for their phone, so the demo and the
                  close are both outside it. */}
              <div className="space-y-1 rounded-xl border border-[color:var(--hairline)] p-3">
                <span className="eyebrow block">What you have, and what is left</span>
                <p className="text-xs text-muted-foreground">
                  This file is the hook and the middle, ending where viewers reach for their
                  phones. Attach your own demo next, then add your own call to action. No text
                  appears on screen — nothing is published for you.
                </p>
              </div>

              {/* The native next step. The download above is the finish line for
                  anyone who does not want it: this panel adds nothing to what
                  they already have, changes no gate, and takes nothing away. It
                  answers a question the copy above already raises — "attach your
                  own demo next" — by opening the native editor for this exact
                  render, in this app, rather than leaving the founder to find
                  it elsewhere. */}
              <div className="space-y-2 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-3">
                <span className="eyebrow block">Product Demo + CTA</span>
                <p className="text-xs text-muted-foreground">
                  Use this video as is, or open it in Demo + CTA to add your demo in a phone
                  mockup and your call to action. Exports save beside the original in History.
                </p>
                <div className="flex flex-wrap gap-2">
                  <Button variant="brand" size="sm" asChild>
                    <Link to={`/demo-cta/${generation.id}`}>
                      <Smartphone className="h-3.5 w-3.5" /> Open in Demo + CTA
                    </Link>
                  </Button>
                </div>
              </div>
              <RecordResultsNudge
                generationId={generation?.id}
                recorded={Boolean(generation?.performance)}
              />
            </>
          )}

          {generation.status === "failed" && (
            <div className="space-y-2">
              <p className="text-xs text-destructive">{generation.error}</p>
              {generation.retryable ? (
                <Button variant="secondary" size="sm" onClick={handleRetry} disabled={busy}>
                  <RotateCcw className="h-3.5 w-3.5" /> Render it again
                </Button>
              ) : (
                <p className="text-xs text-muted-foreground">
                  This failure is not retryable — change the script or model and generate again.
                </p>
              )}
            </div>
          )}

          </div>
      )}
    </div>
  );
}

export default GenerationPanel;
