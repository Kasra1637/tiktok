# ADR 0146: The drift gate diffs the saved direction, raw

Status: accepted

## Context

Kasra hit ADR 0142's rebuild gate as a loop that could never clear: on
a fresh generation he had edited nothing, yet the render panel hid
"Generate the video" behind "The direction changed after this strategy
was built," and clicking Rebuild strategy stamped a fresh strategy and
changed nothing — the same notice came straight back.

The two sides of the gate were diffing different texts. The strategy
build stamps `direction_snapshot` from the raw project row (ADR 0133),
and the server's own diff (`_strategy_direction_changes`) reads that
same raw row, so server-side a rebuild clears the drift. But the client
gate (`frontend/src/lib/strategyStaleness.js`, ADR 0142) diffed the
stamp against the project payload's top-level `location` — which is
display text, not the saved value. `_public_project` rewrites it before
display: an empty saved location is filled from the strategy's scene,
object clauses ("...with the phone lying face-down beside the person")
are stripped, and a continuation fragment is repaired with an anchor.
A plan-written Location is stored raw by the plan save, so any plan
whose Location carried an object clause produced a payload whose
display location could never equal the raw stamp: drift read true
forever, every rebuild re-stamped the raw value, and every read
re-transformed it. The button and the gate disagreed with the server —
the exact failure ADR 0142's shared helper was meant to make
impossible; the helper was shared, but its input was not the server's.

## Decision

- **The comparison is raw against raw.** `_public_project` captures the
  saved direction before any display transform and carries it on the
  payload as `direction_saved` (`_direction_snapshot(row)`: location,
  visual_direction, voice_direction, sound_direction, whitespace
  trimmed — the same normalization the stamp and the server diff use).
- **`directionDrifted` diffs the stamp against `direction_saved`** when
  the payload carries it. Payloads without it (older responses) fall
  back to the top-level fields, keeping the ADR 0142 scene-fill excuse,
  which exists only for that fallback: with the saved value present it
  speaks for itself (an empty saved location diffs as empty, exactly as
  the server sees it).
- **Display behavior is unchanged.** The Location editor still shows
  the place only; `_public_project`'s fill, strip and repair are
  untouched. Only the gate's input changed.

## Consequences

- A rebuild now clears direction drift the way the server already said
  it should: the client gate and `_strategy_direction_changes` answer
  the same question about the same values, so the ADR 0142 mirror
  holds in fact, not just in structure.
- Regression-pinned on both sides: the backend test builds a project
  whose plan wrote an object-clause Location and asserts the payload's
  display location is stripped while `direction_saved` equals the
  stamp and the server diff reports no changes; the frontend tests pin
  that a display-stripped location is not drift, that a moved saved
  value is drift even when its display text matches the stamp, and
  that legacy payloads without `direction_saved` still work.
