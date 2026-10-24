import { useEffect, useState } from "react";
import {
  BUILTIN_LOOK_PRESETS,
  CTA_COPY_VARIANTS,
  DEFAULTS,
  HOOK_COPY_VARIANTS,
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
  // Any non-empty string list loads: founders can keep a limitless rotation
  // of hook messages, not just the three shipped defaults.
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
 * copy variants, clip review approval and named looks all live here; the
 * editor only reads the values and calls the setters/helpers.
 *
 * Copy text itself stays editor-owned: variant selection reports through
 * onHookText/onCtaHeadline, and review approval reads videoUrl plus the
 * loaded clip duration passed in as clipDuration.
 */
export function useOverlayTaste({ overlayScope, videoUrl, clipDuration, recording, onHookText, onCtaHeadline }) {
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
  const [hookVariants, setHookVariants] = useState(() => prefVariants(overlayScope, "hookVariants", HOOK_COPY_VARIANTS));
  const [activeHookVariant, setActiveHookVariant] = useState(0);
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
        hookVariants,
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
  }, [overlayAccent, captionFont, ctaFont, captionAnim, ctaAnim, captionScale, ctaScale, textStyle, hookVariants, ctaVariants, customLookPresets, overlayScope]);

  const selectHookVariant = (idx) => {
    setActiveHookVariant(idx);
    onHookText(hookVariants[idx] ?? "");
  };

  // Auto-rotate: one button walks the whole message list and wraps, so the
  // rotation never runs out no matter how many texts the founder keeps.
  const rotateHookVariant = () => {
    if (hookVariants.length === 0) return;
    const next = (activeHookVariant + 1) % hookVariants.length;
    setActiveHookVariant(next);
    onHookText(hookVariants[next] ?? "");
  };

  const addHookVariant = (text) => {
    const trimmed = String(text || "").trim();
    if (!trimmed) return;
    const existing = hookVariants.indexOf(trimmed);
    if (existing >= 0) {
      setActiveHookVariant(existing);
      onHookText(hookVariants[existing]);
      return;
    }
    const next = [...hookVariants, trimmed];
    setHookVariants(next);
    setActiveHookVariant(next.length - 1);
    onHookText(trimmed);
  };

  const removeHookVariant = () => {
    if (hookVariants.length <= 1) return;
    const next = hookVariants.filter((_, i) => i !== activeHookVariant);
    const idx = Math.min(activeHookVariant, next.length - 1);
    setHookVariants(next);
    setActiveHookVariant(idx);
    onHookText(next[idx] ?? "");
  };

  const updateHookText = (val) => {
    onHookText(val);
    setHookVariants((prev) => prev.map((v, i) => (i === activeHookVariant ? val : v)));
  };

  const selectCtaVariant = (idx) => {
    setActiveCtaVariant(idx);
    onCtaHeadline(ctaVariants[idx] ?? "");
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
    hookVariants, activeHookVariant,
    ctaVariants, activeCtaVariant,
    selectHookVariant, updateHookText, rotateHookVariant, addHookVariant, removeHookVariant,
    selectCtaVariant, updateCtaHeadline,
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
