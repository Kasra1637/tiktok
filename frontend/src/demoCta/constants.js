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

/**
 * Caption/CTA overlay faces. Anton first: it is the long-standing default,
 * so existing renders are byte-identical until the founder picks otherwise.
 * Every other face is a high x-height, open-aperture text face chosen for
 * on-video legibility at small sizes — display faces are deliberately absent.
 * `stack` is what the canvas painter requests; the generic fallback keeps a
 * missing file from ever rendering tofu.
 */
export const OVERLAY_FONTS = [
  { id: "anton", label: "Anton", stack: '"Anton", "Arial Black", sans-serif' },
  { id: "inter", label: "Inter", stack: '"Inter", system-ui, sans-serif' },
  { id: "manrope", label: "Manrope", stack: '"Manrope", system-ui, sans-serif' },
  { id: "archivo", label: "Archivo", stack: '"Archivo", system-ui, sans-serif' },
  { id: "dm-sans", label: "DM Sans", stack: '"DM Sans", system-ui, sans-serif' },
  { id: "sora", label: "Sora", stack: '"Sora", system-ui, sans-serif' },
  { id: "space-grotesk", label: "Space Grotesk", stack: '"Space Grotesk", system-ui, sans-serif' },
  { id: "poppins", label: "Poppins", stack: '"Poppins", system-ui, sans-serif' },
  { id: "montserrat", label: "Montserrat", stack: '"Montserrat", system-ui, sans-serif' },
  { id: "nunito", label: "Nunito", stack: '"Nunito", system-ui, sans-serif' },
];

/**
 * Caption/CTA entrance styles. One catalog, picked independently per overlay:
 * the caption and the end card each name one of these ten. Every style is a
 * pure function of video time (see overlayMotion in overlays.js) — never
 * wall-clock — so the exported recording matches the preview frame for
 * frame. `punch` and `rise` are the two behaviours that shipped before this
 * catalog existed, kept as the defaults so nothing already made changes.
 */
export const OVERLAY_ANIMS = [
  { id: "punch", label: "Punch in" },
  { id: "fade", label: "Fade" },
  { id: "rise", label: "Rise" },
  { id: "slide", label: "Slide in" },
  { id: "pop", label: "Pop" },
  { id: "typewriter", label: "Typewriter" },
  { id: "glow", label: "Glow in" },
  { id: "underline", label: "Underline draw" },
  { id: "drop", label: "Drop in" },
  { id: "steady", label: "Steady" },
];

export const HOOK_COPY_VARIANTS = [
  "I built this so I'd stop journaling in Notes app",
  "How I stopped losing my best thoughts in Apple Notes",
  "The 10-second check-in that replaced my messy journal",
];

export const CTA_COPY_VARIANTS = [
  "Try it free — link in bio",
  "Download free on the App Store",
  "Start your first entry — link in bio",
];

export const CTA_TIMING_PRESETS = [
  { id: "last2", label: "Last 2s", seconds: 2 },
  { id: "last3", label: "Last 3s", seconds: 3 },
  { id: "full", label: "Full clip", seconds: null },
];

export const BUILTIN_LOOK_PRESETS = [
  {
    id: "launch",
    name: "Launch style",
    builtin: true,
    captionFont: "anton",
    ctaFont: "anton",
    captionAnim: "punch",
    ctaAnim: "rise",
    captionScale: 1,
    ctaScale: 1,
    overlayAccent: "#c8ff2e",
  },
  {
    id: "ugc",
    name: "UGC style",
    builtin: true,
    captionFont: "nunito",
    ctaFont: "nunito",
    captionAnim: "pop",
    ctaAnim: "fade",
    captionScale: 1,
    ctaScale: 1,
    overlayAccent: "#ff4d8d",
  },
  {
    id: "editorial",
    name: "Editorial clean",
    builtin: true,
    captionFont: "space-grotesk",
    ctaFont: "inter",
    captionAnim: "rise",
    ctaAnim: "steady",
    captionScale: 0.85,
    ctaScale: 0.85,
    overlayAccent: "#4dd8ff",
  },
];

export function resolveCtaWindow(ctaDuration, clipDuration, ctaTimingMode = "custom") {
  const dur = Number(clipDuration) || 0;
  if (ctaTimingMode === "full") {
    return dur > 0 ? dur : Number(ctaDuration) || DEFAULTS.ctaDuration;
  }
  if (ctaTimingMode === "last2") {
    return dur > 0 ? Math.min(2, dur) : 2;
  }
  if (ctaTimingMode === "last3") {
    return dur > 0 ? Math.min(3, dur) : 3;
  }
  const d = Number(ctaDuration) || DEFAULTS.ctaDuration;
  return dur > 0 ? Math.min(d, dur * 0.45) : d;
}

