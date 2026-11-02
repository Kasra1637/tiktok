/**
 * Upscaler sizing rules: pure functions of dimensions, no DOM, no codecs.
 *
 * Short side grows to 1080; the long side never passes 1920. A 540p portrait
 * phone clip (540x960) therefore lands on 1080x1920, a 4:3 640x480 clip on
 * 1440x1080, and a square clip on 1080x1080 — the short side is the one that
 * hits the target, and the long side is only a ceiling for extreme aspects.
 *
 * The ceiling is why a wide clip can be ineligible even with a short side
 * under 1080: 1920x800 already fills the long side, so growing it to "1080p"
 * would mean returning the input's own size. That is refused (null) rather
 * than exported as a file the button promised would be bigger.
 */

export const UPSCALE = Object.freeze({
  targetMinSide: 1080,
  maxSide: 1920,
  fps: 30,
  // Unchanged from the 4K target on purpose: quality per pixel is a product
  // decision of its own, not something a resolution change should quietly
  // re-decide. At 1080p this is well above typical delivery bitrates, so a
  // smaller figure is available if export size ever matters more than grain.
  videoBitrate: 32_000_000,
  audioBitrate: 192_000,
  // Browser-side AVC encode of a very long clip ties up the tab for many
  // minutes, so overlong files are refused loudly instead of stalling.
  maxDurationSeconds: 300,
});

// Pure function of the source dimensions, so the sizing rule is unit
// testable without decoding anything. Returns null when the source is not
// eligible: already at or above the target, a long side that already fills
// the ceiling (so no dimension could grow), or dimensions that are not
// usable numbers.
export function upscaleTarget(width, height) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
  const minSide = Math.min(width, height);
  if (minSide >= UPSCALE.targetMinSide) return null;
  const maxSide = Math.max(width, height);
  const factor = Math.min(UPSCALE.targetMinSide / minSide, UPSCALE.maxSide / maxSide);
  // A factor of 1 means the long side is already at the ceiling: the clip
  // cannot gain resolution without cropping it, so "upscaling" would hand back
  // the input's own dimensions under a 1080p label. Refusing names that.
  if (factor <= 1) return null;
  // AVC needs even dimensions. The factor already caps the long side at or
  // under the ceiling, and even-rounding moves a side by at most 1px, so no
  // second clamp is needed: the long side lands within a pixel of the cap.
  const even = (n) => Math.max(2, Math.round(n / 2) * 2);
  return { width: even(width * factor), height: even(height * factor) };
}

export function formatDims(width, height) {
  return `${width} × ${height}`;
}
