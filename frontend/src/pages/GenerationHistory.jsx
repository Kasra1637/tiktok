import { memo, useCallback, useEffect, useRef, useState } from "react";
import { Link, useLocation, useNavigate, useSearchParams } from "react-router-dom";
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
import { FactChip } from "../components/FactChip";
import { PostKitSection } from "../components/PostKitSection";
import { HistoryFeedback } from "../components/HistoryFeedback";
import { recordSignal, verdictFor } from "../lib/feedback";
import { isWinnerRow } from "../lib/nextTake";
import { listPendingSaves } from "../demoCta/saveOutbox";
import { PendingSaveCard } from "./PendingSaveCard";
import {
  historyActionError,
  hasCopyContext,
  isAwaitingProvider,
  effectiveCopyFilter,
  getHistoryAttention,
  describeHistoryAttention,
  historyAttentionLink,
  shouldApplyDeepLinkPage,
  pageForRowIndex,
  shouldShowHistoryEmpty,
  shouldOfferDraftLink,
} from "./historyRepair";
import { useAwaitingHistoryPoll } from "./historyPolling";
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
  Film,
  Smartphone,
  CopyPlus,
  Target,
  Clapperboard,
  MessageSquareText,
} from "lucide-react";

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
  return new Date(t).toLocaleString(undefined, {
    month: "numeric",
    day: "numeric",
    year: "numeric",
    hour: "numeric",
    minute: "2-digit",
  });
}

/**
 * The one-line outcome of a render, written to be quiet by default.
 *
 * The row printed three separate negatives on every render nobody had touched
 * yet — "Not posted · Views not recorded · Not rated" — which is the most common
 * state in History and read as a list of failures rather than an invitation.
 * Now an untouched render is one sentence, a missing number is named only when
 * it is the next thing to fill in, and an absent vote says nothing at all: the
 * record beside the clip already offers the vote, and "Not rated" on every row
 * is noise, not information. The word "yet" is deliberate — it is the state,
 * not a verdict on the render.
 */
function describeResults(row) {
  const verdict = verdictFor(row.verdicts, "video");
  const bits = [];
  if (row.tiktok_url) {
    bits.push("Posted");
    bits.push(
      row.tiktok_views == null
        ? "no views yet"
        : `${row.tiktok_views.toLocaleString("en-US")} views`
    );
  } else {
    bits.push("Not posted yet");
  }
  if (verdict !== 0) {
    bits.push(verdict > 0 ? "Your vote: Good" : "Your vote: Not good");
  }
  return bits.join(" · ");
}

/**
 * One render, as one attached card: the clip, then — as a separate full-width grid item
 * — its detail band.
 *
 * The old card spent most of its width on a 152px rail plus a context column,
 * so a page of history read as a stack of admin panels with a small video
 * attached. The clip is the thing being reviewed, so it leads:
 * a playable render shows the video, then its identity and saved results.
 * Detailed context and destructive actions live in the record beside it.
 *
 * A row with nothing to play is the one exception, and it keeps a notice in
 * place of the video: a blank card explains nothing, and each of those four
 * states has its own repair. Every action, its state, and the editors live
 * with the row that owns them.
 */
