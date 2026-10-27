/**
 * Upscaler sizing rules: pure functions of dimensions, no DOM, no codecs.
 *
 * Short side grows to 2160; the long side never passes 3840. A sub-4K
 * portrait phone clip (540x960) therefore lands on 2160x3840, a 540p
 * landscape clip on 3840x2160, and a square clip on 2160x2160.
 */

export const UPSCALE = Object.freeze({
  targetMinSide: 2160,
  maxSide: 3840,
  fps: 30,
  videoBitrate: 32_000_000,
  audioBitrate: 192_000,
  // Browser-side AVC encode of a very long clip ties up the tab for many
  // minutes, so overlong files are refused loudly instead of stalling.
  maxDurationSeconds: 300,
});

// Pure function of the source dimensions, so the sizing rule is unit
// testable without decoding anything. Returns null when the source is not
// eligible: already HD, or dimensions that are not usable numbers.
export function upscaleTarget(width, height) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
  const minSide = Math.min(width, height);
  if (minSide >= UPSCALE.targetMinSide) return null;
  const maxSide = Math.max(width, height);
  const factor = Math.min(UPSCALE.targetMinSide / minSide, UPSCALE.maxSide / maxSide);
  // AVC needs even dimensions. The factor already caps the long side at or
  // under the ceiling, and even-rounding moves a side by at most 1px, so no
  // second clamp is needed: the long side lands within a pixel of the cap.
  const even = (n) => Math.max(2, Math.round(n / 2) * 2);
  return { width: even(width * factor), height: even(height * factor) };
}

export function formatDims(width, height) {
  return `${width} × ${height}`;
}
