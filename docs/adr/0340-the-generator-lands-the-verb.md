# ADR 0340: The generator lands the verb

## Status

Accepted, Nov 25 2026 — Kasra's dictated generation
instruction, in the class of the ADR 0316/0321 exceptions to
his stop-tuning-for-quality settlement.

## Context

Rating his own hook drafts, Kasra kept losing points to the
same defect: a sentence that stops before its verb lands.
"I'm trying to sound like me after dinner, why don't my
words?" has no verb in its question; "I'm trying to keep my
own words after lunch before they slip" leaves its last verb
hanging without its second half. The spoken-line rules
already demanded finished sentences (ADR 0249), but the
failure shape — the dropped verb itself — was not named, and
he directed the fix at the generator: the app should generate
hooks that already meet the standard the hook score rewards,
not hand the founder a fragment to repair. Not by inflating
the score — by finishing the sentence.

## Decision

The shared spoken-line block's FINISHED SENTENCES rule now
carries a LAND THE VERB passage: the generator finishes the
sentence itself before the hook is shown — a question carries
its verb, never drops it ("why don't my words come out
right?", never "why don't my words?"), and a verb that needs
its second half takes it ("before they slip away", never
"before they slip" left hanging). A hook that arrives as a
fragment is a failed draft, however strong its opening words
are.

Because the passage lives in the shared block, every spoken
line prompt carries it — the plan, the strategy, and the
HookSnap hook line alike.

## Consequences

A backend test pins the passage in the shared block. The
passage grows the strategy prompt, whose fully populated form
now measures 48,978 characters; following the measured-raise
practice of ADR 0084/0090, its ceiling moves from 48,600 to
49,500 (~520 of headroom kept), recorded in the budget test.
The deterministic trims question (Cause C) is untouched: this
is a generation instruction, not a post-generation repair.
