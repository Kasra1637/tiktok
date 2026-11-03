import { useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

/**
 * Direction dropdown lifecycle: one owner for profile- and angle-keyed options,
 * per-app picks, saved-plan matching and per-field refresh.
 *
 * Navigation safety: every load carries a request id, picks reset when the
 * profile changes, and a refresh never destroys the founder's current pick.
 */
export function useWizardDirections({ profileId, project, tone, angle, dispatchDraft, editTone }) {
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

  const [dirSel, setDirSel] = useState({ location: "", lighting: "", wardrobe: "", voice: "", tone: "" });

  useEffect(() => {
    setDirSel({ location: "", lighting: "", wardrobe: "", voice: "", tone: "" });
  }, [profileId]);

  const savedDirectionsRef = useRef(null);
  savedDirectionsRef.current = {
    visual: project?.visual_direction || "",
    location: project?.location || "",
    voice: project?.voice_direction || "",
    tone: project?.tone || tone || "",
  };

  useEffect(() => {
    if (!directionOptions) return;
    const { visual: savedVisual, location: savedLocation, voice: savedVoice, tone: savedTone } = savedDirectionsRef.current;
    const matchPart = (text, list) =>
      (list || []).find((option) => text && text.toLowerCase().includes(option.toLowerCase())) || "";
    const matchTone = (list) =>
      (list || []).find((option) =>
        savedTone &&
        (option.toLowerCase().includes(savedTone.toLowerCase()) ||
          savedTone.toLowerCase().includes(option.toLowerCase()))
      ) || "";
    setDirSel({
      location: matchPart(savedLocation, directionOptions.location) || matchPart(savedVisual, directionOptions.location),
      lighting: matchPart(savedVisual, directionOptions.lighting),
      wardrobe: matchPart(savedVisual, directionOptions.wardrobe),
      voice: matchPart(savedVoice, directionOptions.voice),
      tone: matchTone(directionOptions.tone),
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

  const pickTone = (value) => {
    setDirSel((previous) => ({ ...previous, tone: value }));
    editTone(value);
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
    pickTone,
    refreshingField,
    refreshError,
    refreshDirectionField,
    refreshProps,
  };
}
