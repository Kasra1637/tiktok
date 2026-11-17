# ADR 0186: The spoken lines wear the cover frame

Status: accepted

On 2026-11-17 the founder held two screenshots side by
side. In one, a History card's cover text: a small-caps
label, then the line standing in a dark rounded box, in
quotation marks — "Friday morning, lighthouse path, I
feel off". In the other, the Review plan view, where his
hook line and script stood inside the generic input
wells — "the ugliest box". His order: the hook line and
the script line take the cover text's design, in the
Review plan view during the video generation steps and
in the History page's video sections, wherever they
render in that input-box style.

## What the audit found

- **The reference is one class.** The History cover line
  is `.post-kit-cover` (`frontend/src/index.css`),
  rendered at `frontend/src/components/PostKitSection.jsx`
  as a span carrying the line between `&ldquo;`/`&rdquo;`
  under its "Cover text" row label: a sunken frame,
  hairline border, 0.5rem radius, bold 1rem type. There
  is no second cover treatment to reconcile with.
- **History has no input-box hook or script to restyle.**
  On a History card the hook is the record's plain-text
  title, the Plan context rows (audience, location, demo
  brief) are plain spec rows, and the only framed line
  is the cover itself, already wearing the reference.
  The order's History half is therefore satisfied by
  what already stands there; this decision changes no
  History markup.
- **The Review fields are working fields, and they
  stay.** The hook input and the script textarea are how
  the founder shortens an over-budget script (the
  over-budget note beside the script says exactly that),
  and the live counts follow the typing (smoke-pinned).
  A display-only replacement would have removed a
  designed behavior inside a presentation order, so the
  frame wraps the fields instead of replacing them.

## Decision

- **The hook and script fields stand inside the cover
  frame.** `HookLineEditor`'s input and the Review
  script textarea in `CreateVideo.jsx` are wrapped in
  the `.post-kit-cover` element itself, quote glyphs
  flanking the field (aria-hidden; they are the frame's
  punctuation, never part of the saved words), with
  `.spoken-line-frame` rules in `index.css` making the
  frame a full-width flex container and stripping the
  field's own chrome — no border, no well, no padding —
  so the frame alone carries the shape, exactly as the
  cover line's box does.
- **Focus stays visible.** The field's focus aura moves
  to the frame (`:focus-within`, the `.input-well`
  treatment: indigo border step plus the 3px aura over
  the frame's inset shadow), so keyboard users lose no
  signal when the well goes away.
- **Presentation only.** Same elements, same ids
  (`review-hook_line`, `review-script`), same values,
  typing, draft edits, live counts, subtitles, and
  Suggest → accept flows. The frame adds no editing
  affordance and removes none; nothing about generation
  times, budgets, or behavior changes.
- **Not targets.** Review's own cover text keeps
  standing as plain text under its subtitle (ADR 0145's
  founder rule) — the reference is the History display,
  not Review's. The demo-brief field, a genuine note
  field the founder did not name, keeps its input well.
  The strategy panel's spoken lines
  (`HookContinuityPanel`) are plain paragraphs, not
  boxes, and are left alone.

## Pins

A new smoke check, "Review spoken lines stand in the
cover frame", mounts the wizard's Review step and
asserts both fields stand inside a `.post-kit-cover`
frame carrying quote marks, and that Review's cover
text value stands outside any such frame. It failed
before the change (neither field had the frame) and
passes after. The neighbouring live-count check —
which types into the script field and watches the
count follow — is unchanged and still passes, pinning
that the fields' behavior did not move.
