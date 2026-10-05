/**
 * Native Product Demo + CTA engine constants.
 *
 * Ported faithfully from the standalone Product Demo + CTA app: every device
 * spec, preset, background, palette, environment, default, range, step and
 * export candidate below matches that app's behavior exactly. Only the visual
 * skin changed — the math, defaults and capabilities did not.
 *
 * Photographic plates (the hand photo and the five environments) and the Anton
 * face are vendored under `public/demo-cta` and `public/fonts` rather than
 * linked from a third party. They are required inputs: the hand plate is keyed
 * per pixel, and the hook text is painted onto a canvas, so a blocked or slow
 * remote fetch degrades the export instead of just the page.
 */

const ASSET_BASE = `${process.env.PUBLIC_URL || ""}/demo-cta/`;

export const DEVICES = [
  { id: "s24", label: "Samsung Galaxy S24", body: "#0d0d10", rail: "#3a3a3f", aspect: 0.462, radiusRatio: 0.085, bezelRatio: 0.022, camera: "punch-center" },
  { id: "s24_ultra", label: "Samsung Galaxy S24 Ultra", body: "#15161a", rail: "#46474c", aspect: 0.470, radiusRatio: 0.055, bezelRatio: 0.020, camera: "punch-center" },
  { id: "note20", label: "Samsung Galaxy Note 20", body: "#111114", rail: "#2f3035", aspect: 0.455, radiusRatio: 0.060, bezelRatio: 0.024, camera: "punch-center" },
  { id: "zflip", label: "Samsung Galaxy Z Flip5", body: "#1a1a1f", rail: "#3d3d44", aspect: 0.438, radiusRatio: 0.110, bezelRatio: 0.026, camera: "punch-center" },
  { id: "lg_v60", label: "LG V60 ThinQ", body: "#0b0c10", rail: "#34353a", aspect: 0.460, radiusRatio: 0.070, bezelRatio: 0.030, camera: "notch-drop" },
  { id: "lg_velvet", label: "LG Velvet", body: "#101218", rail: "#3a3c44", aspect: 0.448, radiusRatio: 0.090, bezelRatio: 0.028, camera: "notch-drop" },
  { id: "lg_g8", label: "LG G8 ThinQ", body: "#0e0e12", rail: "#33343a", aspect: 0.472, radiusRatio: 0.075, bezelRatio: 0.034, camera: "notch-wide" },
];

export const PRESETS = [
  { id: "tiktok", label: "TikTok / Reels / Shorts", w: 1080, h: 1920, note: "9:16" },
  { id: "story", label: "Instagram Story", w: 1080, h: 1920, note: "9:16" },
  { id: "linkedin_square", label: "LinkedIn Square", w: 1200, h: 1200, note: "1:1" },
  { id: "linkedin_landscape", label: "LinkedIn Landscape", w: 1920, h: 1080, note: "16:9" },
  { id: "youtube", label: "YouTube 1080p", w: 1920, h: 1080, note: "16:9" },
  { id: "source", label: "Tight crop (phone only)", w: 0, h: 0, note: "auto" },
];

export const BACKGROUNDS = [
  { id: "transparent", label: "Transparent (WebM)", preview: "transparent" },
  { id: "lavender", label: "Lavender", preview: "linear-gradient(135deg,#0c0814,#14101e)" },
  { id: "sage", label: "Sage", preview: "linear-gradient(135deg,#080e0a,#0e1810)" },
  { id: "cloud", label: "Cloud", preview: "linear-gradient(135deg,#080a10,#0e1218)" },
  { id: "mist", label: "Mist", preview: "linear-gradient(135deg,#08090e,#0e1016)" },
  { id: "pink", label: "Pink", preview: "linear-gradient(135deg,#14080e,#1e0e16)" },
  { id: "purple", label: "Purple", preview: "linear-gradient(135deg,#0e0814,#180e20)" },
  { id: "blue", label: "Blue", preview: "linear-gradient(135deg,#06081a,#0a1028)" },
];

export const ANIMATIONS = [
  { id: "float", label: "Gentle Float" },
  { id: "pulse", label: "Breathing Pulse" },
  { id: "rays", label: "Light Rays" },
  { id: "aurora", label: "Aurora Waves" },
  { id: "orbit", label: "Orbiting Ring" },
  { id: "breathe", label: "Deep Breathe" },
];

export const COLOR_PALETTES = {
  lavender: { bg1: "#0c0814", bg2: "#14101e", glow: "rgba(150, 100, 220, 0.25)", accent: "rgba(120, 80, 200, 0.12)" },
  sage: { bg1: "#080e0a", bg2: "#0e1810", glow: "rgba(80, 180, 120, 0.22)", accent: "rgba(60, 160, 100, 0.10)" },
  cloud: { bg1: "#080a10", bg2: "#0e1218", glow: "rgba(100, 150, 220, 0.22)", accent: "rgba(80, 130, 200, 0.10)" },
  mist: { bg1: "#08090e", bg2: "#0e1016", glow: "rgba(80, 140, 200, 0.22)", accent: "rgba(60, 120, 180, 0.10)" },
  pink: { bg1: "#14080e", bg2: "#1e0e16", glow: "rgba(240, 80, 160, 0.25)", accent: "rgba(220, 60, 140, 0.12)" },
  purple: { bg1: "#0e0814", bg2: "#180e20", glow: "rgba(160, 60, 240, 0.25)", accent: "rgba(140, 40, 220, 0.12)" },
  blue: { bg1: "#06081a", bg2: "#0a1028", glow: "rgba(60, 120, 255, 0.25)", accent: "rgba(40, 100, 240, 0.12)" },
};

