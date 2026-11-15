# ADR 0142: The strategy rebuild button exists only while a rebuild is owed

Status: accepted

## Context

Kasra's standing Review rule hides "Generate the video" while a strategy
rebuild is owed, so the step always shows exactly one action: the one
that unblocks the render. The mirror image was never applied to the
strategy panel itself. Its "Rebuild strategy" button rendered as a big
primary button on every project, including projects whose strategy was
current and ready to render — on Nov 14 2026 Kasra saw exactly that on
his bakery project (strategy v2 current, Generate available) and read
the button as a required step it is not.

"Owed" also had a hole. The panels owed a rebuild when the plan changed
after the build (the server's `strategy_is_current`) or the picked angle
changed — but not when the direction changed, even though ADR 0133
stamps the direction into the strategy at build time
(`direction_snapshot`) precisely because a direction change is a manual
update that leaves the strategy describing a scene the render would no
longer follow. A direction edit after the build left both panels
treating the strategy as current, and the render gate agreed.

## Decision

- **The strategy panel's build control renders only in the owed or
  missing states** — no strategy yet ("Build the strategy", unchanged),
  a rebuild owed, or a build flight already running (the busy state the
  click started must stay visible). When the strategy is current there
  is no rebuild button at all. The strategy content sections are
  untouched; this is only about the button.
- **Direction drift counts as owed**, in both panels, on the same terms
  as a plan or angle change: while it holds, the strategy panel shows
  the rebuild (with a warning naming the direction as the cause), the
  render panel hides Generate entirely and offers the rebuild remedy,
  and the sticky wizard bar carries the rebuild as the step's unblocking
  action. The click keeps the ADR 0133 flow exactly: suggestions first,
  rebuild once.
- **Drift is computed client-side from the payload**, in one shared
  helper (`frontend/src/lib/strategyStaleness.js`) both panels use, so
  the button and the render gate cannot disagree. It mirrors the
  server's diff in `backend/routers/studio.py`: the current direction
  (location, visual_direction, voice_direction, sound_direction)
  compared against the strategy's `direction_snapshot`, whitespace
  trimmed. A strategy with no snapshot is missing history, not drifted —
  never owed on this ground alone, the ADR 0133 legacy rule. One display
  repair is accounted for: the payload fills an empty saved location
  from the strategy's own scene, so that filled text alone is not drift;
  the saved value is what the comparison answers to, exactly as the
  server's diff sees it.

## Consequences

- A current strategy's Review step shows one primary action — Generate —
  and nothing competing with it, from either direction of Kasra's rule.
- A founder who edits the direction after a build now meets the same
  blocked-until-rebuild honesty the plan and angle edits already had,
  instead of rendering a strategy built for a scene they replaced.
- The ADR 0133 suggestion checks in the render smoke now run on a
  fixture whose direction genuinely moved after the build: the rebuild
  button they click exists because the rebuild is owed, which was the
  premise those checks always assumed.
