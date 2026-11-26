import { useLayoutEffect, useRef, useState } from "react";
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
  const text = String(value || "");
  // The wash is worn only while the line exists (ADR 0264): an
  // unwritten hook is a plain field, never an empty indigo bar.
  const washed = Boolean(text.trim());
  // The input's width is measured from the words themselves (ADR
  // 0342): the character-count estimate it replaces ran wide in a
  // proportional font — most glyphs are narrower than the 0 they
  // were charged for — so the wash trailed past the end of the
  // line, exactly as Kasra's screenshot showed. A hidden mirror in
  // the same font carries the text; the input takes its measured
  // width, plus a breath for the caret. Where nothing can be
  // measured (a layout-less test DOM), the estimate stands.
  const measureRef = useRef(null);
  const [inputWidth, setInputWidth] = useState(null);
  useLayoutEffect(() => {
    if (!washed) {
      setInputWidth(null);
      return;
    }
    const node = measureRef.current;
    if (!node) return;
    const measured = node.scrollWidth;
    setInputWidth(measured > 0 ? measured + 2 : null);
  }, [text, washed]);
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
          live count below. The seat hugs the words (ADR 0264): while
          the line exists the wrapper shrink-wraps and the input is
          sized to its text, so the wash ends where the words do
          instead of stretching the full width of the card. The size
          is the measured width of the words (ADR 0342), read off the
          hidden mirror below — never a character count. */}
      <div
        className={washed ? "generated-highlight-field" : undefined}
        style={washed ? { width: "fit-content", maxWidth: "100%" } : undefined}
      >
        <Input
          id="review-hook_line"
          value={value}
          onChange={(e) => onChange(e.target.value)}
          style={washed ? { width: inputWidth ? `${inputWidth}px` : `${Math.max(text.length, 1)}ch` } : undefined}
        />
        {washed && (
          <span
            ref={measureRef}
            aria-hidden="true"
            style={{
              position: "absolute",
              visibility: "hidden",
              whiteSpace: "pre",
              display: "inline-block",
              font: "inherit",
              letterSpacing: "inherit",
            }}
          >
            {text}
          </span>
        )}
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
