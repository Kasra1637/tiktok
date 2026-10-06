// How a clip is fitted to the phone's screen area.
//
// Extracted because this exact arithmetic was duplicated in two renderers — the
// floating phone and the hand-held phone — and the two drifted. The hand-held
// one implemented "fill"; the floating one silently treated it as "cover". A
// founder who picked Fill to remove a blank strip got the bars back, and it read
// as a broken render rather than as a control that did nothing.
//
// One function, one behaviour, called by both. The units are pixels in and
// pixels out; nothing here knows about devices, canvases or overlays.

/**
 * The drawn size of a clip inside a screen box.
 *
 * The three modes are genuinely different, which is why they are named:
 *
 *   cover   - scale up until the box is covered, cropping the overflow. Never
 *             leaves a gap, and is the right default for a clip already in the
 *             platform's aspect.
 *   contain - scale down until the whole clip fits, padding the difference.
 *             This is the only mode that can leave a gap, which is the point of
 *             it.
 *   fill    - stretch to the box and ignore the source aspect. The only mode
 *             that guarantees no gap regardless of source aspect, at the cost
 *             of distorting the picture. It is what a founder reaches for when a
 *             cover still leaves a strip.
 *
 * `scale` is the Zoom control and multiplies the result in every mode, so the
 * control does the same thing whichever mode is selected. Below 1 it insets the
 * clip and therefore re-opens a gap in cover and fill; that is what zoom means,
 * and the screen behind it is painted rather than left as a void.
 *
 * Returns null when there is nothing sensible to scale — no dimensions yet, or
 * a zero — so callers can skip drawing instead of producing NaN geometry that
 * silently blanks the screen.
 */
export function fitVideoToScreen({
  fit,
  videoW,
  videoH,
  screenW,
  screenH,
  scale = 1,
} = {}) {
  if (!(videoW > 0) || !(videoH > 0) || !(screenW > 0) || !(screenH > 0)) return null;
  const zoom = Number.isFinite(scale) && scale > 0 ? scale : 1;

  if (fit === "fill") {
    return { dw: screenW * zoom, dh: screenH * zoom };
  }

  const base =
    fit === "contain"
      ? Math.min(screenW / videoW, screenH / videoH)
      : Math.max(screenW / videoW, screenH / videoH);

  return { dw: videoW * base * zoom, dh: videoH * base * zoom };
}

/**
 * Whether a fitted clip leaves any part of the screen uncovered.
 *
 * This is the question behind "the phone screen shows a blank strip": a gap is
 * not itself a bug — contain is supposed to make one — but it is what the
 * founder is looking at when they say the picture is blank, so it is worth
 * being able to name rather than eyeball.
 */
export function leavesUncoveredScreen({ fit, videoW, videoH, screenW, screenH, scale = 1 } = {}) {
  const box = fitVideoToScreen({ fit, videoW, videoH, screenW, screenH, scale });
  if (!box) return null;
  // A fifth of a pixel: sub-pixel rounding is not a visible band, and treating
  // it as one would make this report "gap" for a correctly filled screen.
  const EPSILON = 0.2;
  return box.dw + EPSILON < screenW || box.dh + EPSILON < screenH;
}