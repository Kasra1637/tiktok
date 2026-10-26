import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import EmptyState from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { AppPicker, PILL_SELECT_CLASS } from "../components/AppPicker";
import { GroupLabel } from "../components/SectionCard";
import { Skeleton } from "../components/ui/skeleton";
import { api, getErrorMessage, durableMediaUrl, downloadMediaUrl, mediaUrl } from "../lib/api";
import { FactChip, FactList } from "../components/FactChip";
import { PostKitSection } from "../components/PostKitSection";
import { HistoryFeedback } from "../components/HistoryFeedback";
import { recordSignal, verdictFor } from "../lib/feedback";
import { isWinnerRow } from "../lib/nextTake";
import { useVerifiedDraftIds } from "../hooks/useVerifiedDraftIds";
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
  ChevronLeft,
  ChevronUp,
  Film,
  Smartphone,
  CopyPlus,
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
/**
 * Rows per History page. The fetch window (100, then 200 via show-more) is
 * bytes; this is DOM. One page of heavy tiles — a video element, poster
 * logic, and feedback hooks each — keeps the 200-row path mounted light
 * while every row stays one pager turn away.
 */
const HISTORY_PAGE_SIZE = 50;

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
 * One render, as a tile: the clip, then — as a separate full-width grid item
 * — its detail band.
 *
 * The old card spent most of its width on a 152px rail plus a context column,
 * so a page of history read as a stack of admin panels with a small video
 * attached. The clip is the thing being reviewed, so it gets the whole tile:
 * a playable render leads with the video, then its identity and saved results.
 * Detailed context and destructive actions live in the band below the row,
 * so opening one tile never stretches its neighbors and every collapsed tile
 * stays the same flat height.
 *
 * A row with nothing to play is the one exception, and it keeps a notice in
 * place of the video: a blank tile explains nothing, and each of those four
 * states has its own repair.
 *
 * Open state lives in the list (one band at a time); the row only renders
 * its card and, when open, the band directly after it. The fragment's two
 * children are both grid items, which is what puts the band on its own full
 * row instead of inside the card.
 */