export const ENVIRONMENTS = [
  { id: "living_room", label: "Living Room", url: `${ASSET_BASE}env-living-room.jpg` },
  { id: "bedroom", label: "Bedroom", url: `${ASSET_BASE}env-bedroom.jpg` },
  { id: "bedroom_light", label: "Bright Bedroom", url: `${ASSET_BASE}env-bedroom-light.jpg` },
  { id: "bedroom_warm", label: "Sunlit Bedroom", url: `${ASSET_BASE}env-bedroom-warm.jpg` },
  { id: "loft", label: "Soft Loft", url: `${ASSET_BASE}env-loft.jpg` },
];

export const HAND_IMAGE_URL = `${ASSET_BASE}hand.jpg`;

export const DEFAULT_SCREEN = { x: 0.3275, y: 0.09, w: 0.3608, h: 0.7708 };

export const ACCENT_SWATCHES = ["#c8ff2e", "#ff4d8d", "#4dd8ff", "#ffffff"];

export const DEFAULTS = {
  device: "s24",
  frameColor: "black",
  preset: "tiktok",
  bg: "lavender",
  anim: "float",
  scale: 0.82,
  mockupStretchY: 1,
  videoFit: "cover",
  videoScale: 1,
  videoOffsetX: 0,
  videoOffsetY: 0,
  exportFormat: "auto",
  viewMode: "floating",
  envBg: "living_room",
  handZoom: 1,
  handPanX: 0,
  handPanY: 0,
  hookEnabled: true,
  hookText: "I built this so I'd stop journaling in Notes app",
  hookDuration: 1.8,
  hookOffsetX: 0,
  hookOffsetY: 0,
  ctaEnabled: true,
  ctaHeadline: "Try it free — link in bio",
  ctaHandle: "@yourhandle",
  ctaDuration: 2,
  ctaOffsetX: 0,
  ctaOffsetY: 0,
  overlayAccent: "#c8ff2e",
};

export const RANGES = {
  scale: { min: 0.3, max: 1, step: 0.01 },
  mockupStretchY: { min: 0.5, max: 2, step: 0.01 },
  videoScale: { min: 0.5, max: 3, step: 0.01 },
  videoOffset: { min: -100, max: 100, step: 1 },
  handZoom: { min: 0.4, max: 3, step: 0.01 },
  handPan: { min: -1, max: 1, step: 0.005 },
  screen: { min: 0, max: 1, step: 0.001 },
  hookDuration: { min: 0.8, max: 4, step: 0.1 },
  ctaDuration: { min: 1, max: 5, step: 0.1 },
};

export const BASE_PHONE_H = 1800;

export const MP4_CANDIDATES = [
  'video/mp4;codecs="avc1.42E01F,mp4a.40.2"',
  'video/mp4;codecs="avc1.640028,mp4a.40.2"',
  'video/mp4;codecs="h264,aac"',
  "video/mp4",
];

export const WEBM_CANDIDATES = [
  'video/webm;codecs="vp9,opus"',
  'video/webm;codecs="vp8,opus"',
  "video/webm;codecs=vp9",
  "video/webm;codecs=vp8",
  "video/webm",
];

export const VIDEO_BITS_PER_SECOND = 8000000;
export const AUDIO_BITS_PER_SECOND = 192000;
export const CAPTURE_FPS = 30;

/**
 * MIME selection mirrors the standalone exporter: transparent forces WebM,
 * otherwise MP4 candidates come first unless WebM was explicitly chosen.
 * Returns null when the browser reports no supported candidate.
 */
export function selectExportMime({ transparent, exportFormat }) {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return null;
  const candidates = transparent
    ? WEBM_CANDIDATES
    : exportFormat !== "webm"
      ? [...MP4_CANDIDATES, ...WEBM_CANDIDATES]
      : [...WEBM_CANDIDATES, ...MP4_CANDIDATES];
  return candidates.find((m) => MediaRecorder.isTypeSupported(m)) || null;
}

export function extensionForMime(mime) {
  return String(mime || "").startsWith("video/mp4") ? "mp4" : "webm";
}

function sanitizePart(part, fallback) {
  const clean = String(part || "")
    .toLowerCase()
    .replace(/[^a-z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "");
  return clean || fallback;
}

/**
 * Export filename.
 *
 * Deliberately neutral: it names the artifact and the render facts behind it,
 * with no product prefix. A downloaded file should describe what it is rather
 * than which app produced it, and it must not carry the branding of a tool this
 * flow replaced.
 */
export function buildExportFilename({ device, preset, width, height, ext }) {
  return `demo-cta-${sanitizePart(device, "device")}-${sanitizePart(preset, "preset")}-${Math.round(width)}x${Math.round(height)}.${ext}`;
}

export function formatTime(seconds) {
  const s = Number(seconds) || 0;
  const m = Math.floor(s / 60);
  const sec = Math.floor(s % 60);
  const ms = Math.floor((s % 1) * 10);
  return `${m}:${String(sec).padStart(2, "0")}.${ms}`;
}
