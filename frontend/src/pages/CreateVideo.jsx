import { RecommendationCard, TemplateShape, AngleSelector, AngleGoalPicker } from "../components/studio/SelectionPanels";
import { DirectionSelect, PlanPhaseLine } from "../components/studio/ReviewPanels";
import HookLineEditor from "../components/studio/HookLineEditor";
import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { createWizardDraft, wizardDraftReducer } from "./wizardDraft";
import { useWizardTemplates } from "../hooks/useWizardTemplates";
import { useWizardDirections } from "./useWizardDirections";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
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
import SafetyPanel from "../components/SafetyPanel";
import { useTourEligibility } from "../components/onboarding/OnboardingProvider";

import HookContinuityPanel from "../components/HookContinuityPanel";
import GenerationPanel from "../components/GenerationPanel";
import { ThumbPair } from "../components/ThumbPair";
import { ComponentThumbs } from "../components/ComponentThumbs";
import AssetLibrary from "./AssetLibrary";
import { api, getErrorMessage } from "../lib/api";
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

import { readPieceSeconds } from "../lib/videoLength";
// FileText was the "Creative plan" step's icon. That step held nothing but a
// button and is now the top of Review, so the icon went with it.
import { Clapperboard, Loader as Loader2, TriangleAlert as AlertTriangle, Briefcase, Target, Image as ImageIcon, Check, Sparkles, RefreshCw, Save, CircleCheck as CheckCircle2, ChevronDown, ChevronLeft, ChevronRight, FileText, AudioLines, ListChecks, ShieldCheck, Ruler, X } from "lucide-react";
// toast left with AttachedPhoto, the only place on this page that raised one.
// Detaching now happens inside the photo section, which reports its own
// outcome.

// The order is the product, and it is deliberate.
//
//   profile -> angle+goal+template+photo -> review+submit (plan above, render below)
//
// The script is written, checked for banned claims and read by the founder
// BEFORE any video is rendered. The last step then renders the piece that
// script describes: the strategy is built from the approved plan, so the words
// the founder read are the words that get rendered.
//
// This was the other way round. The hook came first, so a founder approved a
// strategy on trust, rendered, and only then read a script describing a
// different video — with the claim check and the SafetyPanel running against
// text nobody had looked at before the render.
/**
 * The three steps, in order.
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
const LEGACY_STEP_KEYS = { template: "angle", hook: "review" };
const STEPS = [
  { key: "profile", label: "App Profile", icon: Briefcase },
  { key: "angle", label: "Audience & template", icon: Target },
  { key: "review", label: "Review & submit", icon: CheckCircle2 },
];

/**
 * What the selected template is still waiting on.
 *
 * Face-only product: the character reference is the single permitted asset
 * and every template requires exactly it. Without a photograph of the
 * person the model would invent one, and the founder would pay for a video
 * of somebody who looks nothing like them. The server refuses that case
 * before rendering, so this is the early warning rather than the guarantee.
 */
function MissingRequirements({ identity, onGoToTemplatePhoto }) {
  if (!identity || identity.length === 0) return null;

  return (
    <div className="inset-panel space-y-4">
      {/* The button leads and the explanation follows it: the button says where
          the upload is, and the upload is on the template step now. It used
          to point at a step called "Assets" whose only content was this same
          upload. */}
      {onGoToTemplatePhoto && (
        <Button variant="secondary" size="sm" onClick={onGoToTemplatePhoto}>
          <ImageIcon className="h-3.5 w-3.5" /> Add your photo
        </Button>
      )}
      <p className="text-base font-semibold">
        This template needs a character reference before it can generate
      </p>
      <p className="text-sm text-muted-foreground" data-subtitle="">
        Your photograph is what the generated video is built from.
      </p>
    </div>
  );
}

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/** What each progress state means, in words. Used for the pill tooltip and
 *  the aria-label, because both a tick and a dashed border are shape-only. */
const STEP_STATE_COPY = {
  done: "done",
  todo: "not started",
  blocked: "needs something from you",
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
function stepCompletion({ profileId, objective, angleId, templateId, project, missingIdentity, hasEdits }) {
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
    }
    return { step, state };
  });
}

/* One owner per half of the Script fit details disclosure. */
function hasSpokenCounts(project) {
  return Boolean(project?.spoken_check);
}
function hasSpokenPartition(project) {
  return Boolean(project?.strategy?.hook_line && typeof project?.spoken_middle === "string" && project.spoken_middle);
}

