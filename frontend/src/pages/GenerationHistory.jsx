import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import EmptyState from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { AppPicker, PILL_SELECT_CLASS } from "../components/AppPicker";
import { GroupLabel, SectionHeading } from "../components/SectionCard";
import { Skeleton } from "../components/ui/skeleton";
import { api, getErrorMessage, durableMediaUrl, downloadMediaUrl, mediaUrl } from "../lib/api";
import { FactChip, FactList } from "../components/FactChip";
import { ComponentThumbs } from "../components/ComponentThumbs";
import { recordSignal } from "../lib/feedback";
import { sentenceCase } from "../lib/copyCase";
import {
  History as HistoryIcon,
  Loader as Loader2,
  TriangleAlert as AlertTriangle,
  Download,
  Trash as Trash2,
  RotateCcw,
  ChevronRight,
  ChevronDown,
  ChevronUp,
  Film,
  Info,
  X,
  Smartphone,
  Target,
  Briefcase,
  Clapperboard,
  GripHorizontal,
} from "lucide-react";

/**
 * How far the tab has to travel before a drag counts as an expand.
 *
 * Short enough that one thumb-flick opens the card, long enough that a shaky
 * click — a few pixels of drift while the button is being pressed — still
 * resolves to the click it looked like. The commit threshold is a fraction of
 * it so the tab follows the pointer and then finishes the gesture.
 */
const DRAG_COMMIT_PX = 56;
const DRAG_COMMIT_RATIO = 0.6;

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * A render timestamp that never reads "Invalid Date".
 *
 * Old rows can carry a created_at the browser cannot parse; the previous code
 * rendered whatever Date produced, so a corrupt timestamp showed up as the
 * literal words "Invalid Date" in the fact row. An unparseable date contributes
 * no fact, so it contributes no chip.
 */
function formatRenderDate(value) {
  const t = Date.parse(value);
  if (Number.isNaN(t)) return "";
  return new Date(t).toLocaleString();
}

function DetailRow({ label, children }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="space-y-1">
      <span className="eyebrow block">{label}</span>
      <div className="text-sm leading-[22px] text-foreground/90">{children}</div>
    </div>
  );
}

/**
 * Everything about one render that the history row deliberately leaves out.
 *
 * The list stays light on purpose, but "why does this video look like this"
 * is answerable only from the prompt and the script it was built from.
 * Those two together are the audit trail for a claim in a published video,
 * so they belong one click away rather than only in the database.
 */
