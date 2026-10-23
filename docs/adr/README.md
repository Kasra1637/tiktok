# Architecture Decision Records

One file per significant decision: **context → decision → consequences**, plus
the alternatives we rejected and why. Git records *what* changed; these record
*why*, in one browsable list.

## Rules

- Numbered `NNNN-<slug>.md`, sequential, never renumbered.
- A new decision that overturns an old one gets a new file; the old file stays,
  with `Status` flipped to `superseded by NNNN`. History is append-only.
- A commit that picks between real alternatives adds or supersedes an ADR in
  the same commit.
- Each record cites a verifiable anchor (commit hash or `file:line`). If the
  anchor doesn't resolve, the record is stale — fix or supersede it.

## Index

| # | Decision | Status |
|---|----------|--------|
| [0001](0001-grok-submit-failures-are-loud.md) | Provider 400s fail loudly with the provider's quoted words; no silent fallback | accepted (Grok eligibility superseded by 0006) |
| [0002](0002-h3max-identity-via-first-frame.md) | H3 Max identity rides as the opening frame, not `input_references` | accepted |
| [0003](0003-temperature-from-endpoint-declaration.md) | Temperature support is read from the endpoint declaration, not a model list | accepted |
| [0004](0004-single-pass-generation-only.md) | Generation is single-pass only; durations clamp, never chain | accepted |
| [0005](0005-per-provider-prompt-ceilings.md) | Each provider gets its own prompt ceiling; the spoken script is sacred on tight ones | accepted |
| [0006](0006-retire-grok-video-model.md) | Retire Grok Imagine Video 1.5 Lite (`input_references` unsupported) | accepted |
| [0007](0007-overlay-font-motion-options.md) | Caption/CTA overlays get selectable fonts, animations, and size | accepted |
| [0008](0008-hook-boundary-lean-in.md) | The hook-boundary transition is a face-anchored lean-in on a committed beat | accepted |
| [0009](0009-history-tiles-expand-on-demand.md) | History tiles open on demand: the clip first, the record behind a tab | accepted |
| [0010](0010-no-warm-button-fills.md) | No warm fills on buttons: coral and red move out of the surface | partially superseded by 0011 (Demo + CTA wears accent) |
| [0011](0011-history-onward-wears-accent.md) | History's onward Demo + CTA wears accent, not brand | accepted |
| [0012](0012-timestamped-tiktok-export.md) | Timestamped, frame-by-frame encoding delivers one TikTok MP4 without real-time capture drift | accepted |
| [0013](0013-eye-catching-motion-expansion.md) | Ten new background motions + ten shared overlay entrances; Output group removed | accepted |
