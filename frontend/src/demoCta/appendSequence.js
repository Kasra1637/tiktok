import {
  IMAGE_SECONDS,
  DEFAULT_IMAGE_MOTION,
  clampImageSeconds,
  composeImageFrame,
} from "./imageSequence";

/**
 * The second slot's media model: one ordered sequence of entries.
 *
 * The slot used to hold either one clip (`appendMedia`) or a list of
 * stills (`appendImages`) — one slot, one kind. It now holds a single
 * ordered list that mixes both kinds: several clips and images together
 * form one sequence, and the order the founder leaves the entries in is
 * the order the preview plays and the export encodes. An entry is
 *
 *   { id, kind: "video" | "image", blob, name, assetId?,
 *     seconds?, motion? }
 *
 * `seconds`/`motion` belong to images (the still's hold and its picked
 * motion, ADR 0237/0354); a video entry plays its own decoded length.
 * `assetId` names the Assets library row the entry was picked from, when
 * it was picked there — it is what lets the library pop-up show the
 * entry as selected and take it back out. A device upload carries none
 * until its library filing returns one (see the editor's stamping).
 *
 * Per-sequence settings (style, backdrop, crop, framing, overlays, mute,
 * the trim window) stay per-sequence exactly as they were per-clip: a
 * one-entry sequence behaves exactly as the single second clip always
 * did, and a one-video sequence still plays through the real media
 * element rather than this module's compositor.
 */

export function makeAppendEntryId() {
  return `${Date.now()}-${Math.random().toString(36).slice(2, 8)}`;
}

export function makeVideoEntry(blob, name, assetId = null) {
  return {
    id: makeAppendEntryId(),
    kind: "video",
    blob,
    name: name || "Added clip",
    ...(assetId ? { assetId } : {}),
  };
}

export function makeImageEntry(blob, name, assetId = null) {
  return {
    id: makeAppendEntryId(),
    kind: "image",
    blob,
    name: name || "Image",
    // A fresh still sits still (ADR 0354): motion is a pick, never an
    // automatic zoom.
    seconds: IMAGE_SECONDS.default,
    motion: DEFAULT_IMAGE_MOTION,
    ...(assetId ? { assetId } : {}),
  };
}

/**
 * The stored draft's append entries, whatever shape the draft was saved
 * in. Drafts saved before the sequence existed carry a lone clip entry
 * and/or a still list with no `kind` on the entries; they migrate to a
 * one-kind sequence here, at the one funnel every restore passes
 * through, so an old draft opens whole instead of losing its second
 * clip. A draft that already carries `appendItems` passes untouched.
 */
export function migrateAppendItems(edit) {
  if (!edit || typeof edit !== "object") return [];
  if (Array.isArray(edit.appendItems)) return edit.appendItems;
  const items = [];
  if (edit.appendMedia && typeof edit.appendMedia === "object") {
    items.push({ ...edit.appendMedia, kind: "video" });
  }
  if (Array.isArray(edit.appendImages)) {
    for (const entry of edit.appendImages) {
      if (entry && typeof entry === "object") items.push({ ...entry, kind: "image" });
    }
  }
  return items;
}

/** A stored edit with its append media normalized to the sequence. */
export function migrateAppendEdit(edit) {
  if (!edit || typeof edit !== "object") return edit;
  if (Array.isArray(edit.appendItems)) return edit;
  return { ...edit, appendItems: migrateAppendItems(edit) };
}

/**
 * Which playback path a sequence takes. "single" (one video) keeps the
 * real media element — its preview audio, its own probe, its trim
 * enforcement — exactly as the lone second clip always played.
 * "images" (stills only) keeps the ADR 0237 image-sequence player.
 * Anything else with a video in it is "mixed" and plays through the
 * sequence player (sequencePlayer.js) over the composed frames.
 */
export function appendShapeOf(items) {
  if (!Array.isArray(items) || items.length === 0) return "empty";
  if (items.length === 1 && items[0]?.kind === "video") return "single";
  if (items.every((item) => item?.kind === "image")) return "images";
  return "mixed";
}

