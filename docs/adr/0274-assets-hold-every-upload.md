# ADR 0274: Assets hold every upload, grouped by photo and video

Status: accepted

## Context

Kasra directed on Nov 21 2026 that the Asset Library show everything a
user ever uploads through the app — not just presenter photos, but all
uploaded videos and images, including Demo + CTA uploads. That approval
was given on a wrong cost premise (that the files were already stored);
the premise was corrected the next day: Demo + CTA media — the base
clip, the second clip, and image sequences — live only as blobs in the
browser's IndexedDB and are never uploaded, so listing them requires
storing each file on the server once. Put to Kasra plainly on Nov 22
2026, he decided: yes, store them once, everything goes up in the
library — "called assets" — listed grouped by photo and by video so
users can find things easily, and searchable by name. In the same call
he renamed the library's visible name to "Assets": the name he picked
for the stored files and the place they live.

## Decision

**The library accepts three kinds.** `ASSET_KINDS` in
`backend/template_library.py` revives two retired kinds in the product's
own vocabulary — `screen_recording` for video clips and `screenshot`
for images — alongside `character_reference`. No schema migration: the
kind column is plain text and kinds were always validated in Python.
Upload validation is per kind's media family (`ASSET_MEDIA_TYPES` /
`ASSET_ALLOWED_EXT` in `backend/routers/assets.py`, the former
`ASSET_IMAGE_TYPES`): images take the existing still set, clips take
`.mp4` / `.mov` / `.webm` — the app's own video set, the same three the
Demo + CTA export accepts — and a mismatched extension is refused with
the allowed list named. The stored file goes through the exact path
presenter photos use: the assets table, the per-profile folder, and the
best-effort R2 mirror, one copy. Two presenter-photo behaviors stay
fenced to `character_reference`: the pre-flight face count runs only
for it (a clip or a screenshot carries no count and no face warning),
and attach-to-project still refuses every other kind. A clip's duration
is measured at upload with the same probe the export path uses, never
taken from the caller. The `update_asset` kind guard widens with the
vocabulary (a normalized kind may be written; a retired one still
refuses), and the facets endpoint now reports all three kinds.

**Adding media in Demo + CTA files one library copy, as a side effect.**
When a founder adds a base clip through the file input, a second clip,
or an image to an image sequence, the editor also uploads that file
once as an asset of the matching kind, named with the file's own name
so library search finds it (`frontend/src/demoCta/libraryUpload.js`,
wired into `handleFile` / `handleAppendFile` / `handleAppendImages` in
`DemoCtaEditor.jsx`). The upload is fire-and-forget: editing, preview,
draft save/restore, and export keep working from the local blob exactly
as before, and a failed library upload resolves quietly to null — no
founder-facing error, no retry — because the working copy is the draft
and the library copy is a filing copy. Dedup is per draft entry: entry
ids already filed are held in a ref set and marked before the request
goes out, so re-renders, undo/redo, and draft restore never file an
entry twice, while replacing a clip mints a new entry and files the
replacement (the replaced file's asset stays in the library;
archive/delete there is the founder's tool). No draft field is added —
the draft still stores blobs locally and the draft parity check is
untouched. Two deliberate exclusions: attaching a finished render from
History as the base does not file a copy (the render is already stored
server-side as a generation; filing it would hold the same bytes
twice, against the store-once decision), and an editor session with no
app profile — a blank standalone session — files nothing, because
assets belong to one app and there is none to file under.

**The library page lists everything, grouped.** The standalone list
renders under group headings — Photos (character references and
images), Videos (screen recordings and clips), and Audio only when a
retired audio row survives — using the page's GroupLabel convention.
The existing search stays one search over the whole fetched list,
crossing the groups, with its match count and its honest empty state.
New-kind rows render their media with a plain-words kind label
("Video clip" / "Image") and archive/delete like every other row; the
attach action is offered only on character references, in the row's
conditions rather than by the retired-kind flag. The embedded
Presenter Photo picker keeps its character-photo behavior unchanged
and excludes video assets entirely — not even behind its "other
photos" fold — because it is a photo picker.

**The visible name is "Assets".** The sidebar link, the library page's
two headers, and the tour's label now say "Assets". The route
(`/assets`), the link's testid, and every other route and selector are
unchanged — Kasra named the link, not the URL.

Checks move in the same commit: the overlay API's retired-kind upload
test now refuses only the kinds that stayed retired (logo, audio,
nonsense) and gains acceptance/mismatch/list coverage for the revived
kinds; the facets pin and the architecture re-export pin follow the
vocabulary and the renamed constant; the topic-header pin follows the
page title; a sidebar pin guards the Assets label with its route and
testid; and new smoke checks pin the grouping, the search across
groups with its empty state, the picker's photos-only list, exactly
one library upload per added entry, and the editor completing
unchanged when that upload fails. New jest coverage pins the upload
helper's once-per-entry, naming, and quiet-failure contract.

## Consequences

Everything a founder adds is findable in one place, under the name
Kasra chose, at the cost he approved: one server copy of each Demo +
CTA file, stored when it is added. The presenter-photo pipeline is
untouched in behavior — the face still anchors every video, and clips
and images in the library are records, never inputs: nothing attaches
them, composites them, or feeds them to a model. A founder who adds a
clip while the library is unreachable loses nothing in the editor;
the clip simply is not in Assets, and re-adding it files it then.
