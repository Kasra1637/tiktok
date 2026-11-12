import { useState } from "react";
import { Sparkles } from "lucide-react";
import { Button } from "../ui/button";
import { api, getErrorMessage } from "../../lib/api";

/**
 * The clearer-line rewrite for one spoken line — the hook, or one sentence
 * of the script.
 *
 * A suggestion only, offered on every line with no warning gate: the
 * founder asks, reads the suggestion beside their own words, and either
 * takes it — "Use this line" goes through the normal draft edit, so
 * autosave and the version rules run exactly as if they had typed it — or
 * keeps theirs. A suggestion made for a line the founder has since edited
 * is stale and hides rather than overwriting their newer words.
 */
export default function LineRewriteAction({
  projectId, line, role, hookLine = "", script = "", onAccept, disabled,
  testIdPrefix, buttonLabel, busyLabel,
}) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestion, setSuggestion] = useState(null);
  const live = suggestion && suggestion.forLine === line ? suggestion.line : "";

  const suggest = async () => {
    setBusy(true);
    setError("");
    try {
      const out = await api.rewriteLine(projectId, { line, role, hook_line: hookLine, script });
      if (!out || typeof out.line !== "string" || !out.line.trim()) {
        throw new Error("No clearer line came back. Try again, or edit the line yourself.");
      }
      setSuggestion({ line: out.line, forLine: line });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-3">
      {!live && (
        <Button type="button" variant="outline" size="sm" onClick={suggest}
          disabled={busy || disabled || !projectId || !String(line || "").trim()}
          busy={busy}
          data-testid={`${testIdPrefix}-button`}>
          <Sparkles className="mr-2 h-3.5 w-3.5" />
          {busy ? busyLabel : buttonLabel}
        </Button>
      )}
      {error && <p className="text-sm text-destructive" role="alert" data-testid={`${testIdPrefix}-error`}>{error}</p>}
      {live && (
        <div className="inset-panel space-y-3" data-testid={`${testIdPrefix}-suggestion`}>
          <p className="text-base font-semibold">&ldquo;{live}&rdquo;</p>
          <div className="flex flex-wrap gap-2">
            <Button type="button" size="sm" disabled={disabled} data-testid={`${testIdPrefix}-accept`}
              onClick={() => { onAccept(live); setSuggestion(null); }}>
              Use this line
            </Button>
            <Button type="button" variant="ghost" size="sm" data-testid={`${testIdPrefix}-dismiss`}
              onClick={() => setSuggestion(null)}>
              Keep mine
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
