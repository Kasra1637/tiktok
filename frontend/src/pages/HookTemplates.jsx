import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import { Card } from "../components/ui/card";
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
      .getHookTemplates()
      .then(setTemplates)
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
      toast.error("Template name cannot be empty.");
      return;
    }
    setSavingEdit(true);
    try {
      const updated = await api.updateHookTemplate(editing.id, {
        name: editName.trim(),
        category: editCategory,
        notes: editNotes.trim(),
      });
      setTemplates((prev) => prev.map((t) => (t.id === updated.id ? { ...t, ...updated } : t)));
      toast.success("Template updated.");
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
      await api.deleteHookTemplate(deleting.id);
      setTemplates((prev) => prev.filter((t) => t.id !== deleting.id));
      toast.success("Template deleted.");
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

  const totalReuses = templates.reduce((sum, t) => sum + (t.times_used || 0), 0);

  if (loading) {
    return (
      <div className="space-y-5" data-testid="hook-templates-loading">
        <Skeleton className="h-8 w-56" />
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-3 rounded-2xl border-border space-y-2.5">
              <Skeleton className="w-full aspect-[9/16] rounded-xl" />
              <Skeleton className="h-4 w-4/5" />
              <Skeleton className="h-3 w-1/2" />
            </Card>
          ))}
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      {/* Header */}
      <div className="space-y-1.5">
        <div className="flex items-center gap-2">
          <span className="flex h-8 w-8 items-center justify-center rounded-lg bg-[color:rgba(99,102,241,0.10)] text-[color:var(--brand-teal)]">
            <Bookmark className="h-4 w-4" />
          </span>
          <h1 className="font-display text-2xl font-bold tracking-tight">Hook Templates</h1>
        </div>
        <p className="text-sm text-muted-foreground">
          Saved hooks keep their analysis, prompt, and motion reference on file. Reusing one skips
          hook analysis and prompt generation entirely — you only pay for the video itself.
        </p>
      </div>

      {templates.length === 0 ? (
        <EmptyState
          icon={Bookmark}
          title="No hook templates yet"
          description="Analyze a viral hook, then hit 'Save as Template' on the analysis page. Saved hooks can be reused on any face swap without re-running the AI analysis."
          action={
            <Button
              onClick={() => navigate("/discover")}
              className="gap-1.5 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white"
              data-testid="templates-discover-button"
            >
              <Sparkles className="h-4 w-4" /> Find a hook to save
            </Button>
          }
        />
      ) : (
        <>
          {/* Savings summary */}
          <Card
            className="flex items-center gap-3 rounded-2xl border-border bg-secondary/40 px-4 py-3"
            data-testid="templates-savings-summary"
          >
            <Zap className="h-4 w-4 text-[color:var(--brand-teal)] shrink-0" />
            <p className="text-xs text-muted-foreground">
              <span className="font-semibold text-foreground">{templates.length}</span>{" "}
              {templates.length === 1 ? "template" : "templates"} saved ·{" "}
              <span className="font-semibold text-foreground">{totalReuses}</span>{" "}
              {totalReuses === 1 ? "reuse" : "reuses"} so far, each one skipping a fresh hook
              analysis and prompt generation.
            </p>
          </Card>

          {/* Category filter */}
          {usedCategories.length > 1 && (
            <div className="flex flex-wrap gap-1.5" data-testid="templates-category-filter">
              <button
                onClick={() => setActiveCategory("all")}
                className={`text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all ${
                  activeCategory === "all"
                    ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.08)] text-[color:var(--brand-teal)]"
                    : "border-border text-muted-foreground hover:border-[color:rgba(99,102,241,0.35)]"
                }`}
                data-testid="templates-filter-all"
              >
                All ({templates.length})
              </button>
              {usedCategories.map((c) => {
                const count = templates.filter((t) => t.category === c.key).length;
                return (
                  <button
                    key={c.key}
                    onClick={() => setActiveCategory(c.key)}
                    className={`text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all ${
                      activeCategory === c.key
                        ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.08)] text-[color:var(--brand-teal)]"
                        : "border-border text-muted-foreground hover:border-[color:rgba(99,102,241,0.35)]"
                    }`}
                    data-testid={`templates-filter-${c.key}`}
                  >
                    {c.label} ({count})
                  </button>
                );
              })}
            </div>
          )}

          {/* Template grid */}
          <div
            className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4"
            data-testid="hook-templates-grid"
          >
            {visible.map((t) => (
              <Card
                key={t.id}
                className="p-3 rounded-2xl border-border shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-tight)] transition-shadow flex flex-col gap-2.5"
                data-testid="hook-template-card"
              >
                {/* Thumbnail */}
                <div className="relative">
                  {t.thumbnail_url ? (
                    <img
                      src={mediaUrl(t.thumbnail_url)}
                      alt={t.name}
                      className="w-full rounded-xl object-cover aspect-[9/16] bg-muted"
                      onError={(e) => {
                        e.currentTarget.style.display = "none";
                        e.currentTarget.nextElementSibling?.classList.remove("hidden");
                      }}
                    />
                  ) : null}
                  <div
                    className={`w-full rounded-xl aspect-[9/16] bg-muted flex items-center justify-center ${
                      t.thumbnail_url ? "hidden" : ""
                    }`}
                  >
                    <ImageOff className="h-6 w-6 text-muted-foreground" />
                  </div>
                  <div className="absolute top-1.5 left-1.5 flex flex-col gap-1 items-start">
                    <Badge className="bg-black/70 border-none text-white text-[10px] font-semibold">
                      {categoryLabel(t.category)}
                    </Badge>
                    {t.has_motion_reference && (
                      <Badge
                        className="bg-[color:var(--brand-teal)] border-none text-white gap-1 text-[10px] font-semibold"
                        title="The source clip is stored with this template for V2V motion transfer"
                      >
                        <Film className="h-2.5 w-2.5" /> Motion ref
                      </Badge>
                    )}
                  </div>
                  {t.effectiveness_score ? (
                    <Badge
                      className="absolute top-1.5 right-1.5 bg-[color:var(--brand-coral)] border-none text-white text-[10px] font-semibold"
                      title="Hook effectiveness score from the original analysis"
                    >
                      {t.effectiveness_score}/10
                    </Badge>
                  ) : null}
                </div>

                {/* Meta */}
                <div className="space-y-1 flex-1">
                  <h3 className="font-display text-sm font-semibold leading-snug line-clamp-2">
                    {t.name}
                  </h3>
                  {t.source_creator && (
                    <p className="text-[11px] text-muted-foreground">
                      from @{t.source_creator}
                      {t.source_tiktok_url && (
                        <a
                          href={t.source_tiktok_url}
                          target="_blank"
                          rel="noreferrer"
                          className="inline-flex ml-1 align-middle text-[color:var(--brand-teal-dark)] hover:underline"
                          title="View the original video on TikTok"
                        >
                          <ExternalLink className="h-2.5 w-2.5" />
                        </a>
                      )}
                    </p>
                  )}
                  {t.hook_summary && (
                    <p className="text-[11px] text-muted-foreground leading-snug line-clamp-2">
                      {t.hook_summary}
                    </p>
                  )}
                  {(t.song_title || t.song_artist) && (
                    <p className="text-[10px] text-muted-foreground flex items-center gap-1 truncate">
                      <Music2 className="h-2.5 w-2.5 shrink-0" />
                      <span className="truncate">
                        {t.song_title || "Untitled sound"}
                        {t.song_artist ? ` — ${t.song_artist}` : ""}
                      </span>
                    </p>
                  )}
                  {t.notes && (
                    <p className="text-[10px] text-muted-foreground italic leading-snug line-clamp-2">
                      {t.notes}
                    </p>
                  )}
                  <p className="text-[10px] font-medium text-[color:var(--brand-teal)]">
                    {formatUsed(t.times_used)}
                  </p>
                </div>

                {/* Actions */}
                <div className="space-y-1.5">
                  <Button
                    onClick={() => navigate(`/face-swap?templateId=${encodeURIComponent(t.id)}`)}
                    className="w-full gap-1.5 rounded-xl text-sm bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white"
                    data-testid="use-template-button"
                  >
                    <Repeat2 className="h-3.5 w-3.5" /> Use This Hook
                  </Button>
                  <div className="flex gap-1.5">
                    <Button
                      variant="outline"
                      onClick={() => openEdit(t)}
                      className="flex-1 gap-1.5 rounded-xl text-xs"
                      data-testid="edit-template-button"
                    >
                      <Pencil className="h-3 w-3" /> Edit
                    </Button>
                    <Button
                      variant="ghost"
                      onClick={() => setDeleting(t)}
                      className="gap-1.5 rounded-xl text-xs text-muted-foreground hover:text-red-500"
                      data-testid="delete-template-button"
                      aria-label={`Delete ${t.name}`}
                    >
                      <Trash2 className="h-3 w-3" />
                    </Button>
                  </div>
                </div>
              </Card>
            ))}
          </div>

          {visible.length === 0 && (
            <p className="text-sm text-muted-foreground text-center py-6">
              No templates in this category.
            </p>
          )}
        </>
      )}

      {/* Edit dialog */}
      <Dialog open={!!editing} onOpenChange={(o) => !o && setEditing(null)}>
        <DialogContent className="sm:max-w-md rounded-2xl" data-testid="edit-template-dialog">
          <DialogHeader>
            <DialogTitle className="font-display">Edit Template</DialogTitle>
            <DialogDescription>
              Rename or recategorize this hook. The saved analysis, prompt, and motion reference stay
              unchanged.
            </DialogDescription>
          </DialogHeader>
          <div className="space-y-3.5 py-1">
            <div className="space-y-1.5">
              <label htmlFor="edit-template-name" className="text-xs font-medium text-muted-foreground">
                Template name
              </label>
              <Input
                id="edit-template-name"
                value={editName}
                onChange={(e) => setEditName(e.target.value)}
                maxLength={80}
                data-testid="edit-template-name-input"
              />
            </div>
            <div className="space-y-1.5">
              <span className="text-xs font-medium text-muted-foreground">Category</span>
              <div className="flex flex-wrap gap-1.5">
                {HOOK_TEMPLATE_CATEGORIES.map((c) => (
                  <button
                    key={c.key}
                    type="button"
                    onClick={() => setEditCategory(c.key)}
                    className={`text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all ${
                      editCategory === c.key
                        ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.08)] text-[color:var(--brand-teal)]"
                        : "border-border text-muted-foreground hover:border-[color:rgba(99,102,241,0.35)]"
                    }`}
                    data-testid={`edit-template-category-${c.key}`}
                  >
                    {c.label}
                  </button>
                ))}
              </div>
            </div>
            <div className="space-y-1.5">
              <label htmlFor="edit-template-notes" className="text-xs font-medium text-muted-foreground">
                Notes <span className="font-normal">(optional)</span>
              </label>
              <Textarea
                id="edit-template-notes"
                value={editNotes}
                onChange={(e) => setEditNotes(e.target.value)}
                maxLength={500}
                rows={2}
                className="text-sm resize-none"
                data-testid="edit-template-notes-input"
              />
            </div>
          </div>
          <DialogFooter className="gap-2 sm:gap-2">
            <Button
              variant="ghost"
              onClick={() => setEditing(null)}
              disabled={savingEdit}
              className="rounded-xl"
            >
              Cancel
            </Button>
            <Button
              onClick={handleSaveEdit}
              disabled={savingEdit}
              className="gap-1.5 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
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
        <AlertDialogContent className="rounded-2xl" data-testid="delete-template-dialog">
          <AlertDialogHeader>
            <AlertDialogTitle className="font-display">Delete this template?</AlertDialogTitle>
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
              className="rounded-xl bg-red-600 hover:bg-red-700 text-white gap-1.5"
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
