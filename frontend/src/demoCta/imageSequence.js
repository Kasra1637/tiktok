/**
 * Image sequences in the Demo + CTA editor's second slot (ADR 0237).
 *
 * A sequence is a list of stills, each held for its own seconds. Everything
 * here is a pure function of sequence time — the same contract the overlay
 * entrances (ADR 0007) and the clip transitions keep — so the preview and
 * the export compose the identical frame for the identical time: each
 * still gets a gentle push-in across its own hold, and the tail of each
 * hold crossfades into the next still, so the sequence plays as one flow
 * instead of a slideshow of frozen frames. Reduced motion parks both: a
 * still is a still, and the joins are cuts.
 */

/** Per-image hold, in seconds. Screens need a read, not a flash. */
export const IMAGE_SECONDS = { min: 1, max: 10, step: 0.1, default: 2.5 };

/** Total push-in across one hold: present, never a lurch. */
export const IMAGE_PUSH_IN = 0.08;

/** Crossfade window at the tail of each hold, in seconds. */
export const IMAGE_FADE_SECONDS = 0.4;

const clamp01 = (v) => Math.min(1, Math.max(0, Number(v) || 0));

export function clampImageSeconds(value) {
  const n = Number(value);
  if (!Number.isFinite(n)) return IMAGE_SECONDS.default;
  return Math.min(IMAGE_SECONDS.max, Math.max(IMAGE_SECONDS.min, n));
}

const secondsOf = (image) => clampImageSeconds(image?.seconds);

/** The sequence's full run: the sum of its holds, in order. */
export function imageSequenceDuration(images) {
  if (!Array.isArray(images)) return 0;
  return images.reduce((sum, image) => sum + secondsOf(image), 0);
}

/**
 * Which still is on screen at a sequence-source time, and how far through
 * its hold it is. Times outside the run clamp to the ends, so a caller
 * holding the last frame a beat long still gets the last still.
 */
export function imageFrameAt(images, sourceTime) {
  if (!Array.isArray(images) || !images.length) return null;
  const total = imageSequenceDuration(images);
  const t = Math.min(Math.max(0, Number(sourceTime) || 0), total);
  let start = 0;
  for (let index = 0; index < images.length; index++) {
    const seconds = secondsOf(images[index]);
    if (t < start + seconds || index === images.length - 1) {
      const local = Math.min(Math.max(0, t - start), seconds);
      return { index, local, progress: seconds > 0 ? local / seconds : 1, start, seconds };
    }
    start += seconds;
  }
  return null;
}

/** Ease-out cubic push-in scale for a hold progress (1 = the still, unzoomed). */
export function pushInScale(progress, reduceMotion = false) {
  if (reduceMotion) return 1;
  const p = clamp01(progress);
  return 1 + IMAGE_PUSH_IN * (1 - Math.pow(1 - p, 3));
}

/**
 * The crossfade in force at a sequence-source time, or null: inside the
 * last IMAGE_FADE_SECONDS of a hold (never more than half the hold, so a
 * short hold still reads before it starts to leave), the next still fades
 * in over the current one. The last still never fades — there is nothing
 * after it. Reduced motion resolves to null: a cut, like the clip
 * transitions (see effectiveTransition in transitions.js).
 */
export function imageFadeAt(images, sourceTime, reduceMotion = false) {
  if (reduceMotion) return null;
  const frame = imageFrameAt(images, sourceTime);
  if (!frame || frame.index >= images.length - 1) return null;
  const span = Math.min(IMAGE_FADE_SECONDS, frame.seconds / 2);
  if (!(span > 0) || frame.local < frame.seconds - span) return null;
  const p = clamp01((frame.local - (frame.seconds - span)) / span);
  return { index: frame.index + 1, alpha: p * p * (3 - 2 * p) };
}

function drawCover(ctx, img, w, h, scale) {
  const iw = img?.naturalWidth || img?.width || 0;
  const ih = img?.naturalHeight || img?.height || 0;
  if (!(iw > 0 && ih > 0)) return;
  const base = Math.max(w / iw, h / ih) * (scale > 0 ? scale : 1);
  const dw = iw * base;
  const dh = ih * base;
  ctx.drawImage(img, (w - dw) / 2, (h - dh) / 2, dw, dh);
}

/**
 * Compose the sequence's frame at a source time into `canvas` and return
 * it — or null when there is nothing drawable, so the caller can skip the
 * frame the way the painters skip an undecoded one. The canvas takes the
 * first still's own size: the sequence is one visual source with one
 * aspect, and every later still cover-fits into it (the slot's own fit,
 * zoom and offsets then apply to the composed frame in the painter,
 * exactly as they apply to a clip's decoded frames).
 */
export function composeImageFrame(canvas, drawables, images, sourceTime, { reduceMotion = false } = {}) {
  if (!canvas || !Array.isArray(drawables) || !drawables.length || !Array.isArray(images) || !images.length) return null;
  const first = drawables[0];
  const w = first?.naturalWidth || first?.width || 0;
  const h = first?.naturalHeight || first?.height || 0;
  if (!(w > 0 && h > 0)) return null;
  if (canvas.width !== w) canvas.width = w;
  if (canvas.height !== h) canvas.height = h;
  const ctx = canvas.getContext("2d");
  if (!ctx) return null;
  ctx.clearRect(0, 0, w, h);
  ctx.fillStyle = "#000";
  ctx.fillRect(0, 0, w, h);
  const frame = imageFrameAt(images, sourceTime);
  if (!frame) return canvas;
  const current = drawables[frame.index];
  if (current) drawCover(ctx, current, w, h, pushInScale(frame.progress, reduceMotion));
  const fade = imageFadeAt(images, sourceTime, reduceMotion);
  if (fade) {
    const incoming = drawables[fade.index];
    if (incoming) {
      ctx.save();
      ctx.globalAlpha = fade.alpha;
      drawCover(ctx, incoming, w, h, pushInScale(0, reduceMotion));
      ctx.restore();
    }
  }
  return canvas;
}
