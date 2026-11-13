import { RecommendationCard, TemplateShape, AngleSelector, AngleGoalPicker, PresenterPhotoControl, MissingRequirements, TEMPLATE_PHOTO_ID } from "../components/studio/SelectionPanels";
import { DirectionSelect, PlanPhaseLine } from "../components/studio/ReviewPanels";
import HookLineEditor from "../components/studio/HookLineEditor";
import ScriptLineRewrites from "../components/studio/ScriptLineRewrites";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { createWizardDraft, wizardDraftReducer } from "./wizardDraft";
import { useWizardTemplates } from "../hooks/useWizardTemplates";
import { useWizardAngleStep } from "../hooks/useWizardAngleStep";
import { useWizardDirections } from "./useWizardDirections";
import { Link, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { CONTROL_CLASS } from "../components/formControls";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import EmptyState from "../components/EmptyState";
import { GroupLabel } from "../components/SectionCard";
import { Disclosure } from "../components/Disclosure";
import { Skeleton } from "../components/ui/skeleton";
import { useTourEligibility } from "../components/onboarding/OnboardingProvider";

import HookContinuityPanel from "../components/HookContinuityPanel";
import GenerationPanel from "../components/GenerationPanel";
import { DemoCtaGenerationEditor } from "./DemoCtaStudio";
import { ThumbPair } from "../components/ThumbPair";
import { ComponentThumbs } from "../components/ComponentThumbs";
import { api, getErrorMessage } from "../lib/api";
import { BUSY_ETA_SECONDS } from "../lib/busyEta";
import { recordSignal, recordThumb, recordBehavior, classifyScriptEdit } from "../lib/feedback";
import { rememberDraft } from "../lib/recentDraft";
import {
  partitionProfiles,
  profileLabel,
  describeUnapprovedCount,
  describeEmptySelection,
} from "../lib/profileSelection";
// requiredAssetStatus left with the per-requirement checklist it fed. The photo
// section now reports the one requirement directly, next to the photograph, so
// the template card only has to say whether anything is still owed.
import {
  blockingRequirements,
} from "../lib/templateRequirements";
import { sentenceCase } from "../lib/copyCase";
import { useReducedMotionPreference } from "../lib/reducedMotion";

import { readPieceSeconds } from "../lib/videoLength";
// FileText was the "Creative plan" step's icon. That step held nothing but a
// button and is now the top of Review, so the icon went with it.
import { Clapperboard, TriangleAlert as AlertTriangle, Briefcase, Target, Image as ImageIcon, Check, Sparkles, RefreshCw, Save, CircleCheck as CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, FileText, AudioLines, ListChecks, ShieldCheck, Smartphone, X, Lock } from "lucide-react";
// toast left with AttachedPhoto, the only place on this page that raised one.
// Detaching now happens inside the photo section, which reports its own
// outcome.

// The order is the product, and it is deliberate.
//
//   profile -> angle+goal+template+photo -> review+submit (plan above, render below)
//     -> finish (Demo + CTA, opening on the render the step above made)
//
// The script is written and read by the founder
// BEFORE any video is rendered. The last step then renders the piece that
// script describes: the strategy is built from the approved plan, so the words
// the founder read are the words that get rendered.
//
// This was the other way round. The hook came first, so a founder approved a
// strategy on trust, rendered, and only then read a script describing a
// different video — with the craft check running against
// text nobody had looked at before the render.
/**
 * The steps, in order.
 *
 * Was seven, then five. "Assets" and "Creative plan" were steps that existed
 * only to hold a button, and both are now part of the step they belonged to;
 * then angle, goal, template and photo merged into one screen (choosing
 * precedes seeing what the choice ranks, with no step change between), and
 * the plan and the render merged into Review & submit (reading precedes the
 * model call, top to bottom of one screen):
 *
 *   - Assets was a photo upload. The template step already says what a template
 *     needs from you and already links to it, so the upload moved there and the
 *     step went from "pick a template, then leave to attach a photo, then come
 *     back" to one continuous decision.
 *   - Creative plan was a "Generate plan" button whose result you immediately had
 *     to go to the next screen to read. It is now the top of Review, which is
 *     where the plan is actually read and edited.
 *
 * The step count is not a vanity metric; every extra step is a place a founder
 * can stall with nothing to do, and nothing is generated until the last one.
 *
 * Last, because this is the only step that calls the model. The plan is text
 * only, and it is what that step renders.
 *
 * Named for what it produces rather than for the old hook-first workflow: one
 * render containing a hook and a middle. The demo and the close are the
 * founder's own footage, added afterwards in their editor.
 */
/* Three steps, not five: angle and goal share a screen with the templates
   they rank and the photo that attaches to them, and the script plan shares
   a screen with the render it approves. Nothing was cut — choosing still
   precedes seeing what the choice ranks, and reading still precedes the
   model call — there are just no steps whose only job was walking to the
   next one. */
/* The fourth step is not a walking step either, which is why it earns its
   place under the rule above: it holds the Demo + CTA editor itself, with
   the finished render already loaded. The flow used to end at the render —
   download it, then go and find the editor as a separate surface that
   started blank and made the founder pick the clip they had just made.
   Now the render's own step is the finish: continue, and the clip is open
   in the editor, ready for the founder's demo and closing message. The
   standalone /demo-cta route stays for re-edits and the founder's own
   footage; inside a flow, the finish is a step, not a detour. */
const LEGACY_STEP_KEYS = { template: "angle", hook: "review" };
const STEPS = [
  { key: "profile", label: "App Profile", icon: Briefcase },
  { key: "angle", label: "Audience & template", icon: Target },
  { key: "review", label: "Review & submit", icon: CheckCircle2 },
  { key: "finish", label: "Demo + CTA", icon: Smartphone },
];

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * The facts an approval actually judges, as review rows for the profile
 * step's inline approval. The four rows mirror the server's approval gaps
 * (_approval_gaps in the brands router) one for one — description, core
 * features, a use, a linked outcome — so what the founder reads here is
 * exactly what the approve endpoint will refuse or accept on, and a blank
 * row names itself instead of hiding the way a rendered-only-if-present
 * field list would.
 */
function profileApprovalFacts(p) {
  const list = (v) => (Array.isArray(v) ? v.map((x) => String(x || "").trim()).filter(Boolean) : []);
  const uses = [p?.usage_moments, p?.primary_use_cases, p?.problems_solved]
    .map(list)
    .find((items) => items.length > 0) || [];
  const outcomes = (Array.isArray(p?.outcome_statements) ? p.outcome_statements : [])
    .map((o) => (typeof o === "string" ? o : String(o?.outcome || "")).trim())
    .filter(Boolean);
  return [
    { label: "What it does", value: String(p?.brand_description || "").trim() },
    { label: "Core features", value: list(p?.core_features).join(", ") },
    { label: "People use it for", value: uses.join(", ") },
    { label: "Outcomes it promises", value: outcomes.join(", ") },
  ];
}

/**
 * The live count for one spoken line.
 *
 * The browser counts the field as it is typed; the server's own targets and
 * ceiling (project.spoken_check, measured on the saved plan a render
 * validates) say what fits. The old "Script fit details" disclosure reported
 * the saved plan behind a click — the budget belongs beside the words it
 * measures, moving on every keystroke.
 */
function spokenCountNote(text, spec) {
  const chars = String(text || "").trim().length;
  const target = Number(spec?.target) || 0;
  const ceiling = Number(spec?.ceiling) || 0;
  if (ceiling && chars > ceiling) {
    return `${chars} characters \u2014 past the ${ceiling} these seconds can speak.`;
  }
  if (target) {
    return chars > target
      ? `${chars} characters, aiming for about ${target} \u2014 longer is a choice, not a fault.`
      : `${chars} characters, aiming for about ${target}.`;
  }
  return `${chars} characters.`;
}

/** The craft score's band in the founder's terms. It is a mirror, not a gate:
 *  no band refuses a render, and the copy says so. */
const QUALITY_BAND_NOTES = {
  distinctive: "Distinctive. The words are doing the work.",
  strong: "Strong. One craft note would sharpen it.",
  competent_but_generic:
    "Competent but generic. The hook or the spoken line is leaving performance on the table.",
  performance_risk: "Weak. Likely to lose the scroll or sound written.",
  off_brief: "Off-brief. Rewrite before rendering.",
};

function qualityBandNote(report) {
  return QUALITY_BAND_NOTES[report?.band] || "Advisory craft score for the saved words.";
}

/** What each progress state means, in words. Used for the pill tooltip and
 *  the aria-label, because both a tick and a dashed border are shape-only. */
const STEP_STATE_COPY = {
  done: "done",
  todo: "not started",
  blocked: "needs something from you",
  locked: "locked",
};

/**
 * A template id the library no longer carries.
 *
 * The wizard treats an id that names no row as "not a pick" (see
 * effectiveTemplateId): the step stays blocked, the inline notice names the
 * gap, and the red button walks back to it. A 404 carrying this detail from
 * any write path is that same state arriving late — the row vanished between
 * picking and saving — so it must resolve to the same gap, never to banner
 * text no button on the page can fix, and never to a retry that 404s again.
 */
function isTemplateGoneError(err) {
  return (
    err?.response?.status === 404 &&
    String(err?.response?.data?.detail || "").includes("Template not found")
  );
}

// The banner copy for a vanished template. Identical to template-gone-notice
// so the banner and the step agree on what happened and what to do next.
const TEMPLATE_GONE_MESSAGE = "That template is no longer available — pick another below.";

/**
 * Whether each step is satisfied, in the wizard's own terms.
 *
 * Returns one entry per STEPS item in order. `blocked` is not an error state —
 * it is the only step that can be waiting on the founder, and it is
 * distinguished from `todo` because the remedy is different: a todo is
 * downstream of work not yet done, a blocked step is the next thing they must
 * do.
 *
 * Review counts as satisfied once a plan exists. It does NOT require the
 * plan to be marked ready: that is a deliberate final gate the founder sets
 * themselves after reading, and ticking the step for it would claim the
 * workflow is finished when the last read is still ahead of them.
 */
function stepCompletion({ profileId, objective, angleId, templateId, project, missingIdentity, hasEdits, hasFinishedRender }) {
  const hasPhoto = missingIdentity.length === 0;
  return STEPS.map((step) => {
    let state = "done";
    if (step.key === "profile") state = profileId ? "done" : "todo";
    // Angle, goal, template and photo are one step now, so one verdict: the
    // angle is still required (the strategy and the render are built around
    // it), and the step is only done when the template and its photo are
    // set too. Anything less reports what is still missing.
    else if (step.key === "angle") {
      state = angleId && objective && templateId && hasPhoto ? "done" : "blocked";
    } else if (step.key === "review") {
      // A plan with unsaved edits is not reviewed. The step says so itself, and
      // a tick here would tell the founder they had finished reading a script
      // they had changed and not stored. And the render below needs the photo,
      // so a plan without one leaves this step reporting what is owed.
      if (!project?.script_version) state = "todo";
      else if (hasEdits || (templateId && !hasPhoto)) state = "blocked";
    } else if (step.key === "finish") {
      // The finishing step is satisfied by the render itself. The demo and
      // closing message are the founder's optional craft on top of a
      // finished clip — the render panel already says "use it as is, or
      // open it in Demo + CTA" — so the step ticks when there is a finished
      // render for it to open on, and waits as a plain todo until then.
      // Requiring an export here would gate the journey on an edit the
      // product itself calls optional.
      state = hasFinishedRender ? "done" : "todo";
    }
    return { step, state };
  });
}

export default function CreateVideo() {
  const [params, setSearchParams] = useSearchParams();

  // The server's updated_at for each project this wizard has adopted from a
  // server response, so a row that is already current is never re-read or
  // re-adopted. Declared here, above every effect that reads or writes it: a
  // dep array is evaluated during render, and the deep-link load below uses it
  // long before the Review step that first needed it was in view.
  const syncedProjectsRef = useRef({});

  // The step mirrors into ?step= so "the Review step with this draft" is a
  // shareable link, the same mirror History keeps for its filters. State stays
  // the source of truth: the URL is read once here on load and follows state
  // after that, so a ?step= pointing past the founder's progress still lands
  // on a step whose guards say what is missing.
  const [step, setStep] = useState(() => {
    // Retired keys still land somewhere honest: a ?step=template link means
    // the merged angle step now, ?step=hook means the merged review step.
    const raw = params.get("step");
    const key = LEGACY_STEP_KEYS[raw] || raw;
    const at = STEPS.findIndex((s) => s.key === key);
    return at >= 0 ? at : 0;
  });
  useEffect(() => {
    // No write when the URL already says where we are: without this the
    // mount-time write would change params, re-fire the deep-link load below
    // (it depends on the params it reads), and loop the load on every step.
    if (params.get("step") === STEPS[step].key) return;
    setSearchParams(
      (prev) => {
        const next = new URLSearchParams(prev);
        next.set("step", STEPS[step].key);
        return next;
      },
      { replace: true }
    );
  }, [step, setSearchParams, params]);
  const [profiles, setProfiles] = useState([]);
  // Inline approval on the profile step: which draft is mid-approval, and
  // the refusal each draft last earned, keyed by profile id so one app's
  // gaps are never read under another app's name.
  const [approvingProfileId, setApprovingProfileId] = useState(null);
  const [approveErrors, setApproveErrors] = useState({});
  const [facets, setFacets] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [draft, dispatchDraft] = useReducer(wizardDraftReducer, {
    profile: params.get("profile") || "",
    angle: params.get("angle") || "",
    template: params.get("template") || "",
  }, createWizardDraft);
  const { selectedProfileId, angleId, templateId, objective, tone, project, edits } = draft;
  const receiveProject = useCallback((fresh) => {
    dispatchDraft({ type: "project-received", project: fresh });
  }, []);
  // The newest finished render for this project, and whether the lookup has
  // answered at all. The finishing step opens on this row and its pill ticks
  // from it, so it is resolved at the page level rather than inside the
  // step: a founder who jumps straight to ?step=finish gets the same answer
  // as one who watched the render complete. `undefined` is "not looked up
  // yet", `null` is "looked, and there is none" — the step shows a loading
  // line for the first and the honest missing-render panel for the second,
  // and never confuses the two. The render panel reports completions into
  // the same state as they land, so a render that finishes while the
  // founder sits on Review ticks the finishing step without a reload.
  const [finishedGeneration, setFinishedGeneration] = useState(undefined);
  useEffect(() => {
    setFinishedGeneration(undefined);
    if (!project?.id) return undefined;
    let cancelled = false;
    api
      .getGenerations({ studio_project_id: project.id, status: "completed", limit: 1 })
      .then((data) => {
        if (cancelled) return;
        setFinishedGeneration((data.generations || [])[0] || null);
      })
      .catch(() => {
        if (!cancelled) setFinishedGeneration(null);
      });
    return () => {
      cancelled = true;
    };
  }, [project?.id]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // A plan attempt ran and failed (or draft creation refused). While true,
  // Review shows the retry path instead of the generating spinner: without
  // this the failure state is indistinguishable from an attempt in flight,
  // and nothing re-fires on its own (ADR 0122), so the failure would read
  // as a step still deciding rather than a click that did not land. Cleared
  // whenever a new attempt starts.
  const [planFailed, setPlanFailed] = useState(false);
  // Confirm-on-arrival: a ?project= link that lands with an intact plan
  // (script_version > 0) says so once, so the founder knows the Review step
  // below is their render's plan and not a blank draft. Dismissible, and
  // re-armed only by a new project link — editing within the wizard never
  // brings it back.
  const [planBannerDismissed, setPlanBannerDismissed] = useState(false);

  // There is no length state and no intent state any more, and that is the
  // whole point of this step's current shape. Duration is computed: a template
  // declares the length its mechanic suits, the project seeds from it, and the
  // render is that long in one pass. `extendIntent` ("hook only" versus "extend
  // into a full video") asked a question about a chain that no longer exists —
  // there is no hook-only render to choose between.
  // Thumbs verdict on the saved Review plan: up advances to the render below,
  // down records the rejection and asks the AI for a fresh plan. Manual
  // editing stays untouched — this is an additive fast path, not a
  // replacement, so the craft check and ready gate keep working as before.
  const [reviewThumb, setReviewThumb] = useState(0);
  /* Review's two halves as sub-screens: "Read the plan" then "Render &
     result". One screen in view at a time so the plan's dozen fields stop
     competing with the render below. Not a new step — STEPS, ?step= and the
     pills are untouched — just focus within step three. Both halves stay
     mounted and switch with `hidden`, so nothing unmounts mid-poll and every
     existing query keeps working; this is a focus split, never a new gate. */
  const [reviewTab, setReviewTab] = useState("plan");
  const scriptVersion = Number(project?.script_version) || 0;
  const effectiveReviewTab = scriptVersion ? reviewTab : "plan";
  // A fresh plan needs reading before it renders: whenever a new version
  // arrives (first generate, regenerate, thumbs-down rewrite), land back on
  // the plan half even if the founder was looking at the render.
  useEffect(() => {
    if (scriptVersion) setReviewTab("plan");
  }, [scriptVersion]);
  // Walking the canvas leaves the opened section under the sticky rail, so a
  // step change scrolls its section into view after the paint, not before:
  // the element must exist first. The rail's height lives in the sections'
  // `scroll-mt-24`. Mount never scrolls — the page starts at the top.
  const steppedOnceRef = useRef(false);
  useEffect(() => {
    if (!steppedOnceRef.current) {
      steppedOnceRef.current = true;
      return;
    }
    requestAnimationFrame(() => {
      document
        .getElementById(`wizard-section-${STEPS[step].key}`)
        ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
    });
  }, [step]);
  // Consecutive AI refinements per saved plan version. Capped so a thumbs-down
  // loop can never spin the text model unboundedly on one plan.
  const reviewRefinesRef = useRef({});

  const profileId = project?.brand_profile_id || selectedProfileId;
  // Angle + goals lifecycle (angles/evidence state, click-to-view gates,
  // live billed goals, regenerate handlers) lives in its own hook; the
  // page keeps the draft, picks, step and plan, and clears through the
  // returned setters.
  const {
    angles, setAngles, objectiveEvidence, setObjectiveEvidence, pairEvidence,
    adoptAngles, generatingAngles, angleError, setAngleError,
    anglesRevealed, setAnglesRevealed, revealAngles, anglesSessionFresh,
    cyclingGoals, liveGoals, liveGoalsLoading, liveGoalsError,
    goalsRevealed, setGoalsRevealed, revealGoals, angleRegenNotice,
    handleGenerateAngles, handleRegenerateAngles,
    handleGenerateGoals, handleRegenerateGoals,
  } = useWizardAngleStep({ profileId, angleId, objective, project, dispatchDraft });

  const {
    recommendations, sharedFit, recError, recKey, recRequestKey, clearRecommendations,
    runTailoring, tailoring, tailorError,
    tailoredReady, recommendationsVisible, visibleRecommendations,
  } = useWizardTemplates({
    profileId, angleId, objective,
    // The approved spoken words shape each card's display when a plan
    // already exists, so cards never promise words nobody speaks (ADR 0108).
    hookLine: project?.hook_line || "",
    middle: project?.script || project?.spoken_middle || "",
  });
  // The reveal state survives for the Review recovery copies only: the
  // angle step itself renders its lists on open now (Part 3), but Review's
  // pickers stay gated, so what counts as "viewed" there is still tracked —
  // and switching apps re-arms it, so a set viewed for one app never counts
  // as viewed for another app's recovery panel.
  const angle = angles.find((a) => a.id === angleId) || null;
  // "Viewed" for the gated Review copies: the gate was clicked, or the pick
  // names a real row — selecting an angle is itself the viewing the gate
  // asks for. A stale ?angle= param or a draft pointing at a deleted angle
  // does NOT count: it must not open a list of strangers in the recovery
  // panel on first view, which is the exact screenshot this rule fixes.
  const showAngles = anglesRevealed || Boolean(angle);
  const showGoals = goalsRevealed || Boolean(objective);
  // The reveal lasts for the visit, not the mount. Entering the angle step
  // without a resolved pick re-arms both gates, so a list viewed earlier
  // never counts as viewed for a founder who navigated away and back
  // unpicked when Review later asks. A resolved angle still bypasses the
  // angle gate — a reopened draft shows its own angle, never an empty
  // gate — while a dangling pick re-gates like any other visit with
  // nothing to show. The goal gate follows the same rule: a resolved
  // objective bypasses it, otherwise the step re-arms it.
  useEffect(() => {
    if (STEPS[step]?.key === "angle" && !angle) setAnglesRevealed(false);
    if (STEPS[step]?.key === "angle" && !objective) setGoalsRevealed(false);
    // angle is an object derived from angles[]: depending on it re-arms the
    // gates on every angles refresh (e.g. shuffle), collapsing a revealed
    // list to the CTA. Depend on the resolved id instead; a dangling pick
    // (id set, row gone) still reads as no angle.
  }, [step, angle?.id, objective]);
  // The detail card prefers the full library, but a failed library fetch must
  // not blank a chosen template the recommendation rows already carry.
  const template = templates.find((t) => t.id === templateId)
    || recommendations.map((r) => r?.template).find((t) => t?.id === templateId) || null;
  const objectiveOptions = facets?.objectives || [];
  const recommendedObjectives = angle
    ? facets?.angle_goal_recommendations?.[angle.kind] || []
    : [];
  const objectiveOutcomes = facets?.objective_outcomes || {};
  const objectiveFitReasons = angle
    ? facets?.angle_goal_fit_reasons?.[angle.kind] || {}
    : {};
  // Live goals replace the persisted facet order only after the founder's
  // Generate click: the angle step opens on the facet list itself, and the
  // click swaps in the live six with their fit scores.

  // The deep-link inputs as plain strings, so the load below depends on what
  // it reads rather than on the params object: the ?step= mirror rewriting
  // the URL must not re-fire this (it would re-pick the profile and drag the
  // founder back to step 1 mid-flow).
  const projectParam = params.get("project") || "";
  useTourEligibility("create", !loading && !projectParam && !project && step === 0 && !profileId);
  const profileParam = params.get("profile") || "";
  useEffect(() => {
    setPlanBannerDismissed(false);
  }, [projectParam]);

  // Goal options come from the template facets, not the angle: a failure
  // here empties a required picker with no reason, so it names itself and
  // retries on its own button instead of borrowing the plan error.
  const [facetsError, setFacetsError] = useState(null);
  const loadFacets = useCallback(() => {
    setFacetsError(null);
    api.getTemplateFacets()
      .then((f) => setFacets(f))
      .catch((err) => {
        setFacets(null);
        setFacetsError(getErrorMessage(err));
      });
  }, []);
  useEffect(() => {
    loadFacets();
  }, [loadFacets]);
  useEffect(() => {
    let cancelled = false;
    api
      .getAppProfiles()
      .then(async (data) => {
        const list = data.profiles || [];
        if (cancelled) return;
        setProfiles(list);
        // Only approved profiles may enter the studio. The `?profile=` deep
        // link is a different path: it preselects a specific app and is
        // handled further down. Both must agree on what counts as approved, so
        // both go through the same partition rather than repeating the filter.
        const approved = partitionProfiles(list).approved;
        const requestedProjectId = projectParam;
        if (requestedProjectId) {
          try {
            const draft = await api.getStudioProject(requestedProjectId);
            const draftProfile = approved.find((p) => p.id === draft.brand_profile_id);
            if (!draftProfile) {
              throw new Error("That draft project is unavailable or its App Profile is not approved.");
            }
            const angleData = await api
              .getContentAngles(draftProfile.id)
              .catch((err) => {
                // The deep link still lands: the gate offers Generate, and the
                // error says why the list is empty.
                if (!cancelled) setAngleError(getErrorMessage(err));
                return { angles: [] };
              });
            if (cancelled) return;
            dispatchDraft({ type: "draft-resumed", project: draft });
            // This row came from the server, so it is already current: recording
            // it means the Review re-read has nothing to reconcile and does not
            // fire. Without that, every deep link issued a second identical
            // request whose late resolution updated state after the check (or
            // the founder) had moved on.
            syncedProjectsRef.current[draft.id] = draft.updated_at || "";
            adoptAngles(angleData);
            clearRecommendations();
            // A duplicate always arrives with its plan intact, so it opens on
            // Review; an unplanned draft still needs a photo before a plan can
            // be written. Both indices are looked up by KEY rather than written
            // as numbers: the wizard was seven steps and is now five, and a
            // hardcoded index is exactly what silently sent a deep link past
            // the end of the wizard.
            setStep(
              draft.script_version > 0
                ? STEPS.findIndex((s) => s.key === "review")
                : STEPS.findIndex((s) => s.key === "angle")
            );
          } catch (err) {
            if (cancelled) return;
            setError(getErrorMessage(err));
          }
          return;
        }
        const preselected = profileParam;
        const chosen =
          approved.find((p) => p.id === preselected) || approved[0] || null;
        if (chosen) {
          // The pick must live in state: profileId drives recommendations,
          // canGenerate, and draft creation, and selectProfile is the only
          // other writer. Reading it from URL params alone left it empty.
          dispatchDraft({ type: "profile-loaded", id: chosen.id });
          // A ?step= link names the step explicitly; only advance to the
          // angle step when none was asked for, so the link survives the
          // profiles load instead of being overridden by it.
          if (!params.get("step")) setStep(1);
          api.getContentAngles(chosen.id).then((d) => adoptAngles(d)).catch((err) => {
            if (!cancelled) {
              setAngles([]);
              setObjectiveEvidence({});
              setAngleError(getErrorMessage(err));
            }
          });
        }
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
    // projectParam / profileParam only: a ?step= mirror write changes the
    // params object but neither input this load reads.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [projectParam, profileParam]);

  // The library answers once per mount. Until it has, a templateId names
  // nothing verifiable: the eager draft sync below must wait for it rather
  // than send an id the lists have not confirmed (see effectiveTemplateId).
  const [templatesLoaded, setTemplatesLoaded] = useState(false);
  useEffect(() => {
    api
      .getTemplates()
      .then((d) => {
        setTemplates((d.templates || []).filter((t) => t.is_usable));
        setTemplatesLoaded(true);
      })
      .catch(() => {
        setTemplates([]);
        setTemplatesLoaded(true);
      });
  }, []);

  // Set once the founder picks a template themselves, and never cleared.
  //
  // This is what makes the default selection safe. The recommender reorders on
  // this app's own recorded feedback (feedback.template_feedback_adjustment
  // shifts a score by up to 4 points either way), so its top pick is
  // meaningful — and reordering it on every reload meant a founder's deliberate
  // choice could be silently replaced by whatever ranked first that time, which
  // discarded the adjustment the click was overriding.
  const templateChosenByHand = useRef(false);
  const reduceMotion = useReducedMotionPreference();
  const scrollToSubstep = (id) => {
    document
      .getElementById(id)
      ?.scrollIntoView?.({ behavior: reduceMotion ? "auto" : "smooth", block: "start" });
  };
  // Auto-scroll to the section a pick just unlocked, in the order the
  // Audience & template screen finishes: angle unlocks the video goals,
  // a finished tailoring run unlocks the templates, and a hand-picked
  // template unlocks the presenter photo. Each effect only fires on a
  // change, never on mount or a reload with a pick already in the draft,
  // and only while this step is in view — the step-change scroll above
  // already brings the founder to the top of this screen.
  const prevAngleIdRef = useRef(angleId);
  useEffect(() => {
    const prevAngleId = prevAngleIdRef.current;
    prevAngleIdRef.current = angleId;
    if (!angleId || angleId === prevAngleId) return;
    if (step !== 1) return;
    requestAnimationFrame(() => scrollToSubstep("substep-goal"));
  }, [angleId, step]);
  const prevRecommendationsVisibleRef = useRef(false);
  useEffect(() => {
    const wasVisible = prevRecommendationsVisibleRef.current;
    const visible = recommendationsVisible && visibleRecommendations.length > 0;
    prevRecommendationsVisibleRef.current = visible;
    if (!visible || wasVisible) return;
    if (step !== 1) return;
    requestAnimationFrame(() => scrollToSubstep("substep-template"));
  }, [recommendationsVisible, visibleRecommendations, step]);
  // Set only by a hand pick below, and consumed by the effect that follows,
  // so the automatic preselect of the top template never jumps past the
  // template cards to the photo section the founder has not chosen yet.
  const handPickedTemplateRef = useRef(false);
  const prevTemplateIdRef = useRef(templateId);
  useEffect(() => {
    const prevTemplateId = prevTemplateIdRef.current;
    prevTemplateIdRef.current = templateId;
    if (!templateId || templateId === prevTemplateId) return;
    if (!handPickedTemplateRef.current) return;
    handPickedTemplateRef.current = false;
    if (step !== 1) return;
    requestAnimationFrame(() => scrollToSubstep(TEMPLATE_PHOTO_ID));
  }, [templateId, step]);






  // Preselect the top pick only once its key is displayable. Deliberately not
  // "on every reload": a reload must never move a selection the founder made,
  // so the only conditions are that nothing is selected and nothing has ever
  // been hand-picked.
  useEffect(() => {
    if (!recommendationsVisible) return;
    if (templateId || templateChosenByHand.current) return;
    if (visibleRecommendations.length === 0) return;
    dispatchDraft({ type: "template-selected", id: visibleRecommendations[0].template.id });
  }, [visibleRecommendations, recommendationsVisible, templateId]);

  // Implicit behavior: what was shown but not picked. Adoption and
  // abandonment are recorded server-side — the plan, strategy and submit
  // seams know exactly what moved forward and what was dropped without
  // proceeding — but only the UI knows what else was on screen when a
  // choice was made. Each shown-but-not-picked item is a soft negative; the
  // server dedupes it to one row per item per project, so a re-rendered
  // list does not spam the loop. Programmatic sets (presets, resets,
  // profile switches) bypass these wrappers and record nothing.
  const behaviorRefs = () => ({
    brand_profile_id: profileId || "",
    studio_project_id: project?.id || "",
  });
  const handleAnglePick = (id) => {
    if (id && id !== angleId && Array.isArray(angles)) {
      const refs = behaviorRefs();
      angles.forEach((a) => {
        if (!a || !a.id || a.id === id) return;
        recordBehavior("generated", "goal", {
          ...refs,
          detail: `angle_id=${a.id};kind=${(a.kind || "").trim()}`,
        });
      });
    }
    dispatchDraft({ type: "angle-selected", id });
  };
  const handleGoalPick = (value) => {
    if (value && value !== objective) {
      // The six the picker actually shows: ranked suggestions first, then
      // the facet list — the same order AngleGoalPicker renders.
      const knownGoals = Array.isArray(objectiveOptions) ? objectiveOptions : [];
      const suggestions = Array.isArray(angle?.goal_suggestions) ? angle.goal_suggestions : [];
      const ordered = suggestions.length > 0
        ? suggestions.filter((goal) => knownGoals.includes(goal))
        : (recommendedObjectives || []).filter((goal) => knownGoals.includes(goal));
      const featured = [...new Set([...ordered, ...knownGoals])].slice(0, 6);
      const refs = behaviorRefs();
      const kind = (angle?.kind || "").trim();
      featured.forEach((goal) => {
        if (!goal || goal === value) return;
        recordBehavior("generated", "goal", {
          ...refs,
          detail: `objective=${goal};kind=${kind}`,
        });
      });
    }
    dispatchDraft({ type: "goal-selected", value });
  };
  const handleTemplatePick = (id) => {
    if (id && id !== templateId && Array.isArray(visibleRecommendations)) {
      const refs = behaviorRefs();
      visibleRecommendations.forEach((r) => {
        const tid = r?.template?.id;
        if (!tid || tid === id) return;
        recordBehavior("generated", "template", { ...refs, template_id: tid });
      });
    }
    // Latched, so a later reload cannot move this pick.
    templateChosenByHand.current = true;
    handPickedTemplateRef.current = true;
    dispatchDraft({ type: "template-selected", id });
  };

  const selectProfile = async (id) => {
    dispatchDraft({ type: "profile-selected", id });
    setAngles([]);
    clearRecommendations();
    // A deliberate template choice is per app, not per session.
    templateChosenByHand.current = false;
    try {
      const data = await api.getContentAngles(id);
      adoptAngles(data);
    } catch (err) {
      setAngles([]);
      setObjectiveEvidence({});
      setAngleError(getErrorMessage(err));
    }
    setStep(1);
  };

  /* Approve a draft profile where the flow starts, instead of sending the
     founder to the App Profile page and back. The approval itself is
     untouched — the same endpoint App Profile's own button calls, with the
     same gaps refusal and the same angles generated on the server — only
     its location moved: the facts are reviewed on this step (the panel
     below renders exactly what approval judges), and approving picks the
     profile and walks on, so a first-run founder goes from draft to
     choosing an angle without leaving the flow. A refusal stays on the
     step and names the gaps beside the profile that earned them; filling
     them is still an edit, and editing still lives on App Profile. */
  const handleInlineApprove = async (profile) => {
    if (approvingProfileId) return;
    setApprovingProfileId(profile.id);
    setApproveErrors((prev) => ({ ...prev, [profile.id]: null }));
    try {
      const approved = await api.approveAppProfile(profile.id);
      setProfiles((list) =>
        list.map((p) => (p.id === approved.id ? { ...p, ...approved } : p))
      );
      await selectProfile(approved.id);
    } catch (err) {
      setApproveErrors((prev) => ({ ...prev, [profile.id]: getErrorMessage(err) }));
    } finally {
      setApprovingProfileId(null);
    }
  };

  const createProject = async (overrides = {}) => {
    setBusy(true);
    setError(null);
    try {
      // Neither duration_seconds nor extend_intent is sent, on either path.
      //
      // The length is the template's: create_studio_project reads
      // `default_duration` off the template the founder just picked and seeds
      // the project from it, so sending a number here could only be a stale
      // copy of a decision the founder is not making. The two columns this used
      // to write are still in the SQLite schema and are still accepted on the
      // request model, so an old payload would be accepted and silently
      // discarded — which is exactly the kind of write that looks like it did
      // something and did nothing.
      const created = project?.id
        ? await api.updateStudioProject(project.id, {
            content_angle_id: angleId || "",
            template_id: template?.id || "",
            objective,
            tone,
            ...overrides,
          })
        : await api.createStudioProject({
            brand_profile_id: profileId,
            content_angle_id: angleId || "",
            template_id: template?.id || "",
            objective,
            tone,
          });
      dispatchDraft({ type: "project-received", project: created });
      return created;
    } catch (err) {
      if (isTemplateGoneError(err)) {
        // The pick names a row the server no longer has: drop it so every
        // gate, pill and sync reads the same "no template" state the library
        // already shows, and latch the choice so the preselect below does not
        // resurrect the disproven pick on the next render. The caller turns
        // the outcome into the gap panel.
        templateGoneRef.current = true;
        templateChosenByHand.current = true;
        dispatchDraft({ type: "template-selected", id: "" });
        setError(TEMPLATE_GONE_MESSAGE);
        return null;
      }
      setError(getErrorMessage(err));
      return null;
    } finally {
      setBusy(false);
    }
  };

  /**
   * Make sure a draft exists without the founder having to ask.
   *
   * The render step writes to a studio project, and the plan is meant to be
   * validated BEFORE anything is rendered. Previously the project was only   * created by the plan step, which forced the Assets step to carry a manual
   * "Create draft" button purely to get out of the way.
   *
   * So: as soon as an App Profile and a hook template are both chosen, the
   * draft is created or updated in the background. A draft calls no model —
   * only a marked-ready generation renders — so doing this eagerly costs
   * nothing. Returns the project, or null when it cannot be created.
   */
  const ensureProject = useCallback(async () => {
    // The resolved row, never the raw string: an id the lists cannot confirm
    // (a stale ?template= link, a draft adopted from a deleted row) must not
    // reach the server — see effectiveTemplateId and the smoke check that pins
    // it. Without a resolved row there is nothing verifiable to sync.
    const resolvedTemplateId = template?.id || "";
    if (!profileId || !resolvedTemplateId) return null;
    try {
      if (project?.id) {
        // Keep the draft's selections in step with the wizard without
        // disturbing a plan that already exists.
        if (
          project.template_id === resolvedTemplateId &&
          // Both sides normalize to "": the writes below send angleId || "",
          // so comparing against (angleId || null) never matched an empty
          // angle and every call fell through to a wasted update write -- which
          // the eager-create effect above turned into an infinite
          // update -> setProject -> re-fire loop.
          (project.content_angle_id || "") === (angleId || "") &&
          project.objective === (objective || "")
        ) {
          return project;
        }
        // duration_seconds is deliberately NOT sent here, and neither is
        // anything else that would move the length. The project already carries
        // the length it was seeded with, and once a plan exists the server
        // refuses a change to it outright — the beats in the shot timeline were
        // clamped to that number, so a separate write could only produce a
        // timeline that no longer adds up.
        const updated = await api.updateStudioProject(project.id, {
          content_angle_id: angleId || "",
          template_id: resolvedTemplateId || "",
          objective,
          tone,
        });
        dispatchDraft({ type: "project-received", project: updated });
        return updated;
      }
      const created = await api.createStudioProject({
        brand_profile_id: profileId,
        content_angle_id: angleId || "",
        template_id: templateId || "",
        objective,
        tone,
      });
      dispatchDraft({ type: "project-received", project: created });
      return created;
    } catch (err) {
      // A failure here is not fatal: the plan step still creates the draft and
      // surfaces the error properly. Swallowing it here would just show an
      // empty render step with no explanation. A vanished template stays
      // silent here for the same reason — the plan step translates it into
      // the gap — and the stale pick is dropped so nothing re-sends it.
      if (isTemplateGoneError(err)) {
        templateChosenByHand.current = true;
        dispatchDraft({ type: "template-selected", id: "" });
        setError(null);
        return null;
      }
      setError(getErrorMessage(err));
      return null;
    }
  }, [profileId, templateId, template, angleId, objective, tone, project]);

  // Wire up the eager creation the ensureProject docstring promises: as soon
  // as a profile and template are both chosen, the draft is created (or kept
  // in step) in the background. Without this the render step shows "Create the
  // draft" instead of the Generate button whenever a founder reaches it by the
  // step pills rather than through the Review step, which is exactly when the
  // button "sometimes" vanishes. A ref guards against concurrent calls because
  // ensureProject is async and the effect re-fires on every project write.
  const ensureProjectInFlight = useRef(false);
  const lastSyncedKey = useRef("");
  useEffect(() => {
    if (!profileId || !templateId || ensureProjectInFlight.current) return;
    // The pick is not verified until the library has answered. Syncing an id
    // the lists have not confirmed is exactly how a stale ?template= link or
    // a draft adopted from a deleted row 404ed "Template not found" into the
    // page banner above a step the pills called done. An unverified id waits
    // here; a disproven one never syncs, and the choosing step owns telling
    // the founder (see template-gone-notice).
    if (!templatesLoaded || !template) return;
    // One sync per selection-set. Without this, any server echo that differs
    // from what was sent (a dropped angle, a normalized field, or a stub that
    // answers a create with a canned project) would ping-pong
    // update -> setProject -> re-fire forever, because this effect re-runs on
    // every project write. The manual buttons bypass the guard and call
    // ensureProject directly.
    const key = `${profileId}:${templateId}:${angleId || ""}:${objective || ""}`;
    if (lastSyncedKey.current === key) return;
    lastSyncedKey.current = key;
    ensureProjectInFlight.current = true;
    ensureProject().finally(() => {
      ensureProjectInFlight.current = false;
    });
  }, [profileId, templateId, angleId, objective, template, templatesLoaded, ensureProject]);

  /* The shell remembers the draft the founder is inside; the sidebar reads it
     and offers one line back into it, so three steps deep stops looking like a
     cold start. Only a real project is written: a wizard with no project has
     nothing to continue, and a link into one would look like a destination and
     open as an empty step. */
  const draftAppName = profiles.find((p) => p.id === profileId)?.brand_name || "";
  useEffect(() => {
    if (!project?.id) return;
    rememberDraft({
      projectId: project.id,
      appName: draftAppName || project.brand_name || "",
      step: STEPS[step].key,
    });
  }, [project?.id, project?.brand_name, draftAppName, step]);

  const handleGeneratePlan = async () => {
    if (!angle || !objective) {
      setError("Choose an audience angle and a video goal before generating the plan.");
      setPlanFailed(true);
      return;
    }
    // Single flight. Concurrent triggers — a double-tapped Regenerate, a
    // thumbs-down retry racing a manual one — must not stack minute-long model
    // calls: each holds `busy`, so stacked flights read as a frozen page
    // with every control disabled. A call already in flight owns the
    // outcome; the extra tap is dropped. The buttons it could come from are
    // `busy`-disabled anyway, so this only ever bites on same-tick races.
    if (planInFlightRef.current) return;
    planInFlightRef.current = true;
    const ready = await createProject();
    if (!ready) {
      // createProject already reported the error above. A vanished template is
      // a gap, not a failure: Review names the missing pick instead of
      // offering a retry that would 404 again.
      const gone = templateGoneRef.current;
      templateGoneRef.current = false;
      planInFlightRef.current = false;
      setPlanFailed(!gone);
      return;
    }
    setPlanFailed(false);
    setBusy(true);
    setError(null);
    try {
      // Switching template after a plan already exists is a rejection of the
      // template the first plan was built from. Recorded here rather than at
      // selection time, because selecting a template is a normal part of the
      // flow and only the replacement is a signal.
      if (ready.script_version > 0 && ready.template_id && ready.template_id !== templateId) {
        recordSignal("template_rejected", "template_changed", {
          brand_profile_id: profileId,
          studio_project_id: ready.id,
          template_id: ready.template_id,
        });
      }
      // One pass, one wait: the server writes the plan and builds the
      // strategy from it before answering, so the project that lands here
      // already carries both. The two-stage shape this replaces made the
      // founder wait for the plan, then wait again while the strategy panel
      // auto-built — two waits and two failure surfaces for a pair where
      // the second is a function of the first. The strategy panel's own
      // build stays as the recovery path for a project that reaches ready
      // without a strategy (a strategy-stage failure retried from the
      // panel, or a draft from before the pass existed).
      const updated = await api.generatePlanAndStrategy(ready.id, {
        objective,
        tone,
      });
      // A freshly generated plan is exactly the text the founder is about to
      // read on Review, so the project is marked ready as part of generating
      // it. There is no manual mark-ready control anywhere: a click that could
      // only confirm what the studio already knew was a button with no meaning,
      // and its absence was read as the render button being broken. The server
      // re-checks readiness on this call and refuses when a requirement is
      // missing, so the gate is unchanged -- it just happens without
      // the founder having to say "I saw it".
      //
      // A refusal is kept as the plan's own state rather than surfaced as a
      // thrown error, because the plan landed and is readable; the render
      // button then states the real reason (a missing
      // photograph) instead of the screen looking broken.
      let settled = updated;
      let readyError = null;
      try {
        settled = await api.markProjectReady(updated.id);
      } catch (err) {
        // The plan landed and is readable, so this is not a failure of the step.
        // The render button below names the real reason (a photograph
        // still owed); swallowing this without comment is what made
        // a refused project look broken rather than gated.
        settled = updated;
        readyError = err;
      }
      // Record what the server now holds, so the Review re-read knows this state is
      // already current and cannot resolve an older row over it. Taken from
      // `settled`, not `updated`: marking ready is itself a write, so its row is
      // the fresher of the two.
      if (settled?.id) {
        syncedProjectsRef.current[settled.id] = settled.updated_at || "";
      }
      // A refusal is stated rather than swallowed, so a founder who lands on a
      // disabled render button can read why instead of assuming the app broke.
      setError(readyError ? getErrorMessage(readyError) : null);
      dispatchDraft({ type: "plan-accepted", project: settled });
      setReviewThumb(0);
      // Straight to the top of Review & submit, where the fresh plan reads: the
      // plan is the thing to read first, and the render section below it is the
      // first one that calls the model. Looked up by key, not written as a
      // number — a hardcoded index is exactly what silently sent this jump past
      // the end of the wizard when the steps merged.
      setStep(STEPS.findIndex((s) => s.key === "review"));
    } catch (err) {
      if (isTemplateGoneError(err)) {
        // The row vanished between picking and saving: same resolution as a
        // gone id at pick time — drop the pick, name the gap, no retry. The
        // latch keeps the preselect from re-picking the disproven row.
        templateChosenByHand.current = true;
        dispatchDraft({ type: "template-selected", id: "" });
        setError(TEMPLATE_GONE_MESSAGE);
        setPlanFailed(false);
      } else {
        setError(getErrorMessage(err));
        setPlanFailed(true);
      }
    } finally {
      planInFlightRef.current = false;
      setBusy(false);
    }
  };

  /* Takes the founder to the photo upload, wherever they currently are.
     It lives on the angle & template step now, so this both jumps to that
     step and scrolls to the field — otherwise "Add your photo" would land
     them on a step with nothing obviously about photographs in view. */
  /* Thumbs-up on the review loop used to walk to the render step; the render
     panel lives on this step now, so approval scrolls to the submit panel
     instead. Same destination, no step change. */
  const scrollToSubmit = () => {
    requestAnimationFrame(() => {
      // Optional call, not just optional element: environments without a
      // scrolling view (tests, previews) expose no scrollIntoView, and a
      // reducing jump must never throw there. Same convention as History.
      document
        .getElementById("review-submit")
        ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    });
  };
  const scrollToTemplatePhoto = () => {
    setStep(1);
    // After the step renders, not before: the element does not exist yet.
    requestAnimationFrame(() => {
      document
        .getElementById(TEMPLATE_PHOTO_ID)
        ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    });
  };

  // Autosave mirrors the Demo + CTA editor's draft rhythm (save shortly
  // after every change), but through the server path, not browser storage:
  // Review edits are plan text the render speaks, so only a real save counts.
  // Silent saves never touch `busy` — disabling the step on every debounced
  // keystroke would interrupt the typing they follow — and the manual Save
  // button stays for an immediate, explicit save.
  const confirmRegeneratePlan = () => {
    const message = hasEdits
      ? "You have unsaved edits. Generating a new plan replaces this one and your edits are lost. Generate anyway?"
      : `Replace plan v${project?.script_version || 0} with a new one? The current plan is discarded.`;
    if (typeof window.confirm !== "function" || !window.confirm(message)) return;
    handleGeneratePlan();
  };

  const [autosaving, setAutosaving] = useState(false);
  const [saveStatus, setSaveStatus] = useState("");
  const handleSaveEdits = async ({ silent = false } = {}) => {
    if (!project) return;
    // Snapshot what this flight is saving: keystrokes that land while the
    // two writes are in the air are newer than this object and must survive
    // the adoption below (see wizardDraft plan-accepted).
    if (silent) {
      if (autosaving) return;
      setAutosaving(true);
      setSaveStatus("Saving…");
    } else {
      setBusy(true);
    }
    setError(null);
    try {
      // Measured against the saved script, not the textarea, so a save that
      // changes nothing records nothing.
      const savedEdits = { ...edits };
      // Measured against the saved script, not the textarea, so a save that
      // changes nothing records nothing.
      const editSignal = Object.prototype.hasOwnProperty.call(savedEdits, "script")
        ? classifyScriptEdit(project.script, savedEdits.script)
        : "";
      const updated = await api.updateStudioProject(project.id, savedEdits);
      if (editSignal) {
        recordSignal("script_edited", editSignal, {
          brand_profile_id: profileId,
          studio_project_id: project.id,
          template_id: project.template_id,
        });
      }
      // A content save un-readies the project server-side (ready_for_generation
      // -> draft), because the strategy and the approval both describe the text
      // as it was before this edit. Re-marked here for the same reason plan
      // generation marks it: the founder just reviewed the exact words they
      // saved, so the approval still describes what they read, and there is no
      // manual mark-ready control for them to reach for instead.
      //
      // The readiness rule this encodes: an edit the founder saved after reading
      // it keeps the project approved, and a server refusal (a photograph
      // detached) is reported rather than hidden -- so
      // the render button is disabled with a stated reason instead of the screen
      // looking broken.
      let settled = updated;
      let readyError = null;
      try {
        settled = await api.markProjectReady(updated.id);
      } catch (err) {
        settled = updated;
        readyError = err;
      }
      if (settled?.id) {
        syncedProjectsRef.current[settled.id] = settled.updated_at || "";
      }
      setError(readyError ? getErrorMessage(readyError) : null);
      dispatchDraft({ type: "plan-accepted", project: settled, savedEdits });
      setReviewThumb(0);
      if (silent) setSaveStatus("All changes saved");
    } catch (err) {
      const message = getErrorMessage(err);
      setError(message);
      if (silent) setSaveStatus(`Could not autosave: ${message}`);
    } finally {
      if (silent) {
        setAutosaving(false);
      } else {
        setBusy(false);
        setSaveStatus("");
      }
    }
  };
  const saveEditsRef = useRef(null);
  saveEditsRef.current = (options) => handleSaveEdits(options);
  // Save ~1s after the last change, never during a plan flight: the same
  // button the founder would press, without being asked. Skipped while a
  // manual save or plan generation holds `busy`, and while a plan flight
  // owns the outcome — stacked writes read as a frozen page.
  const hasEdits = Object.keys(edits).length > 0;
  const editsSignature = JSON.stringify(edits);
  const autosaveProjectId = project?.id;
  useEffect(() => {
    if (!hasEdits || busy || !autosaveProjectId) return undefined;
    if (planInFlightRef.current) return undefined;
    setSaveStatus("");
    const timer = setTimeout(() => {
      saveEditsRef.current?.({ silent: true });
    }, 1000);
    return () => clearTimeout(timer);
  }, [editsSignature, busy, autosaveProjectId, hasEdits]);

  // Thumbs-down on Review asks the AI for a better plan; thumbs-up records
  // the approval and moves to the render below. Down reuses the existing plan
  // generation (ready marking included), capped at three
  // refinements per saved plan version so the loop always terminates.
  const handleReviewThumb = async (next) => {
    setReviewThumb(next);
    if (next === 0 || !project?.id) return;
    recordThumb("plan", next, {
      brand_profile_id: profileId,
      studio_project_id: project.id,
      template_id: project.template_id,
      detail: `plan v${Number(project.script_version) || 0}`,
    });
    if (next === 1) {
      // Approval moves to the render half: thumbs-up is the moment the plan
      // is done being read, so the founder lands on the render instead of
      // having to notice the tab. scrollToSubmit already defers a frame, so
      // it runs after the tab switch paints.
      setReviewTab("render");
      scrollToSubmit();
      return;
    }
    const versionKey = String(Number(project.script_version) || 0);
    const used = Number(reviewRefinesRef.current[versionKey] || 0);
    if (used >= 3) {
      setError(
        "Three fresh plans written for this version already — edit the script by hand or pick another template before refining again."
      );
      // No refinement happened, so the thumb must not stay pressed: left
      // active it claims a fourth plan is coming that the cap forbids.
      setReviewThumb(0);
      return;
    }
    reviewRefinesRef.current[versionKey] = used + 1;
    await handleGeneratePlan();
    setReviewThumb(0);
  };

  // The selection is the resolved row, never the raw id. A templateId that
  // names nothing the founder can see — a stale ?template= link, a draft
  // adopted from a row whose template is gone — is not a pick: it used to
  // tick the step done, hide the recovery button, and 404 "Template not
  // found" out of the eager draft sync with no way back. The project fallback
  // is gone for the same reason: a row id the lists cannot confirm must not
  // drive gates or writes. The draft load re-seeds state from its row, so a
  // live template still flows through here through state.
  const effectiveTemplateId = template?.id || "";
  const canGenerate = Boolean(profileId && effectiveTemplateId);

  // First missing choice in flow order, for the one red button on panels that
  // refuse to generate until the plan's inputs exist: profile, then angle,
  // then goal (angle and goal both live on step 1), then template. Exactly
  // one button ever renders — it names whichever prerequisite is actually
  // missing and jumps there — so two gaps can never show two competing
  // "first" actions. The label carries "first" because the action gates
  // everything after it.
  const firstGap = !profileId
    ? { step: 0, label: "Choose an App Profile first" }
    : !angle
      ? { step: 1, label: "Pick an audience angle first" }
      : !objective
        ? { step: 1, label: "Set the video goal first" }
        : !effectiveTemplateId
          ? { step: 1, label: "Pick a template first" }
          : null;

  // Face-only product: every template requires exactly the character
  // reference, and the backend refuses a generation without one (see
  // _studio_identity_references) as well as any project still holding
  // retired uploads. The requirement used to be decoration: it was listed
  // on the template but nothing stopped the click, so a render could
  // go out with no identity input and the model free to invent a presenter.
  //
  // Kept separate from canGenerate on purpose — "you have not chosen a template
  // yet" and "you still owe this template a photograph" are different problems
  // and the founder needs to be told which one they have. The split lives in
  // a tested helper rather than inline here.
  // The resolved row only: a project id the lists cannot confirm must not
  // resurrect a dangling pick for the photo gate, exactly as it must not for
  // the pills, the gates, or the writes above.
  const effectiveTemplate = template || null;
  const missingIdentity = effectiveTemplate
    ? blockingRequirements(effectiveTemplate.required_assets, project?.assets)
    : [];
  // Server-side refusal is the guarantee; this is the early warning. Not folded
  // into canGenerate, because "you have not chosen a template yet" and "you
  // still owe this template a photograph" are different problems.
  const blockedOnAssets = Boolean(effectiveTemplate) && missingIdentity.length > 0;
  // What the generated piece is and how long it will be — a statement, not a
  // control. Once a project exists its own number is the authority, because
  // that is the length the plan's beat timeline was written to and the length
  // the render is asked for. Before that, the selected template's declared
  // length is what the project will be seeded from, so showing it predicts the
  // same value rather than offering a second one.
  //
  // The hook/middle breakdown is not shown here any more. It lived in a "What
  // you get" card on this step, which was a block of prose between the two
  // choices the step is actually for; the same numbers are on Review, where the
  // length is a read-only field, and the picked angle's own panel.
  const pieceSeconds = readPieceSeconds(project, template);

  const editValue = (key, fallback) =>
    edits[key] !== undefined ? edits[key] : project?.[key] ?? fallback;

  // The live script budget: the count that follows the field, and whether it
  // has outgrown what the middle's seconds can speak. The ceiling is the
  // server's own (spoken_check.script), so the warning agrees with the clamp
  // the render applies.
  const scriptChars = String(editValue("script", "") || "").trim().length;
  const scriptCeiling = Number(project?.spoken_check?.script?.ceiling) || 0;
  const scriptOverBudget = scriptCeiling > 0 && scriptChars > scriptCeiling;

  // Tone is deliberately NOT editable on this step any more: the video-level
  // Tone dropdown duplicated the App Profile's "Tone / voice" and the voice
  // direction, both collapsing into one downstream delivery field. Delivery is
  // written per video from its own plan now — no control owns it (ADR 0102,
  // superseding 0091); a tone a project already carries still seeds the plan.
  // Length has no editor on this step at all: it is the template's number, and
  // the plan's beat timeline is built to it.

  // Direction dropdowns live in their own lifecycle owner (profile-keyed
  // options, per-app picks, saved-plan matching, per-field refresh). See
  // useWizardDirections: request ids ignore stale loads, picks reset on app
  // switch, and a refresh never destroys the founder's current pick.
  const {
    directionOptions,
    dirSel,
    pickScenePart,
    refreshingField,
    refreshError,
    refreshDirectionField,
    refreshProps,
  } = useWizardDirections({ profileId, project, angle, dispatchDraft });

  // The goal the plan is written toward: the wizard's own choice wins, and the
  // draft's stored goal is the fallback, so a complete draft landing on
  // Review reads as ready to generate even when this session's state lost
  // the choice (pill-jump, reload) while the server row kept it. Without the
  // fallback the step shows the goal picker and waits, although everything
  // the plan needs is already decided.
  const effectiveObjective = objective || project?.objective || "";

  // Entering Review generates NOTHING (ADR 0122): going through the steps
  // is display-only, so a draft with no plan shows this step's Generate
  // button and the click is the generation — the same discipline as the
  // angle step's empty set and ADR 0107's goals. (This step used to write
  // the plan on arrival; the founder's rule retired that.) The one effect
  // left here is state sync, not generation: when the server row holds a
  // goal this session lost, adopt it so the gates and the Generate click
  // read one consistent choice.
  useEffect(() => {
    if (step !== 2) return;
    if (!objective && project?.objective) {
      dispatchDraft({ type: "goal-selected", value: project.objective });
    }
  }, [step, objective, project?.objective]);
  // Single-flight latch for plan generation, owned by handleGeneratePlan.
  // `busy` state cannot do this job: two taps in the same tick both read the
  // still-false state, so both would start a model call. A ref flips
  // synchronously, collapsing the race before the first await.
  const planInFlightRef = useRef(false);
  // Set when a draft write learns the picked template is gone server-side.
  // Read once by the plan handler below to offer the gap instead of a retry.
  const templateGoneRef = useRef(false);

  // Review reads the project's words, so it must read them from the server
  // rather than trust whatever the wizard last held. An eager draft update
  // issued while the plan was still being written can resolve after it, which
  // leaves the editors showing a copy of the row from before the plan landed:
  // an empty Hook line and Script above a plan that the render step can count
  // characters in. Re-fetching on entry makes this step authoritative.
  //
  // Guarded three ways, because a read that fights a write is worse than no
  // read at all:
  //   - Keyed on the row's own version stamps, so it re-syncs only when the
  //     server has something new, and a refetch cannot loop against itself.
  //   - Unsaved edits always win; the founder's words are never overwritten.
  //   - Readiness is one-way. The plan handler marks the project ready right
  //     after generating, and this read was able to resolve with the row from
  //     just before that and quietly downgrade an approved project to a draft
  //     -- which left the render button disabled on the next step with nothing
  //     on screen to explain it. A read may move a project forward; it may
  //     never move one back.
  const reviewSynced = useRef("");
  const editsRef = useRef(edits);
  useEffect(() => {
    editsRef.current = edits;
  }, [edits]);
  useEffect(() => {
    if (step !== 2 || !project?.id || busy) return;
    // A row the wizard already adopted from a server response needs no read,
    // and cannot be improved on by another one. That covers the deep-link load
    // and the plan handler's own settled row.
    //
    // The second case is not just a wasted request. Marking ready is itself a
    // write, and a read issued around it could resolve with the row from before
    // it -- quietly downgrading an approved project to a draft and leaving the
    // render button disabled on the next step with nothing on screen to explain
    // it. Skipping the read is the fix; a one-way adoption below is the backstop
    // for any read that still happens.
    if (syncedProjectsRef.current[project.id] !== undefined) {
      return;
    }
    const key = `${project.id}:${project.updated_at || ""}:${project.script_version || 0}`;
    if (reviewSynced.current === key) return;
    reviewSynced.current = key;
    let cancelled = false;
    // A background re-read: the current project stays valid when it fails,
    // so the failure stays silent rather than erroring a healthy step.
    api
      .getStudioProject(project.id)
      .then((fresh) => {
        if (cancelled || !fresh) return;
        if (Object.keys(editsRef.current).length > 0) return;
        if (project.status === "ready_for_generation" && fresh.status !== "ready_for_generation") {
          return;
        }
        syncedProjectsRef.current[project.id] = fresh.updated_at || "";
        dispatchDraft({ type: "project-received", project: fresh });
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [step, project?.id, project?.updated_at, project?.script_version, project?.status, busy]);

  /* Progress state, derived rather than tracked. A founder can reach any step
     from any other, so nothing here can be a counter that advances — the pills
     have to be recomputed from what actually exists, or they go stale the moment
     they change something on an earlier step. */
  // The step counts a template only when the id names a row the founder can
  // see. Counting the raw string ticked this step done for a deleted template
  // while the sync underneath 404ed — see effectiveTemplateId above.
  const stepStates = stepCompletion({
    profileId,
    objective,
    angleId,
    templateId: template?.id || "",
    project,
    missingIdentity,
    hasEdits,
    hasFinishedRender: Boolean(finishedGeneration),
  });

  // Sequential unlock: a step is sealed until every previous step is done.
  // The rail and canvas headers wear the padlock (dimming + "locked" chip)
  // and the body opens on a lock banner naming the predecessor, so the
  // founder sees they must finish it first. Continue is the hard gate:
  // disabled with a padlock until this step is done. Back stays free.
  const unlocked = STEPS.map((_, i) => {
    if (i === 0) return true;
    return stepStates.slice(0, i).every((s) => s.state === "done");
  });

  /* What a satisfied pill names beside its tick. Derived like the states, so
     a changed pick renames its pill on the next render instead of going
     stale. Only done pills carry one: anything earlier has nothing picked
     yet, and the render step never completes.

     The profile pill names nothing. It used to echo the chosen app's name
     beside its "App Profile" label, which repeated the name the picker card
     on step one already carries and read as a second label on the same
     thing. Angle, template and plan keep their picks — those are choices
     made here that nothing else on the page restates. */
  function pillValue(key) {
    // The merged step names its most concrete pick: the template once chosen,
    // else the angle that ranks the list. Goal alone names nothing — it is a
    // filter on the angle, not a choice of its own.
    if (key === "angle") {
      return template?.name || angles.find((a) => a.id === angleId)?.label || null;
    }
    if (key === "review") {
      return project?.script_version ? `Plan v${project.script_version}` : null;
    }
    return null;
  }

  const stepContent = renderStep();

  /* Only state the task line cannot know — that is the footer's whole job
     now. It used to restate the step's own task a second time, once above the
     card and once in the middle of the arrows: step two read "pick the angle,
     goal, template, then add your photo" over "Angle, goal, template and
     photo — each one ranks the next". That ranking sentence lives in the task
     line now, so nothing here repeats it. Plain body copy, deliberately NOT a
     data-subtitle: the subtitle budget (text-sm, 55-60 chars) covers
     label-attached helpers only. A step stays locked until every previous
     step is done: the arrows, the rail segments and the canvas headers all
     refuse to advance past an unfinished step, and the locked visual (padlock
     + dimming + "locked" chip) names what must finish first. */
  const activeStepState = stepStates.find((s) => s.step.key === STEPS[step].key);
  /* The action bar's one line: what the step in view is waiting on, derived
     from the same states the pills and the rail read. It never restates the
     task line under the title, names only a blocker that is actually true —
     a photo already attached is never asked for again — and says the click
     where a click is the gate (ADR 0098). */
  let footerHint;
  if (STEPS[step].key === "profile") {
    footerHint = profileId
      ? "Ready \u2014 continue to Audience & template."
      : "Pick the app this video is for.";
  } else if (STEPS[step].key === "angle") {
    // One line per substep, in the order they finish the screen: the
    // standing sentence still asked for the angle at 4 of 4 done.
    if (!angleId) {
      footerHint = "Pick an angle \u2014 templates wait for your click.";
    } else if (!objective) {
      footerHint = "Pick a goal \u2014 the templates rank for it.";
    } else if (!template?.id) {
      footerHint = "Generate and pick a template when ready.";
    } else if (missingIdentity.length > 0) {
      footerHint = "Attach the presenter photo this template needs.";
    } else {
      footerHint = "Ready \u2014 continue to Review & submit.";
    }
  } else if (STEPS[step].key === "finish") {
    // The last step's line names its one input: the finished render. With
    // it, the editor is the work; without it, the render is the work, and
    // the line sends the founder back to the step that makes it.
    footerHint = finishedGeneration
      ? "Add your demo and closing message — exports save beside the original."
      : "Render the piece first — the finished clip opens here.";
  } else if (activeStepState?.state === "todo") {
    footerHint = "Generate a plan above, read it, then render.";
  } else if (activeStepState?.state === "blocked") {
    // Name only what is owed: the lumped copy asked for a save and a photo
    // even when one of them was already done, and a save in flight says so
    // instead of demanding one the autosave is already writing.
    const needsPhoto = missingIdentity.length > 0;
    if (hasEdits && needsPhoto) {
      footerHint = "Save your edits and attach a photo before rendering.";
    } else if (hasEdits) {
      footerHint = autosaving
        ? "Saving your edits \u2014 one moment before rendering."
        : "Save your edits before rendering.";
    } else if (needsPhoto) {
      footerHint = "Attach a photo before rendering.";
    } else {
      footerHint = "Finish this step before rendering.";
    }
  } else {
    // The review is done: nothing left to ask, so the bar states readiness
    // and the button beside it opens the render half.
    footerHint = "Ready \u2014 review the render below.";
  }
  // The rail score, derived per segment so the bar, the quarters and the
  // number can never disagree: a done step claims its full quarter, the step
  // in view claims half until it is done, the rest claim nothing.
  const railPct = Math.round(
    (stepStates.reduce(
      (sum, s, i) => sum + (s.state === "done" ? 1 : i === step ? 0.5 : 0),
      0
    ) /
      STEPS.length) *
      100
  );

  function renderStep() {
    if (step === 0) {
      // The gate and the explanation come from one place, so the picker can
      // never become permissive while still claiming it excludes the rest.
      const { approved, unapproved } = partitionProfiles(profiles);
      return (
        /* Titled like every other step. Title only, no description: the
           rail's own sentence names the one thing to do here, and a second
           sentence restating it is the duplication step 3's title-only shell
           already avoids. */
        <div className="space-y-3">
          {approved.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No approved App Profile"
              description={describeEmptySelection(profiles)}
              action={
                <Button variant="accent" asChild>
                  <Link to="/brand">Create an App Profile</Link>
                </Button>
              }
            />
          ) : (
            /* The nested box is the Review step's inset panel, not a capped
               tile: one eyebrow, one line of helper copy, then the choice.
               A 20rem tile inside a full-width card read as a different kind
               of control from the "Still missing" panel two steps later, so
               the same shell now carries both. The rows stay full width
               because the app list is the panel's content, not a gallery. */
            <div className="inset-panel space-y-4" data-testid="app-profile-picker">
              <GroupLabel icon={ListChecks}>Choose an app</GroupLabel>
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Only approved App Profiles can make a video in this studio.
              </p>
              <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {approved.map((p) => (
                  <button
                    key={p.id}
                    type="button"
                    aria-pressed={profileId === p.id}
                    onClick={() => selectProfile(p.id)}
                    className={`card-pickable row-pad w-full rounded-xl border text-left ${
                      profileId === p.id
                        ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                        : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <span className="font-display text-sm font-semibold">{p.brand_name}</span>
                      {profileId === p.id && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
                    </div>
                    <p className="mt-1 text-sm text-muted-foreground">
                      {p.app_category || p.niche || "Category not set"}
                    </p>
                  </button>
                ))}
              </div>
            </div>
          )}

          {unapproved.length > 0 && (
            <div className="inset-panel" data-testid="unapproved-profiles-panel">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-base font-semibold">
                    {describeUnapprovedCount(unapproved.length)}
                  </p>
                  <p className="mt-1 text-sm text-muted-foreground" data-subtitle="">
                    Draft profiles need review before a video can use them.
                  </p>
                  {/* The review happens here now: each draft shows the facts
                      its approval will be judged on, and the approve button
                      sits under them. Nothing about the approval weakened —
                      the same endpoint refuses a half-filled profile and
                      names the gaps, which land under that profile below. */}
                  <div className="mt-4 space-y-3">
                    {unapproved.map((p) => (
                      <div
                        key={p.id}
                        className="row-pad space-y-3 rounded-xl border border-[color:var(--hairline)]"
                        data-testid={`unapproved-profile-${p.id}`}
                      >
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <span className="font-display text-sm font-semibold">{profileLabel(p)}</span>
                          <span className="text-xs text-muted-foreground">
                            {p.app_category || p.niche || "Category not set"}
                          </span>
                        </div>
                        <dl className="space-y-1.5">
                          {profileApprovalFacts(p).map((fact) => (
                            <div key={fact.label} className="flex flex-wrap gap-x-2 text-sm">
                              <dt className="font-semibold text-muted-foreground">{fact.label}:</dt>
                              <dd className={fact.value ? "" : "text-muted-foreground"}>
                                {fact.value || "Not filled in yet"}
                              </dd>
                            </div>
                          ))}
                        </dl>
                        {approveErrors[p.id] && (
                          <div className="space-y-2">
                            <p role="alert" className="text-sm text-destructive" data-testid={`inline-approve-error-${p.id}`}>
                              {approveErrors[p.id]}
                            </p>
                            <Button variant="secondary" size="sm" asChild>
                              <Link to="/brand">Fill the gaps in App Profile</Link>
                            </Button>
                          </div>
                        )}
                        <Button
                          variant="accent"
                          size="sm"
                          disabled={Boolean(approvingProfileId)}
                          busy={approvingProfileId === p.id}
                          onClick={() => handleInlineApprove(p)}
                          data-testid={`inline-approve-profile-${p.id}`}
                        >
                          <ShieldCheck className="h-3.5 w-3.5" />
                          {approvingProfileId === p.id ? "Approving" : "Approve for video"}
                        </Button>
                      </div>
                    ))}
                  </div>
                </div>
              </div>
            </div>
          )}
        </div>
      );
    }

    if (step === 1) {
      /* The four picks that finish this screen, in the order they appear. All
         panels stay mounted — these guide and jump, they never hide a required
         pick, so the founder can always scroll and see everything.

         This is a caption row, not a second progress bar. The wizard nav above
         is the only row wearing pill chrome now, because the two rows shared
         it: a dashed ring meant "not started" in both, an indigo ring meant
         "done" in both, and four finished picks read as four more step pills
         stacked under the three real ones. The ticks, the order and the
         click-to-scroll targets all stay; only the pill frame goes, so the nav
         owns that language and this row reads as what it is — the four things
         that finish the screen in view. */
      // Template and photo read the resolved row, never the raw id: a stale
      // ?template= link counted here once ticked the screen "4 of 4 done"
      // while the step below it read blocked — see effectiveTemplateId.
      const substeps = [
        { key: "angle", label: "Angle", done: Boolean(angleId), target: "substep-angle" },
        { key: "goal", label: "Goal", done: Boolean(objective), target: "substep-goal" },
        { key: "template", label: "Template", done: Boolean(template?.id), target: "substep-template" },
        { key: "photo", label: "Photo", done: Boolean(template?.id) && missingIdentity.length === 0, target: TEMPLATE_PHOTO_ID },
      ];
      const substepsDone = substeps.filter((s) => s.done).length;

      return (
        <div className="space-y-3">
          <div className="space-y-4" data-testid="audience-goal-step">
            {/* The caption names the scope the nav cannot: these four are one
                screen, not four more steps. No eyebrow — the section heading
                directly above is already an uppercase kicker, and two stacked
                kickers would read as two headings for one row. */}
            <div className="space-y-2">
              <p className="text-xs text-muted-foreground" data-testid="audience-substeps-caption">
                On this screen · {substepsDone} of {substeps.length} done
              </p>
              <div className="flex flex-wrap items-center gap-1" data-testid="audience-substeps" aria-label="What finishes this screen">
                {substeps.map((s, i, all) => {
                  const current = !s.done && all.slice(0, i).every((p) => p.done);
                  return (
                    <button
                      key={s.key}
                      type="button"
                      onClick={() => scrollToSubstep(s.target)}
                      aria-label={s.done ? `${s.label}: done` : current ? `${s.label}: up next` : `${s.label}: not started`}
                      aria-current={current ? "step" : undefined}
                      data-testid={`audience-substep-${s.key}`}
                      data-state={s.done ? "done" : "todo"}
                      className={`tap-chip inline-flex items-center gap-1.5 rounded-full px-2 py-1 text-xs font-semibold transition-colors hover:bg-[color:var(--indigo-8)] ${
                        s.done
                          ? "text-foreground"
                          : "text-muted-foreground hover:text-foreground"
                      }`}
                    >
                      {s.done ? (
                        <Check className="h-3 w-3 text-[color:var(--brand-indigo)]" aria-hidden="true" />
                      ) : (
                        <span aria-hidden="true" className="h-2.5 w-2.5 rounded-full border border-current opacity-60" />
                      )}
                      {s.label}
                    </button>
                  );
                })}
              </div>
            </div>
            {/* No description on this shell. It carried one three times over:
                the progress rail's own sentence above it, and the angle's hint
                below it, both named the same instruction. The rail's sentence is
                gone now too, and what remains here is text specific to what is
                on screen — the angle you picked, and the goals ranked for it.

                The angle is required: the strategy and the render are built
                around it, so a video without one is the generic framing this
                step exists to prevent. Each block on this step is its own
                bordered card so the picker and the goal list
                read as separate organized units. */}
            <div id="substep-angle" className="scroll-mt-4">
            <AngleSelector
              angles={angles}
              angleId={angleId}
              onSelect={handleAnglePick}
              generating={generatingAngles}
              error={angleError}
              onGenerate={handleGenerateAngles}
              onRegenerate={handleRegenerateAngles}
              objective={objective}
              sessionFresh={anglesSessionFresh}
              hookLine={project?.hook_line || ""}
              notice={angleRegenNotice}
              noticeAction={
                angleRegenNotice
                  ? {
                      label: "Go to Review and rebuild",
                      testId: "angle-regen-notice-action",
                      onClick: () => setStep(STEPS.findIndex((s) => s.key === "review")),
                    }
                  : null
              }
              onDismissNotice={angleRegenNotice ? () => setAngleRegenNotice(null) : null}
            />
            </div>

            {/* The goal step is intentionally downstream of the angle. The panel
                only exists once there is an angle to show goals for: before
                that the picker renders just its waits marker, and wrapping an
                empty marker in an inset-panel is how the stray empty box below
                the angle panel happened. The rating lives inside this same
                panel (flush, no nested box) so picker and verdict read as one
                section, not two stacked cards. */}
            <div id="substep-goal" className={angle ? "inset-panel scroll-mt-4 space-y-4" : "hidden"}>
              {angle && facetsError && (
                <p className="text-sm text-destructive" role="alert">
                  {facetsError}{" "}
                  <button type="button" className="underline" onClick={loadFacets} data-testid="goal-options-retry">
                    Try again
                  </button>
                </p>
              )}
<AngleGoalPicker
              angle={angle}
              value={objective}
              onPick={handleGoalPick}
              options={objectiveOptions}
              recommendations={recommendedObjectives}
              outcomes={objectiveOutcomes}
              fitReasons={objectiveFitReasons}
              objectiveEvidence={objectiveEvidence}
              pairEvidence={pairEvidence}
              suggestions={angle?.goal_suggestions}
              liveGoals={liveGoals}
              onGenerate={handleGenerateGoals}
              generating={liveGoalsLoading}
              generationError={liveGoalsError}
              onRegenerate={handleRegenerateGoals}
              regenerating={cyclingGoals}
            />
              {angle && objective && (
                <ComponentThumbs
                  component="goal"
                  flush
                  question="Is this the right goal for your customers?"
                  hint="Rates the goal only. It shapes future goal suggestions for this app."
                  resetKey={`${angleId}:${objective}`}
                  refs={{
                    brand_profile_id: profileId,
                    studio_project_id: project?.id,
                    detail: `objective=${objective};kind=${angle.kind || ""}`,
                  }}
                  testId="goal-feedback"
                />
              )}
              {/* Nothing starts on the goal pick — no powered generation and
                  no ranked read: every template request waits for this click
                  (ADR 0098). One reflexive tap on a neighbouring goal must
                  cost exactly nothing. The button carries the work: idle it
                  says Generate, processing it says Tailoring templates with
                  a looping sweep — no helper line below while it runs. */}
              {angle && objective && profileId && !(recommendationsVisible && visibleRecommendations.length > 0) && (
                <div className="space-y-2">
                  <Button
                    variant="accent"
                    className="w-full gap-1.5"
                    onClick={() => runTailoring(false)}
                    disabled={tailoring}
                    busy={tailoring}
                    etaSeconds={BUSY_ETA_SECONDS.templates}
                    data-testid="templates-generate"
                  >
                    <Sparkles className="h-3.5 w-3.5" /> {tailoring ? "Tailoring templates" : "Generate tailored templates"}
                  </Button>
                  {!tailoring && (
                    <p className="text-sm text-muted-foreground">
                      Tailoring runs only when you click it — switching goals never starts it.
                    </p>
                  )}
                </div>
              )}
            </div>
            {/* Angle, goal, template and photo share one step now: the angle
                picker above, the goal it ranks, then the templates filtered
                below it. No step change between choosing and seeing what the
                choice ranks. */}
            {!objective && angle && (
              <p className="text-sm text-muted-foreground">
                Pick a goal above — tailored templates are one click away.
              </p>
            )}
            {/* The flight owns the screen: the button above is the only
                narrator while tailoring runs (its looping sweep carries the
                wait), and the cards wait for it to settle — a half-set is not
                a ranked set. No count line, no second spinner. */}
            {tailorError && !tailoring && (
              <p className="text-sm text-muted-foreground">{tailorError}</p>
            )}
            {templateId && !template && templatesLoaded && recKey === recRequestKey && (
              // The pick names nothing the lists carry — a stale ?template=
              // link or a draft adopted from a deleted row. The step stays
              // blocked, the sync above never sends it, and the red button on
              // Review names the way back, so this only has to say what
              // happened rather than leave a step that cannot proceed and
              // will not say why.
              <p className="text-sm text-muted-foreground" data-testid="template-gone-notice">
                That template is no longer available — pick another below.
              </p>
            )}
            {/* The flight owns the screen: the status below is the only
                narrator while tailoring runs, and the cards (or their
                empty-state) wait for it to settle — a half-set is not a
                ranked set. */}
            {objective && !tailoring && recommendationsVisible && visibleRecommendations.length === 0 && (
              <div className="inset-panel">
                <p className="text-base">No templates recommended for this app yet.</p>
                <p className="mt-1 text-sm text-muted-foreground">
                  {recError
                    ? `Ranking failed (${recError}).`
                    : "Nothing ranked for this profile and goal."}
                </p>
              </div>
            )}
            {objective && !tailoring && recommendationsVisible && visibleRecommendations.length > 0 && (
              <div className="space-y-4">
                <div className="flex flex-wrap items-center justify-between gap-2">
                  <span className="eyebrow block">
                    {tailoredReady ? "Tailored for this app" : "Recommended"}
                  </span>
                  {profileId && objective && (
                    <div className="flex min-w-0 shrink-0 flex-wrap items-center justify-end gap-2">
                      <Button
                        variant="ghost"
                        size="sm"
                        className="gap-1.5"
                        onClick={() => runTailoring(true)}
                        disabled={tailoring}
                        title="Replace this goal's tailored templates with a fresh set"
                      >
                        <RefreshCw className="h-3.5 w-3.5" /> Regenerate
                      </Button>
                    </div>
                  )}
                </div>
                {/* Shared fit notes, read once: the scorer reasons per factor
                    (goal, category, angle kind), so every card in this set can
                    earn identical bullets. Repeating those on each card turned
                    evidence into wallpaper, so the server hoists notes every
                    visible card shares and each card keeps only what
                    differentiates it. Renders only when the server sent shared
                    notes — older stubbed responses without the keys read as
                    before, per card.

                    The section reads ONE of them: the strongest, which is
                    first because the server sorts reasons by weight. That
                    single note answers why this set ranks at all, which is the
                    section's whole job. The rest are echoes of input the
                    founder just gave (their app's category, an "open to anyone"
                    tiebreak) and cost a line each above a grid they came to
                    pick from — this block used to run six sentences and ~90
                    words, longer and louder than the cards it summarised.
                    The limits stay, as their own lines: each one changes what
                    the founder has to do (a template needing a photo, a draft
                    that is not approved yet). "Bounded by" is not among them
                    any more — those claims bound the ANGLE, and the picked
                    angle's panel states them directly above this list. */}
                {(sharedFit.reasons.length > 0 || sharedFit.limitations.length > 0) && (
                  <div className="space-y-1 text-sm text-muted-foreground" data-testid="templates-shared-fit">
                    {sharedFit.reasons.length > 0 && (
                      <p data-testid="templates-shared-reason">{sentenceCase(sharedFit.reasons[0])}</p>
                    )}
                    {sharedFit.limitations.length > 0 && (
                      <ul className="space-y-1">
                        {sharedFit.limitations.map((limitation, i) => (
                          <li
                            key={`sl-${i + 1}`}
                            className="flex items-start gap-1.5 leading-relaxed"
                          >
                            <span aria-hidden="true" className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
                            <span>{sentenceCase(limitation)}</span>
                          </li>
                        ))}
                      </ul>
                    )}
                  </div>
                )}
                {/* Exactly three template cards (ADR 0096): one row, no "show
                    more", and the grid matches the count. */}
                <div id="substep-template" className="grid scroll-mt-4 grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3" data-testid="templates-grid">
                {visibleRecommendations.slice(0, 3).map((r, i) => (
                  <div key={r.template.id} className="min-w-0">
                    <RecommendationCard
                      r={r}
                      index={i}
                      selected={templateId === r.template.id}
                      onSelect={() => handleTemplatePick(r.template.id)}
                    />
                  </div>
                ))}
                </div>
              </div>
            )}

            {template && (
              <div className="inset-panel text-base">
                <div className="flex items-center gap-2">
                  <span className="font-semibold">{template.name}</span>
                  <Badge variant="secondary" className="text-xs">
                    {humanize(template.category)}
                  </Badge>
                  {/* Says which of the two states the founder is in. A
                      preselected template is a starting point scored for this
                      app and this goal, and clicking any other card replaces it
                      — but nothing on screen would otherwise distinguish that
                      from a pick they made. */}
                  {!templateChosenByHand.current && (
                    <Badge variant="secondary" className="text-xs">
                      Suggested
                    </Badge>
                  )}
                </div>
                {/* Trimmed: the picked card above already shows the outcome and
                    why-it-fits, so repeating them here doubled the reading.
                    This box keeps only what the card doesn't: the length +
                    middle (TemplateShape) and the photo jump. Once a plan
                    exists the middle is the approved script, never the
                    template's generic middle (ADR 0108). */}
                <TemplateShape template={template} middle={project?.script || project?.spoken_middle || ""} />
                {/* The requirement is stated in one line rather than as a
                    checklist. It was a fourth place the same photograph was
                    reported — template card, upload panel, asset row, and the
                    "Attached" block below all showed it — and the photo section
                    immediately underneath is where the photo actually lives, so
                    the card's job is to say whether anything is still owed and
                    point at it. */}
                {template.required_assets?.length > 0 && project && missingIdentity.length > 0 && (
                  <Button
                    variant="secondary"
                    size="sm"
                    className="mt-2"
                    onClick={scrollToTemplatePhoto}
                  >
                    <ImageIcon className="h-3.5 w-3.5" /> Add your photo below
                  </Button>
                )}
              </div>
            )}

            {effectiveTemplateId && (
              <ComponentThumbs
                component="template"
                question="Is this template a good fit for your customers?"
                hint="Rates the template only. It reorders and reshapes future template suggestions."
                resetKey={effectiveTemplateId}
                refs={{
                  brand_profile_id: profileId,
                  studio_project_id: project?.id,
                  template_id: effectiveTemplateId,
                }}
                testId="template-feedback"
              />
            )}

            {/* Presentational: the photo section only renders once a template
                is picked, so the studio never shows a blank section waiting
                for a template that was never selected. The empty-text state
                ("Pick a template above first") was removed — with no template
                there is nothing to attach a photo to, so the section is hidden
                entirely rather than showing a blank label. The control itself
                is PresenterPhotoControl in SelectionPanels (Part 3): the page
                keeps the template-picked condition and the project writes,
                the panel owns the markup and the anchor id. */}
            {templateId && (
              <PresenterPhotoControl
                project={project}
                profileId={profileId}
                busy={busy}
                onEnsureProject={ensureProject}
                onProjectChanged={(fresh) => dispatchDraft({ type: "project-received", project: fresh || project })}
                onRefreshProject={() => {
                  // Re-read the project's attached assets so the picker updates.
                  // Silent on failure: the pre-change project is still valid.
                  api.getStudioProject(project.id).then(receiveProject).catch(() => {});
                }}
              />
            )}
          </div>
        </div>
      );
    }

    if (step === 2) {
      return (
        <div className="space-y-3">
        {/* The two halves of this step, once a plan exists to read. Before
            that the plan states below (failed / generating / missing) are the
            whole step and there is nothing to render yet, so no tabs. */}
        {scriptVersion > 0 && (
          <div
            className="inline-flex items-center gap-1 self-start rounded-xl border border-[color:var(--hairline)] bg-[color:var(--indigo-6)] p-1"
            role="tablist"
            aria-label="Review sections"
          >
            {[
              { key: "plan", label: "Read the plan" },
              { key: "render", label: "Render & result" },
            ].map((tab) => (
              <button
                key={tab.key}
                type="button"
                role="tab"
                aria-selected={effectiveReviewTab === tab.key}
                onClick={() => setReviewTab(tab.key)}
                data-testid={`review-tab-${tab.key}`}
                className={`rounded-lg px-3 py-1.5 text-sm font-semibold transition-colors ${
                  effectiveReviewTab === tab.key
                    ? "bg-[color:var(--indigo-15)] text-foreground shadow-[var(--shadow-xs)]"
                    : "text-muted-foreground hover:text-foreground"
                }`}
              >
                {tab.label}
              </button>
            ))}
          </div>
        )}
        {!project?.script_version && planFailed && !busy ? (
          /* A plan attempt ran and failed. The page-level error above says why;
             this offers the retry. Manual and enabled: nothing fires on its
             own (ADR 0122), so the retry is the only way forward from here.
             The photo is not listed: it is required to render, never to plan. */
          <div className="inset-panel space-y-4">
            {/* The retry buttons lead and the explanation follows them: one red
                button naming the single gap, then the goal list (which shows
                its waits marker until the angle is picked). Button and subtitle
                sit in one panel so the ask never splits in two. */}
            {firstGap && (
              <Button
                variant="accent"
                className="gap-1.5"
                onClick={() => setStep(firstGap.step)}
                data-testid="plan-first-gap-button"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {firstGap.label}
              </Button>
            )}
            {angle && !objective && (
              /* Angle and goal are chosen on step 1, not here: this panel used
                 to carry the shared selector, but a second full copy beside
                 the retry button split the flow in two. The red button above
                 names whichever choice is missing first, and the goal list
                 below stays absent until an angle exists — only an angle can
                 rank it. */
              <AngleGoalPicker
                angle={angle}
                value={objective}
                onPick={handleGoalPick}
                options={objectiveOptions}
                recommendations={recommendedObjectives}
                outcomes={objectiveOutcomes}
                  fitReasons={objectiveFitReasons}
                  suggestions={angle?.goal_suggestions}
                  showGoals={showGoals}
                  landingGate
                  liveGoals={liveGoals}
                  onGenerate={handleGenerateGoals}
                  generating={liveGoalsLoading}
                  generationError={liveGoalsError}
                  onRegenerate={handleRegenerateGoals}
                  regenerating={cyclingGoals}
                />
              )}
            <Button
              variant="accent"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate || !objective || !angle}
              busy={busy}
              etaSeconds={BUSY_ETA_SECONDS.planStrategy}
              data-testid="plan-retry-button"
            >
              <Sparkles className="h-4 w-4" />
              {busy ? "Generating your plan" : "Try again"}
            </Button>
            {!busy && (
              <>
                <p className="text-base text-muted-foreground">
                  The plan didn't generate. Fix what's missing below, then try again — still free.
                </p>
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  Writes hook, script, shots, and demo note. Editable below.
                </p>
              </>
            )}
          </div>
        ) : !project?.script_version && (busy || loading) ? (
          /* No plan yet, and work is genuinely in flight: a click-fired
             generation is writing, or the draft is still loading. This panel
             is the only narrator while the plan writes: one concise button
             label with a looping sweep, no count line below it. */
          <div className="inset-panel space-y-4">
            <Button
              variant="accent"
              disabled={busy}
              busy={busy || loading}
              etaSeconds={busy ? BUSY_ETA_SECONDS.planStrategy : null}
              data-testid="plan-progress-button"
            >
              {loading && !busy ? "Loading your draft" : "Generating your plan"}
            </Button>
          </div>
        ) : !project?.script_version && canGenerate && effectiveObjective && angle ? (
          /* Every input is set and no plan exists yet: the step waits for
             the founder's click (ADR 0122). Arriving here — or going back
             and returning — writes nothing on its own; this button is the
             generation, carrying the same countdown the retry does. The
             stored goal counts (effectiveObjective), so a draft that
             already holds one offers the button instead of the picker. */
          <div className="inset-panel space-y-4">
            <Button
              variant="accent"
              onClick={handleGeneratePlan}
              disabled={busy}
              etaSeconds={BUSY_ETA_SECONDS.planStrategy}
              data-testid="plan-generate-button"
            >
              <Sparkles className="h-4 w-4" />
              Generate your plan
            </Button>
            <p className="text-base text-muted-foreground">
              Nothing is written yet. Your choices are set — generate the free
              plan when you&rsquo;re ready, then read it here.
            </p>
            <p className="text-sm text-muted-foreground" data-subtitle="">
              Writes hook, script, shots, and demo note. Editable below.
            </p>
          </div>
        ) : !project?.script_version ? (
          /* No plan and a profile, a template or the goal is missing. Name
             it and fix it here — picking the goal below readies this step's
             Generate button; the plan still waits for that click. */
          <div className="inset-panel space-y-4">
            {/* One red button to the first missing choice, in flow order. The
                two black navigation buttons this replaces named their
                destinations but sat beside two different subtitles, so the
                panel read as three separate asks. The button names where it
                goes; the single subtitle below stays constant. Angle and goal
                stay fixable in place just beneath it. */}
            <GroupLabel icon={ListChecks}>Still missing</GroupLabel>
            {firstGap && (
              <Button
                variant="accent"
                className="gap-1.5"
                onClick={() => setStep(firstGap.step)}
                data-testid="goto-first-gap-button"
              >
                <Sparkles className="h-3.5 w-3.5" />
                {firstGap.label}
              </Button>
            )}
            <p className="text-sm text-muted-foreground" data-subtitle="">
              Set the choices above, then generate your free plan here.
            </p>
            {/* Angle and goal are chosen on step 1, not here. The red button
                above names the first missing choice, and the goal list below
                stays absent until an angle exists; angle selection itself
                lives in exactly one place. */}
            {angle && !objective && (
              <AngleGoalPicker
                angle={angle}
                value={objective}
                onPick={handleGoalPick}
                options={objectiveOptions}
                recommendations={recommendedObjectives}
                outcomes={objectiveOutcomes}
                fitReasons={objectiveFitReasons}
                suggestions={angle?.goal_suggestions}
                showGoals={showGoals}
                landingGate
                liveGoals={liveGoals}
                onGenerate={handleGenerateGoals}
                generating={liveGoalsLoading}
                generationError={liveGoalsError}
                onRegenerate={handleRegenerateGoals}
                regenerating={cyclingGoals}
              />
            )}
          </div>
        ) : (
          <div className={effectiveReviewTab === "plan" ? "space-y-4" : "hidden"}>
            {/* Regenerating replaces a plan that may have been edited and
                approved, so it asks first — the same rule as the strategy
                rebuild, and for the same reason. The status beside it names
                the current version and whether it holds words: a version with
                nothing written is a blank row, never a plan, and says so
                rather than wearing a check it did not earn. */}
            {project?.script_version > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  busy={busy}
                  etaSeconds={BUSY_ETA_SECONDS.planStrategy}
                  onClick={confirmRegeneratePlan}
                  data-testid="plan-regenerate-button"
                >
                  <RefreshCw className="h-3.5 w-3.5" />
                  {busy ? "Regenerating plan" : "Regenerate plan"}
                </Button>
                {!busy && (
                  <p className="text-sm text-muted-foreground" data-testid="plan-version-status">
                    Plan v{project.script_version}
                    {(project.hook_line || project.script)
                      ? " · generated ✓"
                      : " · empty — regenerate to write it"}
                  </p>
                )}
              </div>
            )}
            <div className="inset-panel space-y-4" data-testid="review-thumb-loop">
              <span className="eyebrow block">Does this plan work?</span>
              <ThumbPair
                value={reviewThumb}
                disabled={busy || !project?.script_version}
                upLabel="Looks good"
                downLabel="Write a better one"
                testId="review-thumb"
                onChange={handleReviewThumb}
              />
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Thumbs up moves on; thumbs down writes a fresh plan for you.
              </p>
            </div>
            <GroupLabel icon={FileText}>Script</GroupLabel>
            {/* What the chosen template is aiming to leave them with, above the
                hook and script it was picked to carry. The plan step showed the
                words and nothing about their intent, so a founder reading a
                hook had no way to tell whether it served the outcome the
                template was chosen for or was about to drift off it. Read-only
                and from the template, not the plan: it does not change when the
                script is edited, and regenerating the plan rewrites the words
                rather than the aim. Renders nothing for a tailored template
                generated before outcomes existed. */}
            {typeof template?.outcome === "string" && template.outcome.trim() && (
              <div className="inset-panel">
                <GroupLabel icon={Target}>What this is aiming to leave them with</GroupLabel>
                <p className="mt-1 text-base">{sentenceCase(template.outcome.trim())}</p>
                <p className="mt-1 text-sm text-muted-foreground" data-subtitle="">
                  The outcome this template is built for, in their terms.
                </p>
                {/* Its own line, not a clause of the subtitle above: this is the
                    honesty guardrail — the outcome is a framing to write toward,
                    never a promise about what the video will do. Folding it into
                    the subtitle is exactly how it got cut once already, and the
                    budget would have taken it again. */}
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  A framing to aim at, not a result this video can promise.
                </p>
              </div>
            )}
            {/* The arrival clamp, reported. A generated script is measured against the
                middle's seconds and cut to fit before it is stored, so a plan
                arrives renderable rather than needing a repair. When that
                happened the founder is told, with the size of the cut: their
                script is shorter than the model wrote it, and silence about
                that reads as the studio losing words. */}
            {project?.plan_trim?.dropped_chars > 0 && (
              <div className="rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] p-4" data-testid="plan-trimmed-note">
                <p className="text-base">
                  I shortened your script by {project.plan_trim.dropped_chars} characters so it
                  fits the {project.plan_trim.middle_seconds}-second middle
                  {project.plan_trim.budget
                    ? ` (${project.plan_trim.budget} characters is what that many seconds holds)`
                    : ""}
                  . Everything above is spoken exactly as written.
                </p>
              </div>
            )}
            {project?.angle_scene_note && (
              <div className="rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] p-4" data-testid="angle-scene-note">
                <p className="text-base">{project.angle_scene_note}</p>
              </div>
            )}
            <HookLineEditor
              projectId={project?.id}
              value={editValue("hook_line", "")}
              onChange={(next) => dispatchDraft({ type: "edit-field", field: "hook_line", value: next })}
              disabled={busy}
            />
            {/* Real-time, not a saved-plan readout: the count follows the field
                as it is typed, against the same targets and ceilings the render
                validates. */}
            <p className="text-sm text-muted-foreground" data-testid="hook-live-count">
              {spokenCountNote(editValue("hook_line", ""), project?.spoken_check?.hook)}
            </p>
            <div className="space-y-4">
              <label htmlFor="review-script" className="text-sm font-semibold">Script</label>
              <p className="text-sm text-muted-foreground" data-subtitle="">The spoken story after the hook — demo and CTA stay yours.</p>
              <Textarea
                id="review-script"
                value={editValue("script", "")}
                onChange={(e) => dispatchDraft({ type: "edit-field", field: "script", value: e.target.value })}
                className="min-h-[160px]"
              />
              <p className="text-sm text-muted-foreground" data-testid="script-live-count">
                {spokenCountNote(editValue("script", ""), project?.spoken_check?.script)}
              </p>
              {scriptOverBudget && (
                <p className="text-sm text-muted-foreground" data-testid="script-over-budget">
                  The extra words are not spoken. Regenerate the plan to have them rewritten to fit,
                  or shorten the script above.
                </p>
              )}
              {/* Every spoken line carries the clearer-line rewrite, not
                  only a flagged hook: the assist the hook has, per script
                  sentence, each accepted suggestion editing just that
                  sentence through the same draft edit as the textarea. */}
              <ScriptLineRewrites
                projectId={project?.id}
                hookLine={editValue("hook_line", "")}
                script={editValue("script", "")}
                onChange={(next) => dispatchDraft({ type: "edit-field", field: "script", value: next })}
                disabled={busy}
              />
            </div>
            <GroupLabel icon={ShieldCheck}>Checks</GroupLabel>
            {/* The craft score is advisory: it names the weakest part of the
                saved pair and the next rewrite, but no band refuses a render.
                The hard gates are the readiness checks and the spoken counts above. */}
            {project?.quality_report && (
              <div className="inset-panel space-y-3" data-testid="quality-report">
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold">Craft check</p>
                  <p className="text-sm text-muted-foreground">
                    {project.quality_report.grade} · {project.quality_report.total}/100
                  </p>
                </div>
                <p className="text-sm text-muted-foreground">
                  {qualityBandNote(project.quality_report)}
                </p>
                {project.quality_report.next_steps?.length > 0 && (
                  <ul className="space-y-1 text-sm">
                    {project.quality_report.next_steps.slice(0, 2).map((step) => (
                      <li key={step}>{step}</li>
                    ))}
                  </ul>
                )}
                {/* The full breakdown the score is built from: every
                    dimension the backend scores, with its own next step —
                    the grade alone names no fix. */}
                {Object.values(project.quality_report.dimensions || {}).length > 0 && (
                  <ul className="space-y-3" data-testid="quality-dimensions">
                    {Object.values(project.quality_report.dimensions).map((dimension) => (
                      <li key={dimension.key} className="space-y-1">
                        <div className="flex flex-wrap items-baseline justify-between gap-2">
                          <p className="text-sm font-semibold">{dimension.label}</p>
                          <p className="text-sm text-muted-foreground">{dimension.score}/{dimension.max}</p>
                        </div>
                        {dimension.next_step && (
                          <p className="text-sm text-muted-foreground">{dimension.next_step}</p>
                        )}
                      </li>
                    ))}
                  </ul>
                )}
                <p className="text-sm text-muted-foreground">
                  Advisory only — it never blocks a render.
                </p>
              </div>
            )}
            {/* What the middle can actually speak, and what it cannot. The middle's
                seconds hold a fixed number of characters; anything past that is
                dropped from the words reaching the video model, usually the
                payoff sentence. The kept line below is the server's own bound
                text rather than a second implementation of the rule, so what is
                named here is exactly what a render speaks.

                There is no trim control. A generated script is sized to fit
                before it is ever stored (the arrival clamp), so the founder is
                never handed a broken plan to repair by hand — and if they write
                their own over-length words, regenerating the plan is the fix,
                not a second button beside their own editor. */}
            {/* The "Script fit details" disclosure is gone: the two counts and
                the over-budget fix ride beside the fields they measure, live.
                The saved-plan measurement still reaches the page as
                `project.spoken_check` (it sizes those live counts) and as the
                arrival-trim note above. */}
            {/* `cta` and `feature_emphasis` used to sit here as two editable
                fields. Neither is writable any more and neither is returned, so
                leaving the inputs would have looked like editing something and
                silently thrown it away — the exact class of write that let
                `extend_intent` appear to be toggled while the server ignored it.
                A call to action is the founder's own, added in their editor after
                the demo they record, and an editable feature instruction is a
                product demo being planned, which is footage this product does not
                generate. `demo_brief` replaced the second: the plan works out what
                the founder should record, and it is deliberately never passed to
                the render, so correcting it here cannot smuggle a feature
                instruction back into the video. */}
            <div className="inset-panel space-y-4">
              <label htmlFor="review-demo-brief" className="text-sm font-semibold">
                What the demo should show
              </label>
              <Textarea
                id="review-demo-brief"
                value={editValue("demo_brief", "")}
                onChange={(e) => dispatchDraft({ type: "edit-field", field: "demo_brief", value: e.target.value })}
                className="min-h-[70px]"
                placeholder="For example: A spoken recap of one call, then the weekly mood reports screen"
              />
              <p className="text-sm text-muted-foreground" data-subtitle="">
                A note about your own recording — never reaches the render.
              </p>
            </div>
            <div className="space-y-2" data-testid="review-location-field">
              <label htmlFor="review-location" className="text-sm font-semibold text-foreground">
                Location
              </label>
              <Textarea
                id="review-location"
                value={editValue("location", "")}
                onChange={(e) => dispatchDraft({ type: "edit-field", field: "location", value: e.target.value })}
                className="min-h-[86px]"
                placeholder="Describe the place and its visible surroundings."
                data-testid="review-location-input"
              />
              <p className="text-sm text-muted-foreground" data-subtitle="" data-testid="review-location-help">
                This Location feeds the strategy, the prompt and the result.
              </p>
            </div>
            {/* Direction is optional refinement, and it was the densest stack
                in the step: two section labels, a camera select, four
                dropdowns and a live preview between the plan's words and the
                save button. It now sits behind one disclosure whose summary
                says what it holds, so the default read is hook → script →
                checks → save, and a founder who wants a different scene opens
                it deliberately. Camera setup is inside for the same reason:
                it is a framing choice, not a step gate. */}
            <Disclosure
              testId="visual-audio-direction"
              detailsClassName="group inset-panel space-y-3"
              summaryClassName="flex cursor-pointer list-none flex-wrap items-center justify-between gap-2 [&::-webkit-details-marker]:hidden"
              summary={
                <>
                  <GroupLabel icon={AudioLines}>Visual &amp; audio direction</GroupLabel>
                  <Badge variant="outline" className="text-xs">optional</Badge>
                </>
              }
            >
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Optional scene picks; the plan's defaults render as-is.
              </p>
              <div className="space-y-2">
                <label htmlFor="camera-setup" className="text-sm font-semibold">Camera setup</label>
                <select
                  id="camera-setup"
                  data-testid="camera-setup"
                  className={CONTROL_CLASS}
                  value={editValue("camera_setup", "handheld")}
                  disabled={busy}
                  onChange={(e) => {
                    const value = e.target.value;
                    dispatchDraft({ type: "edit-field", field: "camera_setup", value, omitDefault: true, fallback: "handheld" });
                  }}
                >
                  <option value="handheld">Handheld selfie</option>
                  <option value="fixed">Fixed camera</option>
                </select>
                <p className="text-sm text-muted-foreground">
                  {editValue("camera_setup", "handheld") === "fixed"
                    ? "Phone on a shelf or tripod. Head to mid-thigh, natural gestures, no camera movement or automatic zoom. A face reference guides identity, not exact body proportions."
                    : "Mid-chest handheld framing with headroom, subtle sway, and the current centered zoom."}
                </p>
                <p className="text-sm text-muted-foreground">Camera setup controls framing; save, then rebuild the strategy before rendering.</p>
              </div>
              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
                <p className="text-sm font-semibold">Location &amp; wardrobe</p>
                <p className="text-sm text-muted-foreground" data-subtitle="">Updates the field above; wardrobe refines the saved look.</p>
                <DirectionSelect
                  id="review-location-direction"
                  testId="review-location-direction"
                  label="Location"
                  value={dirSel.location}
                  onPick={pickScenePart("location")}
                  options={directionOptions?.location}
                  placeholder="Choose a Location…"
                  disabled={busy}
                  refresh={refreshProps("location", "review-location-refresh")}
                />
                <DirectionSelect
                  id="review-wardrobe"
                  testId="review-wardrobe"
                  label="Wardrobe"
                  value={dirSel.wardrobe}
                  onPick={pickScenePart("wardrobe")}
                  options={directionOptions?.wardrobe}
                  placeholder="Choose wardrobe…"
                  disabled={busy}
                  refresh={refreshProps("wardrobe", "review-wardrobe-refresh")}
                />
                {project?.visual_direction && !edits.visual_direction && (
                  <p className="text-sm text-muted-foreground">
                    Plan default: {sentenceCase(project.visual_direction)}
                  </p>
                )}
                <p id="review-visual-direction-help" className="text-sm text-muted-foreground">
                  Location and wardrobe apply together when you rebuild the strategy. Lighting
                  is set from this video's scene.
                </p>
                {refreshError && (
                  <p role="alert" data-testid="direction-refresh-error" className="text-sm text-red-600">
                    {refreshError}
                  </p>
                )}
              </div>
              {(editValue("visual_direction", "") || editValue("voice_direction", "")) && (
                <div className="inset-panel space-y-1" data-testid="direction-live-preview">
                  <p className="text-sm font-semibold">What will render</p>
                  {editValue("visual_direction", "") && (
                    <p className="text-sm text-muted-foreground">
                      Scene: {sentenceCase(editValue("visual_direction", ""))}
                    </p>
                  )}
                  {editValue("voice_direction", "") && (
                    <p className="text-sm text-muted-foreground">
                      Voice: {sentenceCase(editValue("voice_direction", ""))}
                    </p>
                  )}
                  <p className="text-sm text-muted-foreground" data-subtitle="">
                    Set from this video's plan; save edits before rendering.
                  </p>
                </div>
              )}
            </Disclosure>

            {/* Read-only, and labelled as such, because it sits among seven
                editable fields in the same visual style and founders will
                otherwise try to type in it. It is also the one block that goes
                STALE the moment the script above is edited — the beats describe
                the plan as generated — so the edits warning is repeated here
                where the damage is visible. */}
            {editValue("beat_timeline", []).length > 0 && (
              <details
                className="inset-panel"
                data-testid="shot-timeline"
              >
                <summary className="flex cursor-pointer flex-wrap items-center gap-2">
                  <GroupLabel icon={ListChecks}>Shot timeline</GroupLabel>
                  <Badge variant="outline" className="text-xs">read-only</Badge>
                </summary>
                <div className="mt-2 space-y-2 text-base">
                  {editValue("beat_timeline", []).map((b, i) => (
                    <div key={i} className="flex gap-2">
                      <Badge variant="secondary" className="shrink-0 text-xs">
                        {b.start}&ndash;{b.end}s
                      </Badge>
                      <span className="text-muted-foreground">{b.label}: {sentenceCase(b.text)}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-sm text-muted-foreground">
                  {hasEdits
                    ? "This still describes the plan as generated. Edit the script above and regenerate to bring it back in line."
                    : "Written by the plan to fit this length. Regenerate the plan to rewrite it."}
                </p>
              </details>
            )}

            {/* Length is shown, not edited, and it is not a founder choice at
                all. The template declares it, the project seeds from it, and the
                shot timeline above is written to it. The server refuses a
                duration change once a plan exists precisely because the beats
                were clamped to that number, so the only way to a different
                length is a different template and a regenerated plan. */}
            <div className="inset-panel space-y-1" data-testid="piece-length">
              <div className="flex flex-wrap items-center justify-between gap-2">
                <span className="text-sm font-semibold">Length of the generated piece</span>
                <span className="text-base">{pieceSeconds} seconds</span>
              </div>
              <p className="text-sm text-muted-foreground">
                {project?.script_version
                  ? "The timeline is written to this length. Pick a different template to change it."
                  : "Set by the hook template you pick."}
              </p>
            </div>

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="accent" onClick={() => handleSaveEdits()} disabled={busy || !hasEdits} busy={busy} data-testid="plan-save-button">
                <Save className="h-4 w-4" />
                {busy ? "Saving edits" : "Save edits"}
              </Button>
              {/* No "Mark ready" button. Approval is not a decision the founder
                  makes by hand here: the plan handler marks the project ready
                  as part of generating, because it has just written the words
                  the founder is about to read. A second button said the same
                  thing twice, and a click that could only ever confirm what the
                  studio already knew was a control with no meaning.

                  Saving an edit re-marks, for the same reason: the founder
                  reviewed the exact text they saved, so the approval still
                  describes it. If the server refuses (a
                  missing photograph), the render button below states that real
                  reason instead of sitting disabled behind this control. */}
              {project?.status === "ready_for_generation" && (
                <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Ready for generation.
                </p>
              )}
              {/* Autosave status, same rhythm as the Demo + CTA draft line:
                  narrates the background save so an unpressed button never
                  reads as lost work. Manual saves clear it — the button is
                  the feedback then. */}
              {saveStatus && (
                <p role="status" data-testid="review-autosave-status" className="text-sm text-muted-foreground">
                  {saveStatus}
                </p>
              )}
            </div>
            {hasEdits && (
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Save your edits before rendering — the render speaks them.
              </p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToTemplatePhoto={scrollToTemplatePhoto}
            />

            {/* The render panel closes this step below, so the plan above
                has been read before any render runs. */}
          </div>
        )}
            {/* Plan above, render below: the plan in Review has been read
                before any render down here runs. This is the render half of the
                review sub-tabs: hidden while the plan half is in view (and never
                hidden before a plan exists, so the no-plan states above keep
                their exact behavior). */}
            <div className={scriptVersion && effectiveReviewTab !== "render" ? "hidden" : undefined}>
            {(project?.script_version || !firstGap) && (!angle && project?.script_version ? (
              /* The render is built around the audience angle, so it is the
                 first thing asked for here. This step never generates: its red
                 button sends the founder to Audience & template, where selection
                 lives, instead of spending a call from a screen whose job is
                 the render. Same control and gate as step two; only the red
                 action differs, and its label names the destination. Only once
                 a plan exists: before that the missing panel above already
                 names the gap with its own red button, and a second identical
                 ask below would split one decision in two. */
              <AngleSelector
                angles={angles}
                angleId={angleId}
                onSelect={handleAnglePick}
                showAngles={showAngles}
                landingGate
                generating={generatingAngles}
                error={angleError}
                onGenerate={() => setStep(1)}
                generateLabel="Pick an audience angle first"
                sessionFresh={anglesSessionFresh}
                hookLine={project?.hook_line || ""}
                onRegenerate={handleRegenerateAngles}
                objective={effectiveObjective}
                notice={angleRegenNotice}
                onDismissNotice={angleRegenNotice ? () => setAngleRegenNotice(null) : null}
              />
            ) : !canGenerate && project?.script_version ? (
              <div className="inset-panel space-y-4">
                {/* Names what is actually missing, read from the same two
                    values that gated this panel. It used to spell out the
                    whole chain ("choose an App Profile, goal, and template,
                    then review the free plan") — a fourth copy of an
                    instruction the pills and each step already carry. The red
                    button leads and the explanation follows it: a gate that cannot act
                    names the step that fixes it instead of stating the problem
                    and stopping. Only once a plan exists, for the same reason
                    as the angle gate above: one gap, one red button. */}
                {firstGap && (
                  <Button
                    variant="accent"
                    className="gap-1.5"
                    onClick={() => setStep(firstGap.step)}
                    data-testid="hook-first-gap-button"
                  >
                    <Sparkles className="h-3.5 w-3.5" />
                    {firstGap.label}
                  </Button>
                )}
                <p className="text-base text-muted-foreground">
                  {!profileId
                    ? "Pick an approved App Profile on the first step to continue."
                    : "Pick a template on the Audience & template step to continue."}
                </p>
              </div>
            ) : blockedOnAssets ? (
              <MissingRequirements
                identity={missingIdentity}
                onGoToTemplatePhoto={scrollToTemplatePhoto}
              />
            ) : !project ? (
              <div className="inset-panel">
                {!busy && (
                  <p className="text-base text-muted-foreground">
                    Preparing the video draft for your photo…
                  </p>
                )}
                <Button
                  variant="accent"
                  className="mt-4"
                  disabled={busy}
                  busy={busy}
                  onClick={ensureProject}
                  data-testid="create-draft-button"
                >
                  <Sparkles className="h-3.5 w-3.5" />
                  {busy ? "Creating draft" : "Create the draft"}
                </Button>
              </div>
            ) : (
              <>
                {!project?.script_version ? null : (
                  <>
                    <HookContinuityPanel
                      project={project}
                      onProjectChange={receiveProject}
                    />
                    {project?.strategy && (
                      <ComponentThumbs
                        component="script"
                        question="Does this script speak to your customers?"
                        hint="Rates the generated script only. It guides future scripts for this app."
                        resetKey={`${project.id}:${project.strategy_version || 0}`}
                        refs={{
                          brand_profile_id: profileId,
                          studio_project_id: project.id,
                          template_id: project.template_id,
                          detail: `strategy v${Number(project.strategy_version) || 0}`,
                        }}
                        testId="script-feedback"
                      />
                    )}
                    <div id="review-submit" className="scroll-mt-4">
                      <GenerationPanel
                        project={project}
                        onGenerationChange={(fresh) => {
                          // Adopt the row into project-level state so the
                          // result area never holds a stale pre-poll snapshot
                          // after the backend terminalized it in History.
                          if (fresh && (fresh.status === "completed" || fresh.status === "failed")) {
                            receiveProject({ ...project, last_generation: fresh });
                          }
                          // A completion also arms the finishing step: its
                          // pill ticks and its editor opens on this row,
                          // without waiting for the page-level lookup.
                          if (fresh && fresh.status === "completed") {
                            setFinishedGeneration(fresh);
                          }
                        }}
                        onProjectChange={receiveProject}
                        hasUnsavedEdits={hasEdits}
                        onNavigate={(action) => {
                          if (action === "goto-angle" || action === "goto-photo") {
                            scrollToTemplatePhoto();
                          } else if (action === "goto-finish") {
                            setStep(STEPS.findIndex((s) => s.key === "finish"));
                          } else if (action === "save-edits") {
                            document
                              .getElementById("review-submit")
                              ?.scrollIntoView?.({ behavior: "smooth", block: "start" });
                          } else if (action === "rebuild-strategy") {
                            document
                              .getElementById("strategy-build-button")
                              ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
                          } else if (action === "goto-review") {
                            setReviewTab("plan");
                            scrollToSubmit();
                          }
                        }}
                      />
                    </div>
                  </>
                )}
              </>
            ))}
            </div>
        </div>
      );
    }

    if (step === 3) {
      /* The finishing step. With a finished render it IS the Demo + CTA
         editor, opened on that render — the very loader the standalone
         route renders, so the flow's last step and /demo-cta/:id can never
         disagree about what opening a render means. Without one it says so
         and walks back to the render it is waiting on: a step that cannot
         act yet must navigate to what is missing, not sit blank. */
      if (finishedGeneration) {
        return (
          <DemoCtaGenerationEditor
            key={finishedGeneration.id}
            generationId={finishedGeneration.id}
          />
        );
      }
      return (
        <div className="inset-panel space-y-4" data-testid="finish-needs-render">
          <GroupLabel icon={Smartphone}>Demo + CTA</GroupLabel>
          {finishedGeneration === undefined ? (
            <p role="status" className="text-sm text-muted-foreground">
              Looking for this project&rsquo;s finished render&hellip;
            </p>
          ) : (
            <>
              <p className="text-sm text-muted-foreground">
                Nothing to finish yet. This step opens with your finished render
                loaded in the editor — render the piece first, then continue
                here to add your demo and closing message.
              </p>
              <Button
                variant="accent"
                size="sm"
                onClick={() => {
                  setStep(STEPS.findIndex((s) => s.key === "review"));
                  setReviewTab("render");
                  scrollToSubmit();
                }}
                data-testid="finish-goto-render"
              >
                <Clapperboard className="h-3.5 w-3.5" /> Go to the render
              </Button>
            </>
          )}
        </div>
      );
    }

    // Unreachable: every index in STEPS has a branch above. This is a guard
    // against an index out of range rendering an empty page, so it must not
    // read as a step the founder could have ended up in deliberately.
    return null;
  }

  if (loading) {
    return (
      <PageFrame className="space-y-4">
        <div className="flex items-center gap-2">
          {STEPS.map((s) => (
            <Skeleton key={s.key} className="h-7 w-24 shrink-0 rounded-full" />
          ))}
        </div>
        <div className="surface rounded-2xl">
          <div className="w-full space-y-4" aria-label="Loading studio" data-testid="studio-loading">
            <div className="flex items-start gap-3">
              <Skeleton className="h-8 w-8 shrink-0 rounded-lg" />
              <div className="flex-1 space-y-2">
                <Skeleton className="h-4 w-40" />
                <Skeleton className="h-3 w-full" />
              </div>
            </div>
            <Skeleton className="h-24 rounded-2xl" />
            <Skeleton className="h-24 rounded-2xl" />
          </div>
        </div>
      </PageFrame>
    );
  }

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Clapperboard}
        title="Create Video"
      />
      {/* The step task, directly under the title: the pills below show state
          per step, and this names the one thing to do on the screen in view.
          One guidance line stands here, and it is the only one: the sticky
          footer no longer repeats the step's own sentence. Plain body copy,
          not a data-subtitle, so the subtitle budget (text-sm, 55-60 chars)
          stays for label-attached helpers. */}
      <p className="text-sm text-muted-foreground" data-testid="wizard-step-task">
        {step === 0
          ? "Step 1 of 4: choose the approved app this video is for."
          : step === 1
            ? "Step 2 of 4: Angle, goal, template and photo \u2014 each one ranks the next."
            : step === 2
              ? "Step 3 of 4: read the plan, then render the Hook + Story."
              : "Step 4 of 4: add your demo and closing message in Demo + CTA."}
      </p>
      {/* Progress that tracks state rather than position.
          The tick used to mean "this step is to the left of the one you are on",
          which is not the same thing at all: jump straight to the last step and
          all five showed a tick while nothing had been done. A founder reading
          that has been told they finished the workflow before they started it.

          Each step now declares what makes it satisfied, and the tick means that.
          Ticks are the only color story here: done steps tick, everything else
          shows the same hollow ring. A step that is waiting on the founder
          used to amber its icon, but the amber read as an error and clashed
          with the rest of the row — and the distinction never needed color,
          because the sentence underneath already names what is waiting and the
          pills already announce it. */}
      {/* Progress rail: one navigable bar — the pills were a second nav with
          the same labels, so the bar owns step navigation now. Each segment
          states its step's cumulative quarter (25 / 50 / 75 / 100%) and the live
          score sits at the end; all of it derives from the same step states,
          so the readouts can never disagree. It scrolls with the page — a
          pinned bar over the plan form read as a second, floating layer. */}
      <div data-testid="studio-progress-rail" className="space-y-2">
        <div className="flex items-center gap-2">
        <nav aria-label="Progress" className="flex flex-1 items-stretch gap-1.5">
        {stepStates.map((s, i) => {
          const active = i === step;
          // Cumulative quarters: the segment states how much of the workflow
          // finishes when this step does.
          const cumulative = Math.round(((i + 1) / STEPS.length) * 100);
          // Resolved once per segment: the tick, the label, and the pick below
          // must all agree on the same selection.
          const value = s.state === "done" ? pillValue(s.step.key) : null;
          const isLocked = !unlocked[i];
          const lockedBy = i > 0 ? STEPS[i - 1].label : null;
          const lockTitle = isLocked ? `Locked — finish ${lockedBy} to unlock` : STEP_STATE_COPY[s.state];
          return (
            <button
              key={s.step.key}
              type="button"
              onClick={() => setStep(i)}
              aria-current={active ? "step" : undefined}
              // Announced rather than shown only: the tick is a shape-only cue, and
              // this is the one place the founder looks to answer "what is left".
              aria-label={
                isLocked
                  ? `${s.step.label}: locked — finish ${lockedBy} to unlock, ${cumulative}% complete`
                  : value
                    ? `${s.step.label}: ${value}, done, ${cumulative}% complete`
                    : `${s.step.label}: ${STEP_STATE_COPY[s.state]}, ${cumulative}% complete`
              }
              title={lockTitle}
              data-state={isLocked ? "locked" : s.state}
              data-locked={isLocked ? "true" : "false"}
              data-testid={`studio-progress-segment-${s.step.key}`}
              className={`tap-chip flex min-w-0 flex-1 items-center gap-2 rounded-xl border px-2.5 py-2 text-left transition-colors ${
                isLocked
                  ? "border-dashed border-[color:var(--hairline)] opacity-70 hover:border-[color:var(--indigo-35)]"
                  : active
                    ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                    : s.state === "done"
                      ? "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)]"
                      : "border-dashed border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)]"
              }`}
            >
              <span
                aria-hidden="true"
                className={`inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full text-xs font-semibold ${
                  s.state === "done"
                    ? "bg-[color:var(--brand-indigo)] text-white"
                    : "border border-current text-muted-foreground"
                }`}
              >
                {isLocked ? <Lock className="h-3 w-3" /> : s.state === "done" ? <Check className="h-3 w-3" /> : i + 1}
              </span>
              <span className="flex min-w-0 flex-1 flex-col">
                <span
                  className={`truncate text-xs font-semibold ${
                    active
                      ? "text-[color:var(--brand-indigo)]"
                      : s.state === "done"
                        ? "text-foreground/85"
                        : "text-muted-foreground"
                  }`}
                >
                  {s.step.label}
                </span>
                {/* The pick, or the state in words — never both: a done step
                    names what was chosen, the rest say what is owed. Truncated
                    because an angle label can be a sentence; the full text
                    lives in the aria-label above. */}
                <span className="truncate text-xs text-muted-foreground" aria-hidden="true">
                  {isLocked ? `locked — finish ${lockedBy} to unlock` : value || STEP_STATE_COPY[s.state]}
                </span>
              </span>
              <span
                className="shrink-0 text-xs tabular-nums text-muted-foreground"
                aria-hidden="true"
              >
                {cumulative}%
              </span>
            </button>
          );
        })}
        </nav>
          <span
            role="progressbar"
            aria-label="Studio progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={railPct}
            data-testid="studio-progress-pct"
            className="shrink-0 text-xs tabular-nums text-muted-foreground"
          >
            {railPct}%
          </span>
        </div>
      </div>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {projectParam && (project?.script_version || 0) > 0 && !planBannerDismissed && (
        <Alert variant="warning" data-testid="create-plan-banner">
          <CheckCircle2 className="h-4 w-4" />
          <AlertDescription className="flex w-full flex-wrap items-center justify-between gap-2">
            <span>Plan loaded — change one thing, or generate again.</span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setPlanBannerDismissed(true)}
              aria-label="Dismiss plan notice"
            >
              <X className="h-3.5 w-3.5" />
            </Button>
          </AlertDescription>
        </Alert>
      )}

      {/* The canvas: every step stands on the page as a section, the one in
          view expanded and the rest collapsed to a header and a state chip.
          A locked header cannot open until its predecessor is done; the
          padlock, dimming and "locked — finish <prev> first" banner name
          the seal. Opening an unlocked header walks there exactly like its
          segment — one state machine, one gate set. Disclosure queues no
          request of any kind (ADR 0098). */}
      <div className="page-content-enter space-y-3">
        {STEPS.map((s, i) => {
          const active = i === step;
          const state = stepStates.find((x) => x.step.key === s.key)?.state || "todo";
          const value = state === "done" ? pillValue(s.key) : null;
          const isLocked = !unlocked[i];
          const lockedBy = i > 0 ? STEPS[i - 1].label : null;
          const chipText = isLocked ? `locked — finish ${lockedBy} to unlock` : value || STEP_STATE_COPY[state];
          return (
            <section
              key={s.key}
              data-testid={`wizard-section-${s.key}`}
              data-active={active ? "true" : "false"}
              data-locked={isLocked ? "true" : "false"}
              className={`surface surface-step scroll-mt-24 rounded-2xl ${
                active ? "ring-1 ring-[color:var(--indigo-35)]" : ""
              } ${isLocked ? "opacity-60" : ""}`}
            >
              <button
                type="button"
                onClick={() => setStep(i)}
                aria-expanded={active}
                aria-controls={`wizard-section-body-${s.key}`}
                aria-label={
                  isLocked
                    ? `${s.label}: locked — finish ${lockedBy} to unlock`
                    : `${s.label}: ${chipText}`
                }
                data-testid={`wizard-section-toggle-${s.key}`}
                className="flex w-full items-center gap-2.5 pb-3 text-left"
              >
                <span
                  aria-hidden="true"
                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[color:var(--hairline)] text-xs font-semibold text-muted-foreground"
                >
                  {isLocked ? <Lock className="h-3 w-3" /> : i + 1}
                </span>
                <span className="font-display text-sm font-semibold">{s.label}</span>
                <span
                  data-testid={`wizard-section-chip-${s.key}`}
                  title={isLocked ? `Locked — finish ${lockedBy} first` : value || STEP_STATE_COPY[state]}
                  className={`ml-auto max-w-44 truncate rounded-full border px-2 py-0.5 text-xs ${
                    state === "done" && !isLocked
                      ? "border-[color:var(--indigo-35)] text-foreground"
                      : "border-dashed border-[color:var(--hairline)] text-muted-foreground"
                  }`}
                >
                  {chipText}
                </span>
                {isLocked ? (
                  <Lock
                    aria-hidden="true"
                    className="h-4 w-4 shrink-0 text-muted-foreground"
                  />
                ) : (
                  <ChevronDown
                    aria-hidden="true"
                    className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none ${
                      active ? "rotate-180" : ""
                    }`}
                  />
                )}
              </button>
              {active && (
                <div
                  id={`wizard-section-body-${s.key}`}
                  data-testid={`wizard-section-body-${s.key}`}
                  className="wizard-section-enter border-t border-[color:var(--hairline)] pt-4"
                >
                  {isLocked && (
                    <div
                      data-testid={`wizard-section-locked-${s.key}`}
                      className="inset-panel mb-4 flex items-center gap-2 text-sm text-muted-foreground"
                    >
                      <Lock className="h-4 w-4 shrink-0" aria-hidden="true" />
                      <span>
                        Locked — finish <strong className="font-semibold">{lockedBy}</strong> to unlock{" "}
                        <strong className="font-semibold">{s.label}</strong>.
                      </span>
                    </div>
                  )}
                  {stepContent}
                </div>
              )}
            </section>
          );
        })}
      </div>

      {/* Sticky action bar: the arrow-only pair and the one line naming what
          the step in view is waiting on, in one glass cluster that stays
          within reach however long the canvas runs. Arrow-only — the
          destination lives in the aria-label, never words on the button.
          Continue is locked until the step in view is done: a locked arrow
          shows a padlock and cannot move. The Back arrow stays on every
          step, the last one included — the wizard has no separate exit
          control, so leaving the studio is the sidebar's job. */}
      <div className="sticky bottom-4 z-30 flex justify-center px-2" data-testid="wizard-arrows">
        <div className="flex items-center justify-center gap-2 rounded-full border border-[color:var(--hairline)] bg-background/90 px-2 py-1.5 shadow-lg backdrop-blur">
          <Button
            variant="ghost"
            size="icon"
            onClick={() => setStep(Math.max(0, step - 1))}
            disabled={step === 0}
            aria-label={step === 0 ? "Back (already on the first step)" : `Back to ${STEPS[step - 1].label}`}
            data-testid="wizard-back-button"
            className="h-11 w-11 rounded-full border border-[color:var(--hairline)] bg-background/90 shadow-sm backdrop-blur"
          >
            <ChevronLeft className="h-5 w-5" />
          </Button>
          {/* The one line the task line does not duplicate: what this step is
              waiting on right now, beside the controls that move. */}
          <span
            data-testid="wizard-footer-hint"
            className="max-w-[46ch] px-1 text-sm text-muted-foreground"
          >
            {footerHint}
          </span>
          {/* A ready review has no arrow left to walk: the bar carries the
              one forward action itself, opening the render half the plan was
              read for. Navigation only — the render stays GenerationPanel's. */}
          {STEPS[step].key === "review" && activeStepState?.state === "done" && (
            <Button
              variant="accent"
              size="sm"
              className="gap-1.5"
              onClick={() => {
                setReviewTab("render");
                scrollToSubmit();
              }}
              data-testid="wizard-goto-render"
            >
              <Clapperboard className="h-3.5 w-3.5" /> Go to render
            </Button>
          )}
          {/* Earns prominence: a finished step turns Continue primary, so the
              way forward lights up the moment there is somewhere to go. An
              unfinished step locks Continue: the button is disabled and
              wears a padlock, so the founder sees they must finish this
              step before the next unlocks. The line beside it names what
              is still missing. */}
          {step < STEPS.length - 1 && (
            <Button
              variant={activeStepState?.state === "done" ? "accent" : "secondary"}
              size="icon"
              disabled={activeStepState?.state !== "done"}
              onClick={() => setStep(step + 1)}
              aria-label={
                activeStepState?.state === "done"
                  ? `Continue to ${STEPS[step + 1].label}`
                  : `Locked — finish ${STEPS[step].label} to continue to ${STEPS[step + 1].label}`
              }
              title={
                activeStepState?.state === "done"
                  ? undefined
                  : `Locked — finish ${STEPS[step].label} first`
              }
              data-testid="wizard-continue-button"
              className={`h-11 w-11 rounded-full shadow-sm ${
                activeStepState?.state === "done"
                  ? ""
                  : "cursor-not-allowed border border-dashed border-[color:var(--hairline)] opacity-60"
              }`}
            >
              {activeStepState?.state === "done" ? (
                <ChevronRight className="h-5 w-5" />
              ) : (
                <Lock className="h-5 w-5" />
              )}
            </Button>
          )}
        </div>
      </div>
    </PageFrame>
  );
}
