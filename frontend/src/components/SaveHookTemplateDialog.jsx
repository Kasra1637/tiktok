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
 * Save an analyzed hook as a reusable template.
 *
 * The backend snapshots the existing analysis, pre-builds the video prompt, and
 * copies the source clip for V2V motion transfer — so every later reuse skips
 * hook re-analysis and prompt regeneration entirely.
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
      const saved = await api.createHookTemplate({
        video_id: videoId,
        name: name.trim(),
        category,
        notes: notes.trim(),
      });
      toast.success(`Saved "${saved.name}" — reuse it anytime for free.`);
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
      <DialogContent className="sm:max-w-md" data-testid="save-hook-template-dialog">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2.5">
            <span className="flex h-8 w-8 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-teal)]">
              <Bookmark className="h-4 w-4" />
            </span>
            Save as Hook Template
          </DialogTitle>
          <DialogDescription>
            Snapshots this hook's analysis, prompt, and motion reference. Reusing it later
            costs no analysis or prompt-generation calls.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 py-1">
          <div className="space-y-1.5">
            <label htmlFor="template-name" className="eyebrow block">
              Template name
            </label>
            <Input
              id="template-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              maxLength={80}
              placeholder="e.g. Lean-in Secret Reveal"
              data-testid="save-template-name-input"
            />
            <p className="text-[11px] text-muted-foreground">
              Leave blank to use the hook summary as the name.
            </p>
          </div>

          <div className="space-y-2">
            <span className="eyebrow block">Category</span>
            <div className="flex flex-wrap gap-1.5" data-testid="save-template-category-selector">
              {HOOK_TEMPLATE_CATEGORIES.map((c) => (
                <Chip
                  key={c.key}
                  active={category === c.key}
                  onClick={() => setCategory(c.key)}
                  testId={`save-template-category-${c.key}`}
                >
                  {c.label}
                </Chip>
              ))}
            </div>
            <p className="text-[11px] leading-snug text-muted-foreground" data-testid="category-description">
              {HOOK_TEMPLATE_CATEGORIES.find((c) => c.key === category)?.description}
            </p>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="template-notes" className="eyebrow block">
              Notes <span className="font-normal normal-case tracking-normal">(optional)</span>
            </label>
            <Textarea
              id="template-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Why this hook works, who it's for..."
              className="min-h-[64px] resize-none text-sm"
              data-testid="save-template-notes-input"
            />
          </div>

          {video && (
            <div className="flex items-center gap-2.5 rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)] px-3 py-2.5">
              <Zap className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-teal)]" />
              <p className="text-[11px] leading-snug text-muted-foreground">
                Source: <span className="font-semibold text-foreground">@{video.creator}</span>
                {analysis?.effectiveness_score ? ` · scored ${analysis.effectiveness_score}/10` : ""}
                {video.local_video_path ? " · motion reference included" : ""}
              </p>
            </div>
          )}
        </div>

        <DialogFooter>
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={saving}
            data-testid="save-template-cancel-button"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            variant="accent"
            className="gap-1.5"
            data-testid="save-template-confirm-button"
          >
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Bookmark className="h-3.5 w-3.5" />}
            {saving ? "Saving..." : "Save Template"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}

export default SaveHookTemplateDialog;
