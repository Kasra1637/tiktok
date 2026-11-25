import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "../ui/button";
import { api, getErrorMessage } from "../../lib/api";

/**
 * The cover text in Review (ADR 0145): the words on screen for the
 * opening's first two seconds, appearing ONCE as plain text in the
 * section's flow, directly under its subtitle — no box of any kind,
 * wearing the one generated-text highlight (ADR 0258).
 * The 9:16 frame this used to preview in and the boxed field under it
 * are both gone: the founder found the words cramped and clipped in
 * the frame and repeated in the field. The words shown here are
 * exactly the words that ship on the opening, so they read in place
 * like the hook and script lines around them. With no field, the
 * cover is not hand-typed here: a new cover comes only from the
 * Suggest button below, and accepting it writes through the normal
 * draft edit.
 *
 * The cover is still scored WITH the spoken hook in the Craft check
 * below (ADR 0145), but this area says nothing about scores
 * (ADR 0200): the founder reads the words here, plain, and anyone who
 * wants the score finds it in the Checks card right below. A fresh
 * cover comes only from its own button (ADR 0122) and, like the
 * clearer-line suggestions, is never saved by the server: accepting
 * goes through the normal draft edit. The suggest endpoint still
 * returns the hook score the cover would earn; the editor simply
 * does not read it. A suggestion made for a cover the founder has
 * since edited is stale and hides rather than overwriting their
 * newer words.
 */
export default function CoverTextEditor({
  projectId, value, onChange, hookLine = "", script = "", disabled,
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
        throw new Error("No cover text came back. Try again in a moment.");
      }
      setSuggestion({ text: out.cover_text, forCover: value });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4" data-testid="cover-text-section">
      <p className="text-sm font-semibold">Cover text</p>
      <p className="text-sm text-muted-foreground" data-subtitle="">The words on screen in the first two seconds of your clip.</p>
      {/* The cover itself, as plain text in the flow wearing the
          generated-text highlight (ADR 0258), like every other line
          the app wrote: the words the founder reads here are the
          words that ship on the opening. The empty state's line is
          guidance, not generated words, so it stays unhighlighted. */}
      <p className="text-base" data-testid="cover-text-value">
        {value?.trim() ? <span key={value} className="generated-highlight">{value}</span> : <span className="text-muted-foreground">A few words for the opening frame</span>}
      </p>
      <div className="space-y-3">
        {!live && (
          <Button type="button" variant="secondary" size="sm" onClick={suggest}
            disabled={busy || disabled || !projectId}
            busy={busy}
            data-testid="cover-text-suggest-button">
            <Sparkles className="mr-2 h-3.5 w-3.5" />
            {busy ? "Writing cover text" : "Suggest a new cover text"}
          </Button>
        )}
        {error && <p className="text-sm text-destructive-text" role="alert" data-testid="cover-text-suggest-error">{error}</p>}
        {live && (
          <div className="space-y-3" data-testid="cover-text-suggestion">
            <p className="text-base"><span key={live.text} className="generated-highlight font-semibold">{live.text}</span></p>
            <div className="flex flex-wrap gap-2">
              <Button type="button" size="sm" disabled={disabled} data-testid="cover-text-accept"
                onClick={() => { onChange(live.text); setSuggestion(null); }}>
                Use this cover
              </Button>
              <Button type="button" variant="secondary" size="sm" data-testid="cover-text-dismiss"
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
