import { useCallback, useEffect, useRef, useState } from "react";
import { api, getErrorMessage } from "../lib/api";

/**
 * Angle-step lifecycle: angles + verdict evidence, the viewed-state the
 * gated Review recovery copies read, live (billed) goal generation, and
 * the regenerate handlers. Extracted from CreateVideo.jsx verbatim; the
 * page keeps the draft, the profile/goal/template picks and the step, and
 * talks to this hook over the returned setters (the deep-link load and
 * selectProfile still clear angles/evidence through them).
 *
 * The angle step itself renders its lists on open (Part 3 removed the
 * click-to-reveal gate there); the reveal state below now serves only
 * Review's gated copies. Its discipline is unchanged: switching apps
 * re-arms both, a new angle resets the goals reveal, and a pick bypasses
 * the gates via the derived angle/objective the page still owns.
 */
export function useWizardAngleStep({ profileId, angleId, objective, project, dispatchDraft }) {
  const [angles, setAngles] = useState([]);
  // The GOAL axis of the verdict tally, keyed by objective name and fetched
  // with the angles (`objective_evidence` on the same response). Own state,
  // because it is not per angle: a goal's verdicts are shared across kinds, so
  // they cannot hang off one angle row. Cleared wherever angles are cleared.
  const [objectiveEvidence, setObjectiveEvidence] = useState({});
  // The intersection axis: kind × objective, keyed "kind‖objective". Own
  // state for the same reason as objectiveEvidence — it is not per angle.
  const [pairEvidence, setPairEvidence] = useState({});
  // The whole-video verdict axis (ADR 0124), keyed by objective name like
  // objectiveEvidence but tallied from the frozen verdict bundles — the
  // live signal beside the record axes above. Fetched with the angles
  // (`verdict_objective_evidence` on the same response) and refreshed by
  // the live-goals response; a pure read either way, never a trigger.
  const [verdictObjectiveEvidence, setVerdictObjectiveEvidence] = useState({});
  const adoptAngles = useCallback((data, onAngles = () => {}) => {
    setAngles(data?.angles || []);
    setObjectiveEvidence(data?.objective_evidence || {});
    setPairEvidence(data?.pair_evidence || {});
    setVerdictObjectiveEvidence(data?.verdict_objective_evidence || {});
    onAngles(data?.angles || []);
    return data?.angles;
  }, []);
  // Angles can be generated from in here, not just on the profile page:
  // sending the founder out of the wizard to make an optional angle usable
  // was a round trip the flow never offered a way back from.
  const [generatingAngles, setGeneratingAngles] = useState(false);
  const [angleError, setAngleError] = useState(null);
  // Viewed-state for angles, read only by the gated Review recovery copy
  // (the angle step shows the list on open). Behind that gate the list
  // appears on the click, never as a finished list on landing — and
  // "Regenerate" only ever appears beside a visible list, i.e. when there
  // is a current generation to be unhappy with. The reveal lasts for the
  // visit, not the mount: entering the step without a pick re-arms it (see
  // the page), so navigating away and back never counts a stale list as
  // viewed for an unpicked founder. A pick bypasses the gate entirely — a
  // draft or deep link that already names an angle has been viewed by
  // definition.
  const [anglesRevealed, setAnglesRevealed] = useState(false);
  const revealAngles = useCallback(() => {
    setAnglesRevealed(true);
  }, []);
  // Whether the angles in state were generated in-session (a generate
  // click or in-list regenerate) rather than loaded as cached rows from an
  // earlier approval. It names the Review gate's button: a fresh set is
  // revealed free there ("Show your angles"), while the gate's click over
  // a cached set regenerates instead of dressing a stale reveal up as
  // current. On the angle step the cached set simply renders, its age
  // line beside Regenerate. Reset with the reveal itself whenever the app
  // changes.
  const [anglesSessionFresh, setAnglesSessionFresh] = useState(false);
  // Cycling goal suggestions on the selected angle. Persists server-side per
  // angle, so the re-read of the angles list is the new state.
  const [cyclingGoals, setCyclingGoals] = useState(false);
  // Live goals for the selected angle, generated only on the founder's
  // click. Null until then: the angle step shows the persisted six, the
  // gated Review copies show their gate.
  const [liveGoals, setLiveGoals] = useState(null);
  const [liveGoalsLoading, setLiveGoalsLoading] = useState(false);
  const [liveGoalsError, setLiveGoalsError] = useState(null);
  // Viewed-state for goals, the goals analogue of the angles state above,
  // read only by the gated Review recovery copies: behind that gate, one
  // "Generate goals" CTA, never the facet-ordered list on landing. The
  // reveal lasts for the visit: entering the step without a pick re-arms
  // it (see the page), so navigating away and back never counts a stale
  // list as viewed for an unpicked founder. A pick bypasses the gate
  // entirely — a draft or deep link that already names a goal has been
  // viewed by definition. A set generated in-session is revealed free on
  // step re-entry, so returning never spends a second call.
  const [goalsRevealed, setGoalsRevealed] = useState(false);
  const revealGoals = useCallback(() => {
    setGoalsRevealed(true);
  }, []);
  const [angleRegenNotice, setAngleRegenNotice] = useState(null);
  // The branded confirmation the branded-dialog change (ADR 0210) puts in
  // place of the browser's confirm: the pending cost, held while the dialog
  // is open, and the resolver for the click that is waiting on its answer.
  // The spend itself stays behind the answer — opening the dialog calls
  // nothing, and cancelling resolves the waiting handler as a refusal.
  const [angleRegenConfirm, setAngleRegenConfirm] = useState(null);
  const angleRegenConfirmResolverRef = useRef(null);
  const settleAngleRegenConfirm = useCallback((ok) => {
    const resolve = angleRegenConfirmResolverRef.current;
    angleRegenConfirmResolverRef.current = null;
    setAngleRegenConfirm(null);
    if (resolve) resolve(ok);
  }, []);
  const requestAngleRegenConfirm = useCallback((affected) => {
    if (angleRegenConfirmResolverRef.current) {
      return Promise.resolve(false);
    }
    return new Promise((resolve) => {
      angleRegenConfirmResolverRef.current = resolve;
      setAngleRegenConfirm({ affected });
    });
  }, []);
  const confirmAngleRegen = useCallback(() => {
    settleAngleRegenConfirm(true);
  }, [settleAngleRegenConfirm]);
  const cancelAngleRegen = useCallback(() => {
    settleAngleRegenConfirm(false);
  }, [settleAngleRegenConfirm]);
  // What a completed angle regen cost: how many of the profile's drafts were
  // built on angles it replaced. Shown as a one-time receipt on the angle
  // step only (ADR 0198) — Review carries its own live signal (the rebuild
  // button), so the receipt no longer duplicates there. It clears when the
  // founder dismisses it, leaves the angle step, picks another angle, or
  // completes the owed rebuild, and once cleared by any route it never
  // reappears for that regen: nothing re-derives it. Count of 0 sets
  // nothing: a clean regen is not news.
  const clearAngleRegenNotice = useCallback(() => {
    setAngleRegenNotice(null);
  }, []);
  useEffect(() => {
    setAnglesRevealed(false);
    setGoalsRevealed(false);
    setAnglesSessionFresh(false);
    setAngleRegenNotice(null);
    settleAngleRegenConfirm(false);
  }, [profileId, settleAngleRegenConfirm]);
  useEffect(() => {
    setLiveGoals(null);
    setLiveGoalsError(null);
    setGoalsRevealed(false);
  }, [angleId]);
  // Regenerating the audience angles without leaving the wizard. Offered on
  // a populated list and behind the Review gate alike, because the
  // regenerate endpoint keeps hand-written angles server-side: what the
  // founder wrote on the profile page survives this call. (The bare generate
  // endpoint replaces the whole set and stays empty-list-only — that
  // distinction is why a populated list never uses it.)
  //
  // But generated angles that have a project built on them are deleted and
  // rewritten fresh: the draft survives, the story it was planned around does
  // not. The cost is knowable BEFORE the click — the regen-impact preflight
  // runs the same count the endpoint reports afterwards — so the confirm
  // fires exactly when that count is non-zero (any draft on this profile
  // planned around a generated angle, not only the draft on the selected
  // angle) and names the cost before it happens instead of two screens
  // later. A failed preflight falls back to the selected-angle check
  // rather than dropping the warning silently or blocking the click.
  //
  // Reports success so the gated copy can open the list only on a real
  // fresh set: a failed spend leaves the gate (and its error) in place.
  const runAngleRegeneration = useCallback(async () => {
    setGeneratingAngles(true);
    setAngleError(null);
    setAngleRegenNotice(null);
    try {
      const data = await api.regenerateContentAngles(profileId, { objective });
      const fresh = adoptAngles(data) || [];
      // Replacement rows carry new ids: a pick aimed at the old set would
      // dangle and the goal picker would collapse to its wait state just
      // when fresh options arrived. A surviving row (a kept manual angle)
      // keeps the founder's pick; otherwise park on the strongest new one.
      if (!fresh.some((a) => a && a.id === angleId)) {
        dispatchDraft({ type: "angle-selected", id: fresh.length > 0 ? fresh[0].id : "" });
      }
      const affected = Number(data?.projects_affected) || 0;
      if (affected > 0) {
        // Short receipt, named next step (ADR 0210): the confirmation has
        // already carried the detail, so the receipt states the outcome
        // once and the button below carries the founder to Review.
        setAngleRegenNotice(
          affected === 1
            ? "Regenerated. 1 draft lost its story. Rebuild its strategy at Review."
            : `Regenerated. ${affected} drafts lost their stories. Rebuild their strategies at Review.`
        );
      }
      if (!data.angles?.length) {
        setAngleError("The model returned no usable angles. Try again.");
      }
      // Fresh in-session: step re-entry re-arms the gate as a free reveal
      // of this set instead of spending again.
      setAnglesSessionFresh(true);
      return true;
    } catch (err) {
      setAngleError(getErrorMessage(err));
      return false;
    } finally {
      setGeneratingAngles(false);
    }
  }, [profileId, angleId, objective, adoptAngles, dispatchDraft]);
  // The click behind Regenerate: preflight first, the branded dialog when
  // a draft is at stake, and the spend only after the founder confirms.
  const handleRegenerateAngles = useCallback(async () => {
    if (!profileId) return false;
    const selectedHasProject = Boolean(project && project.content_angle_id && project.content_angle_id === angleId);
    let affected = null;
    try {
      const impact = await api.getAngleRegenImpact(profileId);
      affected = Number(impact?.projects_affected) || 0;
    } catch {
      affected = null;
    }
    const mustConfirm = affected === null ? selectedHasProject : affected > 0;
    if (mustConfirm) {
      const ok = await requestAngleRegenConfirm(affected && affected > 0 ? affected : null);
      if (!ok) return false;
    }
    return runAngleRegeneration();
  }, [profileId, angleId, project, requestAngleRegenConfirm, runAngleRegeneration]);
  // The generate action behind the angle panel's "Generate angles" CTA,
  // which since Part 3 renders only over an empty set on the angle step
  // (the Review copy's gate button redirects here instead of calling
  // this). The handler keeps its full three-way shape from the gated era:
  // a fresh in-session set is revealed free, a cached set regenerates —
  // the regenerate endpoint keeps hand-written angles server-side, where
  // the bare generate endpoint would discard them — and from empty the
  // bare generate endpoint runs, safe because nothing exists to discard.
  // The first two branches are unreachable through the panel now that a
  // populated set renders its list directly; they stay because the
  // handler's contract (reveal bookkeeping included) is shared with the
  // Review gate's state, and narrowing it is a separate decision.
  const handleGenerateAngles = useCallback(async () => {
    if (!profileId || generatingAngles) return;
    if (angles.length > 0 && anglesSessionFresh) {
      revealAngles();
      return;
    }
    if (angles.length > 0) {
      // Fresh over cached: the same call the Regenerate button makes, then
      // open the list the gate was hiding. It reports its own errors and
      // notices, so a failed spend leaves the gate and its error in place.
      const ok = await handleRegenerateAngles();
      if (ok) {
        revealAngles();
      }
      return;
    }
    setGeneratingAngles(true);
    setAngleError(null);
    try {
      // A picked objective aims the set at this video; nothing picked reads
      // exactly as before.
      const data = await api.generateContentAngles(profileId, { objective });
      const fresh = adoptAngles(data) || [];
      // Generated in-session at the founder's own click: there is nothing to
      // gate, so the fresh six render immediately.
      revealAngles();
      setAnglesSessionFresh(true);
      // The fresh set has new row ids, so a previous pick would dangle and
      // the goal picker would collapse to its wait state. Park the founder
      // on the strongest new angle; an empty set clears the pick.
      if (!fresh.some((a) => a && a.id === angleId)) {
        dispatchDraft({ type: "angle-selected", id: fresh.length > 0 ? fresh[0].id : "" });
      }
      if (!data.angles?.length) {
        setAngleError("The model returned no usable angles. Try again.");
      }
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setGeneratingAngles(false);
    }
  }, [profileId, angleId, generatingAngles, angles.length, anglesSessionFresh, revealAngles, handleRegenerateAngles, objective, adoptAngles]);
  // Cycle the selected angle's six goal suggestions. Free (no model call),
  // and the server persists the variant, so re-reading the list brings back
  // the exact new order for every consumer of the angles state.
  const handleRegenerateGoals = useCallback(async () => {
    if (!profileId || !angleId) return;
    setCyclingGoals(true);
    try {
      await api.regenerateContentAngleGoals(profileId, angleId);
      const data = await api.getContentAngles(profileId);
      adoptAngles(data);
      // Shuffle rotates the persisted suggestions; the angle's live set must
      // not keep shadowing them (AngleGoalPicker prefers liveOrdered). The
      // reveal stays (goalsRevealed) so the rotated six show immediately.
      setLiveGoals(null);
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setCyclingGoals(false);
    }
  }, [profileId, angleId, adoptAngles]);
  // Live goals for the selected angle. Billed, so this runs only on the
  // founder's click — never on angle pick. On failure the error names the
  // failure and whatever was showing stays: behind the Review gate that is
  // the gate itself; on the angle step it is the persisted six, which are
  // the initial list there now, not a fallback.
  const handleGenerateGoals = useCallback(async () => {
    if (!profileId || !angleId || liveGoalsLoading) return;
    setLiveGoalsLoading(true);
    setLiveGoalsError(null);
    try {
      const data = await api.generateAngleGoals(profileId, angleId);
      setLiveGoals(Array.isArray(data?.goals) ? data.goals : []);
      if (data?.verdict_objective_evidence) {
        setVerdictObjectiveEvidence(data.verdict_objective_evidence);
      }
      setGoalsRevealed(true);
    } catch (err) {
      setLiveGoals(null);
      setLiveGoalsError(getErrorMessage(err));
    } finally {
      setLiveGoalsLoading(false);
    }
  }, [profileId, angleId, liveGoalsLoading]);

  return {
    angles, setAngles, objectiveEvidence, setObjectiveEvidence, pairEvidence,
    verdictObjectiveEvidence, setVerdictObjectiveEvidence,
    adoptAngles, generatingAngles, angleError, setAngleError,
    anglesRevealed, setAnglesRevealed, revealAngles, anglesSessionFresh,
    cyclingGoals, liveGoals, liveGoalsLoading, liveGoalsError,
    goalsRevealed, setGoalsRevealed, revealGoals, angleRegenNotice,
    clearAngleRegenNotice, angleRegenConfirm, confirmAngleRegen,
    cancelAngleRegen,
    handleGenerateAngles, handleRegenerateAngles,
    handleGenerateGoals, handleRegenerateGoals,
  };
}