function GenerationRow({ row, onChanged, onUpdated, expanded = false, onToggle, deepLinked = false, draftIds = null }) {
  // A #generation- deep link (export "View in History", Analytics "View
  // render") opens this row; when it is still awaiting its TikTok link,
  // finish the job by focusing that input, so the founder lands with the
  // cursor where the next action is instead of having to remember the link
  // step and find the field inside the band. Scoped to the deep-linked
  // row and the awaiting state only: a manual expand never steals focus,
  // and a row that already has its link keeps focus where it was.
  const linkAwaiting = expanded && deepLinked && !row.tiktok_url;
  useEffect(() => {
    if (!linkAwaiting || !expanded) return;
    document.querySelector(`[data-testid="history-tiktok-input-${row.id}"]`)?.focus?.();
  }, [linkAwaiting, expanded, row.id]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

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

  // Esc closes the open band. The listener lives only while expanded so a
  // closed row never steals Esc from other UI.
  useEffect(() => {
    if (!expanded) return;
    const onKey = (event) => {
      if (event.key === "Escape") {
        event.stopPropagation();
        onToggle();
      }
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [expanded, onToggle]);

  // Closing from the footer (which unmounts) or Esc must not drop focus to
  // <body> or leave the card stranded mid-list. Return focus to the tab and
  // bring the card back into view — instant under reduced motion. Skipped
  // when this row closed because another one opened: focus already belongs
  // to that row's tab and yanking it back here would fight the new band.
  useEffect(() => {
    if (wasExpanded.current && !expanded) {
      const active = document.activeElement;
      const card = document.getElementById(`generation-${row.id}`);
      const panel = document.getElementById(drawerId);
      const focusIsOurs =
        !active ||
        active === document.body ||
        card?.contains(active) ||
        panel?.contains(active);
      if (focusIsOurs) {
        document.getElementById(expandTabId)?.focus?.({ preventScroll: true });
        const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
        card?.scrollIntoView?.({
          block: "nearest",
          behavior: reduce ? "auto" : "smooth",
        });
      }
    }
    wasExpanded.current = expanded;
  }, [expanded, expandTabId, row.id, drawerId]);

  // Opening brings the band into view, but only when it needs it: if the
  // whole band already fits on screen, `nearest` is a no-op and the page
  // stays exactly where the founder put it. Scrolling never moves focus,
  // so the focus contract above is untouched.
  useEffect(() => {
    if (!expanded) return;
    const panel = document.getElementById(drawerId);
    const rect = panel?.getBoundingClientRect?.();
    if (panel && rect && rect.bottom > window.innerHeight) {
      const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
      panel.scrollIntoView?.({
        block: "nearest",
        behavior: reduce ? "auto" : "smooth",
      });
    }
  }, [expanded, drawerId]);


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
    <>
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

      <div className="row-pad space-y-2 border-t border-[color:var(--hairline)]" data-testid="history-summary">
        <div className="flex flex-wrap items-center gap-2 text-xs">
          <span className="font-semibold">{row.brand_name || "Unassigned app"}</span>
          <StatusBadge status={row.status} />
          <span className="text-muted-foreground">{formatRenderDate(row.created_at)}</span>
        </div>
        <p className="break-words text-sm font-semibold">
          {row.hook_line ? sentenceCase(row.hook_line) : `${row.segment_role === "demo_cta" ? "Demo + CTA export" : "Render"} · ${row.id.slice(0, 8)}`}
        </p>
        <div className="history-summary-meta flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
          <span>{row.tiktok_url ? "Posted" : "Not posted"}</span>
          <span>{row.tiktok_views == null ? "Views not recorded" : `${row.tiktok_views.toLocaleString("en-US")} views`}</span>
          <span>{verdictFor(row.verdicts, "video") > 0 ? "Your vote: Good" : verdictFor(row.verdicts, "video") < 0 ? "Your vote: Not good" : "Not rated"}</span>              {isWinnerRow(row) && <FactChip>Winner</FactChip>}
        </div>
      </div>

      <HistoryExpandTab
        expanded={expanded}
        onToggle={onToggle}
        controls={drawerId}
        testId="history-expand"
        id={expandTabId}
      />
    </article>

      {/* The detail band: a sibling grid item, not card content. It lands on
          the row below this card and spans every column, so the collapsed
          tiles around it keep their flat contact-sheet height. */}
      {expanded && (
        <div
          id={drawerId}
          role="region"
          aria-label="Render details"
          data-testid="history-detail-panel"
          className="surface surface-flush history-detail-panel history-drawer min-w-0 scroll-mt-6"
        >
          <div className="history-body">
          {/* Two columns on wide bands, one stacked column on narrow: facts
              and context read on the left, votes and actions work on the
              right. Narrow stacking preserves the old top-to-bottom order. */}
          <div className="history-detail-cols">
            <div className="min-w-0 space-y-5">
            {/* Repeat identity here for long drawers scrolled past the tile. */}
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

            {/* Frozen post copy for this render; pre-kit rows show nothing. */}
            {row.post_kit && (
              <div className="space-y-3 border-t border-[color:var(--hairline)] pt-5">
                <PostKitSection postKit={row.post_kit} generationId={row.id} onUpdated={(kit) => onUpdated(row.id, { post_kit: kit })} />
              </div>
            )}

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

            </div>
            <div className="min-w-0 space-y-5">
            {error && <p className="text-xs text-destructive">{error}</p>}
            {checkingRecovery && (
              <p className="text-xs text-muted-foreground" role="status">Checking recovered video…</p>
            )}
            {strandedNote && (
              <p className="text-xs text-muted-foreground" role="status">{strandedNote}</p>
            )}

            <HistoryFeedback row={row} signalRefs={signalRefs} onUpdated={onUpdated} />

            {/* Actions, in two tiers.

                The clip is what this row is for, so Download and Demo + CTA are
                the wide, legible pair; Delete sits on a quieter line beneath them. The old layout scattered these across
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
                {/* The thumbs-only results loop: the recorded per-component
                    verdicts already steer the next plan server-side, so a new
                    take needs no new endpoint — the retired duplicate/variation
                    routes are gone. Reopening this generation's draft project
                    in the studio is the variation: the plan arrives intact and
                    the next render is a fresh generation. */}
                {/* Winners name the take: the thumbs plus the posted link are
                    the loop's proof, so the onward entry says what it reuses.
                    A draft verified gone offers nothing — no dead link, and no
                    fallback that duplicates the Demo + CTA button above. An
                    unverified list fails open to the draft, as before. */}
                {row.studio_project_id && !(isWinnerRow(row) && draftIds && !draftIds.has(row.studio_project_id)) && (
                  <Button
                    variant="secondary"
                    asChild
                    data-testid={`history-variation-${row.id}`}
                    className="min-w-[150px] flex-1"
                  >
                    <Link
                      to={`/create?project=${row.studio_project_id}`}
                      title={isWinnerRow(row)
                        ? "Open this winner's plan in Create Video for another take like this"
                        : "Open this plan in Create Video for another take — your recorded thumbs steer the next plan"}
                    >
                      <CopyPlus className="h-4 w-4" /> {isWinnerRow(row) ? "Another take like this" : "New variation"}
                    </Link>
                  </Button>
                )}
              </div>

              <div className="flex flex-wrap items-center justify-between gap-2">
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

            {/* Footer close: the band can run long (script + prompt +
                actions), so the top Expand/Collapse tab is a scroll away once
                the user reaches the bottom. Same state, same word, quiet
                treatment so it never competes with Download / Demo + CTA. */}
            <div className="border-t border-[color:var(--hairline)] pt-4">
              <Button
                variant="ghost"
                size="sm"
                className="w-full"
                onClick={onToggle}
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
          </div>
        </div>
      )}

    </>
  );
}

export default function GenerationHistory() {
  const [rows, setRows] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  // The URL owns filters, so back/forward and same-page links cannot disagree
  // with a second local copy. Preserve the clip anchor when editing a filter.
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const profileFilter = searchParams.get("profile") || "";
  const statusFilter = searchParams.get("status") || "";
  const query = searchParams.get("q") || "";
  const setFilter = (name, value) => {
    const next = new URLSearchParams(searchParams);
    if (value) next.set(name, value);
    else next.delete(name);
    navigate({ search: next.toString(), hash: location.hash }, { replace: true });
  };
  // Deep links load the same 200-row window as Analytics; other visits start
  // with 100 and offer a second page instead of silently cutting off history.
  const [limit, setLimit] = useState(() => location.hash.startsWith("#generation-") ? 200 : 100);
  // The pager navigates loaded rows; the reset below (after `sort`, which it
  // depends on) keeps a new filter, search, sort, or fetch window from
  // stranding the founder on page 3 of a one-page result.
  const [page, setPage] = useState(1);
  // Sort is client-side like the hook-text search: the endpoint owns
  // app + status filters, the page owns presentation. Uncounted renders
  // (no pasted-back views) always sort after counted ones.
  const [sort, setSort] = useState("newest");
  // One detail band at a time: the open row's id, or null. A #generation-
  // deep link names the open row; the tab, Esc, and the footer close flip it.
  // Open state lives here (not in the row) so opening one tile closes the
  // band elsewhere instead of stacking a second full-width row.
  const [openId, setOpenId] = useState(null);
  const toggleRow = useCallback((id) => {
    setOpenId((cur) => (cur === id ? null : id));
  }, []);
  const updateRow = useCallback((id, patch) => {
    setRows((current) => current.map((row) => row.id === id ? { ...row, ...patch } : row));
  }, []);

  useEffect(() => {
    if (location.hash.startsWith("#generation-")) setLimit(200);
  }, [location.hash]);

  const loadRequest = useRef(null);

  const load = useCallback(async () => {
    const request = {};
    loadRequest.current = request;
    setLoading(true);
    setError(null);
    try {
      const data = await api.getGenerationHistory({
        brand_profile_id: profileFilter || undefined,
        status: statusFilter || undefined,
        limit,
      });
      if (request === loadRequest.current) setRows(data.generations || []);
    } catch (err) {
      if (request === loadRequest.current) setError(getErrorMessage(err));
    } finally {
      if (request === loadRequest.current) setLoading(false);
    }
  }, [profileFilter, statusFilter, limit]);

  useEffect(() => {
    load();
    return () => { loadRequest.current = null; };
  }, [load]);

  // The app filter is a convenience: its load failing must not silently
  // narrow the page to "All apps". It names itself with its own retry.
  const [profilesError, setProfilesError] = useState(null);
  const loadProfiles = useCallback(() => {
    setProfilesError(null);
    api.getAppProfiles()
      .then((d) => setProfiles(d.profiles || []))
      .catch((err) => {
        setProfiles([]);
        setProfilesError(getErrorMessage(err));
      });
  }, []);
  useEffect(() => {
    loadProfiles();
  }, [loadProfiles]);

  // One owner for the verification both the winner entry and the variation
  // entry read: a confirmed-gone draft offers nothing, an unverified list
  // links as before. Runs only when some visible row names a draft.
  const draftIds = useVerifiedDraftIds(
    profileFilter,
    rows.some((r) => r.studio_project_id)
  );

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
  const ordered = sort === "views"
    ? [...visible].sort((a, b) => (b.tiktok_views ?? -1) - (a.tiktok_views ?? -1))
    : visible;
  // The render window over the loaded rows: at most one page mounts. The
  // fetch window above still owns how many rows arrive; this owns how many
  // are in the DOM. Clamped, never empty-headed: a shrink lands on page 1
  // via the reset above, and a mid-list page survives deletions.
  const pageCount = Math.max(1, Math.ceil(ordered.length / HISTORY_PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = ordered.slice((safePage - 1) * HISTORY_PAGE_SIZE, safePage * HISTORY_PAGE_SIZE);
  // Turning the page swaps the rows above the fold, so bring the list back
  // into view instead of stranding the founder at its bottom. The pager
  // buttons survive the turn, so the activating control keeps focus.
  const listRef = useRef(null);
  const goToPage = useCallback((next) => {
    setPage(next);
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    listRef.current?.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }, []);
  // Focus needs no rescue here: the filter and sort controls that caused the
  // reset stay mounted, so focus is already somewhere sensible.
  useEffect(() => {
    setPage(1);
  }, [profileFilter, statusFilter, query, sort, limit]);

  // A #generation-<id> deep link (Analytics "View render") lands on a page
  // whose rows arrive after the fetch, so the browser's native anchor scroll
  // has nothing to land on. Settle it here once rows exist: bring the card
  // into view and open its drawer, so the link names a render that is
  // actually shown rather than a card somewhere below the fold.
  const hashId = (location.hash || "").startsWith("#generation-")
    ? location.hash.slice("#generation-".length)
    : "";
  // A new anchor names a new open row. User closes stick: this only ever
  // opens, and only when the named row is not already the open one.
  useEffect(() => {
    if (hashId) setOpenId((cur) => (cur === hashId ? cur : hashId));
  }, [hashId]);
  // The deep link names a render, not a page: when the row sits past the
  // render window, jump the pager to its page first. Setting an unchanged
  // page is a React no-op, so this settles instead of looping.
  useEffect(() => {
    if (!hashId || ordered.length === 0) return;
    const index = ordered.findIndex((row) => row.id === hashId);
    if (index !== -1) setPage(Math.floor(index / HISTORY_PAGE_SIZE) + 1);
  }, [hashId, ordered]);
  useEffect(() => {
    if (!hashId || rows.length === 0) return;
    document.getElementById(`generation-${hashId}`)?.scrollIntoView?.({ block: "nearest" });
    // safePage re-fires this once the jump above mounts the named row; without
    // it the scroll runs while the row is still on another page.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [hashId, rows, safePage]);

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
              onChange={(value) => setFilter("profile", value)}
              allLabel="All apps"
              ariaLabel="Filter by app"
            />
            {profilesError && (
              <span role="alert" className="flex items-center gap-1 text-xs text-destructive">
                {profilesError}{" "}
                <button type="button" className="underline" onClick={loadProfiles} data-testid="profiles-retry">
                  Try again
                </button>
              </span>
            )}
            <label className="sr-only" htmlFor="history-search">Search by hook text</label>
            <input
              id="history-search"
              type="search"
              value={query}
              onChange={(e) => setFilter("q", e.target.value)}
              placeholder="Search hooks…"
              aria-label="Search by hook text"
              data-testid="history-search"
              className={PILL_SELECT_CLASS}
            />
            <label className="sr-only" htmlFor="history-status-filter">Filter by status</label>
            <select
              id="history-status-filter"
              value={statusFilter}
              onChange={(e) => setFilter("status", e.target.value)}
              aria-label="Filter by status"
              className={PILL_SELECT_CLASS}
            >
              <option value="">All statuses</option>
              {["completed", "failed", "generating", "submitted", "archived"].map((s) => (
                <option key={s} value={s}>{humanize(s)}</option>
              ))}
            </select>
            <label className="sr-only" htmlFor="history-sort">Sort history</label>
            <select
              id="history-sort"
              value={sort}
              onChange={(e) => setSort(e.target.value)}
              aria-label="Sort history"
              data-testid="history-sort"
              className={PILL_SELECT_CLASS}
            >
              <option value="newest">Newest first</option>
              <option value="views">Most viewed</option>
            </select>
          </div>
        }
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>{error}</span>
            <Button variant="secondary" size="sm" onClick={load} data-testid="history-retry">
              Try again
            </Button>
          </AlertDescription>
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
        <div className="history-grid" data-testid="history-list" ref={listRef}>
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
          {/* Flat tiles: the grid pairs them into rows of two (stacked on
              phones). No pair wrappers — grouping rows in divs would remount
              every tile whenever sorting or filtering regroups them, dropping
              focus and typed input mid-edit. Stable row keys let React reorder
              without remounting. */}
          {paged.map((row) => (
            <GenerationRow
              key={row.id}
              row={row}
              onChanged={load}
              onUpdated={updateRow}
              expanded={openId === row.id}
              onToggle={() => toggleRow(row.id)}
              deepLinked={hashId !== "" && hashId === row.id}
              draftIds={draftIds}
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
      {/* The pager navigates the loaded rows; show-more above still owns how
          many rows load. Numbered buttons all stay mounted so turning pages
          never unmounts the control holding focus. At most four pages: the
          fetch window caps at 200 rows of 50. */}
      {pageCount > 1 && (
        <nav aria-label="History pages" data-testid="history-pager" className="flex items-center justify-center gap-1 pt-2">
          <Button
            variant="secondary"
            size="sm"
            disabled={safePage === 1}
            onClick={() => goToPage(safePage - 1)}
            data-testid="history-prev-page"
            aria-label="Previous page"
          >
            <ChevronLeft className="h-3.5 w-3.5" />
          </Button>
          {Array.from({ length: pageCount }, (_, i) => i + 1).map((n) => (
            <Button
              key={n}
              variant="secondary"
              size="sm"
              onClick={() => goToPage(n)}
              data-testid={`history-page-${n}`}
              aria-label={`Page ${n}`}
              aria-current={n === safePage ? "page" : undefined}
            >
              {n}
            </Button>
          ))}
          <Button
            variant="secondary"
            size="sm"
            disabled={safePage === pageCount}
            onClick={() => goToPage(safePage + 1)}
            data-testid="history-next-page"
            aria-label="Next page"
          >
            <ChevronRight className="h-3.5 w-3.5" />
          </Button>
          <span className="ml-2 text-xs text-muted-foreground" data-testid="history-page-status">
            Page {safePage} of {pageCount}
          </span>
        </nav>
      )}
    </PageFrame>
  );
}
