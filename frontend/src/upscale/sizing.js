/**
 * Upscaler sizing rules: pure functions of dimensions, no DOM, no codecs.
 *
 * Short side grows to 1080; the long side never passes 1920. A sub-1080p
 * portrait phone clip (720x1280) therefore lands on 1080x1920, a 480p
 * landscape clip on 1920x1080, and a square clip on 1080x1080.
 */

export const UPSCALE = Object.freeze({
  targetMinSide: 1080,
  maxSide: 1920,
  fps: 30,
  videoBitrate: 12_000_000,
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