// Memoized: the parent re-renders on pagination, pending-save polls and
// deep-link state while the rows stay put. Props are stable callbacks plus
// row objects react-query structurally shares, so untouched rows skip the
// re-render and only the changed row pays for one.
const GenerationRow = memo(function GenerationRow({ row, onChanged, onUpdated, onKitGenerated, deepLinked = false, draftIds = null, compact = false }) {
  // A #generation- deep link (export "View in History", Analytics "View
  // render") opens this row; when it is still awaiting its TikTok link,
  // finish the job by focusing that input, so the founder lands with the
  // cursor where the next action is instead of having to remember the link
  // step and find the field inside the band. Scoped to the deep-linked
  // row and the awaiting state only: a manual expand never steals focus,
  // and a row that already has its link keeps focus where it was.
  const linkAwaiting = deepLinked && !row.tiktok_url;
  const [secondaryOpen, setSecondaryOpen] = useState(linkAwaiting);
  useEffect(() => {
    if (linkAwaiting) setSecondaryOpen(true);
  }, [linkAwaiting]);
  useEffect(() => {
    if (!linkAwaiting || !secondaryOpen) return;
    document.querySelector(`[data-testid="history-tiktok-input-${row.id}"]`)?.focus?.();
  }, [linkAwaiting, row.id, secondaryOpen]);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  // Set when the clip cannot be played inline, so the row can say so instead of
  // leaving a player that looks loaded and does nothing.
  const [previewBroken, setPreviewBroken] = useState(false);
  const [recoveredUrl, setRecoveredUrl] = useState(null);
  const [checkingRecovery, setCheckingRecovery] = useState(false);
  const [recoveryStorageError, setRecoveryStorageError] = useState(null);
  const [playerVersion, setPlayerVersion] = useState(0);
  // True once the founder presses play on this row's clip. Every badge over
  // the preview (goal, duration, delete) describes or acts on the idle frame;
  // once playback starts they all hide so nothing sits over the footage.
  const [hasPlayed, setHasPlayed] = useState(false);
  // Set when a stranded row was re-checked and the provider is genuinely still
  // rendering. Distinct from `error`: this is a successful check that found the
  // render unfinished, not a failed action, so it must not read as one.
  const [strandedNote, setStrandedNote] = useState(null);
  // Post copy and Plan context stack vertically and share one open slot:
  // Post copy starts expanded, opening one closes the other, and the open
  // one never collapses — exactly one panel is always expanded, so the row
  // never shows two dead-end headers and never stacks both open long. A row
  // with context but no kit yet starts on context instead: defaulting to a
  // panel that is not rendered would leave both headers closed.
  const [openPanel, setOpenPanel] = useState(row.post_kit ? "post" : "context");
  const togglePanel = (name) => (e) => {
    e.preventDefault();
    setOpenPanel(name);
  };

  const detailId = `generation-detail-${row.id}`;





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
  // Poster thumbnail: a tiny JPEG served as an image, so the card shows a
  // frame instantly without fetching video bytes. Missing poster (old rows,
  // generation in flight) simply omits the attribute and the <video> behaves
  // as before — a 404 poster must never break playback.
  const posterUrl = row.poster_url ? mediaUrl(row.poster_url) : null;
  const hasClip = row.status === "completed" && Boolean(downloadUrl);
  // A finished render with no fetchable copy still gets a card: the stage has
  // to say the copy is missing and the record offers the repair, which is the
  // only way a clip like that becomes playable again.
  //
  // A row stranded in `generating` gets one too. Those are not in-flight
  // renders: they are rows whose render finished at the provider while the app
  // was down, so nothing ever polled them and they kept the status forever.
  // They are invisible otherwise -- no stage, no player, no repair -- which is
  // how a paid render could sit finished and unreachable with no affordance.
  const awaitingProvider = isAwaitingProvider(row);
  const canRepair = awaitingProvider || (row.status === "completed" && (!downloadUrl || previewBroken));

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
    // A new playable URL is a new idle frame: show the pre-play badges again.
    setHasPlayed(false);
  }, [downloadUrl]);

  const act = async (fn, action = "finish this") => {
    setBusy(true);
    setError(null);
    try {
      await fn();
      onChanged?.();
    } catch (err) {
      setError(historyActionError(err, action));
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
      setError(historyActionError(err, "check this render"));
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
      setError(historyActionError(err, "recover this clip's copy"));
    } finally {
      setBusy(false);
    }
  };

  // A finished render whose post copy never got written has no kit to show
  // and no regenerate control to reach — the section only renders around an
  // existing kit. This writes one on demand through the same regenerate
  // endpoint, then opens the Post copy panel on the fresh kit. A refusal
  // names the next step instead of dying silently: without materials the
  // endpoint 404s and the founder learns the draft is gone rather than
  // staring at a button that does nothing.
  const handleGeneratePostKit = async () => {
    setBusy(true);
    setError(null);
    try {
      const res = await api.regeneratePostKit(row.id);
      const kit = res && typeof res === "object" && res.post_kit ? res.post_kit : res;
      if (!kit || typeof kit !== "object") {
        throw new Error("The server answered without post copy.");
      }
      onUpdated(row.id, { post_kit: kit });
      setOpenPanel("post");
      // The fresh kit moves the row to the with-copy side, which would
      // unmount it out from under the founder mid-click. Follow it there
      // instead, so the generated copy is what lands on screen.
      onKitGenerated?.();
    } catch (err) {
      setError(historyActionError(err, "write this render's post copy"));
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
  } else if (row.status === "submitted" && !row.video_url) {
    stageNotice = {
      title: "Queued — waiting on the provider",
      body: "This render is still queued — nothing has reported back since it was submitted. Press Check again to ask the provider.",
    };
  } else if (awaitingProvider) {
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

  const retryRenderButton = row.status === "failed" && row.retryable && (
    <Button variant="accent" disabled={busy} busy={busy} onClick={() => act(() => api.retryGeneration(row.id))} className="min-w-[150px] flex-1">
      <RotateCcw className="h-4 w-4" /> Retry render
    </Button>
  );
  const recheckButton = awaitingProvider && (
    <Button variant="secondary" size="sm" className="w-full" disabled={busy} busy={busy} onClick={handleRecheckStranded}
      data-testid={`recheck-stranded-${row.id}`} title="Ask the provider whether this render finished, and fetch it if it did">
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
      Check again
    </Button>
  );
  const retryStorageButton = canRepair && !awaitingProvider && (
    <Button variant="secondary" size="sm" className="w-full" disabled={busy} busy={busy} onClick={handleRetryStorage}
      data-testid={`retry-storage-${row.id}`} title="Re-fetch the finished render and save a durable copy, so it plays here">
      {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RotateCcw className="h-3.5 w-3.5" />}
      Retry durable save
    </Button>
  );
  const compactNotice = compact && (!downloadUrl || previewBroken);
  const notice = (
    <div className="history-stage-empty">
      <Film aria-hidden="true" className="h-4 w-4 shrink-0 text-muted-foreground" />
      <div className="min-w-0 space-y-1">
        <p className="text-base font-semibold">{stageNotice?.title}</p>
        <p className="text-sm leading-relaxed text-muted-foreground">{stageNotice?.body}</p>
      </div>
    </div>
  );

  return (
    <article
      id={`generation-${row.id}`}
      className={`surface surface-flush history-card history-row min-w-0 scroll-mt-6${compact ? " history-card-compact" : ""}`}
      data-testid="history-card"
    >
      <div className="history-row-grid">
        <div className="history-media min-w-0">
          {!compactNotice && <div className="history-stage">
            {downloadUrl && !previewBroken ? (
              /* The idle frame carries exactly two facts and no controls: the
                 goal angle top-left (where a viewer looks first) and the
                 duration top-right, so the length reads as one cluster. Both
                 are pre-play only — pressing play hides them together so
                 nothing sits over the footage. Removing the render never
                 floats over the clip: Delete lives beside Download in the row
                 below, for playable and dead rows alike. pointer-events-none
                 on the chips so they never intercept a play tap. */
              /* The clip wears the studio's own edge, not the app's: a
                 hairline indigo surround with two corner marks. It lives in
                 the frame's padding — outside the footage — so it never
                 covers a pixel, survives playback, and never reaches a
                 download. */
              <span
                className="history-preview-frame relative block w-full max-w-full"
                data-testid="history-brand-frame"
              >
                <video
                  key={`${row.id}-${playerVersion}`}
                  src={downloadUrl}
                  controls
                  playsInline
                  // Poster first: the thumbnail is a tiny JPEG image, so the card
                  // shows a frame without fetching video bytes. preload="none"
                  // means the clip itself loads only on Play.
                  preload="none"
                  poster={posterUrl || undefined}
                  onPlay={() => setHasPlayed(true)}
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
                {!hasPlayed && row.objective && (
                  <span
                    className="pointer-events-none absolute left-2 top-2 z-10 flex max-w-[calc(100%-1rem)] flex-wrap gap-1.5"
                    data-testid="history-preview-meta"
                  >
                    <FactChip className="border-white/25 bg-black/65 text-white backdrop-blur-sm">{humanize(row.objective)}</FactChip>
                  </span>
                )}
                {!hasPlayed && row.duration ? (
                  <span
                    className="pointer-events-none absolute right-2 top-2 z-10 flex max-w-[calc(100%-1rem)] items-center gap-1.5"
                    data-testid="history-preview-duration"
                  >
                    <FactChip className="border-white/25 bg-black/65 text-white backdrop-blur-sm">{row.duration}s</FactChip>
                  </span>
                ) : null}
              </span>
            ) : (
              notice
            )}
          </div>}

          <div
            className={`flex gap-2 border-t border-[color:var(--hairline)] py-2 ${compact ? "px-2" : "px-3"}`}
            data-testid="history-media-actions"
          >
            {saveUrl && (
              <Button variant="secondary" size="sm" asChild className="min-w-0 flex-1">
                <a
                  href={saveUrl}
                  download
                  onClick={() => recordSignal("video_downloaded", "downloaded", signalRefs)}
                >
                  <Download className="h-3.5 w-3.5" /> Download
                </a>
              </Button>
            )}
            {/* Delete sits beside the file that saves the render, never over
                the footage: the same icon-only square for playable and dead
                rows, and never a "Delete" label competing with Download. */}
            <Button
              variant="ghost"
              size="icon"
              className={`shrink-0 text-muted-foreground hover:text-destructive${compact ? " h-11 w-11" : " h-9 w-9"}`}
              disabled={busy}
              onClick={() => act(() => api.deleteGeneration(row.id))}
              data-testid={`history-delete-${row.id}`}
              title="Remove this render from history"
              aria-label="Delete this render"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </div>

          <div className="row-pad space-y-2 border-t border-[color:var(--hairline)]" data-testid="history-summary">
            {/* Read top to bottom in the order a founder actually scans: which
                render this is (app, state, date), then the hook that tells one
                row from another, then what happened to it (posted, views,
                vote), then provenance last — model, attempt, template and
                script versions answer a follow-up question ("why does this
                take look different from the last one?"), not the glance. They
                used to lead, which put the dimmest, least decision-relevant
                line first and the loudest one third from last. Length and goal
                stay on the preview above, where the clip they describe plays. */}
            <div className="flex flex-wrap items-center gap-2 text-xs">
              <span className="font-semibold">{row.brand_name || "Unassigned app"}</span>
              <StatusBadge status={row.status} />
              <span className="text-muted-foreground">{formatRenderDate(row.created_at)}</span>
            </div>
            <p className="break-words text-base font-semibold">
              {row.hook_line ? sentenceCase(row.hook_line) : `${row.segment_role === "demo_cta" ? "Demo + CTA export" : "Render"} \u00b7 ${row.id.slice(0, 8)}`}
            </p>
            <div className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
              <span data-testid="history-result-line">{describeResults(row)}</span>
              {isWinnerRow(row) && <FactChip>Winner</FactChip>}
            </div>
            {/* Provenance is a line, not a chip run. Four bordered pills of
                model, attempt and two versions competed with the headline for
                the same corner of the card; they answer a follow-up question
                ("why does this take look different?"), so they read as muted
                metadata now and stop borrowing the badge language the status
                and the winner use. */}
            <p className="text-xs text-muted-foreground" data-testid="history-provenance">
              {[
                row.model,
                row.attempt > 1 ? `attempt ${row.attempt}` : null,
                row.template_id ? `template v${row.template_version}` : null,
                `script v${row.script_version}`,
              ].filter(Boolean).join(" · ")}
            </p>
          </div>
        </div>

        <div
          id={detailId}
          role="region"
          aria-label="Render details"
          data-testid="history-detail-panel"
          className="history-detail min-w-0"
        >
          <div className="history-body">
            <div className="min-w-0 space-y-5">
              {compactNotice && notice}
              {/* Identity (app, status, date, hook line) lives once under the clip in history-summary above, so the record never repeats it. */}
              {(row.post_kit || row.audience || row.demo_brief) && (
                <div className="grid grid-cols-1 items-start gap-2">
                  {row.post_kit && (
                    <details
                      open={openPanel === "post"}
                      className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/20 px-3 py-1.5 transition-colors hover:border-[color:var(--hairline-strong)] hover:bg-secondary/30"
                      data-testid={`history-post-copy-${row.id}`}
                    >
                      <summary onClick={togglePanel("post")} className="flex cursor-pointer select-none list-none items-center gap-2 py-1 text-sm font-semibold text-muted-foreground transition-colors group-hover:text-foreground [&::-webkit-details-marker]:hidden">
                        <MessageSquareText aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                        <span>Post copy</span>
                        <ChevronDown aria-hidden="true" className="ml-auto h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-open:rotate-180" />
                      </summary>
                      <div className="border-t border-[color:var(--hairline)] py-3">
                        <PostKitSection postKit={row.post_kit} generationId={row.id} onUpdated={(kit) => onUpdated(row.id, { post_kit: kit })} />
                      </div>
                    </details>
                  )}

                  {(row.audience || row.demo_brief) && (
                    <details
                      open={openPanel === "context"}
                      className="group rounded-xl border border-[color:var(--hairline)] bg-secondary/20 px-3 py-1.5 transition-colors hover:border-[color:var(--hairline-strong)] hover:bg-secondary/30"
                      data-testid="history-context"
                    >
                      <summary onClick={togglePanel("context")} className="flex cursor-pointer select-none list-none items-center gap-2 py-1 text-sm font-semibold text-muted-foreground transition-colors group-hover:text-foreground [&::-webkit-details-marker]:hidden">
                        <Target aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                        <span>Plan context</span>
                        <ChevronDown aria-hidden="true" className="ml-auto h-3.5 w-3.5 shrink-0 transition-transform duration-150 group-open:rotate-180" />
                      </summary>
                      <dl className="inset-panel mb-3 mt-3 divide-y divide-[color:var(--hairline)]">
                    {row.audience && (
                      <div className="post-kit-row">
                        <dt className="eyebrow sm:pt-1">Audience</dt>
                        <dd className="min-w-0 break-words text-base leading-relaxed text-muted-foreground">{row.audience}</dd>
                      </div>
                    )}
                    {row.demo_brief && (
                      <div className="post-kit-row">
                        <dt className="eyebrow sm:pt-1">Your demo brief</dt>
                        <dd className="min-w-0 break-words text-base leading-relaxed text-muted-foreground">{row.demo_brief}</dd>
                      </div>
                    )}
                      </dl>
                    </details>
                  )}
                </div>
              )}

              {!row.post_kit && (row.status === "completed" || row.status === "archived") && (
                <div
                  className="space-y-2 rounded-xl border border-dashed border-[color:var(--hairline-strong)] px-3 py-3"
                  data-testid={`history-generate-post-copy-${row.id}`}
                >
                  <p className="flex items-center gap-2 text-sm font-semibold text-muted-foreground">
                    <MessageSquareText aria-hidden="true" className="h-3.5 w-3.5 shrink-0" />
                    <span>Post copy</span>
                  </p>
                  <p className="text-sm text-muted-foreground">
                    This render finished before its caption was written, so there is no post copy yet.
                  </p>
                  <Button
                    variant="secondary"
                    size="sm"
                    onClick={handleGeneratePostKit}
                    disabled={busy}
                    busy={busy}
                    data-testid={`history-generate-post-copy-button-${row.id}`}
                    className="gap-1.5"
                  >
                    <RotateCcw className="h-3.5 w-3.5" aria-hidden="true" />
                    {busy ? "Writing post copy" : "Generate post copy"}
                  </Button>
                </div>
              )}

              {error && <p className="text-sm text-destructive">{error}</p>}
              {checkingRecovery && (
                <p className="text-sm text-muted-foreground" role="status">Checking recovered video\u2026</p>
              )}
              {strandedNote && (
                <p className="text-sm text-muted-foreground" role="status">{strandedNote}</p>
              )}

              {(retryRenderButton || recheckButton || retryStorageButton) && (
                <div className="flex flex-wrap gap-2">{retryRenderButton}{recheckButton}{retryStorageButton}</div>
              )}
              {(
                <button
                  type="button"
                  className="history-compact-toggle w-full items-center justify-between gap-2 rounded-lg border border-[color:var(--hairline)] px-3 py-3 text-sm font-semibold hover:bg-secondary/30 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  aria-expanded={secondaryOpen}
                  aria-controls={`${detailId}-secondary`}
                  onClick={() => setSecondaryOpen((open) => !open)}
                >
                  Results &amp; actions <ChevronDown aria-hidden="true" className={`h-4 w-4 transition-transform ${secondaryOpen ? "rotate-180" : ""}`} />
                </button>
              )}
              <div id={`${detailId}-secondary`} className="history-compact-secondary space-y-5" data-expanded={secondaryOpen}>
              <HistoryFeedback row={row} signalRefs={signalRefs} onUpdated={onUpdated} />

              <div className="space-y-3 border-t border-[color:var(--hairline)] pt-5">
                <GroupLabel icon={Clapperboard}>Work with this render</GroupLabel>
                <div
                  className="flex flex-wrap gap-2"
                  role="group"
                  aria-label="Work with this render"
                  data-testid="history-actions"
                >
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
                  {shouldOfferDraftLink(row.studio_project_id, draftIds) && (
                    <Button
                      variant="secondary"
                      asChild
                      data-testid={`history-variation-${row.id}`}
                      className="min-w-[150px] flex-1"
                    >
                      <Link
                        to={`/create?project=${row.studio_project_id}`}
                        onClick={() => recordSignal("plan_opened", "open_plan", signalRefs)}
                        title={isWinnerRow(row)
                          ? "Open this winner's plan in Create Video for another take like this"
                          : "Reopen this plan in Create Video \u2014 tweak one thing, the rest stays intact. Your recorded thumbs steer the next plan"}
                      >
                        <CopyPlus className="h-4 w-4" /> {isWinnerRow(row) ? "Another take like this" : "Remix this plan"}
                      </Link>
                    </Button>
                  )}
                </div>
              </div>
              </div>
            </div>
          </div>
        </div>
      </div>
    </article>
  );
});

