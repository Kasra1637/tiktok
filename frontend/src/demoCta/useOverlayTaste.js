import { useEffect, useState } from "react";
import {
  BUILTIN_LOOK_PRESETS,
  CTA_COPY_VARIANTS,
  DEFAULTS,
  OVERLAY_ANIMS,
  OVERLAY_FONTS,
  TEXT_STYLES,
} from "./constants";

// Remembered overlay taste: font, entrance and size for the hook + CTA
// overlays, plus the accent. Stored per app with a global fallback, so a
// founder's look survives reloads without one app imposing it on another.
// Empty storage yields DEFAULTS, which is what the smoke suite asserts.
const OVERLAY_PREFS_KEY = "hookforge.demoCta.overlayPrefs.v1";
function readOverlayPrefs() {
  try {
    const raw = window.localStorage.getItem(OVERLAY_PREFS_KEY);
    if (!raw) return {};
    const saved = JSON.parse(raw);
    return saved && typeof saved === "object" ? saved : {};
  } catch {
    return {};
  }
}
function prefFor(profileKey, field, fallback) {
  const all = readOverlayPrefs();
  const scoped = all?.byProfile?.[profileKey]?.[field];
  if (scoped !== undefined && scoped !== null && scoped !== "") return scoped;
  const global = all?.global?.[field];
  return global !== undefined && global !== null && global !== "" ? global : fallback;
}
function prefFont(profileKey, field, fallback) {
  const value = prefFor(profileKey, field, fallback);
  return OVERLAY_FONTS.some((f) => f.id === value) ? value : fallback;
}
function prefAnim(profileKey, field, fallback) {
  const value = prefFor(profileKey, field, fallback);
  return OVERLAY_ANIMS.some((a) => a.id === value) ? value : fallback;
}
function prefTextStyle(profileKey, field, fallback) {
  const value = prefFor(profileKey, field, fallback);
  return TEXT_STYLES.some((s) => s.id === value) ? value : fallback;
}
function prefScale(profileKey, field, fallback) {
  const value = Number(prefFor(profileKey, field, fallback));
  return Number.isFinite(value) ? value : fallback;
}
function prefVariants(profileKey, field, fallbackList) {
  const value = prefFor(profileKey, field, null);
  // CTA presets remain user-editable and remembered independently of openings.
  if (Array.isArray(value) && value.length > 0 && value.every((v) => typeof v === "string")) {
    return value;
  }
  return [...fallbackList];
}
function prefLookPresets(profileKey) {
  const all = readOverlayPrefs();
  const scoped = all?.byProfile?.[profileKey]?.lookPresets;
  if (Array.isArray(scoped)) return scoped;
  const global = all?.global?.lookPresets;
  return Array.isArray(global) ? global : [];
}

/**
 * Overlay taste, one owner. Fonts, entrances, sizes, accent, text style,
 * CTA variants, clip review approval and named looks all live here; the
 * editor only reads the values and calls the setters/helpers.
 *
 * Copy text itself stays editor-owned: CTA selection reports through
 * onCtaHeadline, and review approval reads videoUrl plus the
 * loaded clip duration passed in as clipDuration.
 */
