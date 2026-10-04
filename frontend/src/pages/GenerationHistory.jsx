import { useCallback, useEffect, useState } from "react";
import { Link, useNavigate } from "react-router-dom";
import { toast } from "sonner";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import { recordSignal, recordReason } from "../lib/feedback";
import {
  History as HistoryIcon, Loader2, AlertTriangle, Download, Trash2, Archive,
  RotateCcw, GitBranch, RefreshCw, ChevronRight, Film, Star, TrendingUp,
  Check, ThumbsDown, Info, Copy, X,
} from "lucide-react";

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

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
  const [label, variant] = map[status] || [humanize(status), "secondary"];
  return <Badge variant={variant} className="text-xs">{label}</Badge>;
}

/**
 * `openInitially` is how the post-download nudge reaches this form.
 *
 * The nudge in RecordResultsNudge links to /history?generation=<id>, and the
 * founder is standing there holding the view count they just saw on TikTok.
 * Making them then find the right row and find the right button out of eight
 * identical ghost buttons is where the learning loop actually dies, so the
 * query param opens the form on arrival. It is a starting position, not a
 * lock: the founder can still cancel it, and the form stays closable.
 */
function PerformanceForm({ generation, onSaved, openInitially = false }) {
  const [open, setOpen] = useState(openInitially);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [form, setForm] = useState({
    views: "", likes: "", comments: "", shares: "", saves: "",
    notes: "", outcome: "",
  });

  const save = async () => {
    setBusy(true);
    setError(null);
    try {
      const payload = {
        views: form.views === "" ? undefined : Number(form.views),
        likes: form.likes === "" ? undefined : Number(form.likes),
        comments: form.comments === "" ? undefined : Number(form.comments),
        shares: form.shares === "" ? undefined : Number(form.shares),
        saves: form.saves === "" ? undefined : Number(form.saves),
        notes: form.notes || undefined,
        outcome: form.outcome || undefined,
      };
      await api.recordPerformance(generation.id, payload);
      // A recorded verdict is the one place the founder states a judgment
      // outright, so it feeds the loop directly rather than as a bare trigger.
      if (form.outcome === "successful" || form.outcome === "unsuccessful") {
        await recordReason(
          form.outcome === "successful" ? "marked_successful" : "marked_unsuccessful",
          form.outcome === "successful" ? "good_performance" : "poor_performance",
          {
            brand_profile_id: generation.brand_profile_id,
            studio_project_id: generation.studio_project_id,
            generation_id: generation.id,
            template_id: generation.template_id,
          },
        );
      }
      setOpen(false);
      onSaved?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (!open) {
    return (
      <Button
        variant="ghost"
        size="sm"
        onClick={() => setOpen(true)}
        data-testid="record-results-button"
      >
        <TrendingUp className="h-3.5 w-3.5" /> Record results
      </Button>
    );
  }

  return (
    <div
      className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-3"
      data-testid="record-results-form"
    >
      <span className="eyebrow block">Manually entered &mdash; not platform-verified</span>
      {error && <p className="text-xs text-destructive">{error}</p>}
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        {["views", "likes", "comments", "shares", "saves"].map((k) => (
          <label key={k} className="space-y-1">
            <span className="text-[11px] text-muted-foreground">{humanize(k)}</span>
            <Input
              type="number"
              min="0"
              value={form[k]}
              onChange={(e) => setForm({ ...form, [k]: e.target.value })}
              aria-label={humanize(k)}
            />
          </label>
        ))}
      </div>
      <div className="grid grid-cols-1 gap-2 sm:grid-cols-2">
        <select
          value={form.outcome}
          onChange={(e) => setForm({ ...form, outcome: e.target.value })}
          aria-label="Outcome"
          className="rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
        >
          <option value="">No verdict</option>
          <option value="successful">Worked</option>
          <option value="unsuccessful">Did not work</option>
        </select>
        <Input
          value={form.notes}
          onChange={(e) => setForm({ ...form, notes: e.target.value })}
          placeholder="Notes, e.g. posted 3pm"
          aria-label="Notes"
        />
      </div>
      <div className="flex gap-2">
        <Button size="sm" variant="brand" onClick={save} disabled={busy}>
          {busy && <Loader2 className="h-3.5 w-3.5 animate-spin" />} Save
        </Button>
        <Button size="sm" variant="ghost" onClick={() => setOpen(false)}>Cancel</Button>
      </div>
    </div>
  );
}

function DetailRow({ label, children }) {
  if (children === null || children === undefined || children === "") return null;
  return (
    <div className="space-y-0.5">
      <span className="eyebrow block">{label}</span>
      <div className="text-sm">{children}</div>
    </div>
  );
}

/**
 * Everything about one render that the history row deliberately leaves out.
 *
 * The list stays light on purpose, but "why does this video look like this"
 * is answerable only from the prompt, the script it was built from, and the
 * overlays that were composited afterwards. Those three together are the
 * audit trail for a claim in a published video, so they belong one click away
 * rather than only in the database.
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

  const overlays = detail?.overlays || detail?.composition?.applied || [];

  return (
    <div
      className="fixed inset-0 z-50 flex items-start justify-center overflow-y-auto bg-black/50 p-4"
      role="dialog"
      aria-modal="true"
      aria-label="Generation details"
      onClick={onClose}
    >
      <div
        className="surface my-8 w-full max-w-2xl space-y-4 rounded-2xl p-5"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="flex items-start justify-between gap-3">
          <h2 className="font-display text-base font-semibold">Generation details</h2>
          <Button variant="ghost" size="sm" onClick={onClose} aria-label="Close details">
            <X className="h-3.5 w-3.5" />
          </Button>
        </div>

        {error && <p className="text-sm text-destructive">{error}</p>}
        {!detail && !error && (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading...
          </p>
        )}

        {detail && (
          <div className="space-y-4">
            <div className="grid grid-cols-2 gap-3 sm:grid-cols-3">
              <DetailRow label="Model">{detail.model}</DetailRow>
              <DetailRow label="Status">{humanize(detail.status)}</DetailRow>
              <DetailRow label="Cost">{money(detail.cost_usd)}</DetailRow>
              <DetailRow label="Script version">v{detail.script_version}</DetailRow>
              <DetailRow label="Template version">v{detail.template_version}</DetailRow>
              <DetailRow label="Attempt">{detail.attempt}</DetailRow>
              <DetailRow label="Objective">
                {detail.objective ? humanize(detail.objective) : null}
              </DetailRow>
              <DetailRow label="Variance">
                {detail.variation_kind ? humanize(detail.variation_kind) : "None"}
              </DetailRow>
              <DetailRow label="Cost source">{humanize(detail.cost_source)}</DetailRow>
            </div>

            {detail.hook_line && (
              <DetailRow label="Hook">{detail.hook_line}</DetailRow>
            )}

            {detail.script && (
              <div className="space-y-0.5">
                <span className="eyebrow block">Script as generated</span>
                <pre className="max-h-48 overflow-y-auto whitespace-pre-wrap rounded-lg bg-secondary/40 p-3 text-sm">
                  {detail.script}
                </pre>
              </div>
            )}

            {detail.prompt_used && (
              <div className="space-y-0.5">
                <span className="eyebrow block">Exact prompt sent to the model</span>
                <pre className="max-h-56 overflow-y-auto whitespace-pre-wrap rounded-lg bg-secondary/40 p-3 text-xs">
                  {detail.prompt_used}
                </pre>
              </div>
            )}

            {Array.isArray(overlays) && overlays.length > 0 && (
              <div className="space-y-1.5">
                <span className="eyebrow block">On-screen text composited</span>
                <ul className="space-y-1 text-sm">
                  {overlays.map((o, i) => (
                    <li key={i} className="text-muted-foreground">
                      {o.start ?? 0}&ndash;{o.end ?? 0}s: {o.text || o.label || JSON.stringify(o)}
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {detail.safety_report && (
              <div className="space-y-1">
                <span className="eyebrow block">Claim check at generation time</span>
                <p className="text-sm text-muted-foreground">
                  {detail.safety_report.passed ? "Passed" : "Failed"}
                  {detail.safety_summary ? ` — ${detail.safety_summary}` : ""}
                </p>
              </div>
            )}

            {detail.error && (
              <div className="space-y-1">
                <span className="eyebrow block">Recorded error</span>
                <p className="text-sm text-destructive">{detail.error}</p>
              </div>
            )}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * One fact about a render: model, length, cost, objective, version, date.
 *
 * Chips rather than a sentence of middot-separated values, because a sentence
 * has to be read end to end to find one fact in it, and because the row used to
 * carry the same kind of information two ways — four badges opposite the title
 * and a run-on line below it — which is why it never looked settled. Text is
 * `text-xs`, which is 12px: the project's floor, and one step up from the 11px
 * the old badges used.
 */
function FactChip({ children }) {
  return (
    <span className="rounded-full border border-[color:var(--hairline)] px-2 py-0.5 text-xs text-muted-foreground">
      {children}
    </span>
  );
}

function GenerationRow({ row, onChanged, focusGenerationId }) {
  const navigate = useNavigate();
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [showVariations, setShowVariations] = useState(false);
  const [variationKinds, setVariationKinds] = useState([]);
  const [varKind, setVarKind] = useState("hook_line");
  const [varValue, setVarValue] = useState("");
  const [children, setChildren] = useState([]);
  // The founder's verdict on a finished video, or "" if they have not said.
  // Local only: the outcome is a judgment about this render, and reloading the
  // page should not invite them to answer twice.
  const [verdict, setVerdict] = useState("");
  const [showDetails, setShowDetails] = useState(false);
  // Set when the clip cannot be played inline, so the row can say so instead of
  // leaving a player that looks loaded and does nothing.
  const [previewBroken, setPreviewBroken] = useState(false);

  const downloadUrl = row.r2_url || row.video_url;
  const composedUrl = row.composition?.r2_url || row.composition?.output_url;
  const cost = money(row.cost_usd);
  const hasClip = row.status === "completed" && Boolean(downloadUrl);

  const signalRefs = {
    brand_profile_id: row.brand_profile_id,
    studio_project_id: row.studio_project_id,
    generation_id: row.id,
    template_id: row.template_id,
  };

  // Two buttons rather than a reason picker. The spec wants approval and
  // rejection captured; asking the founder to also diagnose the cause at this
  // moment would cost more attention than the answer is worth, so only the
  // factual trigger is recorded and any reason stays optional.
  const judge = (next) => {
    setVerdict(next);
    recordSignal(
      next === "approved" ? "video_approved" : "generation_rejected",
      next,
      signalRefs,
    );
  };

  useEffect(() => {
    if (row.status !== "completed") return;
    api.getVariationKinds().then((d) => setVariationKinds(d.variations || [])).catch(() => {});
  }, [row.status]);

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

  return (
    <div className="surface rounded-2xl p-4">
      {/* One grid for the whole row, and the clip gets a rail of its own.

          It used to sit in a 240px column with roughly 800px of empty card to
          its right, because everything else in the row was full-width text on
          the way to an action bar at the bottom. Putting the player in a rail
          and giving the right column the content it was missing removes the
          void by using it, rather than by stretching the player to fill it —
          a 9:16 clip wide enough to span 1150px would be two thousand pixels
          tall.

          The grid only exists when there is a clip: a failed render has no
          player, and forcing its error message into a 240px rail would make
          the two states look like different components. */}
      <div className={`grid gap-4 ${hasClip ? "sm:grid-cols-[minmax(0,240px)_minmax(0,1fr)]" : ""}`}>
        {hasClip && (
          <div className="space-y-2">
            {previewBroken ? (
              /* Says what is actually true instead of leaving a dead control.
                 A clip whose source cannot be played inline (an expired
                 provider URL, a storage path that no longer resolves) used to
                 render a player that looked loaded and did nothing, which reads
                 as a bug in the app rather than a file that cannot be previewed
                 here. The download is the way through either way. */
              <div className="rounded-xl border border-dashed border-[color:var(--hairline-strong)] p-3">
                <p className="text-sm">Preview unavailable</p>
                <p className="mt-0.5 text-xs text-muted-foreground">
                  This clip cannot be played here. Download it to view.
                </p>
              </div>
            ) : (
              <video
                src={mediaUrl(downloadUrl)}
                controls
                playsInline
                preload="metadata"
                onError={() => setPreviewBroken(true)}
                className="w-full rounded-lg border border-[color:var(--hairline)]"
              />
            )}
            {/* The download sits under the file it produces. It was the most
                likely action on the card and it sat in a ten-item row at the
                bottom, two lines away from the thing it acts on. */}
            <Button variant="secondary" size="sm" className="w-full" asChild>
              <a
                href={mediaUrl(downloadUrl)}
                download
                onClick={() => recordSignal("video_downloaded", "downloaded", signalRefs)}
              >
                <Download className="h-3.5 w-3.5" /> Download MP4
              </a>
            </Button>
            {composedUrl && (
              <Button variant="secondary" size="sm" className="w-full" asChild>
                <a
                  href={mediaUrl(composedUrl)}
                  download
                  onClick={() => recordSignal("video_downloaded", "downloaded", signalRefs)}
                >
                  <Star className="h-3.5 w-3.5" /> With real visuals
                </a>
              </Button>
            )}
          </div>
        )}

        <div className="min-w-0 space-y-3">
          {/* Identity, then what it says. The model/duration/cost badges that
              used to sit opposite the app name are gone from here — they are
              facts about the render, not about which video this is, and they
              join the strip below. */}
          <div className="flex flex-wrap items-center gap-2">
            <span className="font-display text-sm font-semibold">
              {row.brand_name || "Unassigned app"}
            </span>
            <StatusBadge status={row.status} />
            {row.parent_generation_id && (
              <Badge variant="outline" className="text-[11px]">
                <GitBranch className="mr-1 h-2.5 w-2.5" /> Variation
              </Badge>
            )}
            {row.variation_kind && (
              <Badge variant="secondary" className="text-[11px]">
                {humanize(row.variation_kind)}
              </Badge>
            )}
          </div>

          {row.hook_line && (
            <p className="text-sm leading-snug text-muted-foreground">
              &ldquo;{row.hook_line}&rdquo;
            </p>
          )}

          {/* One treatment for every fact about the render.

              These were three: four badges opposite the title, and a run-on
              "a · b · c · date" sentence below it. A sentence of dots is not
              scannable — you cannot find one fact in it without reading it
              all — and two treatments for the same kind of information meant
              the card never looked settled. Chips also let the row go quiet
              when facts are missing instead of leaving a dangling separator. */}
          <div className="flex flex-wrap items-center gap-1.5">
            {row.model && <FactChip>{row.model}</FactChip>}
            {row.duration ? <FactChip>{row.duration}s</FactChip> : null}
            {cost ? <FactChip>{cost}</FactChip> : null}
            {row.attempt > 1 ? <FactChip>attempt {row.attempt}</FactChip> : null}
            {row.objective ? <FactChip>{humanize(row.objective)}</FactChip> : null}
            {row.template_id ? <FactChip>template v{row.template_version}</FactChip> : null}
            <FactChip>script v{row.script_version}</FactChip>
            <FactChip>{new Date(row.created_at).toLocaleString()}</FactChip>
          </div>

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

          {row.performance && (
            <p className="text-xs text-muted-foreground">
              Manually logged: {row.performance.views ?? 0} views
              {row.performance.likes != null && `, ${row.performance.likes} likes`}
              {row.performance.outcome && ` — ${row.performance.outcome}`}
            </p>
          )}

          {/* The verdict is a judgement about the video, which is a different
              kind of action from moving a file or deleting a row. It used to be
              a text fragment sitting inline between two buttons, so it read as
              a label for whatever came next rather than a question. In its own
              bordered group with a heading, it asks to be answered — which is
              the point of asking. */}
          {row.status === "completed" && (
            <div className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-3">
              <span className="eyebrow block">How did this turn out?</span>
              <div className="flex flex-wrap items-center gap-1.5">
                <Button
                  variant="ghost"
                  size="sm"
                  aria-pressed={verdict === "approved"}
                  onClick={() => judge("approved")}
                  className={verdict === "approved" ? "text-success" : undefined}
                >
                  <Check className="h-3.5 w-3.5" /> Looks good
                </Button>
                <Button
                  variant="ghost"
                  size="sm"
                  aria-pressed={verdict === "rejected"}
                  onClick={() => judge("rejected")}
                  className={verdict === "rejected" ? "text-destructive" : undefined}
                >
                  <ThumbsDown className="h-3.5 w-3.5" /> Not good
                </Button>
                <PerformanceForm
                  generation={row}
                  onSaved={onChanged}
                  openInitially={row.id === focusGenerationId}
                />
              </div>
            </div>
          )}
        </div>
      </div>

      {/* One action bar per card, and it carries no file actions.

          Downloads moved up beside the clip, and the verdict controls above.
          What is left is navigation on the left and the destructive pair held
          at the right edge, so Archive and Delete cannot be reached by muscle
          memory on the way to Details. The hairline separates acting on the row
          from reading it, which is what the variations panel below already
          does. */}
      <div className="mt-3 flex flex-wrap items-center gap-1.5 border-t border-[color:var(--hairline)] pt-3">
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
        <span className="ml-auto flex items-center gap-1.5">
          <Button
            variant="ghost"
            size="sm"
            disabled={busy || row.status === "archived"}
            onClick={() => act(() => api.archiveGeneration(row.id))}
          >
            <Archive className="h-3.5 w-3.5" /> Archive
          </Button>
          <Button
            variant="ghost"
            size="sm"
            disabled={busy}
            onClick={() => act(() => api.deleteGeneration(row.id))}
          >
            <Trash2 className="h-3.5 w-3.5" /> Delete
          </Button>
        </span>
      </div>

      {showDetails && (
        <GenerationDetails generationId={row.id} onClose={() => setShowDetails(false)} />
      )}

      {showVariations && (
        <div className="space-y-3 border-t border-[color:var(--hairline)] pt-3">
          {children.length > 0 && (
            <div className="space-y-1.5">
              {children.map((c) => (
                <div key={c.id} className="flex items-center justify-between gap-2 text-xs">
                  <span className="truncate text-muted-foreground">
                    {humanize(c.variation_kind)} &rarr; {c.project_hook || c.status}
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
              className="rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
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
            nothing is spent until you say so.
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
  // Where the post-download nudge sends the founder. They arrive holding the
  // view count they just saw, so the matching row's results form starts open
  // rather than making them find one row out of a list and then pick the right
  // button out of eight identical ones. Read once on mount: a later filter
  // change should not re-open a form someone already dismissed.
  const [focusGenerationId] = useState(() => {
    const raw = new URLSearchParams(window.location.search).get("generation") || "";
    return raw.trim();
  });

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

  const spent = rows.reduce((sum, r) => sum + (r.cost_usd || 0), 0);
  const completed = rows.filter((r) => r.status === "completed").length;
  const failed = rows.filter((r) => r.status === "failed").length;

  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      <PageHeader
        icon={HistoryIcon}
        title="Generation History"
        description="Every video produced, with the exact template, script version, model, and cost behind it. Publishing stays manual."
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="surface flex flex-wrap items-center gap-2 rounded-2xl p-4" data-testid="history-filters">
        <select
          value={profileFilter}
          onChange={(e) => setProfileFilter(e.target.value)}
          aria-label="Filter by app"
          className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
        >
          <option value="">All apps</option>
          {profiles.map((p) => (
            <option key={p.id} value={p.id}>{p.brand_name}</option>
          ))}
        </select>
        <select
          value={statusFilter}
          onChange={(e) => setStatusFilter(e.target.value)}
          aria-label="Filter by status"
          className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-1.5 text-xs font-medium"
        >
          <option value="">All statuses</option>
          {["completed", "failed", "generating", "submitted", "archived"].map((s) => (
            <option key={s} value={s}>{humanize(s)}</option>
          ))}
        </select>
        {rows.length > 0 && (
          <span className="ml-auto text-xs text-muted-foreground">
            {rows.length} result{rows.length === 1 ? "" : "s"} · {completed} completed ·{" "}
            {failed} failed · {money(spent)} spent
          </span>
        )}
      </div>

      {loading ? (
        /* Mirrors the real row rather than a centered spinner: a bare spinner on
           a page whose cards are stacked means the layout jumps the moment data
           lands, which is the same flash the studio loader was changed to
           remove. */
        <div className="space-y-3" aria-label="Loading history" data-testid="history-loading">
          {[0, 1, 2].map((i) => (
            <div key={i} className="surface space-y-3 rounded-2xl p-4">
              <div className="flex items-center justify-between gap-2">
                <div className="h-4 w-32 animate-pulse rounded bg-secondary/60" />
                <div className="h-4 w-20 animate-pulse rounded bg-secondary/40" />
              </div>
              <div className="h-3 w-3/5 animate-pulse rounded bg-secondary/40" />
              <div className="h-40 w-full max-w-[240px] animate-pulse rounded-lg bg-secondary/30" />
            </div>
          ))}
        </div>
      ) : rows.length === 0 ? (
        <EmptyState
          icon={Film}
          title="Nothing generated yet"
          description="Create a video from an approved App Profile and a hook template, and it will appear here."
          action={
            <Button variant="brand" asChild>
              <Link to="/create">
                Create a video <ChevronRight className="h-3.5 w-3.5" />
              </Link>
            </Button>
          }
        />
      ) : (
        <div className="space-y-3" data-testid="history-list">
          {rows.map((row) => (
            <GenerationRow
              key={row.id}
              row={row}
              onChanged={load}
              focusGenerationId={focusGenerationId}
            />
          ))}
        </div>
      )}
    </div>
  );
}
