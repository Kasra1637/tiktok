# ADR 0181: The HeyGen blurry head is cut in the save

Status: accepted

Kasra's order, Nov 16–17 2026, after watching his mural
render frame by frame: the HeyGen Video model's renders
open with a blurry dissolve lasting about 0.2 seconds —
the model's own conversion artifact — and he has been
hand-editing it out. Remove just that blurry head, not
more, at the source, so he never has to edit it again;
the preview still and the History page must show the
clean start too.

## Decision

- **Scope is one model.** The cut applies only to
  generations whose recorded model is `heygen-video-1`
  (`_MODEL_HEAD_TRIM_SECONDS` in server.py, the one place
  the per-model offset lives). Every other model's save is
  byte-for-byte the current behavior.
- **The offset is the dissolve's length: 0.2s.** Not a
  round-up, not a safety margin — the founder's terms are
  "just that blurry head, not more", and the cut must not
  shave the first syllable of the opening line. The helper
  is frame-exact (a test pins a 4s clip to 3.8s within
  0.03s), so nothing past the offset is touched.
- **It hooks into the one pipeline.** `_persist_generation_clip`
  — the function both the poll save and the storage repair
  run — cuts the head FIRST inside the fresh-download
  processing block, before the hook trim, the canvas
  rescale and the camera move, so every later step works on
  the clip the founder will actually get. The cut is in
  place at the canonical path (`pipeline.replace_with_head_trimmed`,
  beside the hook trim's pair), because the canonical path
  is what gets uploaded, previewed and bridged from.
- **Audio and picture are cut together.** The new helper
  (`pipeline.trim_head_exact`) uses an output seek with a
  re-encode — the decoder discards up to the exact offset
  in both streams in one pass — with the length trim's
  encoding parameters. A stream copy could do neither: it
  cuts video on packet boundaries and would leave the
  streams starting at different points.
- **Failure is soft, like the rescale and the camera
  move.** A failed cut is logged as a warning and the
  render is delivered as rendered. The head cut writes no
  storage_error and no trim note: it is an always-on
  per-model transformation, not a per-render deviation
  like the hook trim, and a note in that slot would raise
  the panel's "Durable copy missing" alert on every HeyGen
  completion. Error precedence is therefore untouched —
  a real problem is never masked by the cut.
- **The duration accounting tells the truth.** When the
  cut applied and no hook trim set the length,
  `delivered_seconds` is the recorded duration minus the
  cut, in the accounting's whole seconds and never more
  than the file holds (a 15s render records 14). A hook
  trim still sets the delivered length outright; the head
  cut only shifts which content fills it.
- **The poster needs no change.** Posters are generated
  after the save, from the canonical local file
  (`_apply_persist_outcome` → `_schedule_poster` →
  `posters.ensure_poster`, frame at 0.5s), so a head-cut
  video's poster comes from the trimmed file by
  construction — its first frame is clean, and the 0.5s
  frame sits past the dissolve either way.

## Consequences

Already-stored videos are NOT re-processed, and the
storage-repair path does not change that: "Retry durable
save" runs this same pipeline, but the processing block
runs only on a fresh provider download — a row with a
usable local copy skips it entirely, and a row restored
from its durable copy returns its delivered bytes
untouched by design. So a retry on the mural row (which
landed safely and offers no retry in the first place)
would re-upload the untrimmed file, not cut it. If the
founder later wants stored HeyGen videos repaired, the
shape is an explicit one-time repair that cuts the
stored copy's head once, guarded by a recorded marker so
it can never cut twice — deliberately not built here,
because the pipeline's standing rule is that delivered
bytes are never re-processed: a second cut would take
0.4s, and the canonical file is what extensions bridge
from.

The tests land with it (`backend/test_heygen_head_trim.py`):
the helper is frame-exact, in place, and leaves the
original untouched on failure; a marked clip (red frames
and silence for the first 0.2s, blue frames and a loud
tone after) persisted as heygen-video-1 comes out 0.2s
shorter with its streams in agreement, starting blue and
loud; the same clip persisted as another model comes out
untouched; and the delivered-seconds accounting records
the trimmed length.
