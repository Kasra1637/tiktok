# 0030 — Each sequence clip mutes its own audio

Status: accepted

## Context

After 0029 each clip owned its look but both soundtracks were always kept:
a base with unwanted noise or an upload with unusable audio forced the
founder to re-cut outside the app. The preview monitor mute silences the
browser only and never touches the file, so it could not answer this.

## Decision

- The base owns `baseMuted` (Source & Look) and the added clip owns
  `appendMuted` (Second clip), both defaulting off. Toggling either
  invalidates a finished export, exactly like a look change.
- Preview layers the per-clip flag under the monitor mute: a muted segment
  stays silent even after the founder unmutes preview.
- Export keeps the muted segment's full video length and writes silence for
  it: joined AAC skips the muted segment's samples, `audioSegments` excludes
  it, and a fully muted export is video-only. No retiming, no gap.

Anchors: `frontend/src/demoCta/DemoCtaEditor.jsx` (`base-audio-mute` /
`append-audio-mute`), `frontend/src/demoCta/usePreviewLoop.js` (effective
muting), `frontend/src/demoCta/exportTikTok.js` (muted segments skipped),
`frontend/src/demoCta/exportFlow.js` (flags forwarded).

## Alternatives rejected

- Reusing the monitor mute as the export mute: it exists for autoplay
  policy, defaults on, and would silently ship silent files.
- Cutting the muted segment from the timeline: the request is silence, not
  a shorter video — total length (10s plus 8s gives 18s) must not move.
- One shared mute for both clips: the whole point is independent control,
  e.g. a clean upload carrying a noisy base.

## Consequences

Two clips mean two audio flags alongside the two look states. Unit tests
pin muted-base (video length kept, no audio track) and muted-append (joined
length kept, base audio only); the smoke suite pins both toggles defaulting
off and taking a click.