export const DEFAULTS = {
  device: "s24",
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
  captionFont: "anton",
  ctaFont: "anton",
  captionAnim: "punch",
  ctaAnim: "rise",
  captionScale: 1,
  ctaScale: 1,
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
  // Overlay size multiplier. 1 is the long-standing cw-derived size; the
  // painters wrap inside maxWidth, so 1.3x reflows lines rather than leaving
  // the TikTok safe area.
  overlayScale: { min: 0.7, max: 1.3, step: 0.01 },
};

export const BASE_PHONE_H = 1800;

/**
 * MP4 candidates, ordered by what can actually encode a 1080x1920 canvas.
 *
 * `avc1.42E01F` is H.264 Baseline Level 3.1, which tops out at 3600
 * macroblocks per frame (1280x720). A 1080x1920 canvas is 8160. The encoder
 * therefore rejects it with "configuration not supported" — but
 * `MediaRecorder.isTypeSupported` only checks the codec string, never the
 * resolution against the level, so it falsely passes and the failure surfaces
 * asynchronously at record time. That exact sequence shipped a confusing error
 * to a real export. High Level 4.0 (`avc1.640028`, 8192 macroblocks) fits, so
 * it goes first; Baseline stays in the list as a last resort for small
 * canvases rather than being dropped.
 */
export const MP4_CANDIDATES = [
  'video/mp4;codecs="avc1.640028,mp4a.40.2"',
  'video/mp4;codecs="avc1.42E01F,mp4a.40.2"',
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
 * The one definition of "how loud this export is".
 *
 * Unity on purpose. The complaint this exists for is an export that came back
 * quieter than what the founder heard, and the cause was that nothing in the
 * pipeline said what the level WAS: the element was left to carry it, two
 * different capture paths read it from two different places, and the level the
 * founder heard and the level written into the file were only ever assumed to
 * be the same number.
 *
 * Both paths now pass through a GainNode set to this value, so the monitored
 * level and the recorded level are the same number by construction rather than
 * by coincidence. Raise it here to make every export louder; there is no second
 * place to change, which is the property that makes it trustworthy.
 *
 * One honest limit: this governs the WebAudio path. The browser's own
 * `captureStream()` is preferred when it works, and that path records the
 * element's own audio at whatever level the element is at — unity today,
 * because the element is unmuted at volume 1 for the capture. So this constant
 * is the level on both paths only while it is 1. Anything else, and the native
 * path has to be routed through the graph to honour it too.
 */
export const EXPORT_AUDIO_GAIN = 1;

/**
 * MIME selection mirrors the standalone exporter: transparent forces WebM,
 * otherwise MP4 candidates come first unless WebM was explicitly chosen.
 * Returns the full ordered list of supported candidates, not just the first:
 * `isTypeSupported` can pass a configuration the encoder then rejects at
 * record time (see MP4_CANDIDATES), so the exporter walks this list and falls
 * back rather than failing on a lie the browser told.
 */
export function supportedExportMimes({ transparent, exportFormat }) {
  if (typeof MediaRecorder === "undefined" || !MediaRecorder.isTypeSupported) return [];
  const candidates = transparent
    ? WEBM_CANDIDATES
    : exportFormat !== "webm"
      ? [...MP4_CANDIDATES, ...WEBM_CANDIDATES]
      : [...WEBM_CANDIDATES, ...MP4_CANDIDATES];
  return candidates.filter((m) => MediaRecorder.isTypeSupported(m));
}

export function selectExportMime(opts) {
  return supportedExportMimes(opts)[0] || null;
}

export function extensionForMime(mime) {
  return String(mime || "").startsWith("video/mp4") ? "mp4" : "webm";
}

/**
 * Floor for a believable recording. A multi-second capture at 8Mbps is
 * megabytes; nothing legitimate is smaller. Anything under this is an empty
 * mux, a truncated write, or a recorder that stopped before the first sample
 * — all of which used to be offered as a download with a confident filename.
 */
export const MIN_EXPORT_BYTES = 32768;

export function isPlausibleRecordingSize(size) {
  return Number.isFinite(size) && size >= MIN_EXPORT_BYTES;
}

/**
 * Identify a recorded container from its first bytes, so a corrupt or
 * truncated file is caught before it becomes a download link.
 *
 * MP4 is a box structure: the file opens with a 4-byte big-endian box size
 * followed by the box type, and the first box of a recording is always `ftyp`.
 * WebM is EBML: the stream opens with the fixed 4-byte element ID 0x1A45DFA3.
 * Anything else — a zeroed buffer, an HTML error page saved as .mp4, a file
 * cut mid-header — is not a recording. Returns "mp4", "webm", or null.
 *
 * `bytes` is the first 8+ bytes as a Uint8Array (or any indexable of numbers).
 */
export function sniffRecordingContainer(bytes) {
  if (!bytes || bytes.length < 8) return null;
  const b = (i) => bytes[i] & 0xff;
  if (b(4) === 0x66 && b(5) === 0x74 && b(6) === 0x79 && b(7) === 0x70) return "mp4";
  if (b(0) === 0x1a && b(1) === 0x45 && b(2) === 0xdf && b(3) === 0xa3) return "webm";
  return null;
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
