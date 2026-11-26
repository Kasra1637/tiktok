import { useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

/**
 * Direction dropdown lifecycle: one owner for profile- and angle-keyed options,
 * per-app picks, saved-plan matching and per-field refresh.
 *
 * The option lists are also keyed on the camera setup (ADR 0220): a fixed
 * camera is indoors only (ADR 0219), so the server filters the location
 * list for it, and flipping the setup re-reads the list under the new one.
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
export function useWizardDirections({ profileId, project, angle, dispatchDraft, cameraSetup = "" }) {
  const [directionOptions, setDirectionOptions] = useState(null);
  // Whether the options read for the current profile has settled —
  // landed OR failed (ADR 0356). HookSnap's section cascade reads
  // it to know the direction step is done being prepared; a failed
  // read settles too, so the cascade can never wait forever on a
  // read that already answered with an error. The wizard ignores it.
  const [directionSettled, setDirectionSettled] = useState(false);
  const angleId = angle?.id || "";
  const directionRequestRef = useRef(0);

  useEffect(() => {
    const request = ++directionRequestRef.current;
    if (!profileId) {
      setDirectionOptions(null);
      setDirectionSettled(false);
      return undefined;
    }
    setDirectionSettled(false);
    let cancelled = false;
    api.getDirectionOptions(profileId, angleId, cameraSetup)
      .then((data) => {
        if (!cancelled && directionRequestRef.current === request) {
          setDirectionOptions(data);
          setDirectionSettled(true);
        }
      })
      .catch(() => {
        if (!cancelled && directionRequestRef.current === request) {
          setDirectionOptions(null);
          setDirectionSettled(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [profileId, angleId, cameraSetup]);

  const [dirSel, setDirSel] = useState({ location: "", lighting: "", wardrobe: "" });

  useEffect(() => {
    setDirSel({ location: "", lighting: "", wardrobe: "" });
  }, [profileId]);

  const savedDirectionsRef = useRef(null);
  savedDirectionsRef.current = {
    visual: project?.visual_direction || "",
    location: project?.location || "",
  };

  const matchedProjectRef = useRef(null);

  useEffect(() => {
    if (!directionOptions) return;
    // A re-read of the lists (the camera setup flipped, the angle
    // changed) must not clobber a pick the founder just made on this
    // same project before it saved: a pick that is still offered
    // survives the re-derivation. A pick the new list no longer offers
    // — an outdoor place under a fixed camera — falls out instead,
    // which is the section's ineligible-value pattern: the pick reads
    // empty and the section names why (ADR 0220).
    const sameProject = matchedProjectRef.current === project?.id;
    matchedProjectRef.current = project?.id;
    const { visual: savedVisual, location: savedLocation } = savedDirectionsRef.current;
    const matchPart = (text, list) =>
      (list || []).find((option) => text && text.toLowerCase().includes(option.toLowerCase())) || "";
    setDirSel((previous) => {
      const keep = (pick, list) =>
        sameProject && pick && (list || []).includes(pick) ? pick : "";
      return {
        location: matchPart(savedLocation, directionOptions.location) || matchPart(savedVisual, directionOptions.location) || keep(previous.location, directionOptions.location),
        // No Lighting control reads this slot any more; it is kept so a wardrobe
        // pick recomposes the strategy's own lighting word instead of dropping it.
        lighting: matchPart(savedVisual, directionOptions.lighting) || keep(previous.lighting, directionOptions.lighting),
        wardrobe: matchPart(savedVisual, directionOptions.wardrobe) || keep(previous.wardrobe, directionOptions.wardrobe),
      };
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
        cameraSetup,
      });
      const fresh = (data?.options || []).filter(Boolean);
      if (fresh.length > 0) {
        setDirectionOptions((previous) => {
          if (!previous) return previous;
          const pick = dirSel[field] || "";
          const merged = pick && !fresh.includes(pick) ? [pick, ...fresh] : [...fresh];
          return { ...previous, [field]: merged };
        });
      } else {
        // An empty success is the failure wearing a 200 (ADR 0257):
        // the endpoint fails loudly when nothing survives its filters,
        // and the hook never swallows an empty list either — the
        // section's error line names it instead of the button dying
        // silently in the founder's hand.
        setRefreshError("AI direction options failed. Please try again.");
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
    directionSettled,
    dirSel,
    pickScenePart,
    refreshingField,
    refreshError,
    refreshDirectionField,
    refreshProps,
  };
}
