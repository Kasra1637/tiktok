# ADR 0318: Every label starts with a capital

Status: accepted

## Context

The founder, reading the wizard rail's status words —
"done", "not started" — asked why the first letter was
lowercase, and ruled (Nov 24 2026): every label, and every
sentence, throughout the app starts with a capital letter.
The lowercase words were not a style setting; they were
written lowercase in the code, in the rail's state copy.

## Decision

Standalone UI copy — status words, chips, labels and the
sentences the app states — starts with a capital letter,
app-wide. The wizard rail's state copy is corrected where
it lives: the step states ("Done", "Not started", "Needs
something from you", "Locked"), the locked lines on the
segments, section headers and chips ("Locked — finish … to
unlock"), and the "Optional" marker. A sweep of the app's
pages and studio components found the rest of the visible
copy already sentence-cased; mid-sentence line wraps are
not sentence starts and are untouched, and neither is
anything a user or the model wrote. Where a test pinned
the old lowercase wording, the pin follows the new copy.

## Consequences

The app speaks in sentences everywhere a founder reads a
label, and the rail — where the ruling started — no longer
whispers its states in lowercase.
