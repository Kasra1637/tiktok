import { useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

/**
 * Direction dropdown lifecycle: one owner for profile- and angle-keyed options,
 * per-app picks, saved-plan matching and per-field refresh.
 *
 * Navigation safety: every load carries a request id, picks reset when the
 * profile changes, and a refresh never destroys the founder's current pick.
 *
 * There is deliberately no Tone pick here. The video-level Tone dropdown
 * duplicated the App Profile's "Tone / voice" and the voice direction, and both
 * collapsed into the strategy's single `voice_delivery` downstream — so the
 * Voice direction pick is the one delivery control (ADR 0091). A saved tone on
 * an existing project still rides into plan and strategy generation untouched;
 * only the second control is gone.
 */
export function useWizardDirections({ profileId, project, angle, dispatchDraft }) {
  const [directionOptions, setDirectionOptions] = useState(null);
  const angleId = angle?.id || "";
  const directionRequestRef = useRef(0);

  useEffect(() => {
    const request = ++directionRequestRef.current;
    if (!profileId) {
      setDirectionOptions(null);
      return undefined;
    }
    let cancelled = false;
    api.getDirectionOptions(profileId, angleId)
      .then((data) => {
        if (!cancelled && directionRequestRef.current === request) setDirectionOptions(data);
      })
      .catch(() => {
        if (!cancelled && directionRequestRef.current === request) setDirectionOptions(null);
      });
    return () => {
      cancelled = true;
    };
  }, [profileId, angleId]);

  const [dirSel, setDirSel] = useState({ location: "", lighting: "", wardrobe: "", voice: "" });

  useEffect(() => {
    setDirSel({ location: "", lighting: "", wardrobe: "", voice: "" });
  }, [profileId]);

  const savedDirectionsRef = useRef(null);
  savedDirectionsRef.current = {
    visual: project?.visual_direction || "",
    location: project?.location || "",
    voice: project?.voice_direction || "",
  };

  useEffect(() => {
    if (!directionOptions) return;
    const { visual: savedVisual, location: savedLocation, voice: savedVoice } = savedDirectionsRef.current;
    const matchPart = (text, list) =>
      (list || []).find((option) => text && text.toLowerCase().includes(option.toLowerCase())) || "";
    setDirSel({
      location: matchPart(savedLocation, directionOptions.location) || matchPart(savedVisual, directionOptions.location),
      lighting: matchPart(savedVisual, directionOptions.lighting),
      wardrobe: matchPart(savedVisual, directionOptions.wardrobe),
      voice: matchPart(savedVoice, directionOptions.voice),
    });
  }, [project?.id, directionOptions]);

  const pickScenePart = (field) => (value) => {
    const next = { ...dirSel, [field]: value };
    setDirSel(next);
    if (field === "location") {
      dispatchDraft({ type: "edit-field", field: "location", value, omitDefault: true });
      return;
    }
    const composed = [next.lighting, next.wardrobe].filter(Boolean).join(", ");
    dispatchDraft({ type: "edit-field", field: "visual_direction", value: composed, omitDefault: true });
  };

  const pickVoice = (value) => {
    setDirSel((previous) => ({ ...previous, voice: value }));
    dispatchDraft({ type: "edit-field", field: "voice_direction", value, omitDefault: true });
  };

  const [refreshingField, setRefreshingField] = useState("");
  const [refreshError, setRefreshError] = useState("");

  const refreshDirectionField = (field) => async () => {
    if (!profileId || refreshingField) return;
    setRefreshingField(field);
    setRefreshError("");
    try {
      const data = await api.refreshDirectionOptions(profileId, {
        field,
        avoid: directionOptions?.[field] || [],
        angleId: angle?.id || "",
      });
      const fresh = (data?.options || []).filter(Boolean);
      if (fresh.length > 0) {
        setDirectionOptions((previous) => {
          if (!previous) return previous;
          const pick = dirSel[field] || "";
          const merged = pick && !fresh.includes(pick) ? [pick, ...fresh] : [...fresh];
          return { ...previous, [field]: merged };
        });
      }
    } catch (err) {
      setRefreshError(getErrorMessage(err));
    } finally {
      setRefreshingField("");
    }
  };

  const refreshProps = (field, testId) => ({
    onRefresh: refreshDirectionField(field),
    refreshing: refreshingField === field,
    refreshTestId: testId,
  });

  return {
    directionOptions,
    dirSel,
    pickScenePart,
    pickVoice,
    refreshingField,
    refreshError,
    refreshDirectionField,
    refreshProps,
  };
}
