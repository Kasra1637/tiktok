import { useState } from "react";
import { Loader as Loader2, Sparkles } from "lucide-react";
import { Button } from "../ui/button";
import { Input } from "../ui/input";
import { api, getErrorMessage } from "../../lib/api";

/**
 * The Review hook line, with a one-click clearer rewrite offered only beside
 * a vague-hook warning (ADR 0084). The suggestion is never saved by the
 * server: "Use this line" goes through the normal draft edit, so autosave and
 * the claim check rerun exactly as if the founder had typed it.
 */
export default function HookLineEditor({ projectId, value, onChange, report, disabled }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState("");
  const [suggestion, setSuggestion] = useState(null);
  const vague = (report?.risk_warnings || []).filter((w) => String(w?.reason || "").includes("vague"));
  const live = suggestion && suggestion.forLine === value ? suggestion.line : "";

  const suggest = async () => {
    setBusy(true);
    setError("");
    try {
      const out = await api.rewriteHook(projectId, value);
      if (!out || typeof out.hook_line !== "string" || !out.hook_line.trim()) {
        throw new Error("No clearer line came back. Try again, or edit the line yourself.");
      }
      setSuggestion({ line: out.hook_line, forLine: value });
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="space-y-4">
      <label htmlFor="review-hook_line" className="text-sm font-semibold">Hook line</label>
      <p className="text-sm text-muted-foreground" data-subtitle="">The opening line spoken in your generated Hook + Story clip.</p>
      <Input id="review-hook_line" value={value} onChange={(e) => onChange(e.target.value)} />
      {vague.length > 0 && (
        <div className="inset-panel space-y-3" data-testid="vague-hook-note">
          <p className="text-base">
            &ldquo;{vague[0].claim}&rdquo; doesn&rsquo;t say what the viewer is avoiding. Naming the real
            task makes the hook land faster.
          </p>
          <p className="text-sm text-muted-foreground" data-subtitle="">This is a suggestion — your hook still renders either way.</p>
          {!live && (
            <Button type="button" variant="outline" size="sm" onClick={suggest}
              disabled={busy || disabled || !projectId || !String(value || "").trim()}
              data-testid="hook-rewrite-button">
              {busy ? <Loader2 className="mr-2 h-3.5 w-3.5 animate-spin" /> : <Sparkles className="mr-2 h-3.5 w-3.5" />}
              {busy ? "Writing one" : "Suggest a clearer hook"}
            </Button>
          )}
          {error && <p className="text-sm text-destructive" role="alert" data-testid="hook-rewrite-error">{error}</p>}
          {live && (
            <div className="space-y-3 transition-opacity duration-200" data-testid="hook-rewrite-suggestion">
              <p className="text-base font-semibold">&ldquo;{live}&rdquo;</p>
              <div className="flex flex-wrap gap-2">
                <Button type="button" size="sm" disabled={disabled} data-testid="hook-rewrite-accept"
                  onClick={() => { onChange(live); setSuggestion(null); }}>
                  Use this line
                </Button>
                <Button type="button" variant="ghost" size="sm" data-testid="hook-rewrite-dismiss"
                  onClick={() => setSuggestion(null)}>
                  Keep mine
                </Button>
              </div>
            </div>
          )}
        </div>
      )}
    </div>
  );
}
