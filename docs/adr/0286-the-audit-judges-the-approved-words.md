# ADR 0286: The audit judges the approved words

Status: accepted

## Context

On Nov 23 2026 Kasra tried to render a plan whose words agree with
its Location — the hook "Finally, I'm trying to find a word for
vague sense feeling." and a script set at a bench by a window,
indoors, matching the Location "Inside a quiet room with a bench by
a window…". The render refused: "the spoken words still name
another place: Middle — spoken words is set outdoors."

The approved words were innocent — checked directly, they classify
as indoors and raise no conflict. The guilty text was the strategy's
middle segment, which still carried an older script written for an
outdoor angle before the camera switch and plan regeneration. The
render guard (`_guard_render_scene`, ADR 0092's second net) audits
the strategy's segment scripts, and those are a derived copy of the
plan's words: `bind_spoken_words` exists to keep them equal, but the
submit path only bound them when that same request's repair step
had rewritten the words. Words changed in an earlier request — a
regenerated plan, a Review edit — left the strategy's copies stale,
and the audit judged the copies.

## Decision

The guard binds before it audits. `_guard_render_scene` now runs
`bind_spoken_words` with the project's approved words as its first
step, so the strategy's spoken copies equal the plan's words at the
moment they are judged, and `_submit_generation` passes it
`render_plan` — the repaired words this render will speak — instead
of the raw project row. The submit path's old conditional bind is
removed; the guard is the single bind point before the audit.

Nothing about the audit itself changes: spoken words are still
never rewritten, direction lines are still patched, and approved
words that themselves name another place still refuse the render
with the section named and nothing charged. With no approved plan
on the project the bind is a no-op and the strategy keeps its own
words, the legacy path `bind_spoken_words` documents.

Two regression tests pin both directions with Kasra's exact case:
a stale outdoor middle under a consistent indoor plan renders, its
segments rebound to the plan's words; and a plan whose own script
names the park still refuses, naming the Middle.

## Consequences

A render can no longer be refused for words the founder never
approved, and the refusal that remains always names words that are
actually on the plan. The strategy the prompt is built from speaks
the approved words in its segments, as its design always intended.

One behavior settles with it: where the strategy's spoken copies
and the plan's words differ, the prompt now always speaks the
plan's words — the copies are derived (bind_spoken_words' own
contract), never a second source. The generation suite's
fits-as-written test pinned the strategy's line from a fixture
whose two sources deliberately differ; its assertion now pins the
plan's line, with the repair-not-rewriting assertion untouched.
The bind also runs before the guard's Location early return: a
project with no Location still renders from its strategy, and its
segments carry the repaired words the same way.

The full backend run then found four more tests pinned to the old
source: the timeline-coverage and prompt-detail tests asserted the
strategy's hook line from the same divergent fixture, the HeyGen
ceiling test asserted the strategy's combined hook copy, and the
two-sections workflow test held its middle words only in the
strategy while its plan carried a placeholder. Each now pins the
approved plan words as the prompt's source — the workflow fixture
carries its payoff as the plan's script, as production does — with
every protective assertion (the ceiling fit, the trimmed direction,
the distinct sections) unchanged.
