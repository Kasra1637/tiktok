# ADR 0185: An unattached presenter photo stands in the section

Status: accepted

Refines the embedded Asset Library's "one face plus a
footnote" arrangement. On 2026-11-17 the founder opened
the Presenter photo section of a draft and found it
blank: the label field, the Upload button, the rights
line, and a single line reading "1 other photo" — no
image anywhere, although he had already uploaded his
presenter photo. His order: if the user has already
uploaded a presenter image, this section must display it.

## Cause, proven from the code

In `frontend/src/pages/AssetLibrary.jsx` (embedded mode)
the section shows a photograph in exactly two states:

- `attachedAsset` — the library row whose id is in the
  draft's attachment list with kind `character_reference`
  — renders as a row with its thumbnail.
- `attachedReference` — the draft's own attachment record,
  when the library cannot describe the file — renders as
  a text card (name, "Used for the whole video", Remove).

Everything else in the library falls into `otherAssets`,
which renders collapsed behind the "N other photo(s)"
count button until it is clicked. The founder's photo
was in the profile's library but had never been attached
to this draft — uploaded on the library page, or for an
earlier draft — so it sat in `otherAssets`: the section
knew the photo existed (the count said so) and showed
nothing. The collapse was designed for the case a
presenter is already in place, where the remaining
photographs genuinely are a footnote; with no presenter
attached, it hid the one thing the section exists for.

## Decision

- **A character photo with no presenter in place is a
  candidate, not a footnote.** When the draft holds no
  photo at all (no `attachedAsset`, no
  `attachedReference`), unattached `character_reference`
  assets render as full rows in the section — thumbnail,
  label, and their "Use this photo" control — in the same
  surface where the attached photo stands.
- **Once a presenter is in place, nothing changes.** The
  attached row (or the draft-reported reference card)
  stays the section's subject, and every other asset —
  character photos included — returns to the collapsed
  count, exactly as before. Non-character assets are
  never promoted.
- **Display only.** Upload behavior, the label field,
  the rights line, attach/detach, and every word of copy
  are untouched; the promoted rows are the library's own
  `AssetRow` with the same props the collapsed list uses,
  and their image source is the asset's own `media_url`,
  the same source the app already renders for that photo
  everywhere else.

## Pins

A new smoke check mounts the wizard on a draft with no
attached photo while the library holds one
`character_reference` asset with a `media_url`, and
asserts an `img` carrying that source stands inside the
Presenter photo section without the count being clicked.
It failed before the fix (the photo rendered nowhere)
and passes after. The neighbouring pins — the
draft-reported reference card ("Used for the whole
video") and the standalone library checks — are
unchanged and still pass.
