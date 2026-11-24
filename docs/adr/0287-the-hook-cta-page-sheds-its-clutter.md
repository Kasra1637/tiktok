# ADR 0287: The Hook + CTA page sheds its clutter

Status: accepted

## Context

On Nov 23 2026 Kasra worked the Hook + CTA page from his phone and
ordered four cleanups in one sitting, each from something on screen:

- The "Suggest a clearer hook" and "Generate a new hook" buttons
  stood stacked, one over the other.
- The render preview stood on the page from the start — an empty
  phone frame wearing dashed bands labelled HANDLE ZONE and
  CAPTION ZONE, a helper line under it explaining the dashed zones,
  and wide empty card on both sides of the narrow frame. "None of
  that matters to the user."
- The "Hook + CTA drafts for this app" section stood at the foot of
  the page. Kasra ordered it removed — again: the removal was first
  ordered Nov 21 2026, cancelled the same day, and ADR 0262 shipped
  the fresh-open half with the section kept. This order supersedes
  that cancellation.

## Decision

- The two hook buttons stand side by side in one wrapping row at
  the foot of the spoken-line area. Neither button, its handler, nor
  the suggestion flow changes — only the arrangement.
- The preview area stands only once the hook's render is done:
  HookRenderPanel mounts PlatformPreview for a completed generation
  and not before — no frame, no placeholder. Inside the preview,
  the zone bands keep their geometry (ADR 0245) but carry no words,
  the helper line under the frame is deleted, and the preview
  column hugs the frame's 280px instead of spanning its card, so
  the empty side gaps go. The component's other host (the Create
  Video render panel) inherits the unlabelled bands and the hugged
  column; its mount timing is untouched.
- The drafts section is removed from the page, with the openDraft
  helper that served only it. Nothing else about drafts changes:
  the rows stay in the database, ADR 0262's fresh-open adoption of
  an untouched draft still runs off the same read, worked drafts'
  renders stay in History, and a draft still opens through its own
  ?project= link — the smoke checks that opened drafts from the
  list now open them through the link and pin the list's absence.

## Consequences

The page is shorter and quieter: one row of hook actions, no
preview until there is something to preview, no technical labels
on the frame, and no list at the foot. A worked draft with no
render is no longer reachable from this page — that is the
order's own trade, taken knowingly; its renders, once made, are
in History like every other render.
