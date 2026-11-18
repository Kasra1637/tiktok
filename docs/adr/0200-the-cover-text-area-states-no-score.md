# ADR 0200: The cover text area states no score

Status: accepted

Kasra ruled on Nov 18 2026 that the cover text area in Review
must not state any score. Updating the cover surfaced a note
beside it naming the hook's current Hook stopping power score
("currently 16 out of 20"), and a suggested cover carried a
second line projecting the movement ("would move from … to …
with this cover"). His words: "that doesn't say the new score
right in the cover text area. If they want to see the score,
they can see it right below." The cover area is for reading the
words; the Craft check card directly below it is where scores
live. He also asked that the clearer-line and clearer-hook
suggestions stay "as simple as the rest" — no score annotations
on suggestion surfaces.

## Decision

- `CoverTextEditor` loses both score displays: the standing
  note ("Scored with your hook in Hook stopping power —
  currently N/20.") and the suggestion's move line. A suggestion
  now shows only the quoted cover text and the Use this cover /
  Keep mine buttons, exactly like the clearer-line suggestions.
- The dead plumbing goes with them: the `hookScore` prop
  (previously fed from the project's quality report in
  `CreateVideo.jsx`) is removed, and the editor no longer reads
  the `hook_score` field the suggest endpoint returns. The
  endpoint and its response are unchanged — this is display
  only.
- Nothing about scoring changes. The cover text is still scored
  with the spoken hook in Hook stopping power (ADR 0145), and
  the Craft check card below the cover section keeps every
  dimension score, untouched.

## Audit of the suggestion surfaces

The clearer-hook editor (`HookLineEditor` →
`LineRewriteAction`) and the script's per-sentence rewrites
(`ScriptLineRewrites` → `LineRewriteAction`) were read for score
annotations: their suggestions render only the quoted line and
the accept/dismiss buttons — no score, no projected score, no
"would move" line. Nothing changed there; the cover editor was
the only suggestion surface carrying one.

## Consequences

The two cover smoke checks are re-pinned to the new behavior:
the cover section must contain no score note and no score text,
a suggested cover must render no move line, and the same mount
asserts the Craft check card below still shows the hook
dimension's 13/20 — the score moved nowhere; it was only ever
duplicated in the wrong place, and now it is stated once, where
the founder looks for it.
