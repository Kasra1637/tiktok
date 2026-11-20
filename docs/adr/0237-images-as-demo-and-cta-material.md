# 0237 — Images as demo and CTA material: the second slot's other media kind

Status: accepted (Kasra's feature, approved Nov 20 2026 — "Yes, do it")

## Context

The Demo + CTA step styles the base render and lets the founder add
material after it: a second clip, styled per segment (ADR 0164), joined
by a transition (transitions.js), with the end card closing over the
added segment's tail. Everything addable was footage. Kasra's ruling:
in addition to video, the founder can add still images — their app
screens — as demo/CTA material, several in sequence, with a nice
animation between each image so the sequence appears as one consistent
flow throughout. Flash's guard, stated on the call and accepted: each
image gets a gentle push-in rather than sitting frozen, so the sequence
does not feel dead next to motion footage.

## Decision

1. **Images are a media kind of the second slot, not a third segment.**
   The slot already owns the demo's place in the joined timeline — it
   is where the demo recording goes (the plan's record brief names its
   job) and where the end card paints — so a sequence there serves the
   demo area and, under the card, the CTA area with no new timeline
   machinery. One slot holds one kind: attaching a sequence replaces an
   attached clip and vice versa, the way Replace second clip already
   swaps one clip for another. The video options are untouched and
   remain the default road.

2. **The draft stores entries; everything else is derived.** A sequence
   is `appendImages` in the demo-cta draft — `{ id, blob, name,
   seconds }` per still, in the founder's order — snapshotted and
   restored through the edit session exactly like `appendMedia`, bytes
   riding the same IndexedDB draft (draft parity covers the field).
   Decoded elements, object URLs and the player below are rebuilt from
   the entries and never stored. Per-image holds run 1–10s, default
   2.5s; the slot's existing trim window (`clipWindow` over the summed
   holds) bounds the sequence like a clip's, and the summary line,
   transition picker, crop block and end-card window all read the
   sequence through `appendMeta` — `{ w, h, d }` of the first still and
   the total — exactly as they read a loaded clip.

3. **Composition is a pure function of sequence time.**
   `demoCta/imageSequence.js` resolves the frame at any source time:
   the current still cover-fit with an ease-out push-in across its hold
   (8% total), and a crossfade over the last 0.4s of each hold into the
   next still. Preview and export call the same compositor, so the
   exported sequence is the previewed one — ADR 0007's contract. The
   composed canvas takes the first still's size (one sequence, one
   aspect; later stills cover-fit into it), and the slot's own fit,
   zoom and offsets then apply to the composed frame in the painter,
   per segment, as they do to a clip's decoded frames (ADR 0164).
   Reduced motion parks the motion: no push-in, cuts instead of
   crossfades — the transitions' own rule (transitions.js).

4. **A virtual player stands in the append element's place.**
   The preview transport is built around two media elements.
   `demoCta/imagePlayer.js` exposes the slice of that interface the
   transport reads — currentTime, duration, paused, ended, play,
   pause, and play/pause/timeupdate/seeked/ended events — on an rAF
   clock, and hands the painter the compositor's canvas for its own
   time. Seeks, trims, scoped replays, the base-to-added handoff and
   the joint transition therefore treat the sequence as a clip with no
   second transport shape; the one branch in the preview loop is the
   frame hand-off itself. The player is silent, so the slot's audio
   mute is offered for clips only, and the joined audio is the base's
   alone.

5. **The export synthesizes the segment instead of decoding it.**
   `exportTikTok` gains an `appendImages` input: when the added slot
   holds a sequence (and no clip — a real clip wins if both are passed;
   the editor never sends both), the segment is built from the summed
   holds under the same `clipWindow` trims, and its frames are composed
   at 30 fps through the shared compositor and handed to the painter
   like decoded frames. It contributes no audio segment; the base's
   join, de-click and passthrough are untouched, and clip-only exports
   behave byte-identically (pinned). `exportFlow` decodes each still
   (ImageBitmap, element fallback) and refuses by name when one cannot
   be read — a sequence baked from a missing still would put a blank
   stretch in the file. The probe-before-download ordering stands; its
   smoke pin's exact call string widens to the new condition
   (`appendBlob || appendImageSet`), recorded here as a pin update.

6. **The control surface is a list, in the Second clip group.** "Add
   images" sits beside "Add second clip"; the list names each still in
   order with move-earlier/move-later, a per-still "Show for" hold and
   a remove, plus "Add more images". Removing the last still removes
   the sequence. A still that cannot be decoded names itself in an
   error and leaves the slot not-ready (Export disabled) rather than
   exporting around it. The record brief hides once a sequence is
   attached, as it does for a clip: the demo exists.
