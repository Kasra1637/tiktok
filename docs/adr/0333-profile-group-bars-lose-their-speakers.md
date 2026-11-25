# ADR 0333: The Profile editor's group bars lose their speakers

## Status

Accepted, Nov 25 2026 — Kasra's ruling, from his screenshot of
the Profile editor.

## Context

Every section bar on the Profile editor (BrandSetup) — Basics,
What the app does, Video direction, Audience — carried a
speaker at its right edge that read the whole section aloud.
Kasra pointed at the four bars in his screenshot and ordered
exactly those speakers removed, and no others.

## Decision

The four SectionGroup bars on BrandSetup no longer receive a
listen config, so no speaker renders on them and the bars stand
with their chevron only; the block builders that fed those four
speakers are removed with them. Every other speaker stays: the
field-level listen controls throughout the editor, and the App
Profile detail page's section and card speakers, are untouched.

## Consequences

The group bars read as plain section headers. A founder who
wants a section read aloud still has the field speakers inside
it.