export default function CreateVideo() {
  const [params, setSearchParams] = useSearchParams();
  const navigate = useNavigate();

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
  const [angles, setAngles] = useState([]);
  // The GOAL axis of the verdict tally, keyed by objective name and fetched
  // with the angles (`objective_evidence` on the same response). Own state,
  // because it is not per angle: a goal's verdicts are shared across kinds, so
  // they cannot hang off one angle row. Cleared wherever angles are cleared.
  const [objectiveEvidence, setObjectiveEvidence] = useState({});
  // The intersection axis: kind × objective, keyed "kind‖objective". Own
  // state for the same reason as objectiveEvidence — it is not per angle.
  const [pairEvidence, setPairEvidence] = useState({});
  const adoptAngles = useCallback((data, onAngles = () => {}) => {
    setAngles(data?.angles || []);
    setObjectiveEvidence(data?.objective_evidence || {});
    setPairEvidence(data?.pair_evidence || {});
    onAngles(data?.angles || []);
    return data?.angles;
  }, []);
  // Angles can be generated from in here, not just on the profile page:
  // sending the founder out of the wizard to make an optional angle usable
  // was a round trip the flow never offered a way back from.
  const [generatingAngles, setGeneratingAngles] = useState(false);
  const [angleError, setAngleError] = useState(null);
  // Click-to-view gate for angles. This step always starts gated: one
  // "Generate angles" CTA, never a finished list — and "Regenerate" only
  // ever appears beside a visible list, i.e. when there is a current
  // generation to be unhappy with. The reveal lasts for the visit, not the
  // mount: entering the step without a pick re-arms the CTA (see below), so
  // navigating away and back never greets an unpicked founder with a stale
  // list. A pick bypasses the gate entirely — a draft or deep link that
  // already names an angle has been viewed by definition.
  const [anglesRevealed, setAnglesRevealed] = useState(false);
  const revealAngles = useCallback(() => {
    setAnglesRevealed(true);
  }, []);
  // Whether the angles in state were generated in-session (gate click or
  // in-list regenerate) rather than loaded as cached rows from an earlier
  // approval. A new video always starts blank: the gate generates fresh on
  // first click instead of revealing a set timestamped hours ago. Once fresh,
  // step re-entry re-arms the CTA as a free reveal of the set just made, so
  // returning never spends a second call. Reset with the reveal itself
  // whenever the app changes.
  const [anglesSessionFresh, setAnglesSessionFresh] = useState(false);
  // Cycling goal suggestions on the selected angle. Persists server-side per
  // angle, so the re-read of the angles list is the new state.
  const [cyclingGoals, setCyclingGoals] = useState(false);
  const [angleRegenNotice, setAngleRegenNotice] = useState(null);
  // What a completed angle regen cost: how many of the profile's drafts were
  // built on angles it replaced. Shown as a one-line notice after the fact —
  // the pre-click confirm only covers the selected angle, so this is how a
  // draft on a DIFFERENT angle learns it lost its story. Count of 0 shows
  // nothing: a clean regen is not news.
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
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  // A plan attempt ran and failed (or draft creation refused). While true,
  // Review shows the retry path instead of the generating spinner: without
  // this the failure state is indistinguishable from an attempt in flight,
  // and the spinner spins forever because the auto latch (below) rightly
  // refuses to re-fire the same selection-set on its own. Cleared whenever a
  // new attempt starts.
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
  // replacement, so the claim check and ready gate keep working as before.
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
  // Consecutive AI refinements per saved plan version. Capped so a thumbs-down
  // loop can never spin the text model unboundedly on one plan.
  const reviewRefinesRef = useRef({});

  const profileId = project?.brand_profile_id || selectedProfileId;
  const {
    recommendations, sharedFit, recError, recKey, recRequestKey, clearRecommendations,
    runTailoring, tailoring, tailorError, tailorCount, tailorTotal,
    tailoredReady, recommendationsVisible, visibleRecommendations,
  } = useWizardTemplates({ profileId, angleId, objective });
  // Every app lands gated: switching apps re-arms the CTA so a revealed set
  // for one app never leaks into another app's first view.
  useEffect(() => {
    setAnglesRevealed(false);
    setAnglesSessionFresh(false);
    setAngleRegenNotice(null);
  }, [profileId]);
  const angle = angles.find((a) => a.id === angleId) || null;
  // The list reads revealed when the gate was clicked, or when the pick names
  // a real row — selecting an angle is itself the viewing the gate asks for.
  // A pick alone is deliberately not enough: a stale ?angle= param or a draft
  // pointing at a deleted angle must not open a list of strangers on first
  // view, which is the exact screenshot this rule fixes.
  const showAngles = anglesRevealed || Boolean(angle);
  // The reveal lasts for the visit, not the mount. Entering the angle step
  // without a resolved pick re-arms the CTA, so a list revealed earlier
  // never greets a founder who navigated away and back unpicked. A resolved
  // angle still bypasses the gate — a reopened draft shows its own angle,
  // never an empty gate — while a dangling pick re-gates like any other
  // visit with nothing to show.
  useEffect(() => {
    if (STEPS[step]?.key === "angle" && !angle) setAnglesRevealed(false);
  }, [step, angle]);
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
  const scrollToSubstep = (id) => {
    document.getElementById(id)?.scrollIntoView?.({ behavior: "smooth", block: "start" });
  };
  // Regenerating the audience angles without leaving the wizard. Offered on
  // a populated list and behind the landing gate alike, because the
  // regenerate endpoint keeps hand-written angles server-side: what the
  // founder wrote on the profile page survives this call. (The bare generate
  // endpoint replaces the whole set and stays empty-list-only — that
  // distinction is why a populated list never uses it.)
  //
  // But generated angles that have a project built on them are deleted and
  // rewritten fresh: the draft survives, the story it was planned around does
  // not. A confirm at the click — the same pattern as plan regen — names that
  // before it happens instead of two screens later.
  //
  // Reports success so the landing gate can open the list only on a real
  // fresh set: a failed spend leaves the gate (and its error) in place.
  const handleRegenerateAngles = useCallback(async () => {
    if (!profileId) return false;
    const selectedHasProject = Boolean(project && project.content_angle_id && project.content_angle_id === angleId);
    if (selectedHasProject) {
      const ok =
        typeof window === "undefined" || typeof window.confirm !== "function"
          ? false
          : window.confirm(
              "A draft on this step is built around the angle you picked. Regenerating replaces that " +
                "angle's text with new material and the draft loses its story. Continue?"
            );
      if (!ok) return false;
    }
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
        // Plain words, named next step: the angle the draft was planned
        // around no longer exists, and the fix is rebuilding the strategy
        // for the new angle at Review. The button below carries the founder
        // there — a notice with no action is a dead end.
        setAngleRegenNotice(
          affected === 1
            ? "Regenerated. 1 draft was planned around an angle that no longer exists — its story is gone. A new angle is already picked for this draft; rebuild its strategy at Review."
            : `Regenerated. ${affected} drafts were planned around angles that no longer exist — their stories are gone. For each affected draft: pick a new angle, then rebuild its strategy at Review. This draft already has its new angle picked.`
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
  }, [profileId, angleId, project, objective, adoptAngles]);

  // The step's single CTA: "Generate angles", shown on landing instead of any
  // list. The first click always generates fresh: a cached set from an
  // earlier approval is never revealed as-is, so a new video starts blank
  // and lands on fresh rows instead of a "Refreshed 9h ago" line. Over a
  // cached set the regenerate endpoint is used — it keeps hand-written angles
  // server-side, where the bare generate endpoint would discard them — and
  // from empty the bare generate endpoint is safe because nothing exists to
  // discard. Either way the list — and with it "Regenerate" — appears only
  // after this click. A set made in-session is revealed free on step re-entry
  // (anglesSessionFresh), so returning never spends a second call.
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
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setCyclingGoals(false);
    }
  }, [profileId, angleId, adoptAngles]);

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
    // Single flight. Concurrent triggers — a double-tapped Regenerate, the
    // auto effect racing a manual retry — must not stack minute-long model
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
      const updated = await api.generatePlan(ready.id, {
        objective,
        tone,
      });
      // A freshly generated plan is exactly the text the founder is about to
      // read on Review, so the project is marked ready as part of generating
      // it. There is no manual mark-ready control anywhere: a click that could
      // only confirm what the studio already knew was a button with no meaning,
      // and its absence was read as the render button being broken. The server
      // recomputes claim safety on this call and refuses when a prohibited
      // claim is present, so the gate is unchanged -- it just happens without
      // the founder having to say "I saw it".
      //
      // A refusal is kept as the plan's own state rather than surfaced as a
      // thrown error, because the plan landed and is readable; the render
      // button then states the real reason (a prohibited claim, a missing
      // photograph) instead of the screen looking broken.
      let settled = updated;
      let readyError = null;
      try {
        settled = await api.markProjectReady(updated.id);
      } catch (err) {
        // The plan landed and is readable, so this is not a failure of the step.
        // The render button below names the real reason (a prohibited claim, or
        // a photograph still owed); swallowing this without comment is what made
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
        .getElementById("template-photo")
        ?.scrollIntoView?.({ behavior: "smooth", block: "center" });
    });
  };

  // Autosave mirrors the Demo + CTA editor's draft rhythm (save shortly
  // after every change), but through the server path, not browser storage:
  // Review edits are claim-checked plan text, so only a real save counts.
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
      // it keeps the project approved, and a server refusal (a claim that is now
      // prohibited, a photograph detached) is reported rather than hidden -- so
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
  // generation (claim check + ready marking included), capped at three
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

  // Tone is deliberately NOT editable on this step any more: the video-level
  // Tone dropdown duplicated the App Profile's "Tone / voice" and the voice
  // direction, both collapsing into one downstream delivery field. Voice
  // direction is the single delivery control (ADR 0091); a tone a project
  // already carries still seeds the plan. Length has no editor on this step at
  // all: it is the template's number, and the plan's beat timeline is built
  // to it.

  // Direction dropdowns live in their own lifecycle owner (profile-keyed
  // options, per-app picks, saved-plan matching, per-field refresh). See
  // useWizardDirections: request ids ignore stale loads, picks reset on app
  // switch, and a refresh never destroys the founder's current pick.
  const {
    directionOptions,
    dirSel,
    pickScenePart,
    pickVoice,
    refreshingField,
    refreshError,
    refreshDirectionField,
    refreshProps,
  } = useWizardDirections({ profileId, project, angle, dispatchDraft });

  // The goal the plan is written toward: the wizard's own choice wins, and the
  // draft's stored goal is the fallback so landing on Review with a complete
  // draft always auto-fires — even when this session's state lost the choice
  // (pill-jump, reload) while the server row kept it. Without the fallback the
  // step shows the goal picker and waits, although everything the plan needs
  // is already decided.
  const effectiveObjective = objective || project?.objective || "";

  // Auto-generate the plan on entering Review with a ready draft that has
  // none yet. The step exists to READ the plan, so arriving to an empty step
  // plus a button was a wasted click on every first pass. Same gates as the
  // manual retry below (a profile, a template, a goal, nothing in flight):
  // without them there is nothing to write the plan from. When a gate is
  // unmet the step names the missing input instead of spinning; a failed
  // attempt sets planFailed and offers the retry, and the latch below means
  // a failure never loops. Regenerating an existing plan stays a deliberate,
  // confirmed click. Placed after the renderability consts above:
  // the dep array reads them during render, so this cannot live above their
  // declarations the way the other effects do.
  const planAutoAttempted = useRef("");
  // Single-flight latch for plan generation, owned by handleGeneratePlan.
  // `busy` state cannot do this job: two taps in the same tick both read the
  // still-false state, so both would start a model call. A ref flips
  // synchronously, collapsing the race before the first await.
  const planInFlightRef = useRef(false);
  // Set when a draft write learns the picked template is gone server-side.
  // Read once by the plan handler below to offer the gap instead of a retry.
  const templateGoneRef = useRef(false);
  useEffect(() => {
    // The plan needs a profile, a template and a goal. The character photo is
    // required to RENDER, not to write the plan, so it does not gate this.
    if (step !== 2 || busy || !canGenerate || !angle) return;
    if (!objective && project?.objective) {
      // The draft already holds the goal but this session's state does not:
      // adopt it so the gates below read one consistent choice and the plan
      // starts on arrival. Returned from, not fallen through, because the
      // state update re-runs this effect and the fire happens there — firing
      // here would send the draft's goal while `objective` is still empty.
      dispatchDraft({ type: "goal-selected", value: project.objective });
      return;
    }
    if (!objective) return;
    if (project?.script_version) return;
    const key = `${profileId}:${templateId}:${angleId || ""}:${objective || ""}:${tone || ""}`;
    if (planAutoAttempted.current === key) return;
    planAutoAttempted.current = key;
    handleGeneratePlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleGeneratePlan is a render-scoped closure, same as handleGenerateStrategy in the auto-build below; the key ref guards re-fires, and listing it would re-run the effect on every render.
  }, [step, busy, canGenerate, objective, profileId, templateId, angleId, angle, tone, project?.id, project?.script_version, project?.objective]);

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
     label-attached helpers only. Navigation stays free — a hint names what is
     missing, it never locks the arrows. */
  const activeStepState = stepStates.find((s) => s.step.key === STEPS[step].key);
  /* The action bar's one line: what the step in view is waiting on. It never
     restates the task line under the title, and it names the click where a
     click is the gate (ADR 0098). */
  let footerHint;
  if (STEPS[step].key === "profile") {
    footerHint = profileId
      ? "Ready \u2014 continue to Audience & template."
      : "Pick the app this video is for.";
  } else if (STEPS[step].key === "angle") {
    footerHint = "Pick an angle and a goal \u2014 templates wait for your click.";
  } else if (activeStepState?.state === "todo") {
    footerHint = "Generate a plan above, read it, then render.";
  } else {
    footerHint = "Save your edits and attach a photo before rendering.";
  }
  // The rail score, derived per segment so the bar, the thirds and the
  // number can never disagree: a done step claims its full third, the step
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
                  <Link to="/brand">Create or approve an App Profile</Link>
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
            <div className="inset-panel">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-base font-semibold">
                    {describeUnapprovedCount(unapproved.length)}
                  </p>
                  {unapproved.length > 3 ? (
                    <details className="mt-0.5">
                      <summary className="cursor-pointer text-sm text-muted-foreground">
                        Show all {unapproved.length} apps
                      </summary>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {unapproved.map(profileLabel).join(", ")}
                      </p>
                    </details>
                  ) : (
                    <p className="mt-1 text-sm text-muted-foreground">
                      {unapproved.map(profileLabel).join(", ")}
                    </p>
                  )}
                  <p className="mt-4 text-sm text-muted-foreground" data-subtitle="">
                    Draft profiles need review before a video can use them.
                  </p>
                  <Button variant="secondary" size="sm" asChild className="mt-4">
                    <Link to="/brand">Review in App Profile</Link>
                  </Button>
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
        { key: "photo", label: "Photo", done: Boolean(template?.id) && missingIdentity.length === 0, target: "template-photo" },
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
              showAngles={showAngles}
              generating={generatingAngles}
              error={angleError}
              onGenerate={handleGenerateAngles}
              onRegenerate={handleRegenerateAngles}
              objective={objective}
              sessionFresh={anglesSessionFresh}
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
                  cost exactly nothing. The action leads; the line under it
                  carries the when, not the cost. */}
              {angle && objective && profileId && !tailoring && !(recommendationsVisible && visibleRecommendations.length > 0) && (
                <div className="space-y-2">
                  <Button
                    variant="accent"
                    className="w-full gap-1.5"
                    onClick={() => runTailoring(false)}
                    data-testid="templates-generate"
                  >
                    <Sparkles className="h-3.5 w-3.5" /> Generate tailored templates
                  </Button>
                  <p className="text-sm text-muted-foreground">
                    Tailoring runs only when you click it — switching goals never starts it.
                  </p>
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
            {/* Tailoring narrates fresh work while it reads, then the cards
                arrive. It sits above the list rather than beside a section
                label: the list is hidden while tailoring runs (a half-set is
                not a ranked set), so a status inside it would be invisible
                exactly when the founder is waiting. */}
            {objective && tailoring && (
              <div className="inset-panel space-y-2" role="status" data-testid="templates-tailoring">
                <p className="flex items-center gap-2 text-sm font-semibold">
                  <Loader2 className="h-4 w-4 animate-spin" />
                  Tailoring templates for this goal…
                </p>
                <p className="text-sm text-muted-foreground" data-testid="templates-progress">
                  Reading template {tailorCount} of {tailorTotal}…
                </p>
              </div>
            )}
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
                    middle (TemplateShape) and the photo jump. */}
                <TemplateShape template={template} />
                {/* The requirement is stated in one line rather than as a
                    checklist. It was a fourth place the same photograph was
                    reported — template card, upload panel, asset row, and the
                    "Attached" block below all showed it — and the photo section
                    immediately underneath is where the photo actually lives, so
                    the card's job is to say whether anything is still owed and
                    point at it. */}
                {showAngles && template.required_assets?.length > 0 && project && missingIdentity.length > 0 && (
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

            {/* The photo upload lives here now rather than on its own step. It
                was the only thing on that step, so a founder picked a template,
                left, uploaded, and came back — and the template step already
                said what was missing and offered a jump. The draft is created
                eagerly from the profile and template (see ensureProject), so by
                the time anyone reaches this there is almost always something to
                attach to. */}
            {/* Second sub-card in the same style, not a divided-off section:
                the parent's gap separates it, the way the angle picker's
                groups sit apart. Same one-line helper at the same size as the
                template card above — the two sit side by side, so a different
                type size read as a different kind of control. The gated
                consequence moved off this line and into the empty state below,
                which is where a founder blocked on a missing template already
                reads why. */}
            {/* The photo is the identity input the render needs, and there is
                nothing for it to attach to until the audience angles have
                been generated: landing on this step straight from the pill,
                before any angle exists, shows the template ask alone rather
                than a section asking for a photograph nothing can use yet.
                The card's "Add your photo below" pointer above is gated the
                same way, so it can never scroll to a section that is not
                there. */}
            {showAngles && (
            <div id="template-photo" className="inset-panel scroll-mt-4 space-y-4">
              <GroupLabel icon={ImageIcon}>Presenter photo</GroupLabel>
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Upload one clear photo of the person you want on camera.
              </p>
              {!templateId ? (
                /* Gated, the card would otherwise be a label and a sentence
                   with nothing under them. This says what is waiting, on the
                   same size and budget as the subtitle above. */
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  Pick a template above first; your photo attaches to it.
                </p>
              ) : !project ? (
                <>
                  <p className="text-base text-muted-foreground">
                    Preparing the video draft for your photo…
                  </p>
                  <Button variant="secondary" size="sm" disabled={busy} busy={busy} onClick={() => ensureProject()}>
                    {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <ImageIcon className="h-3.5 w-3.5" />}
                    Try preparing the draft again
                  </Button>
                </>
              ) : (
                <>
                  <AssetLibrary
                    embedded
                    profileId={profileId}
                    projectId={project.id}
                    projectAssets={project.assets}
                    onProjectChanged={(fresh) => dispatchDraft({ type: "project-received", project: fresh || project })}
                    onChanged={() => {
                      // Re-read the project's attached assets so the picker updates.
                      // Silent on failure: the pre-change project is still valid.
                      api.getStudioProject(project.id).then(receiveProject).catch(() => {});
                    }}
                  />
                </>
              )}
            </div>
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
             this offers the retry. Manual and enabled: the auto latch already
             consumed this selection-set, so nothing here fires on its own. The
             photo is not listed: it is required to render, never to plan. */
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
                  onRegenerate={handleRegenerateGoals}
                  regenerating={cyclingGoals}
                />
              )}
            <Button
              variant="accent"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate || !objective || !angle}
            >
              <Sparkles className="h-4 w-4" />
              Try again
            </Button>
            <p className="text-base text-muted-foreground">
              The plan didn't generate. Fix what's missing below, then try again — still free.
            </p>
            <p className="text-sm text-muted-foreground" data-subtitle="">
              Writes hook, script, shots, and demo note. Editable below.
            </p>
          </div>
        ) : !project?.script_version && (busy || loading || (canGenerate && effectiveObjective && angle)) ? (
          /* No plan and nothing wrong: an attempt is in flight, the draft is
             still loading, or every input is present and the auto effect fires
             next — reading the stored goal too, so a draft that already holds
             one spins instead of flashing the picker. Only these three cases
             may show a spinner. */
          <div className="inset-panel space-y-4">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm font-semibold">
                {loading && !busy ? "Loading your draft…" : "Generating your plan…"}
              </span>
            </div>
            <p className="text-sm text-muted-foreground">
              {loading && !busy
                ? "Picking up where you left off."
                : <PlanPhaseLine />}
            </p>
          </div>
        ) : !project?.script_version ? (
          /* No plan and the auto effect cannot fire: a profile, a template or
             the goal is missing. Name it and fix it here — choosing the goal
             starts the plan on its own, no button press. */
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
              Your free plan starts once all required choices are set.
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
                  onClick={confirmRegeneratePlan}
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <RefreshCw className="h-3.5 w-3.5" />}
                  Regenerate plan
                </Button>
                <p className="text-sm text-muted-foreground" data-testid="plan-version-status">
                  Plan v{project.script_version}
                  {(project.hook_line || project.script)
                    ? " · generated ✓"
                    : " · empty — regenerate to write it"}
                </p>
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
              report={project.safety_report}
              disabled={busy}
            />
            <div className="space-y-4">
              <label htmlFor="review-script" className="text-sm font-semibold">Script</label>
              <p className="text-sm text-muted-foreground" data-subtitle="">The spoken story after the hook — demo and CTA stay yours.</p>
              <Textarea
                id="review-script"
                value={editValue("script", "")}
                onChange={(e) => dispatchDraft({ type: "edit-field", field: "script", value: e.target.value })}
                className="min-h-[160px]"
              />
            </div>
            <GroupLabel icon={ShieldCheck}>Checks</GroupLabel>
            <SafetyPanel report={project.safety_report} summary={project.safety_summary}
              busy={busy || autosaving} hasEdits={hasEdits} />
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
            {/* Both spoken lines counted, against the length each one aims at.
                The hook line used to be the one count nothing showed: the middle
                had a budget and the opening line had none, so an over-long hook
                was stored, sent and cut mid-sentence with nothing on screen
                saying so. The numbers here are the server's own
                (spoken_check), measured on the saved plan — which is the plan a
                render validates — rather than a second arithmetic in the
                browser that could disagree with what the render does. */}
            {(hasSpokenCounts(project) || hasSpokenPartition(project)) && (
              <Disclosure
                testId="script-fit-details"
                detailsClassName="inset-panel space-y-4"
                summaryClassName="flex cursor-pointer flex-wrap items-center gap-2"
                summary={<GroupLabel icon={Ruler}>Script fit details</GroupLabel>}
              >
                <p className="text-sm text-muted-foreground">
                  Character counts and what the middle speaks. If Generate is disabled over words that do not fit, the reason is in here.
                </p>
              {hasSpokenCounts(project) && (
              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3" data-testid="spoken-counts">
                <GroupLabel>How the two lines measure up</GroupLabel>
                {[
                  { key: "hook", label: "Hook line" },
                  { key: "script", label: "Script" },
                ].map(({ key, label }) => {
                  const line = project.spoken_check[key] || {};
                  const chars = Number(line.chars) || 0;
                  const target = Number(line.target) || 0;
                  const ceiling = Number(line.ceiling) || 0;
                  const overCeiling = line.verdict === "over_ceiling";
                  return (
                    <p key={key} className="text-sm text-muted-foreground">
                      <span className="font-semibold">{label}: </span>
                      {chars} characters{target ? `, aiming for about ${target}` : ""}
                      {overCeiling
                        ? ` — past the ${ceiling} characters these seconds can speak, so it is cut back before the render.`
                        : chars > target
                          ? " — longer than the target, which is a choice, not a fault."
                          : "."}
                    </p>
                  );
                })}
                <p className="text-sm text-muted-foreground">
                  {project.spoken_check.story?.coherent
                    ? "The hook names the problem and the script closes it."
                    : "The two lines should read as one thought: the hook naming the problem this viewer has, the script answering it."}
                </p>
              </div>
            )}
            {hasSpokenPartition(project) && (
              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3" data-testid="spoken-partition">
                <GroupLabel>What the middle will say</GroupLabel>
                <p className="text-base">{sentenceCase(project.spoken_middle)}</p>
                {/* What is not spoken is counted by the server, not sliced out
                    of the script here. The kept words are no longer always a
                    prefix of the script — an over-long middle gives up the
                    sentences in the MIDDLE of itself and keeps the one that
                    resolves the hook — so a browser slice would name words that
                    are in fact spoken and miss the ones that are not. */}
                {(Number(project?.spoken_overflow?.dropped_chars) || 0) > 0 ? (
                  <p className="text-sm text-muted-foreground">
                    {project.spoken_overflow.dropped_chars} characters of the script are past the
                    middle&apos;s spoken budget and are not spoken. Regenerate the plan to have it
                    rewritten to fit, or shorten the script above and rebuild the strategy.
                  </p>
                ) : (
                  <p className="text-sm text-muted-foreground" data-subtitle="">
                    Your whole script fits the middle — every word is spoken.
                  </p>
                )}
              </div>
            )}
              </Disclosure>
            )}
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
                What you record for the demo
              </label>
              <Textarea
                id="review-demo-brief"
                value={editValue("demo_brief", "")}
                onChange={(e) => dispatchDraft({ type: "edit-field", field: "demo_brief", value: e.target.value })}
                className="min-h-[70px]"
                placeholder="For example: Record yourself tapping the timer once, hands only"
              />
              <p className="text-sm text-muted-foreground" data-subtitle="">
                A note to you, not the model — never reaches the render.
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
                placeholder="Describe the place and its visible surroundings only — lighting and time of day live in Lighting."
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
                Optional scene and voice picks; the defaults render as-is.
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
                    : "Close handheld framing, subtle camera movement, and the current centered zoom."}
                </p>
                <p className="text-sm text-muted-foreground">Camera setup controls framing and camera movement. Save changes, then rebuild and review the strategy before rendering.</p>
              </div>
              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
                <p className="text-sm font-semibold">Location, lighting &amp; wardrobe</p>
                <p className="text-sm text-muted-foreground" data-subtitle="">Updates the field above; lighting and wardrobe refine it.</p>
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
                  id="review-lighting"
                  testId="review-lighting"
                  label="Lighting"
                  value={dirSel.lighting}
                  onPick={pickScenePart("lighting")}
                  options={directionOptions?.lighting}
                  placeholder="Choose lighting…"
                  disabled={busy}
                  refresh={refreshProps("lighting", "review-lighting-refresh")}
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
                  The final Location, lighting and wardrobe are applied together when you rebuild the strategy. Camera setup still owns how it is filmed.
                </p>
                {refreshError && (
                  <p role="alert" data-testid="direction-refresh-error" className="text-sm text-red-600">
                    {refreshError}
                  </p>
                )}
              </div>
              <div className="space-y-2 border-t border-[color:var(--hairline)] pt-3">
                <DirectionSelect
                  id="review-voice-direction"
                  testId="review-voice-direction"
                  label="Voice direction"
                  value={dirSel.voice}
                  onPick={pickVoice}
                  options={directionOptions?.voice}
                  placeholder="Choose a voice direction…"
                  disabled={busy}
                  refresh={refreshProps("voice", "review-voice-refresh")}
                />
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
                    Picks update instantly here — save edits before rendering.
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
              <Button variant="accent" onClick={() => handleSaveEdits()} disabled={busy || !hasEdits} busy={busy}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save edits
              </Button>
              {/* No "Mark ready" button. Approval is not a decision the founder
                  makes by hand here: the plan handler marks the project ready
                  as part of generating, because it has just written the words
                  the founder is about to read. A second button said the same
                  thing twice, and a click that could only ever confirm what the
                  studio already knew was a control with no meaning.

                  Saving an edit re-marks, for the same reason: the founder
                  reviewed the exact text they saved, so the approval still
                  describes it. If the server refuses (a prohibited claim, a
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
                  {autosaving && <Loader2 className="mr-1 inline h-3.5 w-3.5 animate-spin" />}
                  {saveStatus}
                </p>
              )}
            </div>
            {hasEdits && (
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Save your edits before rendering. Edits are claim-checked.
              </p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToTemplatePhoto={scrollToTemplatePhoto}
            />

            {/* The render panel closes this step below, so the claim check above
                has been read before any render runs. */}
          </div>
        )}
            {/* Plan above, render below: the claim check in Review has been read
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
                generating={generatingAngles}
                error={angleError}
                onGenerate={() => setStep(1)}
                generateLabel="Pick an audience angle first"
                sessionFresh={anglesSessionFresh}
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
                <p className="text-base text-muted-foreground">
                  Preparing the video draft for your photo…
                </p>
                <Button
                  variant="accent"
                  className="mt-4"
                  disabled={busy}
                  busy={busy}
                  onClick={ensureProject}
                  data-testid="create-draft-button"
                >
                  {busy ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Sparkles className="h-3.5 w-3.5" />}
                  Create the draft
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
                        onGenerationChange={() => {}}
                        onProjectChange={receiveProject}
                        hasUnsavedEdits={hasEdits}
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
          ? "Step 1 of 3: choose the approved app this video is for."
          : step === 1
            ? "Step 2 of 3: Angle, goal, template and photo \u2014 each one ranks the next."
            : "Step 3 of 3: read the plan, then render the Hook + Story."}
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
      {/* Sticky progress rail: the pills stay in reach while the canvas
          scrolls, and the line under them states real completion — the score
          in percent beside a bar ticked at the third marks, both derived from
          the same states, so the readouts can never disagree. The rail itself
          is transparent: the pills and the score are the chrome, not a panel. */}
      <div
        data-testid="studio-progress-rail"
        className="sticky top-14 z-30 space-y-2 lg:top-0"
      >
        <nav aria-label="Progress" className="flex flex-wrap items-center gap-1.5">
        {stepStates.map((s, i) => {
          const active = i === step;
          const Icon = s.state === "done" ? Check : s.step.icon;
          // Resolved once per pill: the tick, the label, and the suffix below
          // must all agree on the same pick.
          const value = s.state === "done" ? pillValue(s.step.key) : null;
          return (
            <button
              key={s.step.key}
              type="button"
              onClick={() => setStep(i)}
              aria-current={active ? "step" : undefined}
              // Announced rather than shown only: the tick is a shape-only cue, and
              // this is the one place the founder looks to answer "what is left".
              aria-label={value
                ? `${s.step.label}: ${value}, done`
                : `${s.step.label}: ${STEP_STATE_COPY[s.state]}`}
              title={STEP_STATE_COPY[s.state]}
              data-state={s.state}
              data-testid={`step-pill-${s.step.key}`}
              className={`pill-studio tap-chip inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-semibold ${
                active
                  ? "border-[color:var(--indigo-35)] bg-primary/15 text-[color:var(--brand-indigo)] shadow-[0_0_10px_var(--brand-indigo)]"
                  : s.state === "done"
                    ? "border-[color:var(--hairline)] text-foreground/80 hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)] hover:text-foreground"
                    : "border-dashed border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)] hover:text-foreground"
              }`}
            >
              {s.state === "todo" || s.state === "blocked" ? (
                // A hollow ring for anything not done — "not started" and
                // "needs something from you" share it. The difference between
                // the two lives in the sentence underneath and in the announced
                // label, not in color: an amber icon read as an error state.
                <span
                  aria-hidden="true"
                  className="h-3 w-3 rounded-full border border-current opacity-60"
                />
              ) : (
                <Icon className="h-3 w-3" />
              )}
              {s.step.label}
              {value && (
                // The pick beside the tick, truncated: an angle label can be
                // a sentence, and the row wraps rather than scrolling. The
                // full text lives in the title and the aria-label above.
                <span
                  aria-hidden="true"
                  title={value}
                  className="max-w-40 truncate font-normal opacity-70"
                >
                  : {value}
                </span>
              )}
            </button>
          );
        })}
        </nav>
        <div className="flex items-center gap-2">
          <div
            role="progressbar"
            aria-label="Studio progress"
            aria-valuemin={0}
            aria-valuemax={100}
            aria-valuenow={railPct}
            className="relative h-1 flex-1 overflow-hidden rounded-full bg-[color:var(--hairline)]"
          >
            <span
              data-testid="studio-progress-fill"
              className="absolute inset-y-0 left-0 rounded-full bg-[color:var(--brand-indigo)] transition-[width] duration-300 ease-out motion-reduce:transition-none"
              style={{ width: `${railPct}%` }}
            />
            <span aria-hidden="true" className="absolute inset-y-0 left-1/3 w-px bg-background" />
            <span aria-hidden="true" className="absolute inset-y-0 left-2/3 w-px bg-background" />
          </div>
          <span
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
          Opening a header walks there exactly like its pill — one state
          machine, one gate set, no second navigation model. The sections
          render from state the page already holds: disclosure queues no
          request of any kind (ADR 0098). */}
      <div className="page-content-enter space-y-3">
        {STEPS.map((s, i) => {
          const active = i === step;
          const state = stepStates.find((x) => x.step.key === s.key)?.state || "todo";
          const value = state === "done" ? pillValue(s.key) : null;
          const SectionIcon = state === "done" ? Check : s.icon;
          return (
            <section
              key={s.key}
              data-testid={`wizard-section-${s.key}`}
              data-active={active ? "true" : "false"}
              className={`surface surface-step rounded-2xl ${
                active ? "ring-1 ring-[color:var(--indigo-35)]" : ""
              }`}
            >
              <button
                type="button"
                onClick={() => setStep(i)}
                aria-expanded={active}
                aria-controls={`wizard-section-body-${s.key}`}
                data-testid={`wizard-section-toggle-${s.key}`}
                className="flex w-full items-center gap-2.5 pb-3 text-left"
              >
                <span
                  aria-hidden="true"
                  className="inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-full border border-[color:var(--hairline)] text-xs font-semibold text-muted-foreground"
                >
                  {i + 1}
                </span>
                <SectionIcon
                  aria-hidden="true"
                  className="h-4 w-4 shrink-0 text-[color:var(--brand-indigo)]"
                />
                <span className="font-display text-sm font-semibold">{s.label}</span>
                <span
                  data-testid={`wizard-section-chip-${s.key}`}
                  title={value || STEP_STATE_COPY[state]}
                  className={`ml-auto max-w-44 truncate rounded-full border px-2 py-0.5 text-xs ${
                    state === "done"
                      ? "border-[color:var(--indigo-35)] text-foreground"
                      : "border-dashed border-[color:var(--hairline)] text-muted-foreground"
                  }`}
                >
                  {value || STEP_STATE_COPY[state]}
                </span>
                <ChevronDown
                  aria-hidden="true"
                  className={`h-4 w-4 shrink-0 text-muted-foreground transition-transform duration-200 motion-reduce:transition-none ${
                    active ? "rotate-180" : ""
                  }`}
                />
              </button>
              {active && (
                <div
                  id={`wizard-section-body-${s.key}`}
                  data-testid={`wizard-section-body-${s.key}`}
                  className="wizard-section-enter border-t border-[color:var(--hairline)] pt-4"
                >
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
          destination lives in the aria-label, never words on the button. No
          guards, like the pills: these only move. On the last step the exit
          below is the way back, so the wizard Back stays out of its way: two
          stacked Back controls read as two different footers sharing a
          screen. The pills in the rail above still walk anywhere. */}
      <div className="sticky bottom-4 z-30 flex justify-center px-2" data-testid="wizard-arrows">
        <div className="flex items-center justify-center gap-2 rounded-full border border-[color:var(--hairline)] bg-background/90 px-2 py-1.5 shadow-lg backdrop-blur">
          {!(step === STEPS.length - 1 && project) && (
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
          )}
          {/* The one line the task line does not duplicate: what this step is
              waiting on right now, beside the controls that move. */}
          <span
            data-testid="wizard-footer-hint"
            className="max-w-[46ch] px-1 text-sm text-muted-foreground"
          >
            {footerHint}
          </span>
          {/* Earns prominence: a finished step turns Continue primary, so the
              way forward lights up the moment there is somewhere to go. Never
              disabled — a returning founder can always walk forward to look —
              the line beside it already names what is still missing. */}
          {step < STEPS.length - 1 && (
            <Button
              variant={activeStepState?.state === "done" ? "accent" : "secondary"}
              size="icon"
              onClick={() => setStep(step + 1)}
              aria-label={`Continue to ${STEPS[step + 1].label}`}
              data-testid="wizard-continue-button"
              className="h-11 w-11 rounded-full shadow-sm"
            >
              <ChevronRight className="h-5 w-5" />
            </Button>
          )}
        </div>
      </div>

      {/* The one thing the pills cannot do is leave the studio, so the exit
          stays — on the last step only, which is where it already was. It is
          the single back control there: the wizard Back above hides on this
          step while a draft exists, because the two stacked together read as
          two different footers sharing a screen. The pills still walk back. */}
      {step === STEPS.length - 1 && project && (
        <div className="flex items-center justify-center">
          <Button
            variant="ghost"
            onClick={() => navigate("/app-profiles")}
            aria-label="Back to your app"
            data-testid="wizard-exit-button"
          >
            Back to your app
          </Button>
        </div>
      )}
    </PageFrame>
  );
}
