# 0326 — HookSnap's presenter photo section stands at the bottom, faces only

Status: accepted. Kasra's order on the Nov 24 2026 call, in the same
round as ADRs 0324–0325.

## Context

Two of Kasra's rulings meet in one section. He ordered the uploads
split by job: the presenter photo area is for faces only — a Vocolens
screenshot and a screen capture were listing under it in his
screenshot, and uploads that are not faces belong to the full
collection in the Demo + CTA area instead. And he ordered HookSnap's
presenter photo section moved to the very bottom of the page, matching
where it sits in the Create flow.

The section on HookSnap was the shared PresenterPhotoControl, rendered
inside the "Place and wardrobe" card. Its embedded AssetLibrary
fetched every asset kind: the attached presenter photo was the
subject, unattached presenter photos stood as candidate rows, and
screenshots and other stills waited behind the "other photos" fold —
visible in the section, which is what Kasra ruled against. Uploads
are typed server-side (ADR 0274): every asset carries a `kind`, and
`character_reference` is the presenter photo, distinct from
`screenshot` and `screen_recording`.

## Decision

- **The section moves to the very bottom of HookSnap.** The
  PresenterPhotoControl block leaves the Place and wardrobe card and
  renders after the Post kit card, gated on the project like its
  sibling cards, keeping its own panel and label exactly as the
  Create wizard renders it — a move, not a redesign. HookSnap's final
  order: Choose an app, Place and wardrobe, The hook, Render the
  hook, Demo + CTA, Post kit, Presenter photo.
- **The embedded library is faces only.** When AssetLibrary loads
  embedded, it keeps only assets whose `kind` is
  `character_reference`. Screenshots and screen recordings never
  enter the section — not as rows, not behind the fold. The
  standalone Assets page is untouched and keeps the full collection.
  The filter lives in the shared embedded surface, so the Create
  wizard's presenter section — the same control, the same job —
  obeys the same faces-only rule; that is the uploads split working
  as ordered, not a side effect.
- **Out of scope, still queued:** the Demo + CTA area's
  import-from-library picker (the other half of the uploads split)
  is its own build and does not ride here.

## Consequences

- A profile whose uploads are all screenshots now shows the presenter
  section's empty state ("Upload one clear photo…") instead of
  listing the screenshots — the honest face of the rule.
- The embedded "other photos" fold can now only ever hold unattached
  presenter photos.
- Pins: the embedded-picker check now feeds a screenshot alongside
  the video and asserts neither appears, in the list or behind the
  fold ("the embedded presenter picker shows presenter faces only"),
  and a new HookSnap check pins the section after the Post kit and
  outside the direction card. Both went red before the change.
