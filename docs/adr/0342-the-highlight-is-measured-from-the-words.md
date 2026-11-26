# ADR 0342: The highlight is measured from the words

## Status

Accepted, Nov 25 2026 — Kasra's screenshot at the live review:
the hook line's highlight ran wider than the text itself.
"It should only cover the content and text."

## Context

The hook editor's seat already meant to hug (ADR 0264): the
wrapper shrink-wraps and the input is sized to its text. The
sizing was the defect — the input's width was the line's
character count in ch units, and a ch is the width of the
font's 0. In the seat's proportional font most glyphs are far
narrower than that, so the field ran roughly a third wider
than the words, and the wash trailed past the end of the
line, exactly as the screenshot showed.

## Decision

The editor measures the words: a hidden mirror span in the
seat's own font carries the text, and the input takes the
mirror's measured width, plus a small allowance for the
caret. The character count survives only as the fallback for
a DOM that cannot measure (the test harness), where no pixel
claim is made. The wrapper, the wash, the entrance, and the
field itself are unchanged.

Scope: this is the single-line hook editor, the reported
surface, in both its homes (Create's Review and HookSnap).
The script and demo brief are paragraph fields; their words
wrap the field's full width by nature, so their wash backs a
paragraph rather than a line and stands as built.

## Consequences

The render-smoke hug check now also pins the measurement in
the editor's source. A future editable line that wears the
wash sizes itself from its words the same way, or it does
not wear it.