function GenerationDetails({ generationId, onClose }) {
  const [detail, setDetail] = useState(null);
  const [error, setError] = useState(null);
  const closeRef = useRef(null);

  useEffect(() => {
    let cancelled = false;
    api.getGeneration(generationId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err) => { if (!cancelled) setError(getErrorMessage(err)); });
    return () => { cancelled = true; };
  }, [generationId]);

  // Esc closes, matching the row drawer below. Focus lands on Close when the
  // modal opens so keyboard users start inside it instead of behind it.
  useEffect(() => {
    closeRef.current?.focus?.();
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onClose();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [onClose]);

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Generation details"
      onClick={onClose}
    >
      <div
        className="surface my-8 w-full max-w-2xl space-y-4 rounded-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <SectionHeading icon={Film}>Generation details</SectionHeading>
          <Button ref={closeRef} variant="ghost" size="sm" onClick={onClose} aria-label="Close details">
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
        {!detail && !error && (
          <div className="space-y-2" aria-label="Loading details">
            <Skeleton className="h-4 w-1/2" />
            <Skeleton className="h-4 w-3/4" />
          </div>
        )}

        {detail && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-3">
              <DetailRow label="Model">{detail.model}</DetailRow>
              <DetailRow label="Status">{humanize(detail.status)}</DetailRow>
              <DetailRow label="Script version">v{detail.script_version}</DetailRow>
              <DetailRow label="Template version">v{detail.template_version}</DetailRow>
              <DetailRow label="Attempt">{detail.attempt}</DetailRow>
              <DetailRow label="Objective">
                {detail.objective ? humanize(detail.objective) : null}
              </DetailRow>
            </div>

            {detail.hook_line && (
              <DetailRow label="Hook">{sentenceCase(detail.hook_line)}</DetailRow>
            )}

            {detail.script && (
              <DetailRow label="Script as generated">
                <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-xl bg-secondary/40 p-4 text-sm">
                  {sentenceCase(detail.script)}
                </pre>
              </DetailRow>
            )}

            {detail.prompt_used && (
              <DetailRow label="Exact prompt sent to the model">
                <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-xl bg-secondary/40 p-4 text-xs">
                  {detail.prompt_used}
                </pre>
              </DetailRow>
            )}

            {detail.safety_report && (
              <DetailRow label="Claim check at generation time">
                <span className="text-muted-foreground">
                  {detail.safety_report.passed ? "Passed" : "Failed"}
                  {detail.safety_summary ? ` — ${detail.safety_summary}` : ""}
                </span>
              </DetailRow>
            )}

            {detail.error && (
              <DetailRow label="Recorded error">
                <span className="text-destructive">{detail.error}</span>
              </DetailRow>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * The one control a history tile shows below its clip.
 *
 * The grid is a contact sheet: the clip is the content and everything else is
 * one gesture away. A plain "expand" button would be honest but small; a tab
 * that also responds to a drag is the affordance a bottom sheet trained people
 * to look for, and it costs one element. Both gestures end in the same
 * `onToggle`:
 *
 * - Click/Space/Enter toggles, through the native button.
 * - Dragging the tab toward the open direction tracks the pointer (the tab
 *   rises a couple of pixels and a progress rule fills), and releasing past
 *   the threshold toggles. Releasing short of it snaps back, which is what
 *   makes the gesture feel like a sheet rather than a second, hidden button.
 *
 * The drag arms only after 4px of travel, so the click that a normal press
 * produces is not swallowed by a phantom gesture, and a pointerup that ends a
 * real drag suppresses exactly one click. Touch dragging is restricted to the
 * grip in CSS (`touch-action: none`), because a full-width drag strip at the
 * bottom of every card would fight page scrolling on a phone.
 */
function HistoryExpandTab({ expanded, onToggle, controls, testId, id }) {
  const [lead, setLead] = useState(0);
  const drag = useRef({ startY: null, moved: false });
  const suppressClick = useRef(false);

  const beginDrag = (event) => {
    if (event.pointerType === "mouse" && event.button !== 0) return;
    drag.current = { startY: event.clientY, moved: false };
    event.currentTarget.setPointerCapture?.(event.pointerId);
  };

  const moveDrag = (event) => {
    if (drag.current.startY === null) return;
    const dy = event.clientY - drag.current.startY;
    if (Math.abs(dy) > 4) drag.current.moved = true;
    // Opening pulls the tab up; closing pulls it back down. Both are measured
    // as "away from the card", so one formula serves either state.
    const opening = expanded ? dy : -dy;
    setLead(Math.max(0, Math.min(1, opening / DRAG_COMMIT_PX)));
  };

  const endDrag = (event) => {
    if (drag.current.startY === null) return;
    const dy = event.clientY - drag.current.startY;
    const moved = drag.current.moved;
    drag.current = { startY: null, moved: false };
    setLead(0);
    if (!moved) return;
    suppressClick.current = true;
    // The click this pointerup produces comes before the timeout, so only a
    // gesture that ends without one leaves the guard set — and the timeout
    // clears it before the next real press can be mistaken for it.
    window.setTimeout(() => { suppressClick.current = false; }, 0);
    const opening = expanded ? dy : -dy;
    if (opening >= DRAG_COMMIT_PX * DRAG_COMMIT_RATIO) onToggle();
  };

  const cancelDrag = () => {
    drag.current = { startY: null, moved: false };
    setLead(0);
  };

  const handleClick = () => {
    if (suppressClick.current) {
      suppressClick.current = false;
      return;
    }
    onToggle();
  };

  return (
    <button
      type="button"
      id={id}
      className="history-tab"
      aria-expanded={expanded}
      aria-controls={controls}
      data-dragging={lead > 0 ? "true" : "false"}
      data-testid={testId}
      onClick={handleClick}
      onPointerDown={beginDrag}
      onPointerMove={moveDrag}
      onPointerUp={endDrag}
      onPointerCancel={cancelDrag}
      title={
        expanded
          ? "Click, or drag down, to close this render"
          : "Click, or drag up, to see this render's prompt, facts, and actions"
      }
    >
      <GripHorizontal aria-hidden="true" className="history-tab-grip h-3.5 w-3.5" />
      <span className="history-tab-label">
        {lead >= DRAG_COMMIT_RATIO
          ? expanded ? "Release to close" : "Release to open"
          : expanded ? "Collapse" : "Expand"}
      </span>
      <ChevronDown
        aria-hidden="true"
        className={`ml-auto h-4 w-4 shrink-0 transition-transform duration-200 motion-reduce:transition-none ${expanded ? "rotate-180" : ""}`}
      />
      <span aria-hidden="true" className="history-tab-lead" style={{ transform: `scaleX(${lead})` }} />
    </button>
  );
}

/**
 * One render, as a tile: the clip, then a drawer.
 *
 * The old card spent most of its width on a 152px rail plus a context column,
 * so a page of history read as a stack of admin panels with a small video
 * attached. The clip is the thing being reviewed, so it gets the whole tile:
 * a playable render shows the video and the tab, and nothing else — no app
 * name, no status, no facts standing beside the footage. Everything the card
 * used to say at rest lives in the drawer, which also put destructive actions
 * one deliberate gesture further away without hiding them from anyone who
 * opens a render to work on it.
 *
 * A row with nothing to play is the one exception, and it keeps a notice in
 * place of the video: a blank tile explains nothing, and each of those four
 * states has its own repair.
 */
function GenerationRow({ row, onChanged, defaultExpanded = false }) {
  const [expanded, setExpanded] = useState(defaultExpanded);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [showDetails, setShowDetails] = useState(false);
  // Set when the clip cannot be played inline, so the row can say so instead of
  // leaving a player that looks loaded and does nothing.
  const [previewBroken, setPreviewBroken] = useState(false);
  const [recoveredUrl, setRecoveredUrl] = useState(null);
  const [checkingRecovery, setCheckingRecovery] = useState(false);
  const [recoveryStorageError, setRecoveryStorageError] = useState(null);
  const [playerVersion, setPlayerVersion] = useState(0);
  // Set when a stranded row was re-checked and the provider is genuinely still
  // rendering. Distinct from `error`: this is a successful check that found the
  // render unfinished, not a failed action, so it must not read as one.
  const [strandedNote, setStrandedNote] = useState(null);

  const drawerId = `generation-detail-${row.id}`;
  const expandTabId = `generation-expand-${row.id}`;
  const wasExpanded = useRef(false);

  // Shared close for the footer button and Esc, so focus and scroll settle
  // in one place instead of diverging per trigger.
  const collapseRow = useCallback(() => {
    setExpanded(false);
  }, []);

  // Esc closes the open drawer. The listener lives only while expanded so a
  // closed row never steals Esc from the Details modal or other UI.
  useEffect(() => {
    if (!expanded) return;
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        collapseRow();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded, collapseRow]);

  // Closing from the footer (which unmounts) or Esc must not drop focus to
  // <body> or leave the card stranded mid-list. Return focus to the tab and
  // bring the card back into view — instant under reduced motion.
  useEffect(() => {
    if (wasExpanded.current && !expanded) {
      document.getElementById(expandTabId)?.focus?.({ preventScroll: true });
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
      document.getElementById(`generation-${row.id}`)?.scrollIntoView?.({
        block: "nearest",
        behavior: reduce ? "auto" : "smooth",
      });
    }
    wasExpanded.current = expanded;
  }, [expanded, expandTabId, row.id]);

  // The copy the browser can actually fetch, chosen by the same rule every
  // other screen uses (see durableMediaUrl): the durable upload, or the signed
  // local fallback path. It deliberately returns null for a row whose only URL
  // is the provider's temporary link, because a <video> cannot play that and an
  // <a download> cannot save it — handing either one the link produces a player
  // that never loads and a download that answers 401.
  const downloadUrl = recoveredUrl || durableMediaUrl(row);
  // The save button needs a same-origin URL, which the playback href is not
  // whenever the durable copy sits in R2. `recoveredUrl` is already same-origin
  // (it comes from a retry that returned a signed playback path), so it is
  // reused as-is; otherwise a signed path is spliced for the download route.
  const saveUrl = recoveredUrl || downloadMediaUrl(row);
  // Poster thumbnail: a tiny JPEG served as an image, so the tile shows a
  // frame instantly without fetching video bytes. Missing poster (old rows,
  // generation in flight) simply omits the attribute and the <video> behaves
  // as before — a 404 poster must never break playback.
  const posterUrl = row.poster_url ? mediaUrl(row.poster_url) : null;
  const hasClip = row.status === "completed" && Boolean(downloadUrl);
  // A finished render with no fetchable copy still gets a tile: the stage has
  // to say the copy is missing and the drawer offers the repair, which is the
  // only way a clip like that becomes playable again.
  //
  // A row stranded in `generating` gets one too. Those are not in-flight
  // renders: they are rows whose render finished at the provider while the app
  // was down, so nothing ever polled them and they kept the status forever.
  // They are invisible otherwise -- no stage, no player, no repair -- which is
  // how a paid render could sit finished and unreachable with no affordance.
  const stuckGenerating = row.status === "generating" && !row.video_url;
  const canRepair = stuckGenerating || (row.status === "completed" && (!downloadUrl || previewBroken));

  const signalRefs = {
    brand_profile_id: row.brand_profile_id,
    studio_project_id: row.studio_project_id,
    generation_id: row.id,
    template_id: row.template_id,
  };

  // A new URL means a new attempt. Every history response re-signs the media
  // path, so a failure recorded against the previous signature must not keep
  // the player hidden after the row is reloaded.
  useEffect(() => {
    setPreviewBroken(false);
  }, [downloadUrl]);

  const act = async (fn) => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleRecheckStranded = async () => {
    setBusy(true);
    setError(null);
    setStrandedNote(null);
    try {
      const updated = await api.pollGeneration(row.id);
      if (updated.status === "submitted" || updated.status === "generating") {
        // Genuinely still rendering at the provider. Say so plainly rather than
        // claiming a fix, and keep the row visible so it can be checked again.
        setStrandedNote(
          "Checked just now — the provider is still rendering this. Try again shortly."
        );
        onChanged?.();
        return;
      }
      const fresh = await api.getGeneration(row.id);
      const nextUrl = durableMediaUrl(fresh);
      if (nextUrl) {
        setRecoveredUrl(nextUrl);
        setPlayerVersion((version) => version + 1);
        setCheckingRecovery(true);
        setPreviewBroken(false);
      }
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // The studio panel offers this repair, and History is where a broken clip is
  // actually met, so the same action belongs here. Re-running storage re-fetches
  // the provider's copy and re-uploads it, which is the only way a clip whose
  // local copy was wiped by a redeploy becomes playable again. A refusal is
  // specific ("no local copy and no provider link left"), so it is shown rather
  // than flattened into a generic failure.
  const handleRetryStorage = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.retryGenerationStorage(row.id);
      const fresh = await api.getGeneration(row.id);
      const nextUrl = durableMediaUrl(fresh) || mediaUrl(result?.playback_url);
      if (!nextUrl) throw new Error("Storage recovered no playable source.");
      setRecoveredUrl(nextUrl);
      setRecoveryStorageError(result?.storage_error || null);
      setPlayerVersion((version) => version + 1);
      setCheckingRecovery(true);
      setPreviewBroken(false);
      // Keep this row mounted until loadeddata confirms the recovered file
      // actually decodes; an endpoint success alone is not playback success.
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // One place decides what the stage says, because the four reasons a clip is
  // not on screen are four different repairs and must not collapse into
  // "something went wrong".
  let stageNotice = null;
  if (row.status === "failed") {
    stageNotice = {
      title: "No clip — this render failed",
      body: row.error || "The provider returned an error instead of a video.",
    };
  } else if (stuckGenerating) {
    stageNotice = {
      title: "Still marked as generating",
      body: "This render may already be finished at the provider — nothing has checked since it was submitted.",
    };
  } else if (!downloadUrl) {
    stageNotice = {
      title: "No durable copy",
      body: "This render finished without a copy the browser can open, so there is nothing to play or download yet.",
    };
  } else if (previewBroken) {
    stageNotice = {
      title: "Preview unavailable",
      body: "The saved video could not be loaded. Retry recovery to check its local and cloud copies.",
    };
  }

  return (
    <article
      id={`generation-${row.id}`}
      className="surface surface-flush history-card min-w-0 scroll-mt-6"
      data-testid="history-card"
      data-expanded={expanded ? "true" : "false"}
    >
      <div className="history-stage">
        {downloadUrl && !previewBroken ? (
          <video
            key={`${row.id}-${playerVersion}`}
            src={downloadUrl}
            controls
            playsInline
            // Poster first: the thumbnail is a tiny JPEG image, so the tile
            // shows a frame without fetching video bytes. preload="none"
            // means the clip itself loads only on Play — previously
            // "metadata" fired a ranged video request per row on page load,
            // which is what left some thumbnails blank on slow/expired
            // sources. A missing poster simply omits the attribute.
            preload="none"
            poster={posterUrl || undefined}
            onLoadedData={() => {
              if (checkingRecovery) {
                setCheckingRecovery(false);
                toast.success(recoveryStorageError
                  ? "Video recovered locally. Download it now to keep a copy."
                  : "Video recovered and ready to play.");
              }
            }}
            onError={() => {
              setPreviewBroken(true);
              setCheckingRecovery(false);
            }}
            className="history-preview"
            // Contain the complete frame, never crop the creator's footage.
          />
        ) : (
          <div className="history-stage-empty">
            <Film aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
            <div className="min-w-0 space-y-1">
              <p className="text-sm font-semibold">{stageNotice?.title}</p>
              <p className="text-xs leading-relaxed text-muted-foreground">{stageNotice?.body}</p>
            </div>
          </div>
        )}
      </div>

      <HistoryExpandTab
        expanded={expanded}
        onToggle={() => setExpanded((open) => !open)}
        controls={drawerId}
        testId="history-expand"
        id={expandTabId}
      />

      {expanded && (
        <div
          id={drawerId}
          role="region"
          aria-label="Render details"
          className="history-drawer"
        >
          <div className="history-body space-y-5">
            {/* Which app this render belongs to and how it turned out used to
                sit on the tile as a scrim over the footage. The tile is the
                clip now, so they moved in here rather than disappearing — a
                filtered page is still readable, and the status is still on
                screen the moment a render is opened. */}
            <div className="flex flex-wrap items-center gap-2">
              <GroupLabel icon={Briefcase}>{row.brand_name || "Unassigned app"}</GroupLabel>
              <StatusBadge status={row.status} />
            </div>

            {row.hook_line && (
              <p className="break-words text-sm leading-relaxed text-foreground/90">
                &ldquo;{sentenceCase(row.hook_line)}&rdquo;
              </p>
            )}

            {/* One treatment for every fact about the render.

                These were three: four badges opposite the title, a run-on
                "a · b · c · date" sentence, and a separate meta row. A sentence
                of dots is not scannable — you cannot find one fact in it
                without reading it all — and two treatments for the same kind of
                information meant the card never looked settled. Chips also let
                the row go quiet when facts are missing instead of leaving a
                dangling separator. */}
            <FactList>
              {row.model && <FactChip>{row.model}</FactChip>}
              {row.duration ? <FactChip>{row.duration}s</FactChip> : null}
              {row.attempt > 1 ? <FactChip>attempt {row.attempt}</FactChip> : null}
              {row.objective ? <FactChip>{humanize(row.objective)}</FactChip> : null}
              {row.template_id ? <FactChip>template v{row.template_version}</FactChip> : null}
              <FactChip>script v{row.script_version}</FactChip>
              {formatRenderDate(row.created_at) ? (
                <FactChip>{formatRenderDate(row.created_at)}</FactChip>
              ) : null}
            </FactList>

            {(row.audience || row.demo_brief) && (
              <div className="inset-panel space-y-3" data-testid="history-context">
                {row.audience && (
                  <div className="space-y-1">
                    <GroupLabel icon={Target}>Audience</GroupLabel>
                    <p className="break-words text-sm leading-relaxed text-muted-foreground">{row.audience}</p>
                  </div>
                )}
                {row.demo_brief && (
                  <div className="space-y-1">
                    <GroupLabel icon={Smartphone}>Your demo brief</GroupLabel>
                    <p className="break-words text-sm leading-relaxed text-muted-foreground">{row.demo_brief}</p>
                  </div>
                )}
              </div>
            )}

            {error && <p className="text-xs text-destructive">{error}</p>}
            {checkingRecovery && (
              <p className="text-xs text-muted-foreground" role="status">Checking recovered video…</p>
            )}
            {strandedNote && (
              <p className="text-xs text-muted-foreground" role="status">{strandedNote}</p>
            )}

            <div className="space-y-2 border-t border-[color:var(--hairline)] pt-5" data-testid={`history-feedback-${row.id}`}>
              <GroupLabel icon={Clapperboard}>Rate this render &amp; its parts</GroupLabel>
              <ComponentThumbs
                component="video"
                question="Generated video"
                hint="Rates the generated video clip itself."
                resetKey={row.id}
                refs={{
                  ...signalRefs,
                  detail: row.model ? `model=${row.model}` : "",
                }}
                testId={`history-video-feedback-${row.id}`}
              />
              <ComponentThumbs
                component="goal"
                question="Content goal"
                hint="Shapes future goal suggestions for this app."
                resetKey={`${row.id}:goal`}
                refs={{
                  ...signalRefs,
                  detail: `objective=${row.objective || ""};kind=${row.angle_kind || ""}`,
                }}
                testId={`history-goal-feedback-${row.id}`}
              />
              <ComponentThumbs
                component="template"
                question="Hook template"
                hint="Reorders and reshapes future template suggestions."
                resetKey={`${row.id}:template`}
                refs={signalRefs}
                testId={`history-template-feedback-${row.id}`}
              />
              <ComponentThumbs
                component="plan"
                question="Script plan"
                hint="Steers future script plans for this app."
                resetKey={`${row.id}:plan`}
                refs={{
                  ...signalRefs,
                  detail: `plan v${Number(row.script_version) || 0}`,
                }}
                testId={`history-plan-feedback-${row.id}`}
              />
              <ComponentThumbs
                component="script"
                question="Spoken script"
                hint="Guides future spoken scripts for this app."
                resetKey={`${row.id}:script`}
                refs={{
                  ...signalRefs,
                  detail: `strategy v${Number(row.strategy_version) || 0}`,
                }}
                testId={`history-script-feedback-${row.id}`}
              />
            </div>

            {/* Actions, in two tiers.

                The clip is what this row is for, so Download and Demo + CTA are
                the wide, legible pair; Delete and the paper trail sit on a
                quieter line beneath them. The old layout scattered these across
                a rail, a tile group, and a failed-row bar, so "delete" and
                "download" were one mistaken click apart in a 240px column.
                Grouping by consequence instead: get the file, take it onward,
                then act on the record.

                Download points at downloadMediaUrl, the same-origin route that
                forces a save. The playback href was cross-origin whenever the
                durable copy was in R2, and browsers ignore `download` there, so
                the button opened a tab instead of saving the file. */}
            <div className="space-y-3 border-t border-[color:var(--hairline)] pt-5">
              <GroupLabel icon={Clapperboard}>Work with this render</GroupLabel>
              <div
                className="flex flex-wrap gap-2"
                role="group"
                aria-label="Work with this render"
                data-testid="history-actions"
              >
                {saveUrl && (
                  <Button variant="secondary" asChild className="min-w-[150px] flex-1">
                    <a
                      href={saveUrl}
                      download
                      onClick={() => recordSignal("video_downloaded", "downloaded", signalRefs)}
                    >
                      <Download className="h-4 w-4" /> Download
                    </a>
                  </Button>
                )}
                {/* The onward action wears the acting colour (accent/indigo),
                    never the retired warm fill — ADR 0011. */}
                {hasClip && (
                  <Button
                    variant="accent"
                    asChild
                    data-testid={`demo-cta-history-${row.id}`}
                    className="min-w-[150px] flex-1"
                  >
                    <Link to={`/demo-cta/${row.id}`} title="Wrap this clip in a phone mockup and add your close">
                      <Smartphone className="h-4 w-4" /> Demo + CTA
                    </Link>
                  </Button>
                )}
                {row.status === "failed" && row.retryable && (
                  <Button
                    variant="accent"
                    disabled={busy}
                    onClick={() => act(() => api.retryGeneration(row.id))}
                    className="min-w-[150px] flex-1"
                  >
                    <RotateCcw className="h-4 w-4" /> Retry render
                  </Button>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2">
                <Button
                  variant="ghost"
                  size="sm"
                  onClick={() => setShowDetails(true)}
                  data-testid="generation-details-button"
                >
                  <Info className="h-3.5 w-3.5" /> Details
                </Button>
                {/* Delete acts on the record, not the picture, so it lives with
                    the quiet actions and is tinted destructive: spelled out,
                    never parked next to the button that saves the same file. */}
                <Button
                  variant="ghost"
                  size="sm"
                  className="text-muted-foreground hover:text-destructive"
                  disabled={busy}
                  onClick={() => act(() => api.deleteGeneration(row.id))}
                  data-testid={`history-delete-${row.id}`}
                  title="Remove this render from history"
                >
                  <Trash2 className="h-3.5 w-3.5" /> Delete
                </Button>
              </div>

              {stuckGenerating && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  disabled={busy}
                  onClick={handleRecheckStranded}
                  data-testid={`recheck-stranded-${row.id}`}
                  title="Ask the provider whether this render finished, and fetch it if it did"
                >
                  {busy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3.5 w-3.5" />
                  )}
                  Check again
                </Button>
              )}
              {canRepair && !stuckGenerating && (
                <Button
                  variant="secondary"
                  size="sm"
                  className="w-full"
                  disabled={busy}
                  onClick={handleRetryStorage}
                  data-testid={`retry-storage-${row.id}`}
                  title="Re-fetch the finished render and save a durable copy, so it plays here"
                >
                  {busy ? (
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                  ) : (
                    <RotateCcw className="h-3.5 w-3.5" />
                  )}
                  Retry durable save
                </Button>
              )}
            </div>

            {/* Footer close: the drawer can run long (script + prompt +
                actions), so the top Expand/Collapse tab is a scroll away once
                the user reaches the bottom. Same state, same word, quiet
                treatment so it never competes with Download / Demo + CTA. */}
            <div className="border-t border-[color:var(--hairline)] pt-4">
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={collapseRow}
                aria-controls={drawerId}
                aria-label="Collapse this render"
                title="Collapse this render"
                data-testid={`history-collapse-${row.id}`}
              >
                <ChevronUp className="h-3.5 w-3.5" /> Collapse
              </Button>
            </div>
          </div>
        </div>
      )}

      {showDetails && (
        <GenerationDetails generationId={row.id} onClose={() => setShowDetails(false)} />
      )}
    </article>
  );
}

export default function GenerationHistory() {
  const [rows, setRows] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // Filters mirror into ?profile=&status=&q= so a view like "failed renders
  // for this app" is a shareable link, not a re-click every visit. State
  // stays the source of truth; the URL is a mirror updated below.
  const [searchParams, setSearchParams] = useSearchParams();
  const location = useLocation();
  const [profileFilter, setProfileFilter] = useState(() => searchParams.get("profile") || "");
  const [statusFilter, setStatusFilter] = useState(() => searchParams.get("status") || "");
  const [query, setQuery] = useState(() => searchParams.get("q") || "");
  // The endpoint caps at 200 and the page first asks for 100: a history that
  // outgrows the first page says so with a second page, not a silent cut.
  const [limit, setLimit] = useState(100);

  useEffect(() => {
    const next = {};
    if (profileFilter) next.profile = profileFilter;
    if (statusFilter) next.status = statusFilter;
    if (query.trim()) next.q = query.trim();
    setSearchParams(next, { replace: true });
    // setSearchParams is stable; mirroring state -> URL only.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [profileFilter, statusFilter, query]);

  const load = useCallback(async () => {
    setLoading(true);
    setError(null);
    try {
      const data = await api.getGenerationHistory({
        brand_profile_id: profileFilter || undefined,
        status: statusFilter || undefined,
        limit,
      });
      setRows(data.generations || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [profileFilter, statusFilter, limit]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.getAppProfiles().then((d) => setProfiles(d.profiles || [])).catch(() => setProfiles([]));
  }, []);

  // Hook-text search is client-side: founders remember "the plumber one",
  // not its status, and the endpoint only filters by app + status.
  const visible = (() => {
    const q = query.trim().toLowerCase();
    if (!q) return rows;
    return rows.filter((r) =>
      [r.hook_line, r.model, r.audience, r.demo_brief].some((v) =>
        String(v || "").toLowerCase().includes(q)
      )
    );
  })();

  const completed = visible.filter((r) => r.status === "completed").length;
  const failed = visible.filter((r) => r.status === "failed").length;

  // A #generation-<id> deep link (Analytics "View render") lands on a page
  // whose rows arrive after the fetch, so the browser's native anchor scroll
  // has nothing to land on. Settle it here once rows exist: bring the card
  // into view and open its drawer, so the link names a render that is
  // actually shown rather than a card somewhere below the fold.
  const hashId = (location.hash || "").startsWith("#generation-")
    ? location.hash.slice("#generation-".length)
    : "";
  useEffect(() => {
    if (!hashId || rows.length === 0) return;
    document.getElementById(`generation-${hashId}`)?.scrollIntoView?.({ block: "nearest" });
  }, [hashId, rows]);

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        data-testid="history-header"
        icon={HistoryIcon}
        title="Generation History"
        description="Review every render and export, and download your clips."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AppPicker
              profiles={profiles}
              value={profileFilter}
              onChange={setProfileFilter}
              allLabel="All apps"
              ariaLabel="Filter by app"
            />
            <label className="sr-only" htmlFor="history-search">Search by hook text</label>
            <input
              id="history-search"
              type="search"
              value={query}
              onChange={(e) => setQuery(e.target.value)}
              placeholder="Search hooks…"
              aria-label="Search by hook text"
              data-testid="history-search"
              className={PILL_SELECT_CLASS}
            />
            <label className="sr-only" htmlFor="history-status-filter">Filter by status</label>
            <select
              id="history-status-filter"
              value={statusFilter}
              onChange={(e) => setStatusFilter(e.target.value)}
              aria-label="Filter by status"
              className={PILL_SELECT_CLASS}
            >
              <option value="">All statuses</option>
              {["completed", "failed", "generating", "submitted", "archived"].map((s) => (
                <option key={s} value={s}>{humanize(s)}</option>
              ))}
            </select>
          </div>
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {loading ? (
        /* Mirrors the real tile rather than a centered spinner: a bare spinner on
           a page whose cards are stacked means the layout jumps the moment data
           lands, which is the same flash the studio loader was changed to
           remove. The skeleton is the stage plus the expand tab, because that
           is all a collapsed card is. */
        <div className="space-y-4" aria-label="Loading history" data-testid="history-loading">
          {[0, 1, 2].map((i) => (
            <div key={i} className="surface surface-flush history-card min-w-0">
              <div className="history-stage">
                <Skeleton className="h-[240px] w-[135px] rounded-xl" />
              </div>
              <div className="row-pad border-t border-[color:var(--hairline)]">
                <Skeleton className="h-3 w-28" />
              </div>
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Nothing generated yet"
          description="Create Video saves generated Hook + Story clips here."
          action={
            <Button variant="accent" asChild>
              <Link to="/create">
                Create a video <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="history-grid" data-testid="history-list">
          {visible.length > 1 && (
            <p className="col-span-full text-xs text-muted-foreground">
              {visible.length} results · {completed} completed · {failed} failed
            </p>
          )}
          {visible.length === 0 && rows.length > 0 && (
            <p className="col-span-full text-xs text-muted-foreground" role="status">
              No renders match “{query.trim()}”. Clear the search to see everything.
            </p>
          )}
          {visible.map((row) => (
            <GenerationRow
              key={row.id}
              row={row}
              onChanged={load}
              defaultExpanded={hashId !== "" && hashId === row.id}
            />
          ))}
          {rows.length >= limit && limit < 200 && (
            <div className="col-span-full flex justify-center pt-2">
              <Button
                variant="secondary"
                size="sm"
                onClick={() => setLimit(200)}
                data-testid="history-show-more"
              >
                Show more <ChevronDown className="h-3.5 w-3.5" />
              </Button>
            </div>
          )}
        </div>
      )}
    </PageFrame>
  );
}
