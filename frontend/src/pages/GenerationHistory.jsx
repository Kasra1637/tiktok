import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import EmptyState from "../components/EmptyState";
import { StatusBadge } from "../components/StatusBadge";
import { AppPicker, PILL_SELECT_CLASS } from "../components/AppPicker";
import { GroupLabel } from "../components/SectionCard";
import { IconTile } from "../components/IconTile";
import { Skeleton } from "../components/ui/skeleton";
import { api, getErrorMessage, durableMediaUrl, downloadMediaUrl, mediaUrl } from "../lib/api";
import { FactChip, FactList } from "../components/FactChip";
import { recordSignal } from "../lib/feedback";
import { CONTROL_CLASS } from "../components/formControls";
import { sentenceCase } from "../lib/copyCase";
import { History as HistoryIcon, Loader as Loader2, TriangleAlert as AlertTriangle, Download, Trash as Trash2, RotateCcw, GitBranch, RefreshCw, ChevronRight, Film, Info, Copy, X, Smartphone } from "lucide-react";

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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

  useEffect(() => {
    let cancelled = false;
    api.getGeneration(generationId)
      .then((d) => { if (!cancelled) setDetail(d); })
      .catch((err) => { if (!cancelled) setError(getErrorMessage(err)); });
    return () => { cancelled = true; };
  }, [generationId]);

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
          <div className="flex items-start gap-3">
            <IconTile icon={Film} size="section" />
            <h2 className="font-display text-base font-semibold leading-8">Generation details</h2>
          </div>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close details">
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
              <DetailRow label="Variance">
                {detail.variation_kind ? humanize(detail.variation_kind) : "None"}
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
 * One row per generation: what it is, how it turned out, and the
 * actions that apply to it.
 *
 * The facts are `FactChip`s rather than a middot-separated sentence, and the
 * card is a `SectionCard` like every other content card in the app — see those
 * two for why the vocabulary is shared rather than restated per page.
 */
