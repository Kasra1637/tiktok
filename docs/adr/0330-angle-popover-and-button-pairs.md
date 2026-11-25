# 0330 — Angle details move to a popover; camera and direction picks are button pairs

Date: 2026-11-25

## Context

ADR 0328 put the angle cards two-up and fixed the dead stretch inside
each row, but the picked card still expanded in place: its spec sheet
(audience, problem, promise, feature, outcome, emotion, bounds) grew
the card tall while its row-mate stayed short, leaving a dead stretch
under the shorter card — the same inequality the spacing fix had just
removed, one level down. Kasra, reviewing the shipped step, ruled the
expansion itself out: the cards keep the height they have, and the
details open as a pop-up over the grid instead. In the same review he
extended ADR 0329's side-by-side rule to the last dropdowns on the
step: the camera setup (two options) and the Location and Wardrobe
direction fields, which are to stand as two black buttons side by
side, with the existing "New options" action bringing the next set
when the shown pair does not fit.

## Decision

- Angle rows keep the two-up grid, the check, the title and the fit
  pill. The chevron is replaced by a pop-out icon (Maximize2) at the
  row's right edge, and the row carries `aria-haspopup="dialog"`:
  the affordance says a pop-up opens, not a dropdown or an expansion.
- Picking a row still selects the angle; it also opens that angle's
  spec sheet in a popover anchored under the card — an absolutely
  positioned overlay, so no card grows and no row-mate is stretched
  or left short. The popover carries the same divided spec rows as
  before under the angle's name, with a close button; picking another
  row moves it, re-picking the same row closes it, and Escape or a
  click outside closes it too. Only one popover stands at a time.
- The camera setup in Visual & audio direction is a pair of black
  buttons in the thumb-pair design ADR 0329 gave the resolution row
  (small buttons, the pick lit): "Handheld selfie" and "Fixed
  camera", with the same saved value, draft edit and helper copy.
- `DirectionSelect` renders the same pair on both of its surfaces
  (Create's direction section and HookSnap's Place and wardrobe
  card): the first two options of the current list stand as black
  buttons, a saved pick outside the pair takes the pair's second
  seat so what applies always stands on a lit button, and the
  existing "New options" refresh beside the label brings the next
  set of options, unchanged. The saved-value notes (unlisted place,
  fixed-camera-ineligible place) keep their wording and behavior.

## Addendum (Nov 25 2026): Kasra's live review — a centered pop-up, and three spaced pills in the Voice design

Kasra's first live look corrected three things. The anchored
popover covered nothing: the step's other cards — the goal cards,
a lock badge — painted straight over the sheet, because every
card in the step arrives with the fade-up animation, whose
transform makes each card its own stacking layer and left the
popover's z-index competing only inside its own card. The pop-up
is now a centered overlay: a fixed layer over the whole page,
the sheet wide (max-w-2xl) and centered, standing above every
other element, put away by a backdrop click, the close button,
or Escape. The direction fields show three options, not two,
spaced by the row's gap instead of stuck edge to edge, and their
buttons wear the Voice pick's own design — the rounded pills
with the indigo selection — in place of the black thumb-pair
buttons, moving with the resolution buttons' own motion (the
300ms ease and the 1px hover lift, which the Voice pills now
carry too, so the direction area moves as one family); a saved
pick outside the shown three takes the last seat. The camera setup row keeps the thumb-pair design, and its
row gains the same spacing through the shared .thumb-pair rule.

## Addendum (Nov 25 2026, later): the check leaves the angle rows

At the same live review Kasra loved the round and ordered one
removal: the check mark at the head of every angle row is gone,
and the fit pill stands in its seat, opening the row — the list
is scanned by score first, then by name. The picked row still
reads by its indigo wash and border, and the pop-out icon alone
stands at the row's right edge.

## Consequences

- The angle step's tallest state is now the popover, not a card: the
  grid's rows stay even in every state, and comparing angles costs
  one tap per card with no layout shift to re-scan after.
- Direction picking loses the dropdown's clear-to-empty row: a pick
  is changed by picking another option or a new set, and a saved
  value the list cannot show keeps applying under its standing note,
  exactly as the dropdown era handled it.
- Smoke pins: the angle grid check now pins the pop-out icon and the
  dialog affordance; a new check pins the popover (opens on pick,
  carries the spec sheet outside the card, closes); the camera and
  direction checks drive the pairs through a `pickPairButton` helper
  and pin the shown pair against the offered lists.
