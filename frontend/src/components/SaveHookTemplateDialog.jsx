import { useState, useEffect } from "react";
import {
  Dialog,
  DialogContent,
  DialogHeader,
  DialogTitle,
  DialogDescription,
  DialogFooter,
} from "./ui/dialog";
import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Textarea } from "./ui/textarea";
import Chip from "./Chip";
import { Loader2, Bookmark, Zap } from "lucide-react";
import { toast } from "sonner";
import { api, getErrorMessage } from "../lib/api";
import { HOOK_TEMPLATE_CATEGORIES } from "../lib/hookTemplateCategories";

/**
 * Bookmark an analyzed hook for quick access from the history page.
 *
 * The backend snapshots the existing analysis so users can filter and
 * find their bookmarked hooks by category later.
 */
export function SaveHookTemplateDialog({ open, onOpenChange, videoId, analysis, video, onSaved }) {
  const [name, setName] = useState("");
  const [category, setCategory] = useState("intrigue");
  const [notes, setNotes] = useState("");
  const [saving, setSaving] = useState(false);

  // Pre-fill the name from the hook summary each time the dialog opens.
  useEffect(() => {
    if (!open) return;
    const suggested = (analysis?.hook_summary || "").trim();
    setName(suggested ? suggested.slice(0, 60).replace(/[.,\s]+$/, "") : "");
    setCategory("intrigue");
    setNotes("");
  }, [open, analysis]);

  const handleSave = async () => {
    setSaving(true);
    try {
      const saved = await api.createBookmark({
        video_id: videoId,
        name: name.trim(),
        category,
        notes: notes.trim(),
      });
      toast.success(`Bookmarked "${saved.name}" — find it in your history.`);
      onOpenChange(false);
      onSaved?.(saved);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="sm:max-w-md" data-testid="bookmark-hook-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
              <Bookmark className="h-4 w-4" />
            </span>
            Bookmark This Hook
          </DialogTitle>
          <DialogDescription>
            Save this hook to your history with a category so you can easily find and reuse it later.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <label htmlFor="bookmark-name" className="eyebrow block">
              Name
            </label>
            <Input
              id="bookmark-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              placeholder="e.g. Lean-in Secret Reveal"
              data-testid="bookmark-name-input"
            />
            <p className="text-xs text-muted-foreground">
              Leave blank to use the hook summary as the name.
            </p>
          </div>

          <div className="space-y-2">
            <span className="eyebrow block">Category</span>
            <div className="flex flex-wrap gap-1.5" data-testid="bookmark-category-selector">
              {HOOK_TEMPLATE_CATEGORIES.map((c) => (
                <Chip
                  key={c.key}
                  active={category === c.key}
                  onClick={() => setCategory(c.key)}
                  testId={`bookmark-category-${c.key}`}
                >
                  {c.label}
                </Chip>
              ))}
            </div>
            <p className="text-xs leading-snug text-muted-foreground" data-testid="category-description">
              {HOOK_TEMPLATE_CATEGORIES.find((c) => c.key === category)?.description}
            </p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="bookmark-notes" className="eyebrow block">
              Notes <span className="font-normal normal-case tracking-normal">(optional)</span>
            </label>
            <Textarea
              id="bookmark-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Why this hook works, who it's for..."
              className="min-h-[64px] resize-none text-sm"
              data-testid="bookmark-notes-input"
            />
          </div>

          {video && (
            <div className="flex items-center gap-2.5 rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)] px-3 py-2.5">
              <Zap className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
              <p className="text-xs leading-snug text-muted-foreground">
                Source: <span className="font-semibold text-foreground">@{video.creator}</span>
                {analysis?.effectiveness_score ? ` · scored ${analysis.effectiveness_score}/10` : ""}
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={saving}
            data-testid="bookmark-cancel-button"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            variant="accent"
            className="gap-1.5"
            data-testid="bookmark-confirm-button"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bookmark className="h-3.5 w-3.5" />}
            {saving ? "Saving..." : "Bookmark"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default SaveHookTemplateDialog;