function GenerationRow({ row, siblings = [], onChanged }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [showVariations, setShowVariations] = useState(false);
  const [variationKinds, setVariationKinds] = useState([]);
  const [varKind, setVarKind] = useState("hook_line");
  const [varValue, setVarValue] = useState("");
  const [children, setChildren] = useState([]);
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
  // Poster thumbnail: a tiny JPEG served as an image, so the row shows a
  // frame instantly without fetching video bytes. Missing poster (old rows,
  // generation in flight) simply omits the attribute and the <video> behaves
  // as before — a 404 poster must never break playback.
  const posterUrl = row.poster_url ? mediaUrl(row.poster_url) : null;
  const hasClip = row.status === "completed" && Boolean(downloadUrl);
  // A finished render with no fetchable copy still gets the rail: the row has
  // to say the copy is missing and offer the repair, which is the only way a
  // clip like that becomes playable again.
  //
  // A row stranded in `generating` gets it too. Those are not in-flight renders:
  // they are rows whose render finished at the provider while the app was down,
  // so nothing ever polled them and they kept the status forever. They are
  // invisible here otherwise -- no rail, no player, no repair -- which is how a
  // paid render could sit finished and unreachable with no affordance at all.
  const stuckGenerating = row.status === "generating" && !row.video_url;
  const showRail = row.status === "completed" || stuckGenerating;

  const signalRefs = {
    brand_profile_id: row.brand_profile_id,
    studio_project_id: row.studio_project_id,
    generation_id: row.id,
    template_id: row.template_id,
  };

  useEffect(() => {
    if (row.status !== "completed") return;
    api.getVariationKinds().then((d) => setVariationKinds(d.variations || [])).catch(() => {});
  }, [row.status]);

  // A new URL means a new attempt. Every history response re-signs the media
  // path, so a failure recorded against the previous signature must not keep
  // the player hidden after the row is reloaded.
  useEffect(() => {
    setPreviewBroken(false);
  }, [downloadUrl]);

  // Duplicating costs nothing and produces a draft, not a video, so it needs no
  // confirmation. The returned draft is opened directly: telling the founder a
  // draft exists without a path to it would leave the new project stranded in
  // the database with no project list to find it from.
  const handleDuplicate = async () => {
    setBusy(true);
    setError(null);
    try {
      const result = await api.duplicateGeneration(row.id);
      const draft = result?.project;
      if (!draft?.id || !draft?.brand_profile_id) {
        throw new Error("The duplicate response did not include a usable draft project.");
      }
      toast.success("Draft created. Opening the unchanged setup in the studio.");
      onChanged?.();
      navigate(
        `/create?profile=${encodeURIComponent(draft.brand_profile_id)}` +
        `&project=${encodeURIComponent(draft.id)}`
      );
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

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

  const loadChildren = async () => {
    setShowVariations((v) => !v);
    if (!showVariations) {
      try {
        const d = await api.getGenerationVariations(row.id);
        setChildren(d.variations || []);
      } catch (err) {
        setError(getErrorMessage(err));
      }
    }
  };

  // Resolve a row stranded in `generating`. This is NOT the storage repair: that
  // endpoint refuses any row that has not completed (server.py:8632), and a
  // stranded row never did, so it would answer 409 forever. Polling is the only
  // path that can move it -- the provider may already hold a finished clip, and
  // the poll handler is what downloads it, uploads to R2 and flips the status.
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

  return (
    <div id={`generation-${row.id}`} className="surface scroll-mt-6 rounded-2xl">
      {/* One grid for the whole row, and the clip gets a rail of its own.

          It used to sit in a 240px column with roughly 800px of empty card to
          its right, because everything else in the row was full-width text on
          the way to an action bar at the bottom. Putting the player in a rail
          and giving the right column the content it was missing removes the
          void by using it, rather than by stretching the player to fill it —
          a 9:16 clip wide enough to span 1150px would be two thousand pixels
          tall.

          The grid exists for a finished render: a clip, or the card that says
          why there is no playable clip. A failed render has neither, and
          forcing its error message into a 240px rail would make the two states
          look like different components. */}
      <div className={`grid gap-4 ${showRail ? "sm:grid-cols-[minmax(0,240px)_minmax(0,1fr)]" : ""}`}>
        {showRail && (
          <div className="space-y-2">
            {downloadUrl && !previewBroken ? (
              <video
                key={`${row.id}-${playerVersion}`}
                src={downloadUrl}
                controls
                playsInline
                // Poster first: the thumbnail is a tiny JPEG image, so the row
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
                className="mx-auto max-h-[300px] w-full rounded-lg border border-[color:var(--hairline)] object-contain sm:max-h-[340px]"
                // Capped, not cropped: a 9:16 clip in an uncapped full-width box
                // runs ~430px tall and stretches the whole card, leaving the
                // right column mostly empty. object-contain letterboxes it on
                // the dark background instead, which also tames the player on
                // mobile where the rail spans the full width.
              />
            ) : (
              /* Says what is actually true instead of leaving a dead control.
                 Two different truths share this card, and conflating them was
                 the bug: a copy exists but the browser would not play it (an
                 expired signature, an object that is no longer there), or no
                 copy exists at all because the durable save failed — and in the
                 second case there is nothing to download either, so promising
                 one was a dead end. The repair below is the way through both. */
              <div className="rounded-xl border border-dashed border-[color:var(--hairline-strong)] p-4">
                <p className="text-sm">
                  {stuckGenerating
                    ? "Still marked as generating"
                    : downloadUrl
                      ? "Preview unavailable"
                      : "No durable copy"}
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {stuckGenerating
                    ? "This render may already be finished at the provider — nothing has checked since it was submitted. Check again to fetch it."
                    : downloadUrl
                      ? "The saved video could not be loaded. Retry recovery to check its local and cloud copies."
                      : "This render finished without a copy the browser can open, so there is nothing to play or download yet."}
                </p>
              </div>
            )}
            {checkingRecovery && (
              <p className="text-xs text-muted-foreground" role="status">Checking recovered video…</p>
            )}
            {strandedNote && (
              <p className="text-xs text-muted-foreground" role="status">{strandedNote}</p>
            )}
            {/* Download and Delete on one row: both act on this file, and stacking them
                cost a full-width button each in a 240px rail. Download takes
                the slack because it is what the row is for; Delete is
                fixed-width so the two stay aligned at any rail width.
                Download points at downloadMediaUrl, the same-origin route that
                forces a save. The playback href was cross-origin whenever the
                durable copy was in R2, and browsers ignore `download` there, so
                the button opened a tab instead of saving the file.

                Delete sits beside it deliberately, not parked at the far edge:
                it destroys the clip previewed directly above, one click away.
                That muscle-memory safeguard is gone by request, so the label is
                spelled out and the icon is tinted rather than neutral -- it
                should read as destructive at a glance. */}
            <div className="flex items-center gap-2">
              {saveUrl && (
                <Button
                  variant="ghost"
                  size="sm"
                  className="h-8 flex-1 px-2 text-muted-foreground"
                  asChild
                >
                  <a
                    href={saveUrl}
                    download
                    onClick={() => recordSignal("video_downloaded", "downloaded", signalRefs)}
                  >
                    <Download className="h-3.5 w-3.5" /> Download
                  </a>
                </Button>
              )}
              <Button
                variant="ghost"
                size="sm"
                className="h-8 px-2 text-muted-foreground hover:text-destructive"
                disabled={busy}
                onClick={() => act(() => api.deleteGeneration(row.id))}
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
            {!stuckGenerating && (!downloadUrl || previewBroken) && (
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
        )}

        <div className="min-w-0 space-y-4">
          {/* Identity, then what it says. The model/duration badges that
              used to sit opposite the app name are gone from here — they are
              facts about the render, not about which video this is, and they
              join the strip below. */}
          <div className="flex flex-wrap items-center gap-2">
            <GroupLabel>{row.brand_name || "Unassigned app"}</GroupLabel>
            <StatusBadge status={row.status} />
            {row.parent_generation_id && (
              <Badge variant="outline" className="gap-1 text-xs">
                <GitBranch className="h-3 w-3" /> Variation
              </Badge>
            )}
            {row.variation_kind && (
              <Badge variant="secondary" className="text-xs">
                {humanize(row.variation_kind)}
              </Badge>
            )}
          </div>

          {row.hook_line && (
            <p className="text-sm leading-snug text-muted-foreground">
              &ldquo;{sentenceCase(row.hook_line)}&rdquo;
            </p>
          )}

          {/* One treatment for every fact about the render.

              These were three: four badges opposite the title, and a run-on
              "a · b · c · date" sentence below it. A sentence of dots is not
              scannable — you cannot find one fact in it without reading it
              all — and two treatments for the same kind of information meant
              the card never looked settled. Chips also let the row go quiet
              when facts are missing instead of leaving a dangling separator. */}
          <FactList>
            {row.model && <FactChip>{row.model}</FactChip>}
            {row.duration ? <FactChip>{row.duration}s</FactChip> : null}
            {row.attempt > 1 ? <FactChip>attempt {row.attempt}</FactChip> : null}
            {row.objective ? <FactChip>{humanize(row.objective)}</FactChip> : null}
            {row.template_id ? <FactChip>template v{row.template_version}</FactChip> : null}
            <FactChip>script v{row.script_version}</FactChip>
            <FactChip>{new Date(row.created_at).toLocaleString()}</FactChip>
          </FactList>

          {error && <p className="text-xs text-destructive">{error}</p>}

          {row.status === "failed" && (
            <div className="flex flex-wrap items-center gap-2">
              <p className="flex-1 text-xs text-destructive">{row.error}</p>
              {row.retryable && (
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => act(() => api.retryGeneration(row.id))}
                >
                  <RotateCcw className="h-3.5 w-3.5" /> Retry
                </Button>
              )}
            </div>
          )}

          {/* Navigation actions, in a bordered group instead of a full-width bar below the card. The bar
              stretched short cards and left the right column half empty beside
              a tall 9:16 player; the group fills that space with the actions
              that belong to the render.

              Archive and Delete both left this page. They acted on the FILE,
              not the navigation, and the rail under the clip now holds Delete
              beside Download where the thing being destroyed is visible. The
              status filter still offers "archived", so a row archived before
              this change remains findable — just not archivable again. */}
          <div className="space-y-2 border-t border-[color:var(--hairline)] pt-4">
            <GroupLabel>Work with this render</GroupLabel>
            <div className="flex flex-wrap items-center gap-2">
              <Button variant="ghost" size="sm" onClick={loadChildren}>
                <GitBranch className="h-3.5 w-3.5" /> Variations
                {children.length > 0 && ` (${children.length})`}
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => setShowDetails(true)}
                data-testid="generation-details-button"
              >
                <Info className="h-3.5 w-3.5" /> Details
              </Button>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={handleDuplicate}
                title="Copy this setup unchanged into a new draft, for a fresh render of the same video"
              >
                <Copy className="h-3.5 w-3.5" /> Duplicate
              </Button>
              {/* Only a finished clip has anything to wrap, so the entry rides
                  hasClip rather than status alone: offering it on a queued or failed
                  render would open an editor with no source. */}
              {hasClip && (
                <Button variant="ghost" size="sm" asChild data-testid={`demo-cta-history-${row.id}`}>
                  <Link to={`/demo-cta/${row.id}`} title="Wrap this clip in a phone mockup and add your close">
                    <Smartphone className="h-3.5 w-3.5" /> Demo + CTA
                  </Link>
                </Button>
              )}
            </div>
          </div>
        </div>
      </div>

      {siblings.length > 0 && (
        <div className="space-y-2 border-t border-[color:var(--hairline)] pt-4">
          <GroupLabel>More from this app</GroupLabel>
          <ul className="space-y-2">
            {siblings.map((s) => (
              <li key={s.id}>
                <a
                  href={`#generation-${s.id}`}
                  className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] bg-card/70 px-4 py-3 text-left transition-colors hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)]"
                >
                  <span className="min-w-0 flex-1 truncate text-sm text-foreground/90">
                    {s.hook_line ? sentenceCase(s.hook_line) : humanize(s.status)}
                  </span>
                  <StatusBadge status={s.status} />
                </a>
              </li>
            ))}
          </ul>
        </div>
      )}

      {showDetails && (
        <GenerationDetails generationId={row.id} onClose={() => setShowDetails(false)} />
      )}

      {showVariations && (
        <div className="space-y-4 border-t border-[color:var(--hairline)] pt-4">
          {children.length > 0 && (
            <div className="space-y-2">
              {children.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate text-muted-foreground">
                    {humanize(c.variation_kind)} &rarr; {c.project_hook ? sentenceCase(c.project_hook) : c.status}
                  </span>
                  <StatusBadge status={c.status} />
                </div>
              ))}
            </div>
          )}

          <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_1fr_auto]">
            <select
              value={varKind}
              onChange={(e) => setVarKind(e.target.value)}
              aria-label="Variation type"
              className={CONTROL_CLASS}
            >
              {variationKinds.map((v) => (
                <option key={v.key} value={v.key}>{v.label}</option>
              ))}
            </select>
            <Input
              value={varValue}
              onChange={(e) => setVarValue(e.target.value)}
              placeholder="New value"
              aria-label="Variation value"
            />
            <Button
              variant="brand"
              size="sm"
              disabled={busy || !varValue.trim()}
              onClick={() =>
                act(async () => {
                  await api.createVariation(row.id, {
                    kind: varKind,
                    value: varValue.trim(),
                  });
                  setVarValue("");
                  const d = await api.getGenerationVariations(row.id);
                  setChildren(d.variations || []);
                })
              }
            >
              {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
              Create
            </Button>
          </div>
          <p className="text-xs text-muted-foreground">
            A variation makes a draft. You review it and generate the video yourself, so
            nothing runs until you say so.
          </p>
        </div>
      )}
    </div>
  );
}

