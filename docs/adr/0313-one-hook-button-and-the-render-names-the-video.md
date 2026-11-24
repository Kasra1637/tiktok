# ADR 0313: One hook button on Hook + CTA, and the render names the video

Status: accepted

## Context

On the Hook + CTA page, once a hook existed, the hook line card
carried two buttons side by side — "Suggest a clearer hook"
(ADR 0249's stateful button in its written-line state) and
"Generate a new hook" (ADR 0265; the row is ADR 0287) — and the
render card directly below carried a third, "Generate the
hook", which renders the video. Kasra, reviewing his own
screenshots on Nov 24 2026: the two hook buttons are too much —
"Just keep generate a new hook" — and the render button's name
collides with the hook buttons above it, two near-identical
labels for writing a line and rendering a video. He held the
change until he had shown the render button, then re-confirmed
both halves and ruled the render button's text himself:
"update the button text to generate the video".

## Decision

- The Hook + CTA hook card's "Suggest a clearer hook" button
  is removed. Before a hook exists the card's one button is
  "Generate the hook" (unchanged, testid `hook-generate`);
  once a hook exists the ONLY button in the row is "Generate
  a new hook" (testid `hook-generate-new`, behavior unchanged —
  it reruns generation from the current picks and its result
  is the line on file directly). This supersedes the Hook +
  CTA half of ADR 0249's stateful button and ADR 0287's
  side-by-side row. The editor still mounts with
  `suggestClearerHook={false}`, so no suggestion stands
  anywhere in the card, and the page no longer imports
  `LineRewriteAction`.
- The render button in `HookRenderPanel` names the video:
  "Generate the video" for the first render, "Generate
  another video" for a re-render — the same wording Create
  Video's render panel already uses. The gate sentence above
  it ("Generate the hook first — the render speaks its line…")
  is unchanged: it names the hook card's surviving
  "Generate the hook" button, not the render.
- The picks stale note follows the surviving remedy: "The
  line on file was written before these picks — generate a
  new hook to write it with them." (ADR 0265 recorded that the
  note's wording named the suggestion; it names the fresh
  generate now.)
- NOT touched: Create Video's Review step and its own
  "Suggest a clearer hook" for the plan hook (ADR 0205);
  `SpokenLineEditor`'s suggest behavior anywhere else; the
  hook generation logic; any backend file.

## Consequences

One generate verb per job on the page: "Generate the hook" /
"Generate a new hook" write lines, "Generate the video" /
"Generate another video" renders. A founder who wants a
sharper line on Hook + CTA edits it in the field or generates
a new one — the accept-to-write suggestion flow remains
available on Create Video's Review, where the hook is one line
of a longer plan. The render button's busy text still reads
"Generating hook" — the artifact this panel has always called
the hook (the section is "Render the hook"); only the resting
labels were in the collision Kasra named. Smoke pins the new
arrangement red-before-green: the post-generation row holds
Generate a new hook and no clearer-hook control, the fresh
generate still replaces the line from the current picks, the
stale note names the new remedy, and the render button reads
"Generate the video" / "Generate another video".
