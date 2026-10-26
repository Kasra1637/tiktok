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
| [0009](0009-history-tiles-expand-on-demand.md) | History tiles open on demand: the clip first, the record behind a tab | partially superseded by 0033 (tile identity & results) and 0035 (full-width band) |
| [0010](0010-no-warm-button-fills.md) | No warm fills on buttons: coral and red move out of the surface | partially superseded by 0011 (Demo + CTA wears accent) |
| [0011](0011-history-onward-wears-accent.md) | History's onward Demo + CTA wears accent, not brand | accepted |
| [0012](0012-timestamped-tiktok-export.md) | Timestamped, frame-by-frame encoding delivers one TikTok MP4 without real-time capture drift | accepted |
| [0013](0013-eye-catching-motion-expansion.md) | Ten new background motions + ten shared overlay entrances; Output group removed | partially superseded by 0014 (picker retires underline, spotlight) and 0018 (picker retires six background motions) |
| [0014](0014-retire-underline-spotlight-entrances.md) | Retire underline + spotlight from the entrance picker; motion kept for old renders | accepted |
| [0015](0015-preview-transport-owns-playhead.md) | Preview transport owns the playhead (no replay on option change); Sora leaves the font catalog | partially superseded by 0017 (scoped overlay replay) |
| [0016](0016-editable-zoom-lock-preview.md) | Paused zoom drafts remain editable; saved hand/phone locks drive preview and export | accepted |
| [0017](0017-scoped-overlay-review.md) | Replay overlay windows; save reusable looks after final CTA review | accepted |
| [0018](0018-retire-six-background-motions.md) | Retire six background motions from the picker; bloom becomes the default | accepted |
| [0019](0019-one-caption-post-kit.md) | One TikTok caption per post kit, regenerable on demand | partially superseded by 0020 (export-card regenerate, question guard, completed-only) |
| [0020](0020-post-kit-regenerate-everywhere.md) | Regenerate reaches the export card; caption must ask; completed-only | accepted |
| [0021](0021-post-kit-ownership.md) | Post-kit state has one owner per layer | partially superseded by 0034 (frontend snapshot synchronization) |
| [0022](0022-looks-live-together-in-end-card-cta.md) | Saved looks live with saving in End Card CTA | accepted |
| [0023](0023-shared-caption-text-styles.md) | One shared text treatment across hook, story and end card | partially superseded by 0024 (text-style catalog trimmed to three) |
| [0024](0024-retire-three-text-styles.md) | Retire outline, clean and sticker from the text-style picker | accepted |
| [0025](0025-real-video-phone-composite.md) | Real Video combines a base clip and looped phone upload through one timestamped painter | superseded by 0027 (appended sequence) |
| [0027](0027-real-video-appended-sequence.md) | Real Video appends the second clip after the base with both soundtracks | accepted |
| [0028](0028-per-clip-presentation.md) | Each sequence clip picks its own floating/hand/real presentation | accepted |
| [0029](0029-second-clip-group-and-look.md) | Second clip gets its own gated group and its own background/motion/scene | accepted |
| [0026](0026-fresh-opening-message-batches.md) | Opening text consumes twenty app-grounded suggestions instead of saved preset indices | accepted |
| [0030](0030-per-clip-audio-mutes.md) | Each sequence clip mutes its own audio in preview and export | accepted |
| [0031](0031-first-run-checklist.md) | First-run checklist carries the founder across pages with their tours | accepted |
| [0032](0032-history-tiktok-link-and-winner.md) | A TikTok link marks a render posted; thumbs up plus link is the winner | accepted |
| [0033](0033-clip-results-comparison.md) | Compare saved clip reach and votes; keep History summaries synchronized | accepted |
| [0034](0034-history-snapshot-synchronization.md) | History owns confirmed snapshots; URL filters and current requests prevent stale handoffs | accepted |
| [0035](0035-history-detail-band.md) | Open History detail is a full-width band; one band at a time | partially superseded by 0036 (band spans a pair row) |
| [0036](0036-history-pair-rows.md) | History pairs two videos per row; band spans beneath its pair | partially superseded by 0037 (band lands after the open pair) |
| [0037](0037-history-pair-aware-band.md) | History band lands after the open pair via a list-owned portal slot | accepted |
