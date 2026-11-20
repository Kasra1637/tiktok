# 0226 — Angle sets are four by default

Status: accepted

## Context

Kasra's ruling on Nov 20 2026: six angles is too many — "six is too
much." Every angle generation proposed exactly six distinct angles:
`generate_content_angles` in `backend/ai_service.py` defaulted
`max_angles` to 6, the prompt interpolated that count ("Propose
exactly {max_angles} DISTINCT content angles, ordered strongest
first"), and `normalize_content_angles` capped the returned set at
the same value. No caller in `backend/routers/brands.py` passes
`max_angles`, so the one default governed every surface that
produces a set: the auto-generation on profile approval, the manual
generate on the angle step, and every regeneration. Six full angle
cards — each with its problem, promise, feature and fit — is a wall
the founder has to read before they can pick one and move; the
set's size was working against the pick it exists to enable.

Kasra's condition rode with the ruling: if there is no regenerate
button, place one and wire it in. There is one, and it is wired —
`AngleSelector` in `frontend/src/components/studio/SelectionPanels.jsx`
renders "Regenerate angles" (`data-testid="regenerate-angles-button"`)
at the head of the populated angle list, both wizard surfaces that
host the selector pass `onRegenerate`, and the click runs through
the branded `AngleRegenConfirmDialog` to
`api.regenerateContentAngles` and the regenerate endpoint. So the
smaller default lands on a step that already offers a fresh set on
demand; no frontend placement work was needed.

## Decision

1. **The default set size is four.** `generate_content_angles`'
   `max_angles` default is 4. The prompt's interpolated ask and the
   normalizer's cap already follow the parameter, so the first set
   a profile gets, a manual generate, and every regeneration all
   propose exactly four distinct angles, ordered strongest first.
   One size everywhere the default applies — a regeneration never
   brings back the crowded wall of six.

2. **Nothing else about a set changes.** Uniqueness per campaign,
   the diversity and already-offered corrections, and the retry
   rule (a corrected set must not come back smaller than the first
   attempt's) are untouched — they are relative to the set, never
   to a fixed count. Regenerate still replaces only the generated
   angles and keeps hand-written ones; a draft built on a replaced
   angle still keeps the draft and owes a rebuild. An explicit
   `max_angles` argument still means exactly what it meant.

3. **The copy and pins that stated six now state four.** The angle
   prompt's two hardcoded sixes (the differ-in-argument rule and the
   objective block) are reworded count-free — the interpolated
   "exactly {max_angles}" line is the one place the count is
   stated. The angle step's CTA reads "Get four audience angles,
   then pick one to move forward" — "four" is one character longer
   than "six", and the old line already sat at the subtitle
   budget's 60-character ceiling, so the line pays for the swap by
   dropping its "your" and lands at 58. The render smoke's CTA
   pin and its regenerate pin (four fresh rows, four check marks)
   and the backend cap pin follow. The fit score's unused fallback
   `total` in `frontend/src/lib/angleSubtitle.js` defaults to 4 to
   match the set it would describe; every real caller passes the
   list's own length.

4. **The sixes that are not angle sets stay.** Six goals per angle
   (the generated pool behind the top-three display, ADR 0131),
   the six goal suggestions per angle kind, the per-angle claims
   cap, and the historical sixes — ADR 0193's account of the rank
   transform it replaced, and the busy-ETA note recording that its
   50s was founder-measured against six fielded angles — are
   different facts and do not move.

## Consequences

- A founder reads four cards, picks one, and moves. Wanting more
  costs one Regenerate press, which was already there; the set
  that comes back is four again, so the step's reading load is a
  property of the step, not of how the founder arrived at it.
- Angle generation asks the model for a third fewer angles per
  call; the token budget and the doubled-retry recovery are
  unchanged, and the 50s countdown stays as measured — re-measuring
  it against four is a separate observation, not part of this
  change.
- Tests: `test_generation_caps_at_four_angles` in
  `backend/test_ai_json_calls.py` pins the new default — a fake
  model returning nine candidates yields exactly four, and the
  prompt it was handed asked for exactly four. It was watched
  failing against the six default before the change. The template
  API suite's generate double mirrors the new default signature.
