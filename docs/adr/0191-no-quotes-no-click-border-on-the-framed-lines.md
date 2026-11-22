# 0191 — No quotation marks and no click border on the framed lines

Status: partially superseded by 0258 (the sunken frame it kept is
retired for the generated-text highlight; the no-quotation-mark and
no-click-border rules stand and govern the highlight family)

Supersedes the quote element and the focus treatment of ADR 0186;
the sunken cover frame itself stands.

## Context

ADR 0186 stood the Review hook line and script inside the History
cover text's sunken frame, quotation marks included, with the frame
taking an indigo border and ring on `:focus-within`. On the Nov 17
2026 evening call the founder ruled against both details, repeating
the first three times for emphasis:

- He NEVER wants quotation marks shown in the hook line or the
  script line. (The earlier idea of tucking the closing quote against
  the text is cancelled with it — the quotes come off entirely.)
- The script box is too tall: a two-sentence script sat in a fixed
  tall frame with empty space beneath the words.
- Minutes later, the amendment: clicking into either box shows an
  indigo border and ring — "do not display anything when the user
  clicks on those two boxes." And the finished design (sunken frame,
  no quotes, content-fitted height, no click border) is one family,
  referenced on the History page's cover box: it applies to the demo
  brief and to every surface with the same pattern, and the History
  Post copy cover box loses its quotes too, so the family actually
  matches.

## Decision

1. **No quote glyphs in the family.** The aria-hidden `&ldquo;` /
   `&rdquo;` spans flanking the hook field (`HookLineEditor.jsx`) and
   the script field (`CreateVideo.jsx`) are removed, and the History
   cover box's entities come off in `PostKitSection.jsx`. The lines
   stand in the frame with no quotation marks at all.
2. **The script frame fits its content.** The script textarea's
   `min-h-[160px]` floor is removed. The shared `Textarea` already
   auto-grows (it refits its height from `scrollHeight` on every
   render and keystroke); the floor was the only thing holding the
   box open. What remains is the component's own 72px minimum, so a
   short script hugs its words and a longer one still grows.
3. **No click border, anywhere in the family.** The one rule the
   founder saw — `.spoken-line-frame:focus-within` (indigo border,
   3px ring) — is deleted. Because the framed field is an
   `.input-well`, its own hover/focus-visible treatments and 150ms
   border/shadow transition also reached inside the frame; both are
   neutralized within the family only (the resting treatment restated
   at higher specificity, `transition: none` on the framed field).
   After this change the frame looks identical at rest, hover, focus
   and focus-within; the caret is the only sign of editing. Ordinary
   form fields keep their focus treatment untouched. The trade is
   recorded plainly: keyboard focus visibility on these three fields
   is the caret alone, by the founder's explicit ruling.
4. **The demo brief joins the family.** The "What the demo should
   show" textarea in Review now stands in the same frame, fitted to
   its content the same way. It never carried quotes; none are added.
   Its label, subtitle, placeholder and save behavior are unchanged.
5. **The History cover box matches.** `PostKitSection`'s cover line
   renders without its quote entities. Because the component is
   shared, the same change lands on its other two render sites — the
   render result's post copy in `GenerationPanel` and the Demo + CTA
   studio's saved kit — which is the family matching, not scope
   creep: one component, one presentation.

## Audit (amendment B.3)

Changed: the Review hook frame, the Review script frame, the Review
demo brief (framed by this ADR), and the PostKitSection cover box
(History cards, GenerationPanel, Demo + CTA studio).

Left alone, with reasons:

- `HookContinuityPanel` — plain-paragraph spoken lines; not the
  framed pattern.
- `CoverTextEditor`'s preview — Review's own cover text stands plain
  by ADR 0145 and was named out of scope; it is an unframed paragraph.
- `LineRewriteAction`'s suggestion preview — an unframed bold
  paragraph quoting a proposed rewrite inside the Suggest flow; not
  a framed field. Borderline: if the founder wants his no-quotes
  rule to reach suggestion previews too, that is a one-line follow-up
  on his word.
- `SelectionPanels`' angle example and `HistoryFeedback`'s prose —
  quotation marks as ordinary writing in explanatory text, not line
  displays.

## Consequences

The ADR 0186 smoke check is rewritten ("Review spoken lines stand
in the cover frame with no quote marks and no click border", red
before green): it now asserts no quote glyphs in either frame, the
script field free of its fixed tall height, the demo brief standing
in the family frameless of quotes, and no `:focus-within` rule for
the frame in `index.css`; the live-count behavioral checks (typing
moves the counts) still pass, and Review's own cover text still
stands plain outside the frame. A new check pins the History cover
box without quote marks. AGENTS.md's sentence describing ADR 0186's
framed fields is updated so it no longer implies quotes or a focus
aura.

Numbering note: the parallel craft/save bundle took 0188 and held
the camera-move decision at 0189, then at 0191, before landing it as
0192 — so this delivery's sequence (0187 behavior rule, 0189 History
split, 0190 plan helper, 0191 this ADR) stands without a duplicate.
One interleaving remains on the record: the bundle's craft commit
(fe15fd7) swept this ADR's CreateVideo.jsx hunks (the script frame
and the demo brief) into itself, because both builders were editing
the same file; the changes are identical to this ADR's decision and
are committed on main under that commit.
