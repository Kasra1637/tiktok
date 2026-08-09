import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Skeleton } from "../components/ui/skeleton";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "../components/ui/dialog";
import {
  AlertDialog,
  AlertDialogContent,
  AlertDialogHeader,
  AlertDialogFooter,
  AlertDialogTitle,
  AlertDialogDescription,
  AlertDialogAction,
  AlertDialogCancel,
} from "../components/ui/alert-dialog";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import Chip from "../components/Chip";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { HOOK_TEMPLATE_CATEGORIES, categoryLabel } from "../lib/hookTemplateCategories";
import {
  Bookmark,
  Repeat2,
  Trash2,
  Pencil,
  Zap,
  Film,
  ImageOff,
  Loader2,
  Music2,
  ExternalLink,
  Sparkles,
} from "lucide-react";
import { toast } from "sonner";

function formatUsed(n) {
  if (!n) return "Never used";
  return n === 1 ? "Used once" : `Used ${n} times`;
}

/**
 * Whether a template can seed a face swap directly.
 *
 * Templates are one of only two permitted sources for a face-swap target (the
 * other is the discovery feed), but that depends on the template owning a
 * locally-stored frame. `thumbnail_url` falls back to the source video's
 * external TikTok CDN cover when the frame copy failed at save time, and the
 * backend allowlists only /api/media/frames and /api/media/templates — so
 * offering the button for a CDN URL would just produce a 400.
 */
const SWAPPABLE_TARGET_PREFIXES = ["/api/media/templates/", "/api/media/frames/"];

function canSeedFaceSwap(template) {
  const url = template?.thumbnail_url || "";
  return SWAPPABLE_TARGET_PREFIXES.some((prefix) => url.startsWith(prefix));
}

/**
 * Route a remote thumbnail through our proxy.
 *
 * Most template thumbnails are locally-copied frames, but when that copy failed
 * at save time we fall back to the TikTok CDN cover URL — and those routinely
 * fail to load in-browser due to referrer restrictions. Same proxy VideoCard uses.
 */
function proxyThumb(url) {
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
  return `${BACKEND_URL}/api/proxy-thumb?url=${encodeURIComponent(url)}`;
}

function TemplateThumbnail({ url, alt }) {
  const [src, setSrc] = useState(url ? mediaUrl(url) : null);
  const [failed, setFailed] = useState(!url);

  if (failed) {
    return (
      <div className="flex aspect-[9/16] w-full items-center justify-center rounded-xl bg-gradient-to-b from-secondary/60 to-muted">
        <ImageOff className="h-6 w-6 text-muted-foreground/50" />
      </div>
    );
  }
  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      className="aspect-[9/16] w-full rounded-xl bg-muted object-cover transition-transform duration-500 ease-out-expo group-hover:scale-[1.04]"
      onError={() => {
        // Remote covers get one retry through the proxy before giving up.
        if (url.startsWith("http") && src !== proxyThumb(url)) setSrc(proxyThumb(url));
        else setFailed(true);
      }}
    />
  );
}

