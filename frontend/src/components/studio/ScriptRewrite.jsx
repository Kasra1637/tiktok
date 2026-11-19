import LineRewriteAction from "./LineRewriteAction";

/**
 * The script's one rewrite assist: a single button that remakes the
 * script whole (ADR 0205), replacing the per-sentence clearer-line
 * buttons that stood here before — one per sentence, each editing only
 * its own span. The textarea above stays the editor; this is the assist
 * under it. The whole script is the action's line, so any edit in the
 * textarea stales a standing suggestion and it hides rather than
 * overwriting the founder's newer words; accepting the suggestion
 * replaces the entire script through the same draft edit the textarea
 * makes.
 */
export default function ScriptRewrite({ projectId, hookLine, script, onChange, disabled }) {
  if (!String(script || "").trim()) return null;
  return (
    <div className="space-y-3" data-testid="script-rewrite">
      <p className="text-sm text-muted-foreground">
        Or remake the script in one go. One suggestion for the whole story,
        and nothing changes until you accept it.
      </p>
      <LineRewriteAction
        projectId={projectId}
        line={script}
        role="script"
        hookLine={hookLine}
        script={script}
        onAccept={onChange}
        disabled={disabled}
        testIdPrefix="script-rewrite"
        buttonLabel="Remake the script"
        busyLabel="Remaking script"
        acceptLabel="Use this script"
      />
    </div>
  );
}
