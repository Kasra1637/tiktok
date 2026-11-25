# ADR 0319: One-word rail labels on phones

Status: accepted

## Context

The founder's phone screenshot (Nov 24 2026) showed the
Create Video wizard rail with its step labels truncated to
stubs — "Ap…", "Au…", "Rev…", "De…". ADR 0285 had shed
the per-segment percentage and the state line on phones,
but the full step names ("App Profile", "Audience &
template", "Review & submit", "Demo + CTA") still shared
a phone's width four ways beside their badges, and the
label span truncates by design. Offered badges-only,
active-step-only, and one-word labels, the founder chose
one-word labels.

## Decision

Below the sm breakpoint each rail segment stacks — badge
over label, centered — and the label is a single word:
Profile, Audience, Review, Demo (each step now carries a
shortLabel beside its label). At sm and up nothing
changes: badge beside the full name, state line and
percentage in place. The aria-label keeps the full name
and state at every width, so assistive tech and the
smoke suite's step navigation are untouched.

## Consequences

The rail shows its content on a phone for the first time:
four whole words, tappable, with the progress line under
them. A future step name must bring a one-word short
form with it, or the phone fit check fails.