export default function HookTemplates() {
  const navigate = useNavigate();
  const [templates, setTemplates] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeCategory, setActiveCategory] = useState("all");
  const [editing, setEditing] = useState(null);
  const [editName, setEditName] = useState("");
  const [editCategory, setEditCategory] = useState("other");
  const [editNotes, setEditNotes] = useState("");
  const [savingEdit, setSavingEdit] = useState(false);
  const [deleting, setDeleting] = useState(null);
  const [deletingBusy, setDeletingBusy] = useState(false);

  const load = useCallback(() => {
    setLoading(true);
    api
      .getBookmarks()
      .then((data) => setTemplates(Array.isArray(data) ? data : []))
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(load, [load]);

  const openEdit = (t) => {
    setEditing(t);
    setEditName(t.name || "");
    setEditCategory(t.category || "other");
    setEditNotes(t.notes || "");
  };

  const handleSaveEdit = async () => {
    if (!editing) return;
    if (!editName.trim()) {
      toast.error("Bookmark name cannot be empty.");
      return;
    }
    setSavingEdit(true);
    try {
      const updated = await api.updateBookmark(editing.id, {
        name: editName.trim(),
        category: editCategory,
        notes: editNotes.trim(),
      });
      setTemplates((prev) => prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)));
      toast.success("Bookmark updated.");
      setEditing(null);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSavingEdit(false);
    }
  };

  const handleDelete = async () => {
    if (!deleting) return;
    setDeletingBusy(true);
    try {
      await api.deleteBookmark(deleting.id);
      setTemplates((prev) => prev.filter((t) => t.id !== deleting.id));
      toast.success("Bookmark deleted.");
      setDeleting(null);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setDeletingBusy(false);
    }
  };

  const visible =
    activeCategory === "all" ? templates : templates.filter((t) => t.category === activeCategory);

  const usedCategories = HOOK_TEMPLATE_CATEGORIES.filter((c) =>
    templates.some((t) => t.category === c.key)
  );

  // Deleting or recategorizing the last template in the active category would
  // otherwise strand the user: the filter row hides itself when only one
  // category remains, leaving "No templates in this category" with no visible
  // way to clear the filter. Fall back to "all" whenever the active category
  // no longer has anything in it.
  useEffect(() => {
    if (activeCategory === "all") return;
    if (!templates.some((t) => t.category === activeCategory)) {
      setActiveCategory("all");
    }
  }, [templates, activeCategory]);

  const totalReuses = templates.reduce((sum, t) => sum + (t.times_used || 0), 0);

  if (loading) {
    return (
      <div className="space-y-6" data-testid="bookmarks-loading">
        <Skeleton className="h-10 w-64 rounded-xl" />
        <Skeleton className="h-16 w-full rounded-2xl" />
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="surface space-y-3 rounded-2xl p-3">
              <Skeleton className="aspect-[9/16] w-full rounded-xl" />
              <Skeleton className="h-4 w-4/5 rounded-md" />
              <Skeleton className="h-3 w-1/2 rounded-md" />
              <Skeleton className="h-10 w-full rounded-xl" />
            </div>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Bookmark}
        title="Bookmarks"
        description="Your bookmarked hooks, organized by category. Tap any bookmark to jump back to its analysis."
      />

      {templates.length === 0 ? (
        <EmptyState
          icon={Bookmark}
          title="No bookmarks yet"
          description="Analyze a viral hook, then hit 'Bookmark This Hook' on the analysis page. Bookmarked hooks appear here so you can find and reuse them by category."
          action={
            <Button
              onClick={() => navigate("/discover")}
              variant="brand"
              data-testid="bookmarks-discover-button"
            >
              <Sparkles className="h-4 w-4" /> Find a hook to bookmark
            </Button>
          }
        />
      ) : (
        <>
          {/* Savings summary — two headline numbers instead of a sentence */}
          <div
            className="surface flex flex-col gap-4 rounded-2xl p-4 sm:flex-row sm:items-center"
            data-testid="templates-savings-summary"
          >
            <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
              <Zap className="h-[18px] w-[18px]" />
            </span>
            <div className="flex flex-1 flex-wrap items-center gap-x-8 gap-y-3">
              <div>
                <p className="font-display text-xl font-bold leading-none">{templates.length}</p>
                <p className="eyebrow mt-1">{templates.length === 1 ? "Template" : "Templates"} saved</p>
              </div>
              <div className="h-8 w-px bg-border/60" aria-hidden="true" />
              <div>
                <p className="font-display text-xl font-bold leading-none text-[color:var(--brand-indigo)]">
                  {totalReuses}
                </p>
                <p className="eyebrow mt-1">{totalReuses === 1 ? "Reuse" : "Reuses"} so far</p>
              </div>
              <p className="max-w-xs text-xs leading-snug text-muted-foreground">
                Each reuse skips a fresh hook analysis and prompt generation.
              </p>
            </div>
          </div>

          {/* Category filter */}
          {usedCategories.length > 1 && (
            <div className="flex flex-wrap gap-1.5" data-testid="templates-category-filter">
              <Chip
                active={activeCategory === "all"}
                onClick={() => setActiveCategory("all")}
                testId="templates-filter-all"
              >
                All ({templates.length})
              </Chip>
              {usedCategories.map((c) => {
                const count = templates.filter((t) => t.category === c.key).length;
                return (
                  <Chip
                    key={c.key}
                    active={activeCategory === c.key}
                    onClick={() => setActiveCategory(c.key)}
                    testId={`templates-filter-${c.key}`}
                  >
                    {c.label} ({count})
                  </Chip>
                );
              })}
            </div>
          )}

          {/* Template grid */}
          <div
            className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3"
            data-testid="bookmarks-grid"
          >
            {visible.map((t) => (
              <div
                key={t.id}
                className="surface surface-interactive group flex flex-col gap-3 rounded-2xl p-3"
                data-testid="bookmark-card"
              >
                {/* Thumbnail */}
                <div className="relative overflow-hidden rounded-xl">
                  <TemplateThumbnail url={t.thumbnail_url} alt={t.name} />
                  <div
                    aria-hidden="true"
                    className="pointer-events-none absolute inset-x-0 bottom-0 h-16 bg-gradient-to-t from-black/60 to-transparent"
                  />
                  <div className="absolute left-2 top-2 flex flex-col items-start gap-1">
                    <Badge className="border-transparent bg-black/65 text-xs font-semibold text-white backdrop-blur-sm">
                      {categoryLabel(t.category)}
                    </Badge>
                    {t.has_motion_reference && (
                      <Badge
                        className="border-transparent bg-[color:var(--brand-indigo)] text-xs font-semibold text-white"
                        title="The source clip is stored with this template for V2V motion transfer"
                      >
                        <Film className="h-2.5 w-2.5" /> Motion ref
                      </Badge>
                    )}
                  </div>
                  {t.effectiveness_score ? (
                    <Badge
                      className="absolute right-2 top-2 border-transparent bg-[color:var(--brand-coral)] text-xs font-bold text-white shadow-[var(--shadow-sm)]"
                      title="Hook effectiveness score from the original analysis"
                    >
                      {t.effectiveness_score}/10
                    </Badge>
                  ) : null}
                  <p className="absolute bottom-2 left-2.5 right-2.5 text-xs font-semibold text-white/90">
                    {formatUsed(t.times_used)}
                  </p>
                </div>

                {/* Meta */}
                <div className="flex-1 space-y-1.5">
                  <h3 className="font-display line-clamp-2 text-sm font-semibold leading-snug">
                    {t.name}
                  </h3>
                  {t.source_creator && (
                    <p className="text-xs text-muted-foreground">
                      from @{t.source_creator}
                      {t.source_tiktok_url && (
                        <a
                          href={t.source_tiktok_url}
                          target="_blank"
                          rel="noreferrer"
                          className="ml-1 inline-flex align-middle text-[color:var(--brand-indigo)] transition-colors hover:text-[color:var(--brand-indigo-dark)]"
                          title="View the original video on TikTok"
                        >
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </p>
                  )}
                  {t.hook_summary && (
                    <p className="line-clamp-2 text-xs leading-snug text-muted-foreground">
                      {t.hook_summary}
                    </p>
                  )}
                  {(t.song_title || t.song_artist) && (
                    <p className="flex items-center gap-1 truncate text-xs text-muted-foreground">
                      <Music2 className="h-2.5 w-2.5 shrink-0" />
                      <span className="truncate">
                        {t.song_title || "Untitled sound"}
                        {t.song_artist ? ` — ${t.song_artist}` : ""}
                      </span>
                    </p>
                  )}
                  {t.notes && (
                    <p className="line-clamp-2 text-xs italic leading-snug text-muted-foreground">
                      {t.notes}
                    </p>
                  )}
                </div>

                {/* Actions */}
                <div className="space-y-1.5">
                  {canSeedFaceSwap(t) ? (
                    <>
                      <Button
                        onClick={() =>
                          navigate(
                            `/face-swap?target=${encodeURIComponent(t.thumbnail_url)}` +
                              `&templateId=${encodeURIComponent(t.id)}` +
                              `&templateName=${encodeURIComponent(t.name || "")}`
                          )
                        }
                        variant="brand"
                        className="w-full"
                        data-testid="face-swap-template-button"
                      >
                        <Repeat2 className="h-3.5 w-3.5" /> Face Swap This Hook
                      </Button>
                      <Button
                        onClick={() => navigate(`/analysis/${t.source_video_id}`)}
                        variant="outline"
                        className="w-full"
                        data-testid="use-template-button"
                      >
                        View Analysis
                      </Button>
                    </>
                  ) : (
                    <Button
                      onClick={() => navigate(`/analysis/${t.source_video_id}`)}
                      variant="brand"
                      className="w-full"
                      data-testid="use-template-button"
                      title="This template has no stored frame — open the analysis and swap from there"
                    >
                      <Repeat2 className="h-3.5 w-3.5" /> View Analysis
                    </Button>
                  )}
                  <div className="flex gap-1.5">
                    <Button
                      variant="outline"
                      size="sm"
                      onClick={() => openEdit(t)}
                      className="flex-1 gap-1.5"
                      data-testid="edit-template-button"
                    >
                      <Pencil className="h-3 w-3" /> Edit
                    </Button>
                    <Button
                      variant="ghost"
                      size="sm"
                      onClick={() => setDeleting(t)}
                      className="gap-1.5 text-muted-foreground hover:text-[color:var(--brand-coral)]"
                      data-testid="delete-template-button"
                      aria-label={`Delete ${t.name}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </div>
            ))}
          </div>

          {visible.length === 0 && (
            <p className="py-6 text-center text-sm text-muted-foreground">
              No templates in this category.
            </p>
          )}
        </>
      )}

      {/* Edit dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-md" data-testid="edit-template-dialog">
          <DialogHeader>
            <DialogTitle className="flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                <Pencil className="h-4 w-4" />
              </span>
              Edit Bookmark
            </DialogTitle>
            <DialogDescription>
              Rename or recategorize this bookmarked hook. The saved analysis stays
              unchanged.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-4 py-1">
            <div className="space-y-1.5">
              <label htmlFor="edit-template-name" className="eyebrow block">
                Bookmark name
              </label>
              <Input
                id="edit-template-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                maxLength={80}
                data-testid="edit-template-name-input"
              />
            </div>
            <div className="space-y-2">
              <span className="eyebrow block">Category</span>
              <div className="flex flex-wrap gap-1.5">
                {HOOK_TEMPLATE_CATEGORIES.map((c) => (
                  <Chip
                    key={c.key}
                    active={editCategory === c.key}
                    onClick={() => setEditCategory(c.key)}
                    testId={`edit-template-category-${c.key}`}
                  >
                    {c.label}
                  </Chip>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="edit-template-notes" className="eyebrow block">
                Notes <span className="font-normal normal-case tracking-normal">(optional)</span>
              </label>
              <Textarea
                id="edit-template-notes"
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                maxLength={500}
                rows={2}
                className="min-h-[64px] resize-none text-sm"
                data-testid="edit-template-notes-input"
              />
            </div>
          </div>
          <DialogFooter>
            <Button variant="ghost" onClick={() => setEditing(null)} disabled={savingEdit}>
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={savingEdit}
              variant="accent"
              className="gap-1.5"
              data-testid="edit-template-save-button"
            >
              {savingEdit ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : null}
              Save Changes
            </Button>
          </DialogFooter>
        </DialogContent>
      </Dialog>

      {/* Delete confirmation */}
      <AlertDialog open={!!deleting} onOpenChange={(o) => !o && setDeleting(null)}>
        <AlertDialogContent data-testid="delete-template-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display flex items-center gap-2.5">
              <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-destructive/30 bg-destructive/10 text-destructive">
                <Trash2 className="h-4 w-4" />
              </span>
              Delete this template?
            </AlertDialogTitle>
            <AlertDialogDescription>
              &ldquo;{deleting?.name}&rdquo; will be removed along with its stored motion reference.
              Reusing this hook afterwards would require a fresh AI analysis. This cannot be undone.
            </AlertDialogDescription>
          </AlertDialogHeader>
          <AlertDialogFooter>
            <AlertDialogCancel className="rounded-xl" disabled={deletingBusy}>
              Cancel
            </AlertDialogCancel>
            <AlertDialogAction
              onClick={(e) => {
                e.preventDefault();
                handleDelete();
              }}
              disabled={deletingBusy}
              className="gap-1.5 rounded-xl bg-destructive text-destructive-foreground hover:bg-destructive/90"
              data-testid="delete-template-confirm-button"
            >
              {deletingBusy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Trash2 className="h-3.5 w-3.5" />}
              Delete
            </AlertDialogAction>
          </AlertDialogFooter>
        </AlertDialogContent>
      </AlertDialog>
    </div>
  );
}
