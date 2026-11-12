import LineRewriteAction from "./LineRewriteAction";

/**
 * Split a script into its spoken sentences, each with its exact span in
 * the original text. A terminator ends a sentence only when a space, a
 * newline or the end of the text follows — the same rule the backend's
 * `_split_sentences` applies — so "12.5" stays whole, and accepting a
 * rewrite replaces only that sentence's characters, leaving the founder's
 * other words byte-for-byte intact.
 */
export function splitScriptSentences(script) {
  const text = String(script || "");
  const spans = [];
  const push = (rawStart, rawEnd) => {
    const raw = text.slice(rawStart, rawEnd);
    const trimmed = raw.trim();
    if (!trimmed) return;
    const start = rawStart + (raw.length - raw.trimStart().length);
    spans.push({ text: trimmed, start, end: start + trimmed.length });
  };
  let start = 0;
  for (let i = 0; i < text.length; i++) {
    const ch = text[i];
    if (ch !== "." && ch !== "!" && ch !== "?") continue;
    const following = i + 1 < text.length ? text[i + 1] : "";
    if (following === "" || following === " " || following === "\n" || following === "\t") {
      push(start, i + 1);
      start = i + 1;
    }
  }
  push(start, text.length);
  return spans;
}

export function replaceScriptSentence(script, span, next) {
  const text = String(script || "");
  return text.slice(0, span.start) + next + text.slice(span.end);
}

/**
 * The script's lines, one by one, each with the clearer-line rewrite the
 * hook has always had — now for every spoken line, not only a flagged
 * hook. The textarea above stays the editor; this list is the per-line
 * assist under it. Accepting a suggestion rewrites just that sentence in
 * the draft, through the same edit the textarea makes.
 */
export default function ScriptLineRewrites({ projectId, hookLine, script, onChange, disabled }) {
  const spans = splitScriptSentences(script);
  if (!spans.length) return null;
  return (
    <div className="space-y-4" data-testid="script-line-rewrites">
      <p className="text-sm text-muted-foreground">
        Or sharpen one line at a time. A suggestion appears beside your words,
        and only the line you accept changes.
      </p>
      {spans.map((span, i) => (
        <div key={`${span.start}-${span.text}`} className="space-y-2">
          <p className="text-sm">{span.text}</p>
          <LineRewriteAction
            projectId={projectId}
            line={span.text}
            role="middle"
            hookLine={hookLine}
            script={script}
            onAccept={(next) => onChange(replaceScriptSentence(script, span, next))}
            disabled={disabled}
            testIdPrefix={`script-rewrite-${i}`}
            buttonLabel="Suggest a clearer line"
            busyLabel="Writing line"
          />
        </div>
      ))}
    </div>
  );
}