export default function GenerationHistory() {
  const [rows, setRows] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [moreFiltersOpen, setMoreFiltersOpen] = useState(false);
  // Failed exports that created no server row: the save path files them in
  // the outbox, and they render here as repair cards above the list — so a
  // 413 never reads as a silently missing clip.
  const [pendingSaves, setPendingSaves] = useState(() => listPendingSaves());
  const refreshPending = useCallback(() => setPendingSaves(listPendingSaves()), []);
  useEffect(() => {
    refreshPending();
    window.addEventListener("hookforge:pending-saves-changed", refreshPending);
    return () => window.removeEventListener("hookforge:pending-saves-changed", refreshPending);
  }, [refreshPending]);
  // The URL owns filters, so back/forward and same-page links cannot disagree
  // with a second local copy. Preserve the clip anchor when editing a filter.
  const [searchParams] = useSearchParams();
  const location = useLocation();
  const navigate = useNavigate();
  const profileFilter = searchParams.get("profile") || "";
  const statusFilter = searchParams.get("status") || "";
  const query = searchParams.get("q") || "";
  // Availability of post copy & plan context, URL-owned like the other
  // filters so back/forward agree. The two sides never share the screen:
  // "with" shows only cards carrying copy or context, "without" only
  // cards carrying neither. Anything else (including a missing param)
  // reads as "with", the section that leads the page.
  const copyFilter = searchParams.get("copy") === "without" ? "without" : "with";
  // A #generation-<id> deep link names one render, not one side of the
  // copy/context split. Resolve it early so the target's side wins: a
  // standalone Demo + CTA export would otherwise stay hidden behind the
  // default with-side while the URL claims to show it.
  const hashId = (location.hash || "").startsWith("#generation-")
    ? location.hash.slice("#generation-".length)
    : "";
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
      if (request === loadRequest.current) setError(historyActionError(err, "load History"));
    } finally {
      if (request === loadRequest.current) setLoading(false);
    }
  }, [profileFilter, statusFilter, limit]);

  useEffect(() => {
    load();
    return () => { loadRequest.current = null; };
  }, [load]);

  // Awaiting rows poll themselves through one hook; the page owns nothing
  // of the timer — rows in, finished rows out through updateRow.
  useAwaitingHistoryPoll(rows, updateRow);

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

  // One banner, driven by data: selection, words, and link each have one
  // owner in historyRepair, so the two cases cannot disagree.
  const attention = loading || rows.length === 0 ? null : getHistoryAttention(rows);
  const attentionWords = attention ? describeHistoryAttention(attention) : null;
  const attentionLink = attention ? historyAttentionLink(searchParams, attention) : null;

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

  // The copy/context filter narrows after the hook-text search: both are
  // client-side presentation over the same fetched window. A deep link
  // forces its target's side so the named clip is never filtered out.
  const hashTarget = hashId ? rows.find((row) => row.id === hashId) : null;
  const effectiveCopy = effectiveCopyFilter(copyFilter, hashTarget || null);
  const copyVisible = effectiveCopy === "without"
    ? visible.filter((row) => !hasCopyContext(row))
    : visible.filter(hasCopyContext);
  const completed = copyVisible.filter((r) => r.status === "completed").length;
  const failed = copyVisible.filter((r) => r.status === "failed").length;
  const ordered = sort === "views"
    ? [...copyVisible].sort((a, b) => (b.tiktok_views ?? -1) - (a.tiktok_views ?? -1))
    : copyVisible;
  // Window counts behind the two section headings: the pager below owns how
  // many cards mount, the headings own how many each side holds in full.
  const orderedWith = ordered.filter(hasCopyContext);
  const orderedWithout = ordered.filter((row) => !hasCopyContext(row));
  // The render window over the loaded rows: at most one page mounts. The
  // fetch window above still owns how many rows arrive; this owns how many
  // are in the DOM. Clamped, never empty-headed: a shrink lands on page 1
  // via the reset above, and a mid-list page survives deletions.
  const pageCount = Math.max(1, Math.ceil(ordered.length / HISTORY_PAGE_SIZE));
  const safePage = Math.min(page, pageCount);
  const paged = ordered.slice((safePage - 1) * HISTORY_PAGE_SIZE, safePage * HISTORY_PAGE_SIZE);
  // The current page split the same way as the window: each section mounts
  // only its own cards, so the two kinds are never mixed in one run.
  const pagedWith = paged.filter(hasCopyContext);
  const pagedWithout = paged.filter((row) => !hasCopyContext(row));
  const renderRow = (row) => (
    <GenerationRow
      key={row.id}
      row={row}
      compact={effectiveCopy === "without"}
      onChanged={load}
      onUpdated={updateRow}
      onKitGenerated={() => setFilter("copy", "with")}
      deepLinked={hashId !== "" && hashId === row.id}
      draftIds={draftIds}
    />
  );
  // Turning the page swaps the rows above the fold, so bring the list back
  // into view instead of stranding the founder at its bottom. The pager
  // buttons survive the turn, so the activating control keeps focus.
  const listRef = useRef(null);
  const goToPage = useCallback((next) => {
    setPage(next);
    // A manual page turn consumes the deep link: the anchor named a render,
    // not a standing claim on the pager, so leaving it would pull every
    // later turn back to the linked clip's page.
    if (location.hash) {
      navigate({ search: searchParams.toString(), hash: "" }, { replace: true });
    }
    const reduce = window.matchMedia?.("(prefers-reduced-motion: reduce)")?.matches;
    listRef.current?.scrollIntoView?.({ block: "start", behavior: reduce ? "auto" : "smooth" });
  }, [location.hash, navigate, searchParams]);
  // Focus needs no rescue here: the filter and sort controls that caused the
  // reset stay mounted, so focus is already somewhere sensible.
  useEffect(() => {
    setPage(1);
  }, [profileFilter, statusFilter, query, sort, limit, effectiveCopy]);

  // A #generation-<id> deep link (Analytics "View render") lands on a page
  // whose rows arrive after the fetch, so the browser's native anchor scroll
  // has nothing to land on. Settle it here once rows exist: bring the card
  // into view, so the link names a render that is
  // actually shown rather than a card somewhere below the fold.
  // A new anchor names the row to scroll to.
  // The deep link names a render, not a page: when the row sits past the
  // render window, jump the pager to its page exactly once per anchor. The
  // guard keeps manual pager turns on the page the founder chose instead of
  // pulling every turn back to the linked clip.
  const deepLinkHandledRef = useRef(null);
  useEffect(() => {
    if (!hashId) {
      deepLinkHandledRef.current = null;
      return;
    }
    if (!shouldApplyDeepLinkPage(deepLinkHandledRef.current, hashId)) return;
    if (ordered.length === 0) return;
    const index = ordered.findIndex((row) => row.id === hashId);
    if (index !== -1) {
      setPage(pageForRowIndex(index, HISTORY_PAGE_SIZE));
      deepLinkHandledRef.current = hashId;
    }
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
      />
      <div className="history-filters space-y-2" aria-label="History filters">
        <div className="flex flex-wrap items-center gap-2">
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
          <label className="sr-only" htmlFor="history-copy-filter">Filter by post copy and plan context</label>
          <select id="history-copy-filter" value={effectiveCopy} onChange={(e) => setFilter("copy", e.target.value)}
            aria-label="Filter by post copy and plan context" data-testid="history-copy-filter" className={PILL_SELECT_CLASS}>
            <option value="with">With post copy & context</option>
            <option value="without">Without post copy & context</option>
          </select>
          <button type="button" className="history-more-filters pill-studio tap-chip h-8 rounded-full border border-[color:var(--hairline)] px-3 text-sm font-semibold"
            aria-expanded={moreFiltersOpen} aria-controls="history-secondary-filters" onClick={() => setMoreFiltersOpen((open) => !open)}>
            More filters{(profileFilter || statusFilter || sort !== "newest") ? " (active)" : ""} <ChevronDown aria-hidden="true" className={`inline h-3.5 w-3.5 ${moreFiltersOpen ? "rotate-180" : ""}`} />
          </button>
        </div>
        <div id="history-secondary-filters" className="history-secondary-filters flex-wrap items-center gap-2" data-expanded={moreFiltersOpen}>
            <AppPicker
              profiles={profiles}
              value={profileFilter}
              onChange={(value) => setFilter("profile", value)}
              allLabel="All apps"
              ariaLabel="Filter by app"
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
        {profilesError && (
          <span role="alert" className="flex items-center gap-1 text-sm text-destructive">
            {profilesError}{" "}
            <button type="button" className="underline" onClick={loadProfiles} data-testid="profiles-retry">Try again</button>
          </span>
        )}
      </div>

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

      {!loading && pendingSaves.length > 0 ? (
        <div className="space-y-4" data-testid="pending-saves">
          {pendingSaves.map((entry) => (
            <PendingSaveCard
              key={entry.id}
              entry={entry}
              onResolved={() => {
                refreshPending();
                load();
              }}
            />
          ))}
        </div>
      ) : null}

      {attention && (
        <Alert data-testid="history-attention">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription className="flex flex-wrap items-center gap-2">
            <span>
              {attentionWords.summary}
              {attentionWords.guidance}
            </span>
            <Button variant="secondary" size="sm" asChild>
              <Link to={{ search: attentionLink.search, hash: attentionLink.hash }} data-testid="history-attention-review">
                {attentionWords.cta} <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {loading ? (
        /* Mirrors the real tile rather than a centered spinner: a bare spinner on
           a page whose cards are stacked means the layout jumps the moment data
           lands, which is the same flash the studio loader was changed to
           remove. The skeleton is the media column plus the record, because
           that is all an attached card is. */
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
      ) : shouldShowHistoryEmpty({ loading, error, rowsLength: rows.length }) ? (
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
        <div className="history-grid page-content-enter" data-testid="history-list" ref={listRef}>
          {copyVisible.length > 1 && (
            <p className="col-span-full text-sm text-muted-foreground">
              {copyVisible.length} results · {completed} completed · {failed} failed
            </p>
          )}
          {copyVisible.length === 0 && rows.length > 0 && (
            <p className="col-span-full text-sm text-muted-foreground" role="status">
              {query.trim()
                ? <>No renders match “{query.trim()}”. Clear the search to see everything.</>
                : <>No renders match this filter. Clear the filters to see everything.</>}
            </p>
          )}
          {/* Two page sections, never mixed: renders carrying post copy or
              plan context stack under one heading, renders carrying neither
              under another. Without-copy cards pair on wide screens and
              remain single-column on phones; stable row keys let React reorder without remounting, so sorting
              or filtering never drops focus and typed input mid-edit. */}
          {effectiveCopy === "with" && pagedWith.length > 0 && (
            <section
              aria-label="Renders with post copy and plan context"
              data-testid="history-section-with"
              className="col-span-full space-y-4"
            >
              <div className="space-y-1">
                <SectionHeading as="h2" icon={MessageSquareText}>
                  With post copy & plan context · {orderedWith.length} total
                </SectionHeading>
                <p className="text-sm text-muted-foreground">
                  Clips with a saved caption, audience, or demo brief attached.
                </p>
              </div>
              {pagedWith.map(renderRow)}
            </section>
          )}
          {effectiveCopy === "without" && pagedWithout.length > 0 && (
            <section
              aria-label="Renders without post copy and plan context"
              data-testid="history-section-without"
              className="col-span-full space-y-4"
            >
              <div className="space-y-1">
                <SectionHeading as="h2" icon={Film}>
                  Without post copy & context · {orderedWithout.length} total
                </SectionHeading>
                <p className="text-sm text-muted-foreground">
                  Clips with no saved copy or context yet.
                </p>
              </div>
              <div className="history-compact-grid">
                {pagedWithout.map(renderRow)}
              </div>
            </section>
          )}
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
          <span className="ml-2 text-sm text-muted-foreground" data-testid="history-page-status">
            Page {safePage} of {pageCount}
          </span>
        </nav>
      )}
    </PageFrame>
  );
}
