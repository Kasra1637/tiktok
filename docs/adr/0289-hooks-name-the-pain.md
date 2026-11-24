# ADR 0289: Hooks name the pain

Status: accepted

## Context

Kasra rated the Hook + CTA hook "I'm trying to notice feelings
tonight and keep guessing." a 6/10 (Nov 23 2026): the goal leads
and "tonight" grounds it, but "notice feelings" is abstract and the
line ends on a shrug. His ruling for the generation behind it:
hooks must be outcome-driven and problem/pain-driven — speak to
the potential user's internal pain that the app can solve, not
vague activity talk. His example: talking about journaling is
vague; nobody cares about writing a journal — they care about the
blank feeling, the tight chest, the thoughts they keep losing.
And the hook's last words should lead naturally into the Demo +
CTA that follows, which showcases the app resolving that pain.
He then ordered the Create Video plan's hook generation aligned
to the same doctrine, so both hook surfaces generate the same way.

The prompts were not there. The shared spoken-line rules carried
NAME THE ACTION — "say the real task in the viewer's own words",
with a journaling line as its exemplar — and OPEN WITH THE GOAL
defined the attempt without the pain it answers ("I'm trying to
notice feelings" passes both). The Hook + CTA prompt's own rules
opened with the goal the same way.

## Decision

One doctrine, both surfaces, stated in the prompts:

- NAME THE ACTION is superseded by NAME THE PAIN, NOT THE
  ACTIVITY: the hook speaks to the internal pain the app resolves,
  in the viewer's own words — Kasra's sentence rides in the rule
  ("talking about journaling is vague, and nobody cares about
  writing a journal") — with no vague stand-in and no abstract
  label ('notice feelings') where the pain belongs. The activity
  belongs to the script's moment.
- OPEN WITH THE GOAL, NOT THE PLACE keeps its title and its
  place ban; the goal is now defined as the pain's relief — the
  felt pain named concretely and her attempt on it, as a
  first-person trying-line ("I'm trying to find a word for this
  tight feeling").
- WITHHOLD THE RESOLUTION gains the handoff: the line's last
  words leave the pain pointing forward, so the demo that follows
  lands as the answer to this exact ache.
- generate_hook_line's opening rule states the same doctrine for
  the standalone hook (its pinned "- hook_line opens with the
  GOAL:" prefix stands), and the rewrite surface inherits it
  through the shared rules block, so Suggest a clearer hook
  sharpens toward the pain too.

The wording was compressed to hold ADR 0201's strategy-prompt
ceiling: the fully-populated prompt measures under 48,600 again,
with the doctrine's pinned sentences intact. Everything else in
the rules — budgets, finished sentences, the place ban, the cost
riding along — is untouched.

## Consequences

Generated hooks on both surfaces now lead with the felt pain and
end toward the demo, in the shape Kasra approved on the call.
Settled ratings and examples elsewhere in the doctrine (the mural
pair, the cost cue) stand: the goal-first shape (ADR 0182) is
refined, not reversed — the goal still opens the line; it is now
defined by the pain it relieves.