/**
 * One entry's run length in the sequence. An image runs its hold; a
 * video runs its decoded length, which only the probe knows — the
 * caller passes the probed map (entry id → { w, h, d }) it keeps. An
 * unprobed video contributes nothing yet: the sequence is not ready
 * while any of its videos is unmeasured.
 */
export function appendItemDuration(item, probed) {
  if (!item) return 0;
  if (item.kind === "image") return clampImageSeconds(item.seconds);
  const meta = probed?.get ? probed.get(item.id) : probed?.[item.id];
  return Number.isFinite(meta?.d) && meta.d > 0 ? meta.d : 0;
}

/** The sequence's full run: the sum of its entries, in order. */
export function appendSequenceDuration(items, probed) {
  if (!Array.isArray(items)) return 0;
  return items.reduce((sum, item) => sum + appendItemDuration(item, probed), 0);
}

/**
 * Which entry is on screen at a sequence-source time, and how far
 * through it. Times outside the run clamp to the ends, the same
 * contract imageFrameAt keeps for stills.
 */
export function appendItemAt(items, probed, sourceTime) {
  if (!Array.isArray(items) || !items.length) return null;
  const total = appendSequenceDuration(items, probed);
  const t = Math.min(Math.max(0, Number(sourceTime) || 0), total);
  let start = 0;
  for (let index = 0; index < items.length; index++) {
    const seconds = appendItemDuration(items[index], probed);
    if (t < start + seconds || index === items.length - 1) {
      return { index, item: items[index], local: Math.min(Math.max(0, t - start), seconds), start, seconds };
    }
    start += seconds;
  }
  return null;
}

function drawCoverFrame(ctx, drawable, w, h) {
  const iw = drawable?.videoWidth || drawable?.naturalWidth || drawable?.width || 0;
  const ih = drawable?.videoHeight || drawable?.naturalHeight || drawable?.height || 0;
  if (!(iw > 0 && ih > 0)) return;
  const base = Math.max(w / iw, h / ih);
  const dw = iw * base;
  const dh = ih * base;
  ctx.drawImage(drawable, (w - dw) / 2, (h - dh) / 2, dw, dh);
}

/**
 * Compose a mixed sequence's frame at a source time into `canvas` and
 * return it — or null when there is nothing drawable, so the caller can
 * skip the frame the way the painters skip an undecoded one.
 *
 * `drawables` aligns with `items`: the decoded still for an image, the
 * (probed, sync-playing) video element for a clip. The canvas takes the
 * first entry's own size — the sequence is one visual source with one
 * aspect, like the image sequence before it — and every later entry
 * cover-fits into it. A run of consecutive stills composes through
 * composeImageFrame whole, so still-to-still crossfades and per-still
 * motions survive inside a mixed sequence unchanged; a clip draws its
 * element's current frame, and the joins around a clip are cuts.
 */
export function composeAppendFrame(canvas, drawables, items, probed, sourceTime, { reduceMotion = false } = {}) {
  if (!canvas || !Array.isArray(drawables) || !Array.isArray(items) || !items.length) return null;
  const first = drawables[0];
  const w = first?.videoWidth || first?.naturalWidth || first?.width || 0;
  const h = first?.videoHeight || first?.naturalHeight || first?.height || 0;
  if (!(w > 0 && h > 0)) return null;
  const at = appendItemAt(items, probed, sourceTime);
  if (!at) return null;
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, w, h);
  if (at.item?.kind === "video") {
    const drawable = drawables[at.index];
    if (drawable) drawCoverFrame(ctx, drawable, w, h);
    return canvas;
  }
  // The maximal run of consecutive stills around the active one,
  // composed as the image sequence it is.
  let runStart = at.index;
  while (runStart > 0 && items[runStart - 1]?.kind === "image") runStart -= 1;
  let runEnd = at.index;
  while (runEnd < items.length - 1 && items[runEnd + 1]?.kind === "image") runEnd += 1;
  const runItems = items.slice(runStart, runEnd + 1);
  const runDrawables = drawables.slice(runStart, runEnd + 1);
  let runOffset = 0;
  for (let i = runStart; i < at.index; i++) runOffset += appendItemDuration(items[i], probed);
  composeImageFrame(canvas, runDrawables, runItems, runOffset + at.local, { reduceMotion });
  return canvas;
}
