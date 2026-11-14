import { useCallback, useEffect, useRef, useState } from "react";
import { Link } from "react-router-dom";
import { Button } from "./ui/button";
import { Badge } from "./ui/badge";
import { Textarea } from "./ui/textarea";
import { StatusBadge } from "./StatusBadge";
import { Alert, AlertTitle, AlertDescription } from "./ui/alert";
import { api, getErrorMessage, mediaUrl, downloadMediaUrl, durableMediaUrl } from "../lib/api";
import { recordSignal } from "../lib/feedback";
import { PostKitSection } from "./PostKitSection";
import { CONTROL_CLASS } from "./formControls";
import {
  exceedsSinglePass, readPieceSeconds, singlePassCeiling,
} from "../lib/videoLength";
import {
  Clapperboard, AlertTriangle, Download, RotateCcw,
  Play, Info, Clock, Smartphone, Check, Film, MapPin, Save,
} from "lucide-react";
import { GroupLabel } from "./SectionCard";

/**
 * Paid render progress — the same UI the mock preview used.
 *
 * Three stages, one progress bar, one checklist. Driven by the real
 * generation row, not timers: submitted means the script lock stage,
 * generating means the provider is working the single-pass clip (shown as
 * the final "Stitching one clip" stage at 85%, matching the capture).
 * No mock frame, no replay, no hypothetical copy — this only renders while
 * a paid render is in flight.
 */
const STAGES = [
  "Locking your approved script",
  "Rendering hook + story in one pass",
  "Stitching one clip",
];

function stageLabel(status, hasUrl) {
  if (hasUrl) return "Done";
  if (status === "generating") return "Stitching one clip";
  if (status === "submitted") return "Locking your approved script";
  if (status === "completed") return "Done";
  if (status === "failed") return "Failed";
  return "Rendering hook + story in one pass";
}

