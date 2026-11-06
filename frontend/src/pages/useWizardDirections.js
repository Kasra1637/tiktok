import { useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

/**
 * Direction dropdown lifecycle: one owner for profile- and angle-keyed options,
 * per-app picks, saved-plan matching and per-field refresh.
 *
 * Navigation safety: every load carries a request id, picks reset when the
 * profile changes, and a refresh never destroys the founder's current pick.
 *
 * There is deliberately no Tone or Voice pick here: the plan and the strategy
 * write this video's delivery from its own objective, audience and angle
 * emotion, so voice direction is set per video, never from a control (ADR 0102,
 * superseding 0091). Nor is Lighting a pick: the strategy's scene states it
 * from the video's own context — only Location and Wardrobe stay pickable. A
 * saved tone or voice on an existing project still rides into plan and
 * strategy generation untouched.
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

  const [dirSel, setDirSel] = useState({ location: "", lighting: "", wardrobe: "" });

  useEffect(() => {
    setDirSel({ location: "", lighting: "", wardrobe: "" });
  }, [profileId]);

  const savedDirectionsRef = useRef(null);
  savedDirectionsRef.current = {
    visual: project?.visual_direction || "",
    location: project?.location || "",
  };

  useEffect(() => {
    if (!directionOptions) return;
    const { visual: savedVisual, location: savedLocation } = savedDirectionsRef.current;
    const matchPart = (text, list) =>
      (list || []).find((option) => text && text.toLowerCase().includes(option.toLowerCase())) || "";
    setDirSel({
      location: matchPart(savedLocation, directionOptions.location) || matchPart(savedVisual, directionOptions.location),
      // No Lighting control reads this slot any more; it is kept so a wardrobe
      // pick recomposes the strategy's own lighting word instead of dropping it.
      lighting: matchPart(savedVisual, directionOptions.lighting),
      wardrobe: matchPart(savedVisual, directionOptions.wardrobe),
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
    refreshingField,
    refreshError,
    refreshDirectionField,
    refreshProps,
  };
}