export function useOverlayTaste({ overlayScope, videoUrl, clipDuration, recording, onCtaHeadline }) {
  const [overlayAccent, setOverlayAccent] = useState(() => prefFor(overlayScope, "overlayAccent", DEFAULTS.overlayAccent));
  const [captionFont, setCaptionFont] = useState(() => prefFont(overlayScope, "captionFont", DEFAULTS.captionFont));
  const [ctaFont, setCtaFont] = useState(() => prefFont(overlayScope, "ctaFont", DEFAULTS.ctaFont));
  const [captionAnim, setCaptionAnim] = useState(() => prefAnim(overlayScope, "captionAnim", DEFAULTS.captionAnim));
  const [ctaAnim, setCtaAnim] = useState(() => prefAnim(overlayScope, "ctaAnim", DEFAULTS.ctaAnim));
  const [captionScale, setCaptionScale] = useState(() => prefScale(overlayScope, "captionScale", DEFAULTS.captionScale));
  const [ctaScale, setCtaScale] = useState(() => prefScale(overlayScope, "ctaScale", DEFAULTS.ctaScale));
  // One shared text treatment for hook, story and end card: a single state
  // feeds all three painters, so the picker lives once (Hook Text) and the
  // story inherits it through the hook painter it already reuses.
  const [textStyle, setTextStyle] = useState(() => prefTextStyle(overlayScope, "textStyle", DEFAULTS.textStyle));
  const [ctaVariants, setCtaVariants] = useState(() => prefVariants(overlayScope, "ctaVariants", CTA_COPY_VARIANTS));
  const [activeCtaVariant, setActiveCtaVariant] = useState(0);
  const [customLookPresets, setCustomLookPresets] = useState(() => prefLookPresets(overlayScope));
  const [newLookName, setNewLookName] = useState("");
  const [reviewedLookKey, setReviewedLookKey] = useState(null);
  const [savedLookNotice, setSavedLookNotice] = useState(null);
  // Approval belongs to this clip and this exact reusable styling, not to
  // whichever choices happen to be selected after the next edit.
  const lookReviewKey = JSON.stringify([
    videoUrl, captionFont, ctaFont, captionAnim, ctaAnim,
    captionScale, ctaScale, overlayAccent, textStyle,
  ]);
  const canReviewLook = !!videoUrl && Number.isFinite(clipDuration) && clipDuration > 0 && !recording;
  const lookReviewed = reviewedLookKey === lookReviewKey;
  const canSaveLook = canReviewLook && lookReviewed && !!newLookName.trim();

  // Persist taste on change, per app with a global fallback. Convenience
  // only: private mode or quota failures must never break the editor.
  useEffect(() => {
    try {
      const all = readOverlayPrefs();
      const prefs = {
        overlayAccent,
        captionFont,
        ctaFont,
        captionAnim,
        ctaAnim,
        captionScale,
        ctaScale,
        textStyle,
        ctaVariants,
        lookPresets: customLookPresets,
      };
      const next = {
        ...all,
        global: { ...(all.global || {}), ...prefs },
        byProfile: { ...(all.byProfile || {}), [overlayScope]: { ...((all.byProfile || {})[overlayScope] || {}), ...prefs } },
      };
      window.localStorage.setItem(OVERLAY_PREFS_KEY, JSON.stringify(next));
    } catch {
      // Nothing to do: persistence is a convenience, not the feature.
    }
  }, [overlayAccent, captionFont, ctaFont, captionAnim, ctaAnim, captionScale, ctaScale, textStyle, ctaVariants, customLookPresets, overlayScope]);

  const surpriseCtaVariant = () => {
    if (ctaVariants.length === 0) return;
    let next = activeCtaVariant;
    if (ctaVariants.length > 1) {
      do {
        next = Math.floor(Math.random() * ctaVariants.length);
      } while (next === activeCtaVariant);
    }
    setActiveCtaVariant(next);
    onCtaHeadline(ctaVariants[next] ?? "");
  };

  const updateCtaHeadline = (val) => {
    onCtaHeadline(val);
    setCtaVariants((prev) => prev.map((v, i) => (i === activeCtaVariant ? val : v)));
  };

  const allLookPresets = [...BUILTIN_LOOK_PRESETS, ...customLookPresets];

  const isLookPresetActive = (look) =>
    captionFont === look.captionFont &&
    ctaFont === look.ctaFont &&
    captionAnim === look.captionAnim &&
    ctaAnim === look.ctaAnim &&
    Math.abs(captionScale - look.captionScale) < 1e-6 &&
    Math.abs(ctaScale - look.ctaScale) < 1e-6 &&
    textStyle === (look.textStyle || "signature") &&
    overlayAccent.toLowerCase() === String(look.overlayAccent || "").toLowerCase();

  const applyLookPreset = (look) => {
    if (!look) return;
    setCaptionFont(look.captionFont);
    setCtaFont(look.ctaFont);
    setCaptionAnim(look.captionAnim);
    setCtaAnim(look.ctaAnim);
    setCaptionScale(look.captionScale);
    setCtaScale(look.ctaScale);
    setOverlayAccent(look.overlayAccent);
    setTextStyle(look.textStyle || "signature");
  };

  const handleSaveLookPreset = () => {
    const trimmed = newLookName.trim();
    if (!canSaveLook) return;
    const slug = trimmed.toLowerCase().replace(/[^a-z0-9]+/g, "-").replace(/^-+|-+$/g, "") || `look-${Date.now()}`;
    const entry = {
      id: `custom-${slug}`,
      name: trimmed,
      builtin: false,
      captionFont,
      ctaFont,
      captionAnim,
      ctaAnim,
      captionScale,
      ctaScale,
      overlayAccent,
      textStyle,
    };
    setCustomLookPresets((prev) => {
      const filtered = prev.filter((p) => p.name.toLowerCase() !== trimmed.toLowerCase());
      return [...filtered, entry];
    });
    setNewLookName("");
    setReviewedLookKey(null);
    setSavedLookNotice({ name: trimmed, key: lookReviewKey });
  };

  const handleDeleteLookPreset = (id) => {
    setCustomLookPresets((prev) => prev.filter((p) => p.id !== id));
  };

  return {
    overlayAccent, setOverlayAccent,
    captionFont, setCaptionFont,
    ctaFont, setCtaFont,
    captionAnim, setCaptionAnim,
    ctaAnim, setCtaAnim,
    captionScale, setCaptionScale,
    ctaScale, setCtaScale,
    textStyle, setTextStyle,
    ctaVariants, activeCtaVariant,
    updateCtaHeadline, surpriseCtaVariant,
    customLookPresets,
    allLookPresets,
    newLookName, setNewLookName,
    reviewedLookKey, setReviewedLookKey,
    savedLookNotice,
    lookReviewKey, canReviewLook, lookReviewed, canSaveLook,
    isLookPresetActive, applyLookPreset,
    handleSaveLookPreset, handleDeleteLookPreset,
  };
}
