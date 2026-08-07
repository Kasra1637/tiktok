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
      <DialogContent className="sm:max-w-md rounded-2xl" data-testid="save-hook-template-dialog">
        <DialogHeader>
          <DialogTitle className="font-display flex items-center gap-2">
            <Bookmark className="h-4 w-4 text-[color:var(--brand-teal)]" />
            Save as Hook Template
          </DialogTitle>
          <DialogDescription>
            Snapshots this hook's analysis, prompt, and motion reference. Reusing it later
            costs no analysis or prompt-generation calls.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-3.5 py-1">
          <div className="space-y-1.5">
            <label htmlFor="template-name" className="text-xs font-medium text-muted-foreground">
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
            <p className="text-[10px] text-muted-foreground">
              Leave blank to use the hook summary as the name.
            </p>
          </div>

          <div className="space-y-1.5">
            <span className="text-xs font-medium text-muted-foreground">Category</span>
            <div className="flex flex-wrap gap-1.5" data-testid="save-template-category-selector">
              {HOOK_TEMPLATE_CATEGORIES.map((c) => (
                <button
                  key={c.key}
                  type="button"
                  onClick={() => setCategory(c.key)}
                  className={`text-[11px] font-medium px-2.5 py-1 rounded-full border transition-all ${
                    category === c.key
                      ? "border-[color:var(--brand-teal)] bg-[color:rgba(99,102,241,0.08)] text-[color:var(--brand-teal)]"
                      : "border-border text-muted-foreground hover:border-[color:rgba(99,102,241,0.35)]"
                  }`}
                  data-testid={`save-template-category-${c.key}`}
                >
                  {c.label}
                </button>
              ))}
            </div>
          </div>

          <div className="space-y-1.5">
            <label htmlFor="template-notes" className="text-xs font-medium text-muted-foreground">
              Notes <span className="font-normal">(optional)</span>
            </label>
            <Textarea
              id="template-notes"
              value={notes}
              onChange={(e) => setNotes(e.target.value)}
              maxLength={500}
              rows={2}
              placeholder="Why this hook works, who it's for..."
              className="text-sm resize-none"
              data-testid="save-template-notes-input"
            />
          </div>

          {video && (
            <div className="flex items-center gap-2 rounded-xl border border-border bg-secondary/50 px-3 py-2">
              <Zap className="h-3.5 w-3.5 text-[color:var(--brand-teal)] shrink-0" />
              <p className="text-[11px] text-muted-foreground leading-snug">
                Source: <span className="font-medium text-foreground">@{video.creator}</span>
                {analysis?.effectiveness_score ? ` · scored ${analysis.effectiveness_score}/10` : ""}
                {video.local_video_path ? " · motion reference included" : ""}
              </p>
            </div>
          )}
        </div>

        <DialogFooter className="gap-2 sm:gap-2">
          <Button
            variant="ghost"
            onClick={() => onOpenChange(false)}
            disabled={saving}
            className="rounded-xl"
            data-testid="save-template-cancel-button"
          >
            Cancel
          </Button>
          <Button
            onClick={handleSave}
            disabled={saving}
            className="gap-1.5 rounded-xl bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white"
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