export default function GenerationHistory() {
  const [rows, setRows] = useState([]);
  const [profiles, setProfiles] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [profileFilter, setProfileFilter] = useState("");
  const [statusFilter, setStatusFilter] = useState("");

  const load = useCallback(async () => {
    setLoading(true);
    try {
      const data = await api.getGenerationHistory({
        brand_profile_id: profileFilter || undefined,
        status: statusFilter || undefined,
        limit: 100,
      });
      setRows(data.generations || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [profileFilter, statusFilter]);

  useEffect(() => {
    load();
  }, [load]);

  useEffect(() => {
    api.getAppProfiles().then((d) => setProfiles(d.profiles || [])).catch(() => setProfiles([]));
  }, []);

  const completed = rows.filter((r) => r.status === "completed").length;
  const failed = rows.filter((r) => r.status === "failed").length;

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        data-testid="history-header"
        icon={HistoryIcon}
        title="Generation History"
        description="Review renders and exports, and download your clips."
        actions={
          <div className="flex flex-wrap items-center gap-2">
            <AppPicker
              profiles={profiles}
              value={profileFilter}
              onChange={setProfileFilter}
              allLabel="All apps"
              ariaLabel="Filter by app"
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
        /* Mirrors the real row rather than a centered spinner: a bare spinner on
           a page whose cards are stacked means the layout jumps the moment data
           lands, which is the same flash the studio loader was changed to
           remove. */
        <div className="space-y-4" aria-label="Loading history" data-testid="history-loading">
          {[0, 1, 2].map((i) => (
            <div key={i} className="surface space-y-4 rounded-2xl">
              <div className="flex items-center justify-between gap-2">
                <Skeleton className="h-4 w-32" />
                <Skeleton className="h-4 w-20" />
              </div>
              <Skeleton className="h-4 w-3/5" />
              <Skeleton className="h-40 w-full max-w-[240px]" />
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Nothing generated yet"
          description="Create Video saves generated Hook + Story clips here."
          action={
            <Button variant="brand" asChild>
              <Link to="/create">
                Create a video <ChevronRight className="h-4 w-4" />
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-4" data-testid="history-list">
          {rows.length > 1 && (
            <p className="text-xs text-muted-foreground">
              {rows.length} results · {completed} completed · {failed} failed
            </p>
          )}
          {rows.map((row) => (
            <GenerationRow
              key={row.id}
              row={row}
              siblings={rows
                .filter((r) => r.id !== row.id && r.brand_profile_id && r.brand_profile_id === row.brand_profile_id)
                .slice(0, 4)}
              onChanged={load}
            />
          ))}
        </div>
      )}
    </PageFrame>
  );
}
