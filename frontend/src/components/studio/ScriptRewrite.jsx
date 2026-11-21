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
 *
 * The button stands alone, with no explainer line (ADR 0242): the
 * hook's assist carries none and is understood, and the suggestion
 * itself arrives with its accept/dismiss, so the "nothing changes
 * until you accept it" the line used to narrate is visible at the
 * moment it matters instead.
 */
export default function ScriptRewrite({ projectId, hookLine, script, onChange, disabled }) {
  if (!String(script || "").trim()) return null;
  return (
    <div className="space-y-3" data-testid="script-rewrite">
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
