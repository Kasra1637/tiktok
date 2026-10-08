import { Button } from "./ui/button";
import { Input } from "./ui/input";
import { Plus, Trash2 } from "lucide-react";

export const MAX_CAPTIONS = 12;
export const CAPTION_MAX_CHARS = 60;

/**
 * The burned-in captions, editable on the Review step.
 *
 * The backend was already built for this — `_normalize_overlays` describes
 * overlays as "hand-editable in the review step" and the PATCH accepts them —
 * but no editor existed, so the text burned into every video was AI-written,
 * unseen and uneditable. That matters more than it looks: three of the five
 * studio models render silent, so for those the captions are the only words
 * the viewer ever gets, and each caption is checked for claims and for
 * feature-list framing exactly like the script is.
 *
 * Controlled: `value` is the overlay array, `onChange` takes the next one.
 */
export function CaptionEditor({ value, onChange }) {
  const rows = Array.isArray(value) ? value : [];

  const update = (index, patch) => {
    onChange(rows.map((row, i) => (i === index ? { ...row, ...patch } : row)));
  };
  const remove = (index) => {
    onChange(rows.filter((_, i) => i !== index));
  };
  const add = () => {
    const last = rows[rows.length - 1] || { start: 0, end: 0 };
    const start = Number(last.end) || 0;
    onChange([...rows, { start, end: start + 2, text: "" }]);
  };

  return (
    <div data-testid="caption-editor" className="space-y-1.5 rounded-xl border border-[color:var(--hairline)] p-4">
      <label htmlFor="caption-text-0" className="text-sm font-medium">
        On-screen captions
      </label>
      {rows.length === 0 && (
        <p className="text-sm text-muted-foreground">
          No captions. The finished video will show no text at all.
        </p>
      )}
      {rows.map((row, i) => (
        <div key={i} className="flex items-center gap-2">
          <Input
            id={`caption-text-${i}`}
            data-testid={`caption-text-${i}`}
            value={String(row.text ?? "")}
            maxLength={CAPTION_MAX_CHARS}
            placeholder="Short phrase, about six words"
            onChange={(e) => update(i, { text: e.target.value })}
            className="min-w-0 flex-1"
          />
          <Input
            data-testid={`caption-start-${i}`}
            aria-label={`Caption ${i + 1} start, seconds`}
            type="number"
            min="0"
            step="0.5"
            value={row.start ?? 0}
            onChange={(e) => update(i, { start: e.target.value })}
            className="w-20 shrink-0"
          />
          <Input
            data-testid={`caption-end-${i}`}
            aria-label={`Caption ${i + 1} end, seconds`}
            type="number"
            min="0"
            step="0.5"
            value={row.end ?? 0}
            onChange={(e) => update(i, { end: e.target.value })}
            className="w-20 shrink-0"
          />
          <Button
            variant="ghost"
            size="sm"
            data-testid={`caption-remove-${i}`}
            aria-label={`Remove caption ${i + 1}`}
            onClick={() => remove(i)}
          >
            <Trash2 className="h-4 w-4" />
          </Button>
        </div>
      ))}
      <div>
        <Button
          variant="secondary"
          size="sm"
          data-testid="caption-add"
          onClick={add}
          disabled={rows.length >= MAX_CAPTIONS}
        >
          <Plus className="h-4 w-4" />
          Add caption
        </Button>
      </div>
      <p className="text-xs text-muted-foreground">
        Burned into the finished video when you add captions on the next step. Short
        phrases — each is checked for claims and feature-list framing like the
        script is, and on a silent render this is the only text the viewer reads.
      </p>
    </div>
  );
}

export default CaptionEditor;
