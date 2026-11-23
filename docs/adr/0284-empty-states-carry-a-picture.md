# ADR 0284: Empty states carry a picture

Status: accepted

## Context

A new founder opening History or Analytics before creating a clip
met a small icon in a tile and a line of text — correct, but the
pages read as blank rather than as places waiting to be filled. On
Nov 23 2026 Kasra ordered the third of three visual enhancements:
minimal, branded inline SVG mini-illustrations for the History and
Analytics empty states, matching the clean indigo line-art style of
the landing page's How it works strip.

## Decision

A new `frontend/src/components/EmptyStateArt.jsx` carries three
scenes drawn in the landing strip's exact family (its `STEP_ART`):
one `200x150` viewBox, the brand indigo stroke at one weight, round
caps and joins, layered cards at stepped opacities, one solid glyph
per scene. Each scene shows what its page will hold:

- History: a film frame with sprocket dots and a solid play mark —
  the clips that will stand here.
- Analytics ("No posted results yet"): a rising line over a baseline
  with dotted vertices — the results that will chart here.
- Analytics ("No app yet"): an app tile with text lines and a solid
  plus badge — the profile the page waits on.

`EmptyState` gains an optional `illustration` prop that stands in
the icon tile's seat when a page brings one; the tile stays the
default for every other empty state in the app. The three call sites
pass their scene and drop their icon. Titles, descriptions, actions
and tour links are word-for-word unchanged, and the art is
decorative (`aria-hidden`) — the words carry the meaning.

Render-smoke assertions pin each scene to its state: the two
Analytics mounts and a new empty-History mount each require their
illustration's testid in the rendered empty state.

## Consequences

History and Analytics now open as designed places, in the same line
family a visitor met on the landing page, instead of blank boxes.
Every other empty state keeps its icon tile until a scene is drawn
for it.