function PaidRenderProgress({ status, modelName, videoUrl }) {
  const hasUrl = Boolean(videoUrl);
  const isDone = status === "completed" || hasUrl;
  const stageIndex = isDone ? 3 : status === "generating" ? 2 : 0;
  const progress = isDone ? 100 : status === "generating" ? 85 : 25;
  return (
    <div className="space-y-3" aria-live="polite" data-testid="paid-render-progress">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={Film}>Render in progress — paid render</GroupLabel>
      </div>
      <div className="flex items-center justify-between gap-2">
        <p className="text-sm font-semibold">{stageLabel(status, hasUrl)}…</p>
        <span className="text-xs text-muted-foreground">{progress}%</span>
      </div>
      <div
        role="progressbar"
        aria-valuemin={0}
        aria-valuemax={100}
        aria-valuenow={progress}
        aria-label="Paid render progress"
        className="h-2 w-full overflow-hidden rounded-full bg-[color:var(--indigo-8)]"
      >
        <div
          className="h-full rounded-full bg-gradient-to-r from-[color:var(--brand-indigo)] to-[color:var(--brand-indigo-dark)] transition-[width] duration-500"
          style={{ width: `${progress}%` }}
        />
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
 * The ready gate stays. It is the thing standing
 * between an unreviewed plan and the render, and nothing about making the
 * render a single job weakened it.
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

/** localStorage key holding one project's chosen video model. */
function modelStorageKey(projectId) {
  return `studio-video-model:${projectId}`;
}

function resolutionStorageKey(projectId) {
  return `studio-video-resolution:${projectId}`;
}

export function GenerationPanel({ project, onGenerationChange, onProjectChange, hasUnsavedEdits = false, onNavigate }) {
  const [models, setModels] = useState(null);
  const [modelError, setModelError] = useState(null);
  const [modelRetry, setModelRetry] = useState(0);
  const [selectedModel, setSelectedModel] = useState("");  const [generation, setGeneration] = useState(null);
  // A per-render resolution override, only for models that offer a choice.
  // "" means the catalog default; anything else must be one of the model's
  // supported_resolutions or the server refuses the render.
  const [selectedResolution, setSelectedResolution] = useState("");
  const [busy, setBusy] = useState(false);
  // Set when the finished clip cannot be played inline, so the panel replaces a
  // dead-looking player with the truth instead of leaving a dead control.
  const [previewBroken, setPreviewBroken] = useState(false);
  const [retryingPreview, setRetryingPreview] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [retryingStorage, setRetryingStorage] = useState(false);
  // The Location editor. The plan's `visual_direction` is the single source of
  // truth for where the video happens; editing it here saves it (and rewrites
  // the strategy's place-bearing lines server-side) without leaving the render
  // step. The draft follows the saved value so a re-render never shows a stale
  // local edit.
  const [locationDraft, setLocationDraft] = useState("");
  const [savingLocation, setSavingLocation] = useState(false);
  const [locationNote, setLocationNote] = useState(null);
  const timer = useRef(null);
  const generationRef = useRef(null);
  // Keep generationRef current so visibility resumes can read the live row
  // without re-subscribing.
  useEffect(() => { generationRef.current = generation; }, [generation]);

  const projectId = project?.id;
  const ready = project?.status === "ready_for_generation";
  // The render gate refuses words that cannot be spoken in the piece's seconds,
  // and that verdict is recomputed from the live plan — so the button has to
  // answer to it too. Without this the founder clicks an enabled Generate into
  // a 409, which is the gate working and the UI lying about it.
  const overflowBlocked = (project?.spoken_overflow?.dropped_chars || 0) > 0;
  const blocked = overflowBlocked;
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
  // A rebuild is owed whenever a strategy exists but no longer matches what
  // it would render: the plan moved after the build (staleStrategy) or the
  // angle did (angleStale). The remedies below offer exactly that rebuild —
  // except with no angle picked at all, where the standing remedy is the
  // angle pick itself and the disabled button stays as the gate it names.
  const rebuildRequired = !noAngle && (staleStrategy || angleStale);
  // The same one-action rule before a strategy exists at all: the render
  // follows the strategy, so without one the generate control cannot
  // function — it stays unrendered beside the strategy panel's bright
  // build control, and the note below names the step. The no-angle state
  // is carved out: there the standing remedy is the angle pick itself,
  // and the disabled button stays as the gate that names it.
  const strategyMissing = !noAngle && !hasStrategy;

  // The presenter must be the founder's own face. Judged by the asset KIND on
  // what is attached, matching the server: a project can legitimately hold other
  // rows, and an attached photo of the wrong kind is still no presenter.
  const noPhoto = !(project?.assets || []).some(
    (a) => String(a?.kind || "").trim().toLowerCase() === "character_reference"
  );

  // Every refusal the panel can name must also name its remedy: the step and
  // the control that fixes it. A block with no jump button is a wall, not a
  // guard — the founders who hit it stop trusting the panel and ask whether
  // the app broke. The wizard can only jump within this page, so the remedies
  // are:
  //   noAngle        -> Audience & template (angle pick)
  //   blockedOnAssets -> Audience & template (photo requirement)
  //   hasUnsavedEdits -> save edits on Review & submit (same page)
  //   angleStale      -> rebuild the strategy on Review & submit (same page)
  //   staleStrategy   -> rebuild the strategy on Review & submit (same page)
  //   !ready          -> Review & submit (same page, save the plan)
  // Anything the panel cannot name here (overflow, camera-incompatible,
  // tooLong, model load) is self-evident from its own alert, so it needs no
  // jump. When this page cannot navigate between steps, the block falls
  // through with no jump — the button is still disabled with the reason.
  const remedies = [];
  if (noAngle) remedies.push({ label: "Pick an audience angle first", action: "goto-angle" });
  else if (angleStale || staleStrategy) {
    // One label for the rebuild everywhere it is offered (the strategy
    // panel's button reads the same): the reason it is owed lives in the
    // alert above, and two phrasings of one action read as two actions.
    remedies.push({ label: "Rebuild strategy", action: "rebuild-strategy" });
  }
  if (noPhoto) remedies.push({ label: "Attach the presenter photo", action: "goto-photo" });
  if (!ready && !noPhoto && !noAngle && !staleStrategy && !angleStale) {
    remedies.push({ label: "Review and save the plan", action: "save-edits" });
  }

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
    setModels(null);
    setModelError(null);
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
        const nextModel = offered ? saved : data.default || "";
        setSelectedModel(nextModel);
        // Same rule for the resolution choice, validated against the model
        // actually selected: a saved value from another model (or a retired
        // option) falls back to that model's default rather than sticking.
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

  // schedulePoll is declared BEFORE the effect that depends on it. A dependency
  // array is evaluated during render, so listing this effect above the `const`
  // read the binding in its temporal dead zone and threw a ReferenceError on
  // every mount — which the app-wide ErrorBoundary turned into a blank screen
  // on every route. scripts/check-render-smoke.cjs mounts this component, so
  // that class of ordering mistake fails the gate instead of shipping.
  //
  // Consecutive poll failures and the generation they belong to. One failed
  // Polling budget. A rate-limited poll is NEVER counted as an outage
  // failure and NEVER escalates the banner — 429 means the render is healthy
  // at the provider (see server ADR 0061: 429 is throttling, never a render
  // failure). Sustained 429s are still BOUNDED: after MAX_POLL_429s the
  // panel surfaces a visible "still rendering — check History once" state
  // instead of looping silently at 85% forever. Polling stops permanently
  // ONLY on a terminal row status; a transient network/5xx failure walks
  // the outage budget and, once spent, names History as the next step —
  // never a frozen progress bar.
  //
  // The poll chain is the only thing that flips the panel off 85%. If the
  // chain dies — tab backgrounded past browser timer floors, unmount, a
  // missed timeout — the founder is left staring at a frozen bar while the
  // backend keeps rendering and History later shows the clip completed.
  // So every generation advance re-arms the chain, and a visibility return
  // forces an immediate poll: the first poll after the tab returns the
  // terminal row, not another silent wait.
  const pollFailures = useRef(0);
  const poll429s = useRef(0);
  const pollingId = useRef(null);
  const pollTimedOut = useRef(false);
  const MAX_POLL_FAILURES = 5;
  const MAX_POLL_429s = 20;

  const onPollSettled = useCallback((updated) => {
    setGeneration(updated);
    onGenerationChange?.(updated);
    return updated.status === "submitted" || updated.status === "generating";
  }, [onGenerationChange]);

  const pollOnce = useCallback(async (id) => {
    try {
      const updated = await api.pollGeneration(id);
      pollFailures.current = 0;
      poll429s.current = 0;
      if (onPollSettled(updated)) {
        schedulePollRef.current?.(id);
      }
    } catch (err) {
      if (err?.response?.status === 429) {
        poll429s.current += 1;
        try {
          const data = await api.getGenerations({ studio_project_id: projectId, limit: 1 });
          const newest = data.generations?.[0] || null;
          if (newest && newest.id !== id) {
            onPollSettled(newest);
            if (newest.status === "submitted" || newest.status === "generating") {
              schedulePollRef.current?.(newest.id);
            }
            return;
          }
          if (newest && newest.id === id && newest.status !== "submitted" && newest.status !== "generating") {
            onPollSettled(newest);
            return;
          }
        } catch {
          /* best-effort */
        }
        if (poll429s.current >= MAX_POLL_429s) {
          pollTimedOut.current = true;
          setError(
            "The render is still in progress at the video provider but the studio is being rate-limited. The clip is not lost; it will appear in History once the provider finishes. Check History for this project; the panel will not loop forever."
          );
          return;
        }
        schedulePollRef.current?.(id);
        return;
      }
      pollFailures.current += 1;
      if (pollFailures.current >= MAX_POLL_FAILURES) {
        pollTimedOut.current = true;
        setError(
          `We couldn't check the render status after ${MAX_POLL_FAILURES} tries: `
          + `${getErrorMessage(err)}. The render may still be running — check `
          + "History for this project. The panel will not loop forever."
        );
      } else {
        schedulePollRef.current?.(id);
      }
    }
  }, [onPollSettled, projectId]);

  const schedulePoll = useCallback((id) => {
    if (pollingId.current !== id) {
      pollingId.current = id;
      pollFailures.current = 0;
      poll429s.current = 0;
      pollTimedOut.current = false;
    }
    if (pollTimedOut.current) return;
    if (timer.current) clearTimeout(timer.current);
    const delay = poll429s.current > 0 ? Math.min(POLL_INTERVAL_MS * (1 + poll429s.current), 60_000) : POLL_INTERVAL_MS;
    timer.current = setTimeout(() => {
      pollOnce(id);
    }, delay);
  }, [pollOnce]);

  // Keep the ref current so pollOnce (which runs outside render) always calls
  // the latest scheduler.
  const schedulePollRef = useRef(schedulePoll);
  schedulePollRef.current = schedulePoll;

  // A backgrounded tab throttles every setTimeout to minutes; when the
  // founder returns the chain may already be dead. Force one poll on
  // visibility return, and re-arm the chain if the row is still in flight.
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

  // A HeyGen render that the polling chain died on leaves the panel frozen
  // at 85% while History shows completed. Re-arm the chain whenever the
  // panel mounts or the project changes and the newest row is still in
  // flight: this catches the "reload kept showing the message" case, where
  // getGenerations returned the in-flight row but the fetch died before
  // schedulePoll ran.
  useEffect(() => {
    const current = generation;
    if (!current) return;
    if (current.status !== "submitted" && current.status !== "generating") return;
    if (!timer.current) {
      schedulePoll(current.id);
    }
  }, [generation, schedulePoll]);


  // A new render's preview starts unbroken: a load error on the previous
  // clip must not hide this one's player before it has even been tried.
  const trackedGenerationId = generation?.id || "";
  useEffect(() => {
    setPreviewBroken(false);
  }, [trackedGenerationId]);

  // The Location draft follows the saved plan's value whenever the project
  // reloads — an autosave elsewhere, a sync, or this panel's own save — so the
  // input never shows text that is not what will render. `location` is the
  // canonical field; `visual_direction` is the legacy mirror.
  useEffect(() => {
    setLocationDraft(project?.location || project?.visual_direction || "");
  }, [projectId, project?.location, project?.visual_direction]);

  const handleSaveLocation = async () => {
    const value = locationDraft.trim();
    if (value === (project?.location || project?.visual_direction || "").trim()) return;
    setSavingLocation(true);
    setError(null);
    setLocationNote(null);
    try {
      const updated = await api.updateStudioProject(projectId, { location: value });
      // Same rule as every other saved edit on Review: a content save
      // re-marks the project ready, because the founder reviewed the exact
      // text they saved. A server refusal (a location the scene
      // checks reject) is reported rather than hidden, and the draft state stands.
      let settled = updated;
      try {
        settled = await api.markProjectReady(updated.id);
      } catch (err) {
        setError(getErrorMessage(err));
      }
      onProjectChange?.(settled);
      const change = updated?.location_change || {};
      const changed = change.changed || [];
      const blocked = change.blocked || [];
      const parts = [];
      if (changed.length) {
        parts.push(`Rewritten to match: ${changed.join(", ")}.`);
      }
      if (blocked.length) {
        // Spoken words are never rewritten; a props or movement list that
        // cannot hold everything is reported instead of cut (ADR 0092).
        parts.push(
          `Something still disagrees (${blocked
            .map((b) => `${b.field} ${b.reason}`)
            .join("; ")}). Fix it on Review & submit, or the render will refuse.`
        );
      }
      setLocationNote(parts.join(" ") || "Location saved.");
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setSavingLocation(false);
    }
  };

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
      //
      // Resolution IS sent, but only an explicit pick: omitted means the
      // model's catalog default, so a default change server-side never needs
      // a client change to follow it.
      const created = await api.generateVideo(projectId, {
        model: selectedModel || undefined,
        resolution: selectedResolution || undefined,
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

  // A preview error is often just an expired signed URL — the signature is
  // minted when the row is read and the panel stops polling once the render
  // completes, so a clip that finished a while ago can hold a dead link
  // while the clip itself is fine. Retry means refetching the row (fresh
  // signatures) and mounting the player again, not declaring it gone.
  const handleRetryPreview = async () => {
    if (!projectId) return;
    setRetryingPreview(true);
    try {
      const data = await api.getGenerations({ studio_project_id: projectId, limit: 1 });
      const newest = data.generations?.[0] || null;
      if (newest) setGeneration(newest);
    } catch {
      /* best-effort: clearing the flag below still remounts the player */
    } finally {
      setPreviewBroken(false);
      setRetryingPreview(false);
    }
  };

  const capability = models?.models?.find((m) => m.key === selectedModel);
  const cameraIncompatible = project?.camera_setup === "fixed" && capability?.identity_via_first_frame;
  const inFlight = generation && (generation.status === "submitted" || generation.status === "generating");
  // The playable URL follows the same rule History uses (durableMediaUrl):
  // the signed playback route first, then the durable copy. Never the
  // provider's temporary link in video_url — the browser cannot fetch it
  // (it needs a bearer token, then it expires), so a player or download
  // pointed at it never loads, and a completed render looked broken in
  // this panel while the same clip played fine in History.
  const downloadUrl = generation ? durableMediaUrl(generation) : null;
  // The save must originate same-origin: the playback href above is a raw
  // cross-origin R2 locator whenever the durable copy sits in R2, and browsers
  // ignore `download` there — the button opened an R2 error page instead of
  // saving. downloadMediaUrl splices the signed same-origin /download route,
  // whose signature is minted fresh by the server on every read. Falls back
  // to the playback href only when no same-origin source exists at all.
  const saveUrl = generation ? downloadMediaUrl(generation) || downloadUrl : null;
  // Preview through the fresh signed same-origin route for the same reason:
  // a raw R2 href fails on play (masked until then by preload="none").
  // durableMediaUrl already prefers that route, so the preview and the
  // download read the same source and cannot disagree about playability.
  const previewUrl = downloadUrl;
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
    /* This panel is an aside inside the step card, so it is the LAST border in
       the stack: everything grouped under it is separated by a hairline, not by
       another bordered box. The pre-render summary, "what you have", and the
       Product Demo call-out were each an inset or an indigo box inside the
       inset — three boxes in a box, each with its own 12px gutter and radius,
       which is what made this panel read as a stack of frames rather than one
       panel. They are divider-separated groups now, the level
       design_guidelines.md §4 calls "group inside a card". */
    <div className="inset-panel space-y-3">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <GroupLabel icon={Clapperboard}>Render your Hook + Story</GroupLabel>
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

      {/* No photograph attached. Named here rather than left to the server's
          409, because this is the panel where the founder decides to generate:          telling them before the click is the difference between a rule they
          have not met yet and an app that appears to have broken. */}
      {noPhoto && (
        <Alert variant="destructive">
          <AlertTitle>No photo attached</AlertTitle>
          <AlertDescription>
            Add a clear photo of the person you want on camera on the Audience &amp; template step. The video model uses it as a presenter reference; rendering stays blocked until it is attached.
          </AlertDescription>
        </Alert>
      )}
      {!ready && !noPhoto && (
        <p className="text-base text-muted-foreground">
          Review and save your script plan first. A saved plan is checked before rendering.
        </p>
      )}
      {/* No overflow alert in this panel either: the strategy panel above
          carries the one detailed notice for this state (Kasra's one-notice
          rule). This panel's part of the stop is the disabled Generate
          button — the gate still refuses the render, it just speaks once. */}

      {/* Location, editable here on the render step. The plan's saved location
          is the single source of truth for where the video happens: saving a
          change rewrites the strategy's place-bearing lines to match on the
          server (hook concept, position in frame, what they do, movement,
          lighting, colour palette) and keeps the strategy current, so no
          second tab and no paid rebuild are needed to move the video. Spoken
          lines, wardrobe, props, voice and camera are deliberately untouched. */}
      <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3" data-testid="render-location">
        <GroupLabel icon={MapPin}>Location</GroupLabel>
        <p className="text-sm text-muted-foreground">
          The one place this video happens. Editing it rewrites the hook concept, position in
          frame, what they do, movement, lighting and colour palette to match; your spoken lines,
          wardrobe, props, voice and camera are untouched.
        </p>
        <div className="flex flex-wrap items-end gap-2">
          <div className="min-w-0 flex-1 space-y-1">
            <label htmlFor="render-location" className="text-sm font-semibold">Where it happens</label>
            {/* A place is a sentence, not a single line: a text input cut a
                long Location off at the edge, so the founder could never read
                the whole description they were about to save. The shared
                Textarea wraps and grows with the text. */}
            <Textarea
              id="render-location"
              data-testid="render-location-input"
              rows={2}
              value={locationDraft}
              onChange={(e) => setLocationDraft(e.target.value)}
              disabled={inFlight || savingLocation}
              placeholder="For example: A tidy kitchen with a coffee maker on the counter"
            />
          </div>
          <Button
            variant="secondary"
            size="sm"
            onClick={handleSaveLocation}
            disabled={
              inFlight
              || savingLocation
              || !projectId
              || locationDraft.trim() === (project?.location || project?.visual_direction || "").trim()
            }
            busy={savingLocation}
          >
            <Save className="h-3.5 w-3.5" /> {savingLocation ? "Saving" : "Save location"}
          </Button>
        </div>
        {!locationNote && (
          <p className="text-sm text-muted-foreground">
            Lighting and time of day live in the strategy panel above; saving moves only what matches the place.
          </p>
        )}
        {locationNote && (
          <p className="text-sm text-muted-foreground" data-testid="render-location-note">
            {locationNote}
          </p>
        )}
      </div>

      {models && (
        <div className="space-y-2">
          <label htmlFor="gen-model" className="text-sm font-semibold">Model</label>
          <select
            id="gen-model"
            value={selectedModel}
            onChange={(e) => {
              const next = e.target.value;
              setSelectedModel(next);
              // A resolution picked for another model must not ride along: the
              // server refuses values the new model does not offer, so the
              // select falls back to that model's default.
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
            disabled={inFlight}
            className={CONTROL_CLASS}
          >
            {models.models.map((m) => (
              <option key={m.key} value={m.key}>
                {m.name} — one render, up to {m.max_duration}s{m.key === models.default ? " (default)" : ""}
              </option>
            ))}
          </select>
          {cameraIncompatible && (
            <p className="text-sm text-destructive" role="alert" data-testid="fixed-camera-model-warning">
              This model uses your face photo as its literal first frame. For Fixed camera,
              select a model that accepts an identity reference image, or save Handheld selfie
              and rebuild the strategy. No model is switched automatically.
            </p>
          )}
          {(capability?.supported_resolutions || []).length > 0 && (
            <div className="space-y-2 pt-1">
              <label htmlFor="gen-resolution" className="text-sm font-semibold">Resolution</label>
              <select
                id="gen-resolution"
                value={selectedResolution}
                onChange={(e) => {
                  const next = e.target.value;
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
                disabled={inFlight}
                className={CONTROL_CLASS}
              >
                <option value="">{capability?.resolution || ""} (default)</option>
                {(capability.supported_resolutions || [])
                  .filter((r) => r !== capability?.resolution)
                  .map((r) => (
                    <option key={r} value={r}>{r}</option>
                  ))}
              </select>
            </div>
          )}
        </div>
      )}

      {/* Kasra's rule: one action at a time in Review. While a strategy
          rebuild is owed — or before a strategy exists at all — the
          generate control is not rendered at all: a greyed "Generate the
          video" beside the one bright control that unblocks the render
          reads as two competing actions. The control returns the moment
          a current strategy exists. A render already in flight keeps its
          progress button: hiding that would strand the wait, and the
          rebuild remedies already stand down while one runs. */}
      {((!rebuildRequired && !strategyMissing) || busy || inFlight) && (
        <Button
          variant="accent"
          onClick={handleGenerate}
          disabled={
            busy || inFlight || !models || hasUnsavedEdits || !ready || blocked || tooLong || cameraIncompatible || !projectId || !strategyReady || noPhoto || noAngle
          }
          busy={busy || inFlight}
          data-testid="render-generate-button"
        >
          <Play className="h-4 w-4" />
          {inFlight || busy
            ? "Generating video"
            : generation
              ? "Generate another"
              : "Generate the video"}
        </Button>
      )}

      {remedies.length > 0 && !(busy || inFlight) && (
        <div className="flex flex-wrap gap-2" data-testid="render-remedies">
          {remedies.map((remedy) => (
            <Button
              key={remedy.label}
              variant="accent"
              size="sm"
              className="gap-1.5"
              onClick={() => onNavigate?.(remedy.action)}
            >
              <Play className="h-3.5 w-3.5" />
              {remedy.label}
            </Button>
          ))}
        </div>
      )}

      {hasUnsavedEdits && (
        <p role="status" className="text-base text-muted-foreground" data-testid="render-unsaved-edits">
          Save edits in the script plan above before rendering. The video uses the saved plan, not your unsaved text.
        </p>
      )}
      {!models && (
        <div role={modelError ? "alert" : "status"} className="space-y-2 text-base text-muted-foreground" data-testid="render-model-status">
          <p>{modelError ? `Video models could not load: ${modelError}` : "Loading video models before rendering…"}</p>
          {modelError && (
            <Button variant="secondary" size="sm" onClick={() => setModelRetry((value) => value + 1)}>
              Retry loading models
            </Button>
          )}
        </div>
      )}
      {tooLong && (
        <p role="status" className="text-base text-muted-foreground">
          Choose a model above that supports {pieceSeconds}s, or pick a shorter template on Audience &amp; template and regenerate the plan.
        </p>
      )}
      {noAngle && (
        <Alert variant="destructive">
          <AlertTitle>No audience angle picked</AlertTitle>
          <AlertDescription>
            Pick one on the Audience &amp; template step. The strategy and the render are built around
            it — rendering is blocked until an angle is picked.
          </AlertDescription>
        </Alert>
      )}

      {!strategyReady && (
        <p className="text-base text-muted-foreground">
          {angleStale
            ? "The audience angle changed after this strategy was built. Rebuild it for the angle now picked, then render."
            : staleStrategy
              ? "The plan changed after this strategy was built. Rebuild it so it matches your saved plan, then render."
              : "Read the app-specific strategy above, then generate. It guides the Hook + Story clip and is separate from your filmed product demo."}
        </p>
      )}

      {/* Paid render progress is the stage checklist with a real bar — the
          button's looping sweep alone cannot carry a minutes-long paid wait
          with a stage state, so this stays as the result/queue narrator and
          is not a helper line under an idle CTA. It flips to a checkmark the
          second the row has a playable URL, so a completed render can never
          leave the panel frozen at 85% with History already showing it. */}
      {(busy || inFlight || (generation && (generation.playback_url || generation.r2_url || generation.video_url))) && (
        <PaidRenderProgress
          status={generation?.status || "submitted"}
          modelName={capability?.name || selectedModel || ""}
          videoUrl={generation?.playback_url || generation?.r2_url || generation?.video_url}
        />
      )}

      {generation && (
        <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3 text-base">
          <div className="flex flex-wrap items-center gap-2">
            {generation.model && <Badge variant="outline" className="text-xs">{generation.model}</Badge>}
            {generation.duration && (
              <Badge variant="outline" className="text-xs">
                <Clock className="mr-1 h-2.5 w-2.5" />{generation.duration}s
              </Badge>
            )}
            {generation.attempt > 1 && (
              <Badge variant="outline" className="text-xs">attempt {generation.attempt}</Badge>
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
                    size="sm"                      onClick={handleRetryStorage}
                      disabled={retryingStorage}
                      busy={retryingStorage}
                  >
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
              {/* Finished render: narrow video left, frozen post copy right on
                  wide screens, stacked on narrow ones. Only the post-copy card
                  sits beside the video; votes and Demo + CTA stay full-width below. */}
              <div className="flex flex-col gap-4 sm:flex-row sm:items-start">
                <div className="w-full max-w-[280px] shrink-0 space-y-2">
                  {previewBroken ? (
                    <div className="w-full space-y-2 rounded-xl border border-dashed border-[color:var(--hairline-strong)] p-3">
                      <p className="text-sm text-muted-foreground">
                        Preview unavailable — download it to view.
                      </p>
                      <Button
                        variant="secondary"
                        size="sm"
                        onClick={handleRetryPreview}
                        disabled={retryingPreview}
                        busy={retryingPreview}
                      >
                        Try the preview again
                      </Button>
                    </div>
                  ) : (
                    <video
                      key={`${generation.id}-${previewUrl}`}
                      src={previewUrl}
                      controls
                      playsInline
                      preload="none"
                      poster={posterUrl || undefined}
                      onError={() => setPreviewBroken(true)}
                      className="w-full rounded-xl border border-[color:var(--hairline)]"
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
                </div>
                {/* Frozen post copy for this render; pre-kit renders show nothing. */}
                {generation.post_kit && (
                  <div className="min-w-0 flex-1 space-y-3 sm:border-t sm:border-[color:var(--hairline)] sm:pt-3">
                    <PostKitSection
                      postKit={generation.post_kit}
                      generationId={generation.id}
                    />
                  </div>
                )}
              </div>
              {/* No rating on the render here (ADR 0124): the panel used
                  to carry its own video thumbs, a second whole-video
                  judgment beside History's. The one verdict lives on the
                  finished video's History card, judged as posted. */}
              {/* The native next step. The download above is the finish line for
                  anyone who does not want it: this panel adds nothing to what
                  they already have, changes no gate, and takes nothing away.
                  Inside the wizard it walks to the flow's own finishing step,
                  where this exact render is already loaded in the editor —
                  the wizard's last step IS Demo + CTA now, so leaving the
                  flow to reach it would strand the step the flow ends on.
                  Mounted without the wizard's navigation (a direct mount),
                  it keeps the route link to the standalone editor. */}
              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
                <GroupLabel icon={Smartphone}>Product Demo + CTA</GroupLabel>
                <div className="flex flex-wrap gap-2">
                  {onNavigate ? (
                    <Button variant="accent" size="sm" onClick={() => onNavigate("goto-finish")}>
                      <Smartphone className="h-3.5 w-3.5" /> Open in Demo + CTA
                    </Button>
                  ) : (
                    <Button variant="accent" size="sm" asChild>
                      <Link to={`/demo-cta/${generation.id}`}>
                        <Smartphone className="h-3.5 w-3.5" /> Open in Demo + CTA
                      </Link>
                    </Button>
                  )}
                </div>
                <p className="text-sm text-muted-foreground">
                  This is the hook and the middle. Use it as is, or open it in Demo + CTA
                  to add your demo and call to action — exports save beside the original.
                </p>
              </div>
            </>
          )}

          {generation.status === "failed" && (
            <div className="space-y-2">
              <p className="text-sm text-destructive break-words whitespace-pre-wrap">{generation.error}</p>
              {generation.retryable ? (
                <Button variant="secondary" size="sm" onClick={handleRetry} disabled={busy} busy={busy}>
                  <RotateCcw className="h-3.5 w-3.5" /> Render it again
                </Button>
              ) : (
                <p className="text-sm text-muted-foreground">
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
