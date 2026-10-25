# 0009 — History tiles open on demand: the clip first, the record behind a tab

- **Status:** partially superseded by 0033 (collapsed tiles now show identity & saved result facts)
- **Date:** 2026-10-16
- **Anchors:** `frontend/src/pages/GenerationHistory.jsx:44` (drag constants),
  `:183` (`HistoryExpandTab`), `:493` (the tab in the card), `frontend/src/index.css:656`
  (`.history-stage`), `:694` (`.history-tab`)

## Context

A history card showed everything at once: a 152px preview rail, a context
column with the hook, facts, audience and demo brief, a Download and Delete pair
under the clip, a three-tile work row beside it, and a separate failed-row bar.
Every card in a two-column grid was therefore ~460px of chrome around a 270px
preview, and the actions that matter most — download the file, take it onward —
competed for attention with the facts that are only interesting *after* you have
decided to open a render. Delete sat one click away from Download in a 240px
column, guarded only by its wording.

The page is read in two moods, and each card served neither well: scanning
("which of these is the clip I want") and working ("download it, open it in Demo
+ CTA, read the prompt that produced it, delete it").

## Decision

A tile is the clip, and nothing else. The card opens with a full-bleed stage
holding the contained video and a single tab beneath it — no app name, no
status, no facts standing beside the footage. The app name, status, hook, facts,
audience, demo brief, the paper trail, and every action live in the drawer the
tab opens. A render with nothing to play is the one exception and keeps a notice
where the video would be, because a blank tile explains nothing.

The tab is one control with three ways in — click, Enter/Space, and a drag
toward the open direction that follows the pointer and commits past 60% of
`DRAG_COMMIT_PX` (56px). The drag arms only after 4px of travel so a shaky press
still resolves to a click, and a drag's trailing click is suppressed exactly
once. Touch dragging is restricted to the grip (`touch-action: none`); the rest
of the tab stays a click surface so a phone can still scroll past the card.

Inside the drawer, actions are grouped by consequence rather than by kind:
Download and Demo + CTA are the wide pair, `Retry render` joins them on a failed
row, and Details and Delete sit on a quieter line beneath. Delete is never in the
row that saves the file. The card's border turns to the indigo hairline while a
tile is open, and tiles are not exclusive — two renders can be compared open.

## Alternatives rejected

- **A details modal for everything.** History doubles as the download screen, so
  the actions cannot live behind a dialog that has to be dismissed between two
  downloads. The `Details` dialog survives for the prompt and claim check, which
  is reading material, not an action bar.
- **Always-rendered actions, hidden with CSS.** A drawer whose contents exist
  while closed puts Delete in the tab order of a collapsed tile and defeats the
  point of the gesture. Closed tiles render only the stage and the tab.
- **A measured `height: auto` animation.** It reads the card's geometry back
  mid-flight, which is exactly the layout dance that fights the grid it lives in.
  The card grows to its real height and the drawer's own contents slide in
  (`.history-drawer`), and the animation is dropped entirely under
  `prefers-reduced-motion`.
- **Deleting without the deliberate gesture.** The extra gesture is the point:
  the file controls belong to a render you have opened.
- **A scrim on the footage.** Carrying the app name, status and duration over
  the video kept a filtered page readable at a glance, but it also made the tile
  "the clip plus a caption" rather than the clip. Those facts moved into the
  drawer, which is where the page already sends anyone who wants to know more.

## Consequences

- Reaching any action costs one interaction more than before. That is the
  trade: ten tiles of clips read as a contact sheet instead of ten panels of
  chrome, and the destructive control is no longer adjacent to the saving one.
- `frontend/scripts/check-render-smoke.cjs` asserts the collapsed tile exposes
  no action labels, that the tab opens the drawer by click *and* by drag, and
  that a drag short of the threshold does not open it. The old checks that
  reached straight for Download/Delete now expand the tile first.
- Collapsed tiles are all one height regardless of status, so a row containing a
  failed render does not go ragged. The preview height and the stage padding are
  custom properties on `.history-card` for that reason.
- The tile no longer says which app it belongs to. Expanding a render shows it
  again at the top of the drawer, and the app filter is still how a page of
  tiles is narrowed in the first place; a founder who needs the label reads it
  one gesture in.
- The cost of a longer card is layout, not fetch: the drawer holds no media, and
  the poster keeps `preload="none"` so a page of tiles still fetches no video
  bytes.
