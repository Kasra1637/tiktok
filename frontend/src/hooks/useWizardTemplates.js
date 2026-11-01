import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

const emptyFit = () => ({ reasons: [], limitations: [] });

/** Template loading is a separate lifecycle from draft writes and plan saves. */
export function useWizardTemplates({ profileId, angleId, objective, active }) {
  const [ranked, setRanked] = useState({ key: "", rows: [], shared: emptyFit(), error: null });
  const [tailored, setTailored] = useState({ key: "", templates: [] });
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState(null);
  const [tailorCount, setTailorCount] = useState(0);
  const recRequestRef = useRef(0);
  const tailorKeyRef = useRef("");

  const clearRecommendations = useCallback(() => {
    setRanked((previous) => ({ ...previous, rows: [], shared: emptyFit(), error: null }));
  }, []);

  const loadRecommendations = useCallback(async (pid, aid) => {
    if (!pid) return;
    const request = ++recRequestRef.current;
    const key = `${pid || ""}:${aid || ""}:${objective || ""}`;
    setRanked({ key, rows: [], shared: emptyFit(), error: null });
    try {
      const rec = await api.getTemplateRecommendations(pid, {
        angle_id: aid || undefined, objective: objective || undefined, limit: 6,
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
  }, [objective]);

  useEffect(() => {
    loadRecommendations(profileId, angleId);
  }, [profileId, angleId, loadRecommendations]);

  const runTailoring = useCallback(async (regenerate) => {
    if (!profileId || !objective) return;
    const key = `${profileId}:${objective}`;
    setTailoring(true);
    setTailorError(null);
    try {
      const res = await api.ensureObjectiveTemplates(profileId, {
        objective, ...(regenerate ? { regenerate: true } : {}),
      });
      if (tailorKeyRef.current !== key) return;
      setTailored({ key, templates: Array.isArray(res?.templates) ? res.templates : [] });
      if (res.generated) await loadRecommendations(profileId, angleId);
      if (res.error) setTailorError(res.error);
    } catch (err) {
      if (tailorKeyRef.current !== key) return;
      setTailored({ key, templates: [] });
      setTailorError(getErrorMessage(err));
    } finally {
      if (tailorKeyRef.current === key) setTailoring(false);
    }
  }, [profileId, objective, angleId, loadRecommendations]);

  useEffect(() => {
    if (!active || !profileId || !objective) return;
    const key = `${profileId}:${objective}`;
    if (tailorKeyRef.current === key) return;
    tailorKeyRef.current = key;
    runTailoring(false);
  }, [active, profileId, objective, runTailoring]);

  const tailorKey = profileId && objective ? `${profileId}:${objective}` : "";
  const recRequestKey = `${profileId || ""}:${angleId || ""}:${objective || ""}`;
  const tailoredReady = Boolean(tailorKey && tailored.key === tailorKey && tailored.templates.length > 0);
  const tailorFallbackVisible = Boolean(
    tailorKey && tailored.key === tailorKey && !tailored.templates.length && tailorError && !tailoring
  );
  const recommendationsVisible = Boolean(
    objective && ranked.key && ranked.key === recRequestKey && (tailoredReady || tailorFallbackVisible)
  );
  const visibleRecommendations = useMemo(() => {
    if (!recommendationsVisible) return [];
    if (!tailoredReady) return ranked.rows;
    const ids = new Set(tailored.templates.map((template) => template?.id).filter(Boolean));
    return ranked.rows.filter((row) => ids.has(row?.template?.id));
  }, [recommendationsVisible, tailoredReady, tailored.templates, ranked.rows]);

  const tailorTotal = Math.max(visibleRecommendations.length, 1);
  useEffect(() => {
    if (!tailoring) {
      setTailorCount(0);
      return undefined;
    }
    setTailorCount(1);
    const timer = setInterval(() => {
      setTailorCount((count) => Math.min(count + 1, tailorTotal));
    }, 450);
    return () => clearInterval(timer);
  }, [tailoring, tailorTotal]);

  return {
    recommendations: ranked.rows, sharedFit: ranked.shared, recError: ranked.error,
    recKey: ranked.key, recRequestKey,
    clearRecommendations, loadRecommendations, runTailoring,
    tailoring, tailorError, tailorCount, tailorTotal, tailorKey, tailoredReady,
    recommendationsVisible, visibleRecommendations,
  };
}
