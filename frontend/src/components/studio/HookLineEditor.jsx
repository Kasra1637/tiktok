import { Input } from "../ui/input";
import LineRewriteAction from "./LineRewriteAction";

/**
 * The Review hook line field, with the clearer-line rewrite one click away
 * for every hook. The rewrite used to be offered only beside a vague-hook
 * warning taken from the claim-safety report; that report is gone
 * (ADR 0119), so the assist is simply there now, on this line and on every
 * script line. The suggestion is never saved by the server: accepting it
 * goes through the normal draft edit, so autosave runs as if the founder
 * had typed it.
 */
export default function HookLineEditor({ projectId, value, onChange, disabled }) {
  return (
    <div className="space-y-4">
      <label htmlFor="review-hook_line" className="text-sm font-semibold">Hook line</label>
      <p className="text-sm text-muted-foreground" data-subtitle="">The opening line spoken in your generated Hook + Story clip.</p>
      <Input id="review-hook_line" value={value} onChange={(e) => onChange(e.target.value)} />
      <LineRewriteAction
        projectId={projectId}
        line={value}
        role="hook"
        onAccept={onChange}
        disabled={disabled}
        testIdPrefix="hook-rewrite"
        buttonLabel="Suggest a clearer hook"
        busyLabel="Writing hook"
      />
    </div>
  );
}
