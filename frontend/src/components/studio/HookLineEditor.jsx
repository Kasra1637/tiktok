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
 *
 * The Hook + CTA page mounts this editor WITHOUT its rewrite
 * (suggestClearerHook={false}, ADR 0249): that page's one hook button
 * becomes the clearer-hook suggestion itself once a line exists, so an
 * editor-mounted second copy would put the same control in the card
 * twice. The capability stays here for every other surface — Create
 * Video's Review above all.
 */
export default function HookLineEditor({ projectId, value, onChange, disabled, clipLabel = "Hook + Story clip", suggestClearerHook = true }) {
  return (
    <div className="space-y-4">
      <label htmlFor="review-hook_line" className="text-sm font-semibold">Hook line</label>
      {/* The helper names the clip the line is spoken in, and the two
          surfaces' clips differ: Create Video's render is a Hook +
          Story clip, the Hook + CTA page's is the hook alone — there
          is no story on that page, so its helper says so (ADR 0248).
          The caller passes its own clip's name; the default is the
          wizard's, the editor's original home. */}
      <p className="text-sm text-muted-foreground" data-subtitle="">The opening line spoken in your generated {clipLabel}.</p>
      {/* The line stands in the generated-text highlight (ADR 0258):
          the same light wash every generated line wears, so the words
          read as the finished line, not as a form in a box. No
          quotation marks anywhere in the highlight family (ADR 0191)
          — the founder never wants them on the spoken lines. The
          field inside is the same input — same id, same typing, same
          live count below. */}
      <div className="generated-highlight-field">
        <Input id="review-hook_line" value={value} onChange={(e) => onChange(e.target.value)} />
      </div>
      {suggestClearerHook && (
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
      )}
    </div>
  );
}
