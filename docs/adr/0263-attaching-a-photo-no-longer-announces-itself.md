# 0263 — Attaching a photo no longer announces itself

Status: accepted

## Context

The Asset Library stands on its own page and embedded inside the
Presenter Photo card (`PresenterPhotoControl` renders it in the
wizard and on Hook + CTA). A successful attach in
`AssetLibrary.jsx`'s `handleAttach` set a notice —

    Now using "avata.jpg" for this video.

— in the shared notice line above the list, so the sentence
showed inside the Presenter Photo card on the creation pages as
well as on the library page itself.

On Nov 22 2026 Kasra showed that line in the Presenter Photo
card and ordered it removed: "remove this."

## Decision

1. **Attaching sets no notice.** The `setNotice` call in
   `handleAttach` is removed, and only that call. The attach
   itself, the busy state, the error path, the list reload and
   the `onProjectChanged` / `onChanged` callbacks are unchanged.

2. **The row is the confirmation.** The attached photo already
   reads as Attached on its own row, in the same card, at the
   moment the attach lands — the notice repeated what the screen
   already said, in a second place.

3. **The notice line stays for its other messages.** Upload
   ("Added ..."), the face warning, and the archive result note
   still use the same notice element, which renders only when a
   message exists — no empty box is left behind. Detach keeps
   its own distinct confirmation ("Removed ... from this
   video."); Kasra's order named the "Now using" line, so the
   detach line stands.

## Checks

A render-smoke check pins the new contract on the Hook + CTA
page, where the line showed in the screenshot: after clicking
"Use this photo", the photo reads as Attached and no "Now
using" text stands anywhere on the page. It failed on the old
code with exactly that announcement present.
