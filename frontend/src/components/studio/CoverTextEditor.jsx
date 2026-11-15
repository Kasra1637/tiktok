import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { api, getErrorMessage } from "../../lib/api";

/**
 * The cover text in Review (ADR 0145): the words on screen for the
 * opening's first two seconds, shown as they will sit on the opening
 * frame — lower portion, centered — beside the field that edits them.
 *
 * The cover is scored WITH the spoken hook in Hook stopping power, and
 * the editor says so, with the current dimension score, so the founder
 * sees how the words they are reading are the words being graded. A
 * fresh cover comes only from its own button (ADR 0122) and, like the
 * clearer-line suggestions, is never saved by the server: accepting
 * goes through the normal draft edit. The suggestion carries the hook
 * score it would earn beside the current cover's, both from the
 * endpoint, so the movement is visible before the founder decides. A
 * suggestion made for a cover the founder has since edited is stale
 * and hides rather than overwriting their newer words.
 */
export default function CoverTextEditor({
  projectId, value, onChange, hookLine = "", script = "", hookScore = null, disabled,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestion, setSuggestion] = useState(null);
  const live = suggestion && suggestion.forCover === value ? suggestion : null;

  const suggest = async () => {
    setBusy(true);
    setError("");
    try {
      const out = await api.suggestCoverText(projectId, {
        cover_text: value, hook_line: hookLine, script,
      });
      if (!out || typeof out.cover_text !== "string" || !out.cover_text.trim()) {
        throw new Error("No cover text came back. Try again, or write the cover yourself.");
      }
      setSuggestion({ text: out.cover_text, hookScore: out.hook_score || null, forCover: value });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <label htmlFor="review-cover_text" className="text-sm font-semibold">Cover text</label>
      <p className="text-sm text-muted-foreground" data-subtitle="">The words on screen in the first two seconds of your clip.</p>
      {/* The opening frame as the viewer meets it: a 9:16 still with the
          cover sitting where the render lays it, lower-center. The text
          is the live draft, so the preview and the field never disagree. */}
      <div
        className="relative aspect-[9/16] w-40 overflow-hidden rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)]"
        data-testid="cover-text-preview"
      >
        <div className="absolute inset-x-3 bottom-[18%] text-center">
          <p className="text-base font-semibold leading-snug" data-testid="cover-text-preview-text">
            {value?.trim() ? value : "Your cover text appears here"}
          </p>
        </div>
      </div>
      <Input
        id="review-cover_text"
        value={value}
        onChange={(e) => onChange(e.target.value)}
        placeholder="A few words for the opening frame"
      />
      <p className="text-sm text-muted-foreground" data-testid="cover-text-score-note">
        Scored with your hook in Hook stopping power
        {hookScore
          ? <> — currently <span className="font-semibold">{hookScore.score}/{hookScore.max}</span>.</>
          : "."}
      </p>
      <div className="space-y-3">
        {!live && (
          <Button type="button" variant="outline" size="sm" onClick={suggest}
            disabled={busy || disabled || !projectId}
            busy={busy}
            data-testid="cover-text-suggest-button">
            <Sparkles className="mr-2 h-3.5 w-3.5" />
            {busy ? "Writing cover text" : "Suggest a new cover text"}
          </Button>
        )}
        {error && <p className="text-sm text-destructive-text" role="alert" data-testid="cover-text-suggest-error">{error}</p>}
        {live && (
          <div className="inset-panel space-y-3" data-testid="cover-text-suggestion">
            <p className="text-base font-semibold">&ldquo;{live.text}&rdquo;</p>
            {live.hookScore && (
              <p className="text-sm text-muted-foreground" data-testid="cover-text-score-move">
                Hook stopping power would move from {live.hookScore.current}/{live.hookScore.max} to{" "}
                {live.hookScore.suggested}/{live.hookScore.max} with this cover.
              </p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" disabled={disabled} data-testid="cover-text-accept"
                onClick={() => { onChange(live.text); setSuggestion(null); }}>
                Use this cover
              </Button>
              <Button type="button" variant="ghost" size="sm" data-testid="cover-text-dismiss"
                onClick={() => setSuggestion(null)}>
                Keep mine
              </Button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
