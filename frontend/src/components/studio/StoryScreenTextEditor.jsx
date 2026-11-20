import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { api, getErrorMessage } from "../../lib/api";

/**
 * The story's screen text (ADR 0236): the words the founder places on
 * the frame as a native text sticker at posting — never burned into
 * the render, never spoken (ADR 0228). It must carry the whole
 * message with the sound off, so its caps are the format's contract:
 * at most 80 characters and at most 14 words, the settled numbers in
 * `backend/story_types.py`. The editor enforces them at the field: a
 * change that would cross either cap is refused where it is typed,
 * with the cap named — an over-cap text never enters the draft, so
 * it can never autosave its way onto the row and fail the craft
 * check later. Inside the caps, typing is an ordinary draft edit.
 *
 * The field stands in the spoken-line frame family (ADR 0186), like
 * the hook and script beside it. A fresh text comes from the Suggest
 * button under the same suggest-and-accept pattern as the cover
 * text (ADR 0145): the suggestion is never saved by the server,
 * accepting goes through the normal draft edit, and a suggestion
 * made for words the founder has since edited is stale and hides
 * rather than overwriting their newer text.
 */
export const STORY_TEXT_MAX_CHARS = 80;
export const STORY_TEXT_MAX_WORDS = 14;

function wordCount(text) {
  return String(text || "").split(/\s+/).filter(Boolean).length;
}

export default function StoryScreenTextEditor({
  projectId, value, onChange, hookLine = "", script = "", disabled,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestion, setSuggestion] = useState(null);
  const [capNote, setCapNote] = useState("");
  const live = suggestion && suggestion.forText === value ? suggestion : null;

  const handleChange = (candidate) => {
    if (candidate.length > STORY_TEXT_MAX_CHARS) {
      setCapNote(
        `That runs past the screen text's cap of ${STORY_TEXT_MAX_CHARS} characters — ` +
        "the sticker has to read whole inside the frame."
      );
      return;
    }
    if (wordCount(candidate) > STORY_TEXT_MAX_WORDS) {
      setCapNote(
        `That runs past the screen text's cap of ${STORY_TEXT_MAX_WORDS} words — ` +
        "the sticker has to read whole inside the frame."
      );
      return;
    }
    setCapNote("");
    onChange(candidate);
  };

  const suggest = async () => {
    setBusy(true);
    setError("");
    try {
      const out = await api.suggestStoryScreenText(projectId, {
        screen_text: value, hook_line: hookLine, script,
      });
      if (!out || typeof out.screen_text !== "string" || !out.screen_text.trim()) {
        throw new Error("No screen text came back. Try again in a moment.");
      }
      setSuggestion({ text: out.screen_text, forText: value });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="story-screen-text-section">
      <label htmlFor="story-screen-text" className="text-sm font-semibold">Screen text</label>
      <p className="text-sm text-muted-foreground" data-subtitle="">
        The words on the story as a sticker you place at posting.
      </p>
      <div className="post-kit-cover spoken-line-frame">
        <Input
          id="story-screen-text"
          data-testid="story-screen-text-value"
          value={value}
          onChange={(e) => handleChange(e.target.value)}
          disabled={disabled}
        />
      </div>
      <p className="text-sm text-muted-foreground" data-testid="story-screen-text-count">
        {String(value || "").length} / {STORY_TEXT_MAX_CHARS} characters ·{" "}
        {wordCount(value)} / {STORY_TEXT_MAX_WORDS} words
      </p>
      {capNote && (
        <p className="text-sm text-muted-foreground" role="status" data-testid="story-screen-text-cap-note">
          {capNote}
        </p>
      )}
      <div className="space-y-3">
        {!live && (
          <Button type="button" variant="outline" size="sm" onClick={suggest}
            disabled={busy || disabled || !projectId}
            busy={busy}
            data-testid="story-screen-text-suggest-button">
            <Sparkles className="mr-2 h-3.5 w-3.5" />
            {busy ? "Writing screen text" : "Suggest a new screen text"}
          </Button>
        )}
        {error && (
          <p className="text-sm text-destructive-text" role="alert" data-testid="story-screen-text-suggest-error">
            {error}
          </p>
        )}
        {live && (
          <div className="inset-panel space-y-3" data-testid="story-screen-text-suggestion">
            <p className="text-base font-semibold">&ldquo;{live.text}&rdquo;</p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" disabled={disabled} data-testid="story-screen-text-accept"
                onClick={() => { onChange(live.text); setSuggestion(null); }}>
                Use this text
              </Button>
              <Button type="button" variant="ghost" size="sm" data-testid="story-screen-text-dismiss"
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
