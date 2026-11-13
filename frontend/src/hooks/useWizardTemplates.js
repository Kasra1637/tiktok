import { useCallback, useMemo, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

const emptyFit = () => ({ reasons: [], limitations: [] });

/** Template loading is a separate lifecycle from draft writes and plan saves. */
export function useWizardTemplates({ profileId, angleId, objective, hookLine = "", middle = "" }) {
  const [ranked, setRanked] = useState({ key: "", rows: [], shared: emptyFit(), error: null });
  const [tailored, setTailored] = useState({ key: "", templates: [] });
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState(null);
  const recRequestRef = useRef(0);
  const tailorRequestRef = useRef(0);
  // Latest wizard identity: a tailor flight that resolves after the founder
  // moves on must not reload recommendations for the profile/angle it left.
  const latestRef = useRef({ profileId, angleId, objective, hookLine, middle });
  latestRef.current = { profileId, angleId, objective, hookLine, middle };

  const clearRecommendations = useCallback(() => {
    setRanked((previous) => ({ ...previous, rows: [], shared: emptyFit(), error: null }));
  }, []);

  // The picker shows exactly three templates (ADR 0096). The server
  // guarantees the count; the client asks for three so both agree. Called
  // only inside a tailoring flight — never as an effect: no template
  // request, free or billed, fires on the goal pick (ADR 0098).
  const loadRecommendations = useCallback(async (pid, aid, oid = objective, hook = hookLine, mid = middle) => {
    if (!pid) return;
    const request = ++recRequestRef.current;
    // The approved spoken words shape each card's display (ADR 0108), so
    // they ride the same request and key: a new plan is a new set of cards.
    const key = `${pid || ""}:${aid || ""}:${oid || ""}:${hook || ""}:${mid || ""}`;
    setRanked({ key, rows: [], shared: emptyFit(), error: null });
    try {
      const rec = await api.getTemplateRecommendations(pid, {
        angle_id: aid || undefined, objective: oid || undefined,
        ...(String(hook || "").trim() ? { hook_line: String(hook).trim() } : {}),
        ...(String(mid || "").trim() ? { middle: String(mid).trim() } : {}),
        limit: 3,
      });
      if (recRequestRef.current !== request) return;
      setRanked({
        key, rows: rec.recommendations || [], error: null,
        shared: {
          reasons: Array.isArray(rec.shared_reasons) ? rec.shared_reasons : [],
          limitations: Array.isArray(rec.shared_limitations) ? rec.shared_limitations : [],
        },
      });
    } catch (err) {
      if (recRequestRef.current !== request) return;
      setRanked({ key, rows: [], shared: emptyFit(), error: getErrorMessage(err) });
    }
  }, [objective, hookLine, middle]);

  const runTailoring = useCallback(async (regenerate) => {
    if (!profileId || !objective) return;
    // The set is generated from this angle's Problem and First 3 Seconds
    // Promise, so the angle is part of the request, not just of the ranking
    // (ADR 0089). A set for another angle is a different set.
    const key = `${profileId}:${objective}:${angleId || ""}`;
    const request = ++tailorRequestRef.current;
    const startPid = profileId;
    const startAid = angleId;
    const startObjective = objective;
    setTailoring(true);
    setTailorError(null);
    try {
      const res = await api.ensureObjectiveTemplates(startPid, {
        objective: startObjective,
        ...(startAid ? { angle_id: startAid } : {}),
        ...(regenerate ? { regenerate: true } : {}),
      });
      if (tailorRequestRef.current !== request) return;
      setTailored({ key, templates: Array.isArray(res?.templates) ? res.templates : [] });
      if (res.error) setTailorError(res.error);
    } catch (err) {
      if (tailorRequestRef.current !== request) return;
      setTailored({ key, templates: [] });
      setTailorError(getErrorMessage(err));
    }
    // The display read comes after the POST settles or fails, while the
    // founder is still watching: a fresh or cached set needs the score order
    // for its cards (ordering and the ADR 0096 backfill), and the documented
    // fallback on refusal is the curated list — "Your curated picks still
    // work" — which the same read surfaces. The read is a purely-scored scan
    // of stored rows, the billed part is the POST above, so it rides the
    // same click without spending a second model call — and, riding no
    // effect, it never fires on the goal pick: switching goals queues
    // nothing at all (ADR 0098).
    //
    // The refresh lands only when the wizard still shows the
    // profile/angle/objective the tailor ran for. Without this, a slow
    // tailor for app A reloads app B's list when it lands.
    const latest = latestRef.current;
    if (
      latest.profileId === startPid &&
      latest.angleId === startAid &&
      latest.objective === startObjective
    ) {
      await loadRecommendations(startPid, startAid, startObjective, latest.hookLine, latest.middle);
    }
    if (tailorRequestRef.current === request) setTailoring(false);
  }, [profileId, objective, angleId, loadRecommendations]);

  // Tailoring is a billed generation (ADR 0087), so it never rides an effect
  // on the goal pick, and since the ranking read rides the same flight no
  // template request of any kind queues on the pick: switching goals fires
  // nothing until the founder asks. The page triggers it — the goals-section
  // Generate CTA, or the header Regenerate for a deliberate fresh set.

  // Scoped to the angle as well as the goal: templates are generated from the
  // angle's Problem and First 3 Seconds Promise, so a set made for one angle
  // must not present itself as the set for another (ADR 0089).
  const tailorKey = profileId && objective
    ? `${profileId}:${objective}:${angleId || ""}`
    : "";
  const recRequestKey = `${profileId || ""}:${angleId || ""}:${objective || ""}:${hookLine || ""}:${middle || ""}`;
  const tailoredReady = Boolean(tailorKey && tailored.key === tailorKey && tailored.templates.length > 0);
  const tailorFallbackVisible = Boolean(
    tailorKey && tailored.key === tailorKey && !tailored.templates.length && tailorError && !tailoring
  );
  const recommendationsVisible = Boolean(
    objective && ranked.key && ranked.key === recRequestKey && (tailoredReady || tailorFallbackVisible)
  );
  // Exactly three templates, always (ADR 0096): the server guarantees the
  // count, and this list is the display contract. If ranking drops a tailored
  // row, backfill from the current ranked rows so the picker never shows a
  // partial choice — but only from rows that are themselves tailored/custom
  // templates, never from pre-made ones. The bespoke list is the only
  // promise the picker makes ("Tailored template for this app"), and a pre-made card
  // appearing alongside it is a leak of a different kind.
  const visibleRecommendations = useMemo(() => {
    if (!recommendationsVisible) return [];
    if (!tailoredReady) return ranked.rows.slice(0, 3);
    const ids = new Set(tailored.templates.map((template) => template?.id).filter(Boolean));
    const matched = ranked.rows.filter((row) => ids.has(row?.template?.id));
    const seen = new Set(matched.map((row) => row?.template?.id).filter(Boolean));
    const backfill = ranked.rows.filter((row) => {
      if (seen.has(row?.template?.id)) return false;
      const template = row?.template || {};
      return template.origin === "custom" || template.brand_profile_id;
    });
    return [...matched, ...backfill].slice(0, 3);
  }, [recommendationsVisible, tailoredReady, tailored.templates, ranked.rows]);

  return {
    recommendations: ranked.rows, sharedFit: ranked.shared, recError: ranked.error,
    recKey: ranked.key, recRequestKey,
    clearRecommendations, loadRecommendations, runTailoring,
    tailoring, tailorError, tailorKey, tailoredReady,
    recommendationsVisible, visibleRecommendations,
  };
}
