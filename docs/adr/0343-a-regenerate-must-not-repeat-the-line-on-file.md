# ADR 0343: A regenerate must not repeat the line on file

## Status

Accepted, Nov 25 2026 — Kasra's live report: HookSnap's
"Generate a new hook" returned the same line, and the button
read as doing nothing.

## Context

The wiring was sound end to end; the generation was not. The
hook prompt never mentioned the line already on file, so a
repeat click sent a byte-identical prompt, and at the app's
fixed temperature the model could hand the same hook back.
Nothing downstream charged a repeat: the draft loop, the
bake-off filter and the craft correction all validated the
line only against the length and finish gates.

## Decision

The line on file joins the generation two ways. In the
prompt it rides as an explicit exclusion — already on file,
write a genuinely new line, not a restatement. In the hard
gates (`_line_issues`, the one list every stage validates
against) a word-for-word repeat of the line on file is a
named issue, so the draft loop corrects it, the bake-off
cannot select it, and the craft correction cannot restore
it. When no line is on file, the prompt stays byte-for-byte
what it has always been.

## Consequences

A regenerate now ends in one of two honest states: a
genuinely new line, or the loop's standing failure message
after its bounded attempts — never a silent repeat. The
rule is HookSnap's generator's own (the only surface with
this button); Create's plan generation writes a whole
package and is untouched.
