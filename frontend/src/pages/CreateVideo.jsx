import { useCallback, useEffect, useRef, useState } from "react";
import { Link, useNavigate, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Textarea } from "../components/ui/textarea";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import SafetyPanel from "../components/SafetyPanel";
import HookContinuityPanel from "../components/HookContinuityPanel";
import GenerationPanel from "../components/GenerationPanel";
import AssetLibrary from "./AssetLibrary";
import { api, getErrorMessage } from "../lib/api";
import { recordSignal, classifyScriptEdit } from "../lib/feedback";
import {
  partitionProfiles,
  profileLabel,
  describeUnapprovedCount,
  describeEmptySelection,
} from "../lib/profileSelection";
import {
  requiredAssetStatus,
  blockingRequirements,
} from "../lib/templateRequirements";
import {
  readPieceSeconds,
  sectionSplit,
  clampHookSeconds,
  DEFAULT_HOOK_SECONDS,
} from "../lib/videoLength";
// FileText was the "Creative plan" step's icon. That step held nothing but a
// button and is now the top of Review, so the icon went with it.
import {
  Clapperboard, Loader2, AlertTriangle, Briefcase, Target, LayoutTemplate,
  Image as ImageIcon, Check, Sparkles, RefreshCw,
  Save, CheckCircle2, Star, Plus, Trash2,
} from "lucide-react";
import { toast } from "sonner";

// The order is the product, and it is deliberate.
//
//   profile -> angle -> template -> assets -> plan -> review -> hook & middle
//
// The script is written, checked for banned claims and read by the founder
// BEFORE any video is paid for. The last step then renders the piece that
// script describes: the strategy is built from the approved plan, so the words
// the founder read are the words that get rendered.
//
// This was the other way round. The hook came first, so a founder approved a
// strategy on trust, spent money on a render, and only then read a script
// describing a different video — with the claim check and the SafetyPanel
// running against text nobody had looked at before the spend.
/**
 * The five steps, in order.
 *
 * Was seven. "Assets" and "Creative plan" were steps that existed only to hold a
 * button, and both are now part of the step they belonged to:
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
 * can stall with nothing to do, and nothing is spent until the last one.
 *
 * Last, because this is the only step that spends money. The plan is free text,
 * and it is what that step renders.
 *
 * Named for what it produces rather than for the old hook-first workflow: one
 * render containing a hook and a middle. The demo and the close are the
 * founder's own footage, added afterwards in their editor.
 */
const STEPS = [
  { key: "profile", label: "App Profile", icon: Briefcase },
  { key: "angle", label: "Audience & goal", icon: Target },
  { key: "template", label: "Template & photo", icon: LayoutTemplate },
  { key: "review", label: "Review", icon: CheckCircle2 },
  { key: "hook", label: "Hook & middle", icon: Sparkles },
];

function formatTemplateUse(n) {
  if (!n) return "Never used";
  return n === 1 ? "Used once" : `Used ${n} times`;
}

/**
 * One recommended template.
 *
 * Every fit reason and every limitation is shown, always. They used to be
 * collapsed behind a "Show all N more" link, which was wrong twice over: these
 * ARE the evidence for the choice the founder is making here, and the count
 * they were hiding behind is not a quality signal. The scorer emits one reason
 * per matched factor and sorts by weight, so a single "Built for the 'create
 * curiosity' objective" (3.0) outranks three 1.0 matches — and a miss becomes
 * a LIMITATION rather than a reason, so a template can match strongly and still
 * carry a caveat. Four reasons is not better than two.
 *
 * The score is therefore the number worth reading, and it is already computed
 * server-side (and already what the list is sorted by), so it is shown here
 * rather than left for the founder to infer from ordering.
 *
 * Two blocks, not one: a reason is the case FOR this template and a limitation
 * is the caveat ON it. Rendering them identically made a warning look like
 * supporting evidence.
 *
 * A div with button semantics rather than a <button> because the whole card is
 * the control. There is no longer a nested toggle — the previous one called
 * stopPropagation on click but not on keydown, so Enter and Space on the link
 * selected the template instead of expanding it.
 */
function RecommendationCard({ r, selected, onSelect }) {
  const reasons = Array.isArray(r.why_it_fits) ? r.why_it_fits : [];
  const limits = Array.isArray(r.limitations) ? r.limitations : [];
  const score = Number(r.score);
  const example =
    typeof r.template.example_preview === "string" && r.template.example_preview.trim()
      ? r.template.example_preview.trim()
      : "";
  return (
    <div
      role="button"
      tabIndex={0}
      onClick={onSelect}
      onKeyDown={(e) => {
        if (e.key === "Enter" || e.key === " ") {
          e.preventDefault();
          onSelect();
        }
      }}
      aria-pressed={selected}
      className={`w-full rounded-xl border p-3 text-left transition-colors ${
        selected
          ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
          : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
      }`}
    >
      <div className="flex items-center justify-between gap-2">
        <span className="text-sm font-medium">{r.template.name}</span>
        <span className="flex items-center gap-2">
          <Badge variant="outline" className="text-[11px]">
            {r.suggested_duration}s
          </Badge>
          {Number.isFinite(score) && (
            // The sort key. Not a percentage or a rating: a weighted sum of
            // matched factors, comparable only between these cards.
            <Badge
              variant="outline"
              className="text-[11px]"
              data-testid="template-fit-score"
              title="Fit score — a weighted sum of the factors this template matched. Only comparable against the other templates below."
            >
              Fit {score}
            </Badge>
          )}
          <Badge variant="secondary" className="text-[11px]">
            {formatTemplateUse(r.template.times_used)}
          </Badge>
          {selected && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
        </span>
      </div>
      {example && (
        <p className="mt-1 text-xs text-foreground/80">
          <span className="text-muted-foreground">Sounds like: </span>
          &ldquo;{example}&rdquo;
        </p>
      )}
      {reasons.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/80">
            Why it fits
          </p>
          {reasons.map((reason, i) => (
            <p key={`r-${i}`} className="text-xs text-muted-foreground">{reason}</p>
          ))}
        </div>
      )}
      {limits.length > 0 && (
        <div className="mt-2 space-y-1">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/80">
            Before you use it
          </p>
          {limits.map((limitation, i) => (
            <p key={`l-${i}`} className="text-[11px] text-muted-foreground/80">{limitation}</p>
          ))}
        </div>
      )}
    </div>
  );
}

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

/**
 * The middle's curated structure, under whichever name the row still carries.
 *
 * `middle_structure` replaced `continuation_structure` and a separate
 * `cta_pattern`: the old pair described a chain with a closing beat, which is
 * not what a template declares any more. Rows seeded before the change still
 * carry the retired name, and the backend reads it as a fallback for the same
 * reason. Reading only the new name would leave those templates showing a blank
 * where the curated middle lives, which reads as a template with nothing after
 * its opening.
 */
function middleStructure(template) {
  return String(template?.middle_structure || template?.continuation_structure || "");
}

/**
 * The shape of the piece a template produces: its length, its two section
 * lengths, and the curated middle.
 *
 * Shown on the template card because the template is where the length comes
 * from. A founder choosing between two openings is also choosing between two
 * lengths, and a picker on the step after this used to make that look
 * independent. The numbers are the ones the project will be seeded with, so
 * nothing on the later steps can quietly disagree.
 */
function TemplateShape({ template }) {
  const total = readPieceSeconds(null, template);
  const hook = clampHookSeconds(template?.hook_seconds) || DEFAULT_HOOK_SECONDS;
  const split = sectionSplit(total, hook);
  const middle = middleStructure(template);
  return (
    <div className="mt-2 space-y-1">
      <p className="text-xs">
        <span className="font-medium">{total}s piece</span>: a {split.hookSeconds}s hook, then a{" "}
        {split.middleSeconds}s middle.
      </p>
      {middle && <p className="text-xs text-muted-foreground">{middle}</p>}
    </div>
  );
}

/**
 * What the selected template is still waiting on.
 *
 * Face-only product: the character reference is the single permitted asset
 * and every template requires exactly it. Without a photograph of the
 * person the model would invent one, and the founder would pay for a video
 * of somebody who looks nothing like them. The server refuses that case
 * before spending, so this is the early warning rather than the guarantee.
 */
function MissingRequirements({ identity, onGoToTemplatePhoto }) {
  if (!identity || identity.length === 0) return null;

  return (
    <div className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-4">
      <p className="text-sm font-medium">
        This template needs a character reference before it can generate
      </p>
      <p className="text-xs text-muted-foreground">
        Every video is generated from your photograph — the person on camera
        is the person in the reference, and the scene around them is invented
        from the App Profile. Without one the model would invent somebody else.
      </p>
      {/* The button says where the upload is, and the upload is on the template
          step now. It used to point at a step called "Assets" whose only
          content was this same upload. */}
      {onGoToTemplatePhoto && (
        <Button variant="secondary" size="sm" onClick={onGoToTemplatePhoto}>
          <ImageIcon className="h-3.5 w-3.5" /> Add your photo
        </Button>
      )}
    </div>
  );
}

function StepShell({ icon: Icon, title, description, children }) {
  return (
    <div className="space-y-4">
      <div className="flex items-start gap-3">
        <span className="flex h-10 w-10 shrink-0 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
          <Icon className="h-[18px] w-[18px]" />
        </span>
        <div>
          <h2 className="font-display text-base font-semibold">{title}</h2>
          {description && <p className="mt-0.5 text-sm text-muted-foreground">{description}</p>}
        </div>
      </div>
      {children}
    </div>
  );
}

/**
 * One attached photograph, and a Remove button.
 *
 * This used to carry start/end seconds, an audio role and a gain, plus a "Save
 * timing" button that wrote them back. None of it does anything now. The video
 * is one render with captions composited over it, so there is no in and out
 * point for an asset, and audio mixing was never reachable from the studio —
 * the composition spec is captions only. The controls rendered as though a
 * founder could place their own face on screen at 4 seconds and hear it at
 * twice the volume, and none of those writes changed the output.
 *
 * The photograph itself has no timing either: it rides to the model as an input
 * reference for the whole generation. So a row is now a confirmation that it is
 * attached, and a way to detach it.
 */
function AttachedPhoto({ project, attachment, onChanged }) {
  const detach = async () => {
    try {
      await api.detachAsset(project.id, attachment.asset_id);
      const fresh = await api.getStudioProject(project.id);
      onChanged(fresh);
    } catch (err) {
      toast.error(getErrorMessage(err));
    }
  };

  return (
    <div className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] p-3">
      <Badge variant="secondary" className="shrink-0 text-[11px]">
        {humanize(attachment.kind)}
      </Badge>
      <span className="min-w-0 flex-1 truncate text-sm">
        {attachment.label || attachment.asset_id.slice(0, 8)}
      </span>
      <span className="shrink-0 text-xs text-muted-foreground">
        used for the whole video
      </span>
      <Button variant="ghost" size="sm" aria-label="Remove from project" onClick={detach}>
        Remove
      </Button>
    </div>
  );
}

/** What each progress state means, in words. Used for the pill tooltip and
 *  the aria-label, because both a tick and a dashed border are shape-only. */
const STEP_STATE_COPY = {
  done: "done",
  todo: "not started",
  blocked: "needs something from you",
};

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
function stepCompletion({ profileId, objective, templateId, project, missingIdentity, hasEdits }) {
  const hasPhoto = missingIdentity.length === 0;
  return STEPS.map((step) => {
    let state = "done";
    if (step.key === "profile") state = profileId ? "done" : "todo";
    else if (step.key === "angle") state = objective ? "done" : "blocked";
    else if (step.key === "template") {
      if (!templateId) state = "blocked";
      else if (!hasPhoto) state = "blocked";
    }     else if (step.key === "review") {
      // A plan with unsaved edits is not reviewed. The step says so itself, and
      // a tick here would tell the founder they had finished reading a script
      // they had changed and not stored.
      if (!project?.script_version) state = "todo";
      else if (hasEdits) state = "blocked";
    } else {
      // The render step has NO completion state, deliberately. A clip can be
      // generated, but the workflow does not end there - it ends at "attach
      // your own demo", which happens in the founder's editor and cannot be
      // observed from here. So this step is never ticked: doing so would claim
      // the job is finished when the half the founder still has to shoot is not.
      // It reports what is waiting instead.
      state = templateId && !hasPhoto ? "blocked" : "todo";
    }
    return { step, state };
  });
}

/** The one sentence under the pills. Names the first thing actually waiting. */
function nextStepMessage(stepStates, step) {
  const current = stepStates[step];
  if (current.state === "blocked") {
    if (current.step.key === "angle") {
      return "Next: choose what this video is for. It is the strongest signal in the template score.";
    }
    if (current.step.key === "template" && !stepStates[2].state.startsWith("d")) {
      return "Next: pick a template and add your photo. Both are needed before anything can be generated.";
    }
  }
  if (step === 0) return "Nothing is spent until the last step.";
  // "Everything is ready" has to be measured against the steps that CAN be
  // ready. The render step is deliberately never marked done -- it has no
  // completion state, because a project stays renderable and gets re-rendered
  // -- so `every(s => s.state === "done")` was permanently false and this line
  // was unreachable. Comparing only the steps before it makes the message
  // reachable, and says it at the point where it is true.
  if (stepStates.slice(0, step).every((s) => s.state === "done")) {
    return "Everything before this is ready. This is the only step that costs money.";
  }
  const first = stepStates.findIndex((s) => s.state !== "done");
  if (first > step) {
    return `${stepStates[first].step.label} is still ahead of you.`;
  }
  return "Nothing is spent until the last step.";
}

export default function CreateVideo() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const [step, setStep] = useState(0);
  const [profiles, setProfiles] = useState([]);
  const [angles, setAngles] = useState([]);
  const [facets, setFacets] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [recError, setRecError] = useState(null);
  const [templates, setTemplates] = useState([]);
  const [project, setProject] = useState(null);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);

  const [selectedProfileId, setSelectedProfileId] = useState(params.get("profile") || "");
  const [angleId, setAngleId] = useState(params.get("angle") || "");
  const [templateId, setTemplateId] = useState(params.get("template") || "");
  const [objective, setObjective] = useState("");
  // There is no length state and no intent state any more, and that is the
  // whole point of this step's current shape. Duration is computed: a template
  // declares the length its mechanic suits, the project seeds from it, and the
  // render is that long in one pass. `extendIntent` ("hook only" versus "extend
  // into a full video") asked a question about a chain that no longer exists —
  // there is no hook-only render to choose between.
  const [tone, setTone] = useState("");
  const [edits, setEdits] = useState({});

  const profileId = project?.brand_profile_id || selectedProfileId;
  const profile = profiles.find((p) => p.id === profileId) || null;
  const angle = angles.find((a) => a.id === angleId) || null;
  const template = templates.find((t) => t.id === templateId) || null;

  useEffect(() => {
    let cancelled = false;
    api.getTemplateFacets().then(setFacets).catch(() => setFacets(null));
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
        const requestedProjectId = params.get("project");
        if (requestedProjectId) {
          try {
            const draft = await api.getStudioProject(requestedProjectId);
            const draftProfile = approved.find((p) => p.id === draft.brand_profile_id);
            if (!draftProfile) {
              throw new Error("That draft project is unavailable or its App Profile is not approved.");
            }
            const angleData = await api
              .getContentAngles(draftProfile.id)
              .catch(() => ({ angles: [] }));
            if (cancelled) return;
            setProject(draft);
            setAngles(angleData.angles || []);
            setAngleId(draft.content_angle_id || "");
            setTemplateId(draft.template_id || "");
            setObjective(draft.objective || "");
            setTone(draft.tone || "");
            setRecommendations([]);
            setRecError(null);
            setEdits({});
            // A duplicate always arrives with its plan intact, so it opens on
            // Review; an unplanned draft still needs a photo before a plan can
            // be written. Both indices are looked up by KEY rather than written
            // as numbers: the wizard was seven steps and is now five, and a
            // hardcoded index is exactly what silently sent a deep link past
            // the end of the wizard.
            setStep(
              draft.script_version > 0
                ? STEPS.findIndex((s) => s.key === "review")
                : STEPS.findIndex((s) => s.key === "template")
            );
          } catch (err) {
            if (cancelled) return;
            setError(getErrorMessage(err));
          }
          return;
        }
        const preselected = params.get("profile");
        const chosen =
          approved.find((p) => p.id === preselected) || approved[0] || null;
        if (chosen) {
          // The pick must live in state: profileId drives recommendations,
          // canGenerate, and draft creation, and selectProfile is the only
          // other writer. Reading it from URL params alone left it empty.
          setSelectedProfileId(chosen.id);
          setStep(1);
          api.getContentAngles(chosen.id).then((d) => setAngles(d.angles || [])).catch(() => setAngles([]));
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
  }, [params]);

  useEffect(() => {
    api
      .getTemplates()
      .then((d) => setTemplates((d.templates || []).filter((t) => t.is_usable)))
      .catch(() => setTemplates([]));
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

  const loadRecommendations = useCallback(
    async (pid, aid) => {
      if (!pid) return;
      try {
        const rec = await api.getTemplateRecommendations(pid, {
          angle_id: aid || undefined,
          objective: objective || undefined,
          limit: 6,
        });
        const rows = rec.recommendations || [];
        setRecommendations(rows);
        setRecError(null);
        // Preselect the top pick when the founder has not chosen for
        // themselves. Deliberately not "on every reload": a reload must never
        // move a selection the founder made, so the only condition is that
        // nothing is selected and nothing has ever been hand-picked.
        //
        // setTemplateId is called with a function so the check reads the value
        // at the time this response lands rather than a value captured when the
        // request was made — otherwise a slow response could overwrite a pick
        // made while it was in flight.
        if (rows.length > 0) {
          setTemplateId((current) => {
            if (current || templateChosenByHand.current) return current;
            return rows[0].template.id;
          });
        }
      } catch (err) {
        // An empty list used to mean three different things: nothing ranked,
        // nothing compatible, or the request failed. The third one stranded the
        // founder in front of a step that looked merely thin, so the reason is
        // shown rather than absorbed.
        setRecommendations([]);
        setRecError(getErrorMessage(err));
      }
    },
    [objective]
  );

  useEffect(() => {
    loadRecommendations(profileId, angleId);
  }, [profileId, angleId, loadRecommendations]);

  // Tailored templates generate per (profile, selected objective) — the
  // objective does not exist at approve time, so this is where the request
  // belongs. Auto-fires once per key while the founder reads the step
  // (cache hits return instantly); the button below forces a refresh.
  // Guarded by ref so a remount never pays for a second generation.
  const tailorKeyRef = useRef("");
  const [tailoring, setTailoring] = useState(false);
  const [tailorError, setTailorError] = useState(null);

  const runTailoring = useCallback(async (regenerate) => {
    if (!profileId || !objective) return;
    setTailoring(true);
    setTailorError(null);
    try {
      const res = await api.ensureObjectiveTemplates(profileId, {
        objective,
        ...(regenerate ? { regenerate: true } : {}),
      });
      if (res.generated) {
        await loadRecommendations(profileId, angleId);
      }
      if (res.error) setTailorError(res.error);
    } catch (err) {
      setTailorError(getErrorMessage(err));
    } finally {
      setTailoring(false);
    }
  }, [profileId, objective, angleId, loadRecommendations]);

  useEffect(() => {
    if (step !== 2 || !profileId || !objective) return;
    const key = `${profileId}:${objective}`;
    if (tailorKeyRef.current === key) return;
    tailorKeyRef.current = key;
    runTailoring(false);
  }, [step, profileId, objective, runTailoring]);

  const selectProfile = async (id) => {
    setSelectedProfileId(id);
    setAngles([]);
    setAngleId("");
    setRecommendations([]);
    setRecError(null);
    setEdits({});
    setProject(null);
    // The template is cleared with everything else, because it was chosen
    // against the previous app's profile. This was latent before; auto-selection
    // made it reachable, since a template preselected for one app would survive
    // the switch and the new profile's recommendations would then see a
    // selection already made and decline to preselect theirs.
    setTemplateId("");
    // The objective and tone were left behind, which is the same bug for a
    // different field: both are creative direction chosen against the PREVIOUS
    // app, and both are written onto the next project in createProject. Carrying
    // them over means the new app's plan is built toward another app's goal,
    // and the Audience & goal step shows a choice the founder already made for
    // a product they just switched away from.
    setObjective("");
    setTone("");
    // The latch is per-app, not per-session: a deliberate pick for one app says
    // nothing about the next one, so the new app starts from its own top pick.
    templateChosenByHand.current = false;
    try {
      const d = await api.getContentAngles(id);
      setAngles(d.angles || []);
    } catch {
      setAngles([]);
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
            template_id: templateId || "",
            objective,
            tone,
            ...overrides,
          })
        : await api.createStudioProject({
            brand_profile_id: profileId,
            content_angle_id: angleId || "",
            template_id: templateId || "",
            objective,
            tone,
          });
      setProject(created);
      return created;
    } catch (err) {
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
   * validated BEFORE anything is paid for. Previously the project was only
   * created by the plan step, which forced the Assets step to carry a manual
   * "Create draft" button purely to get out of the way.
   *
   * So: as soon as an App Profile and a hook template are both chosen, the
   * draft is created or updated in the background. Drafts are free — only a
   * marked-ready generation spends money — so doing this eagerly costs
   * nothing. Returns the project, or null when it cannot be created.
   */
  const ensureProject = useCallback(async () => {
    if (!profileId || !templateId) return null;
    try {
      if (project?.id) {
        // Keep the draft's selections in step with the wizard without
        // disturbing a plan that already exists.
        if (
          project.template_id === templateId &&
          project.content_angle_id === (angleId || null) &&
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
          template_id: templateId || "",
          objective,
          tone,
        });
        setProject(updated);
        return updated;
      }
      const created = await api.createStudioProject({
        brand_profile_id: profileId,
        content_angle_id: angleId || "",
        template_id: templateId || "",
        objective,
        tone,
      });
      setProject(created);
      return created;
    } catch (err) {
      // A failure here is not fatal: the plan step still creates the draft and
      // surfaces the error properly. Swallowing it here would just show an
      // empty render step with no explanation.
      setError(getErrorMessage(err));
      return null;
    }
  }, [profileId, templateId, angleId, objective, tone, project]);

  const handleGeneratePlan = async () => {
    const ready = await createProject();
    if (!ready) return;
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
      setProject(updated);
      setEdits({});
      // Straight to the top of Review, which is this step now: the plan is the
      // thing to read, and the render step below it is the first one that
      // spends money. The old indices were 5 (Review) and 6 (Hook & middle);
      // merging the plan step into Review moved both down by one.
      setStep(3);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  /* Takes the founder to the photo upload, wherever they currently are.
     It lives on the template step now, so this both jumps to that step and
     scrolls to the field — otherwise "Add your photo" would land them on a step
     with nothing obviously about photographs in view. */
  const scrollToTemplatePhoto = () => {
    setStep(2);
    // After the step renders, not before: the element does not exist yet.
    requestAnimationFrame(() => {
      document
        .getElementById("template-photo")
        ?.scrollIntoView({ behavior: "smooth", block: "center" });
    });
  };

  const handleSaveEdits = async () => {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      // Measured against the saved script, not the textarea, so a save that
      // changes nothing records nothing.
      const editSignal = Object.prototype.hasOwnProperty.call(edits, "script")
        ? classifyScriptEdit(project.script, edits.script)
        : "";
      const updated = await api.updateStudioProject(project.id, edits);
      if (editSignal) {
        recordSignal("script_edited", editSignal, {
          brand_profile_id: profileId,
          studio_project_id: project.id,
          template_id: project.template_id,
        });
      }
      setProject(updated);
      setEdits({});
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleMarkReady = async () => {
    if (!project) return;
    setBusy(true);
    setError(null);
    try {
      const updated = await api.markProjectReady(project.id);
      setProject(updated);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const canGenerate = Boolean(profileId && templateId);

  // Face-only product: every template requires exactly the character
  // reference, and the backend refuses a generation without one (see
  // _studio_identity_references) as well as any project still holding
  // retired uploads. The requirement used to be decoration: it was listed
  // on the template but nothing stopped the click, so a paid render could
  // go out with no identity input and the model free to invent a presenter.
  //
  // Kept separate from canGenerate on purpose — "you have not chosen a template
  // yet" and "you still owe this template a photograph" are different problems
  // and the founder needs to be told which one they have. The split lives in
  // a tested helper rather than inline here.
  const missingIdentity = template
    ? blockingRequirements(template.required_assets, project?.assets)
    : [];
  // Server-side refusal is the guarantee; this is the early warning. Not folded
  // into canGenerate, because "you have not chosen a template yet" and "you
  // still owe this template a photograph" are different problems.
  const blockedOnAssets = Boolean(template) && missingIdentity.length > 0;
  // What the generated piece is and how long it will be — a statement, not a
  // control. Once a project exists its own number is the authority, because
  // that is the length the plan's beat timeline was written to and the length
  // the render is asked for. Before that, the selected template's declared
  // length is what the project will be seeded from, so showing it predicts the
  // same value rather than offering a second one.
  //
  // The hook is a boundary inside the piece, not a separate clip: it is where
  // the middle begins, clamped to 2-4s because a hook that needs longer to land
  // is not a hook. The middle gets whatever is left, which is why the two
  // numbers below always add up to the piece.
  const pieceSeconds = readPieceSeconds(project, template);
  const hookBoundary = clampHookSeconds(
    project?.hook_seconds || template?.hook_seconds || DEFAULT_HOOK_SECONDS
  );
  const pieceSplit = sectionSplit(pieceSeconds, hookBoundary);

  const editValue = (key, fallback) =>
    edits[key] !== undefined ? edits[key] : project?.[key] ?? fallback;
  const hasEdits = Object.keys(edits).length > 0;

  // Tone is editable here and also seeds the plan, so a change has to move
  // both or going back and regenerating would silently reinstate the old value.
  // Length has no editor on this step at all, editable or otherwise: it is the
  // template's number, and the plan's beat timeline is built to it.
  const editTone = (value) => {
    setTone(value);
    setEdits((prev) => ({ ...prev, tone: value }));
  };

  const setOverlay = (index, patch) => {
    setEdits((prev) => ({
      ...prev,
      overlays: (prev.overlays ?? project?.overlays ?? []).map((o, i) =>
        i === index ? { ...o, ...patch } : o,
      ),
    }));
  };
  const addOverlay = () => {
    setEdits((prev) => ({
      ...prev,
      overlays: [...(prev.overlays ?? project?.overlays ?? []), { start: 0, end: 3, text: "" }],
    }));
  };
  const removeOverlay = (index) => {
    setEdits((prev) => ({
      ...prev,
      overlays: (prev.overlays ?? project?.overlays ?? []).filter((_, i) => i !== index),
    }));
  };

  /* Progress state, derived rather than tracked. A founder can reach any step
     from any other, so nothing here can be a counter that advances — the pills
     have to be recomputed from what actually exists, or they go stale the moment
     they change something on an earlier step. */
  const stepStates = stepCompletion({
    profileId,
    objective,
    templateId,
    project,
    missingIdentity,
    hasEdits,
  });
  const nextUp = nextStepMessage(stepStates, step);

  const stepContent = renderStep();

  function renderStep() {
    if (step === 0) {
      // The gate and the explanation come from one place, so the picker can
      // never become permissive while still claiming it excludes the rest.
      const { approved, unapproved } = partitionProfiles(profiles);
      return (
        <StepShell
          icon={Briefcase}
          title="Which app are you promoting?"
          description="Only approved profiles can be used, so scripts only ever build on facts you have reviewed."
        >
          {approved.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No approved App Profile"
              description={describeEmptySelection(profiles)}
              action={
                <Button variant="brand" asChild>
                  <Link to="/app-profiles">Go to your app</Link>
                </Button>
              }
            />
          ) : (
            <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
              {approved.map((p) => (
                <button
                  key={p.id}
                  type="button"
                  onClick={() => selectProfile(p.id)}
                  className={`rounded-2xl border p-4 text-left transition-colors ${
                    profileId === p.id
                      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                  }`}
                >
                  <div className="flex items-center justify-between gap-2">
                    <span className="font-display text-sm font-semibold">{p.brand_name}</span>
                    {profileId === p.id && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
                  </div>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {p.app_category || p.niche || "Category not set"}
                  </p>
                </button>
              ))}
            </div>
          )}

          {unapproved.length > 0 && (
            <div className="rounded-2xl border border-[color:var(--hairline)] bg-secondary/20 p-4">
              <div className="flex items-start gap-2">
                <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                <div className="min-w-0 flex-1">
                  <p className="text-sm font-medium">
                    {describeUnapprovedCount(unapproved.length)}
                  </p>
                  <p className="mt-0.5 text-xs text-muted-foreground">
                    {unapproved.map(profileLabel).join(", ")}
                  </p>
                  <p className="mt-2 text-xs text-muted-foreground">
                    These are the apps you already created. They are not selectable until you
                    review and approve them, so that a script can only build on facts you have
                    checked.
                  </p>
                  <Button variant="secondary" size="sm" asChild className="mt-3">
                    <Link to="/app-profiles">Review and approve</Link>
                  </Button>
                </div>
              </div>
            </div>
          )}
        </StepShell>
      );
    }

    if (step === 1) {
      return (
        <StepShell
          icon={Target}
          title="Audience and goal"
          description="Pick the audience segment, and say what this video is for. Both change which template is recommended."
        >
          <div className="space-y-4">
            {/* The content angle is optional, and this now says so. It was
                labelled exactly like the objective and read as required, so a
                founder who wanted to move fast reasonably skipped it — then had
                no way to tell that skipping it narrowed the template match. */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                Content angle{" "}
                <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <p className="text-xs text-muted-foreground">
                Who this video is for. Your App Profile already describes your audience, so this
                narrows the match further rather than defining it.
              </p>
              {angles.length === 0 ? (
                <Alert>
                  <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                  <AlertDescription>
                    No content angles on this profile yet. Generate them on the profile page if you
                    want to target one audience — or skip this and pick an objective below.
                  </AlertDescription>
                </Alert>
              ) : (
                <div className="space-y-2">
                  {angles.map((a) => (
                    <button
                      key={a.id}
                      type="button"
                      onClick={() => setAngleId(a.id)}
                      className={`w-full rounded-xl border p-3 text-left transition-colors ${
                        angleId === a.id
                          ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                          : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium">{a.label}</span>
                        <Badge variant="secondary" className="text-[11px]">
                          {humanize(a.kind)}
                        </Badge>
                      </div>
                      {a.user_problem && (
                        <p className="mt-1 text-xs text-muted-foreground">{a.user_problem}</p>
                      )}
                    </button>
                  ))}
                </div>
              )}
            </div>

            {/* What gets generated, stated rather than chosen.
                The two controls this used to sit between — a "what happens
                after the hook" toggle and a total-length picker — are both gone,
                and neither had anything left to decide. There is no hook-only
                render to choose against a full one, and the length is the
                template's: a template declares the length its mechanic suits, the
                project seeds from it, and the render is that long in one pass.
                A picker here would also have been a trap, because the plan's
                beat timeline is written to whatever number was showing, so
                changing it after the plan existed would leave a timeline that no
                longer added up. */}
            <div className="space-y-1.5 rounded-xl border border-[color:var(--hairline)] p-4">
              <span className="text-sm font-medium">What you get</span>
              <p className="text-sm">
                One render of {pieceSeconds}s in two sections: a {pieceSplit.hookSeconds}s hook,
                then a {pieceSplit.middleSeconds}s middle that develops it and stops at the moment
                you would reach for your phone.
              </p>
              <p className="text-xs text-muted-foreground">
                {template
                  ? `The length comes from ${template.name} and is not a choice — pick a different template for a different one.`
                  : "Choose a template and its length is used."}{" "}
                There is no product demo in the generated video and no closing
                card: you record the demo yourself, add your own call to action
                after it, then post the result.
              </p>
            </div>

            {/* The objective is REQUIRED, which it was not until now, and it is
                the heaviest single signal in the template scorer: an exact
                objective match scores 3.0 where a near-miss scores 0.5, and it is
                also what generates the templates tailored to this app for this
                goal. Leaving it optional meant the strongest recommendation
                input was silently dropped whenever a founder skipped it, and the
                template step then claimed to be "scored for this app" on
                materially weaker signal than it said.

                The audience segment is genuinely optional — it narrows the
                match further, but a profile already describes its audience — so
                this one is the required one and that one is not. Saying so here
                is the difference between a rule the founder understands and one
                they trip over. */}
            <div className="space-y-1.5">
              <label htmlFor="objective" className="text-sm font-medium">
                What is this video for? <span className="text-muted-foreground">(required)</span>
              </label>
              <select
                id="objective"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                aria-required="true"
                className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
              >
                <option value="">Choose an objective</option>
                {(facets?.objectives || []).map((o) => (
                  <option key={o} value={o}>{humanize(o)}</option>
                ))}
              </select>
              {!objective && (
                <p className="text-xs text-muted-foreground">
                  Pick one to continue. This is the strongest signal in the
                  template recommendation — a template built for this goal outranks
                  one that merely fits — and tailored templates are generated for the
                  goal you choose here.
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label htmlFor="tone" className="text-sm font-medium">Tone (optional)</label>
              <Input
                id="tone"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder="e.g. calm and direct"
              />
              <p className="text-xs text-muted-foreground">
                Seeds the plan, and you can change it on the Review step.
              </p>
            </div>
          </div>
        </StepShell>
      );
    }

    if (step === 2) {
      return (
        <StepShell
          icon={LayoutTemplate}
          title="Choose a template and add your photo"
          description={
            objective
              ? `Every template below is scored against ${profile?.brand_name || "this app"} and your goal. Pick one, then attach the photo it is generated from.`
              : "Pick a goal on the previous step first — the templates are scored against it."
          }
        >
          <div className="space-y-4">
            {/* No objective means no honest scoring to show. The card list used
                to render anyway with the empty rationale the scorer returns, so a
                founder could pick the top card from reasons that did not mention
                their goal at all. */}
            {!objective && (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm">
                  Choose what this video is for before picking a template.
                </p>
                <p className="mt-1 text-xs text-muted-foreground">
                  The objective is the heaviest signal in the score, and tailored templates are
                  generated for the goal you choose. Without it the list below would be ranked on
                  much weaker evidence while looking identical.
                </p>
                <Button variant="secondary" size="sm" className="mt-3" onClick={() => setStep(1)}>
                  <Target className="h-3.5 w-3.5" /> Set the goal
                </Button>
              </div>
            )}
            {profileId && objective && (
              <div className="flex flex-wrap items-center gap-2">
                {tailoring ? (
                  <p className="flex items-center gap-2 text-xs text-muted-foreground">
                    <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    Tailoring templates for this goal…
                  </p>
                ) : (
                  <Button
                    variant="ghost"
                    size="sm"
                    onClick={() => runTailoring(true)}
                    title="Replace this goal's tailored templates with a fresh set"
                  >
                    <RefreshCw className="h-3.5 w-3.5" /> Regenerate tailored templates
                  </Button>
                )}
              </div>
            )}
            {tailorError && !tailoring && (
              <p className="text-xs text-muted-foreground">{tailorError}</p>
            )}
            {objective && recommendations.length === 0 && (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm">No templates recommended for this app yet.</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {recError
                    ? `The ranking request failed (${recError}) — nothing was ranked, so this is not a verdict on the app. You can still pick one below if the library has anything.`
                    : "Nothing was ranked for this profile and goal — the request may have failed, or this app has no compatible templates. You can still pick one below if the library has anything."}
                </p>
              </div>
            )}
            {objective && recommendations.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">Recommended</span>
                {recommendations.map((r) => (
                  <RecommendationCard
                    key={r.template.id}
                    r={r}
                    selected={templateId === r.template.id}
                    onSelect={() => {
                      // Latched, so a later reload cannot move this pick.
                      templateChosenByHand.current = true;
                      setTemplateId(r.template.id);
                    }}
                  />
                ))}
              </div>
            )}

            {template && (
              <div className="rounded-xl border border-[color:var(--hairline)] p-3 text-sm">
                <div className="flex items-center gap-2">
                  <span className="font-medium">{template.name}</span>
                  <Badge variant="secondary" className="text-[11px]">
                    {humanize(template.category)}
                  </Badge>
                  {/* Says which of the two states the founder is in. A
                      preselected template is a starting point scored for this
                      app and this goal, and clicking any other card replaces it
                      — but nothing on screen would otherwise distinguish that
                      from a pick they made. */}
                  {!templateChosenByHand.current && (
                    <Badge variant="secondary" className="text-[11px]">
                      Suggested
                    </Badge>
                  )}
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{template.opening_structure}</p>
                <TemplateShape template={template} />
                {template.required_assets?.length > 0 && (
                  <div className="mt-2 space-y-1.5">
                    <span className="eyebrow block">Needs from you</span>
                    {requiredAssetStatus(template.required_assets, project?.assets).map((r, i) => (
                      <div key={`${r.kind || "unnamed"}-${i}`} className="flex items-center gap-2 text-xs">
                        {project ? (
                          r.have ? (
                            <Check className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
                          ) : (
                            <span aria-hidden="true" className="h-3.5 w-3.5 shrink-0 rounded-full border border-[color:var(--hairline-strong)]" />
                          )
                        ) : null}
                        <span className={r.have ? "text-muted-foreground" : ""}>{humanize(r.kind)}</span>
                        {!r.have && project && (
                          <span className="text-muted-foreground">
                            — required, the video is generated from it
                          </span>
                        )}
                      </div>
                    ))}
                    {project && missingIdentity.length > 0 && (
                      <Button
                        variant="secondary"
                        size="sm"
                        className="mt-2"
                        onClick={scrollToTemplatePhoto}
                      >
                        <ImageIcon className="h-3.5 w-3.5" /> Attach it below
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}

            {/* The photo upload lives here now rather than on its own step. It
                was the only thing on that step, so a founder picked a template,
                left, uploaded, and came back — and the template step already
                said what was missing and offered a jump. The draft is created
                eagerly from the profile and template (see ensureProject), so by
                the time anyone reaches this there is almost always something to
                attach to. */}
            <div id="template-photo" className="space-y-3 border-t border-[color:var(--hairline)] pt-4">
              <span className="eyebrow block">Your photo</span>
              <p className="text-sm text-muted-foreground">
                Every video is generated from one photograph — the person on camera is the person in
                the reference, and the room around them is written from your App Profile. Without
                one the model invents somebody else.
              </p>
              {!templateId ? (
                <p className="text-sm text-muted-foreground">
                  Pick a template above first — the draft that holds your photo is created from it.
                </p>
              ) : !project ? (
                <>
                  <p className="text-sm text-muted-foreground">
                    A free draft from your profile, goal and template is created so your photo has
                    somewhere to live. Drafts cost nothing; only a marked-ready generation spends
                    money.
                  </p>
                  <Button variant="secondary" size="sm" disabled={busy} onClick={() => ensureProject()}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImageIcon className="h-4 w-4" />}
                    Create the draft
                  </Button>
                </>
              ) : (
                <>
                  <AssetLibrary
                    embedded
                    profileId={profileId}
                    projectId={project.id}
                    projectAssets={project.assets}
                    onProjectChanged={(fresh) => setProject(fresh || project)}
                    onChanged={() => {
                      // Re-read the project's attached assets so the picker updates.
                      api.getStudioProject(project.id).then(setProject).catch(() => {});
                    }}
                  />
                  <div className="space-y-2">
                    <span className="text-[11px] font-semibold uppercase tracking-[0.08em] text-muted-foreground/80">
                      Attached
                    </span>
                    {(project.assets || []).length === 0 ? (
                      <p className="text-sm text-muted-foreground">
                        Nothing attached yet. Attach your photograph above — the video cannot be
                        generated without it.
                      </p>
                    ) : (
                      <div className="space-y-2">
                        {(project.assets || []).map((a) => (
                          <AttachedPhoto
                            key={a.asset_id}
                            project={project}
                            attachment={a}
                            onChanged={setProject}
                          />
                        ))}
                      </div>
                    )}
                  </div>
                </>
              )}
            </div>
          </div>
        </StepShell>
      );
    }

    if (step === 4) {
      return (
        <StepShell
          icon={Sparkles}
          title="Hook & middle"
          description="Read the strategy built from the plan you approved, then render the piece: a hook, then a middle that stops where you would reach for your phone. The demo and the close are yours to record and add afterwards."
        >
          <div className="space-y-3">
            {!canGenerate ? (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm text-muted-foreground">
                  Pick an App Profile and a hook template first — the strategy is built from
                  both, so the piece has to serve the mechanism you picked.
                </p>
              </div>
            ) : blockedOnAssets ? (
              <MissingRequirements
                identity={missingIdentity}
                onGoToTemplatePhoto={scrollToTemplatePhoto}
              />
            ) : !project ? (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm text-muted-foreground">
                  A free draft is created from your profile, angle, and template so the
                  strategy and the piece have somewhere to live. Drafts cost nothing; only a
                  marked-ready generation spends money.
                </p>
                <Button
                  variant="brand"
                  size="sm"
                  className="mt-3"
                  disabled={busy}
                  onClick={() => ensureProject()}
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
                  Create the draft
                </Button>
              </div>
            ) : (
              <>
                {!project?.script_version ? (
                  <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                    <p className="text-sm text-muted-foreground">
                      There is no plan yet, so there are no approved words to render. Generate one
                      on the Review step first — it costs nothing, and it is what the strategy below
                      is built from.
                    </p>
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-3"
                      onClick={() => setStep(3)}
                    >
                      Go to Review
                    </Button>
                  </div>
                ) : (
                  <>
                    <HookContinuityPanel
                      project={project}
                      onProjectChange={setProject}
                    />
                    {/* The one and only render. It used to sit on the review
                        step, where it let money be spent on text the founder had
                        not read yet, and it sat BELOW the segmented chain, which
                        made the chain look like the product.

                        onProjectChange lets the panel build the strategy itself
                        on the way to a paid render. It was a button above,
                        which meant a founder could skip it and pay for a
                        generic take without ever being told the specific one
                        existed. */}
                    <GenerationPanel
                      project={project}
                      onGenerationChange={() => {}}
                      onProjectChange={setProject}
                    />
                  </>
                )}
              </>
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 3) {
      return (
        <StepShell
          icon={CheckCircle2}
          title="Review the plan"
          description="Write your script here, then check every claim in it. Free — nothing is generated until you open the next step."
        >
        {!project?.script_version ? (
          /* The plan button. This was a step of its own that held nothing but
             this button, so a founder pressed it and was immediately told to go
             to the next screen to see the result. It is now the top of the step
             that reads the result. */
          <div className="space-y-3 rounded-xl border border-[color:var(--hairline)] p-4">
            {!templateId && (
              <p className="text-sm text-muted-foreground">
                Choose a template first — the plan is written to serve the one you pick.
              </p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToTemplatePhoto={scrollToTemplatePhoto}
            />
            <Button
              variant="brand"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate || blockedOnAssets}
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              Generate the plan
            </Button>
            <p className="text-xs text-muted-foreground">
              Free, and nothing is charged. It writes the hook line, the script, the shot timeline,
              your on-screen text, and a note on what to record for your own demo — then checks every
              claim in it. Everything it produces is editable below.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
            {/* Regenerating replaces a plan that may have been edited and
                approved. Stating the version is not enough next to a button
                that discards it, so it asks — the same rule as the strategy
                rebuild, and for the same reason. */}
            {project?.script_version > 0 && (
              <div className="flex flex-wrap items-center gap-2">
                <Button
                  variant="secondary"
                  size="sm"
                  disabled={busy}
                  onClick={() => {
                    if (hasEdits) {
                      const ok =
                        typeof window === "undefined" || typeof window.confirm !== "function"
                          ? false
                          : window.confirm(
                              "You have unsaved edits. Generating a new plan replaces this one and " +
                                "your edits are lost. Generate anyway?"
                            );
                      if (!ok) return;
                    } else {
                      const ok =
                        typeof window === "undefined" || typeof window.confirm !== "function"
                          ? true
                          : window.confirm(
                              `Replace plan v${project.script_version} with a new one? The current ` +
                                `plan is discarded.`
                            );
                      if (!ok) return;
                    }
                    handleGeneratePlan();
                  }}
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <RefreshCw className="h-4 w-4" />}
                  Regenerate plan
                </Button>
                <p className="text-xs text-muted-foreground">
                  Plan v{project.script_version}. Regenerating replaces it and bumps the version.
                </p>
              </div>
            )}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Hook line</label>
              <Input
                value={editValue("hook_line", "")}
                onChange={(e) => setEdits({ ...edits, hook_line: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Script</label>
              <Textarea
                value={editValue("script", "")}
                onChange={(e) => setEdits({ ...edits, script: e.target.value })}
                className="min-h-[160px]"
              />
            </div>
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
            <div className="space-y-1.5 rounded-xl border border-[color:var(--hairline)] p-4">
              <label htmlFor="review-demo-brief" className="text-sm font-medium">
                What you record for the demo
              </label>
              <Textarea
                id="review-demo-brief"
                value={editValue("demo_brief", "")}
                onChange={(e) => setEdits({ ...edits, demo_brief: e.target.value })}
                className="min-h-[70px]"
                placeholder="e.g. Record yourself tapping the timer once, hands only"
              />
              <p className="text-xs text-muted-foreground">
                A note to you, not to the model. The generated video ends where you would reach
                for your phone, and this is what happens next — so it never reaches the render,
                and the demo is your own footage attached afterwards.
              </p>
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Visual direction</label>
              <Textarea
                value={editValue("visual_direction", "")}
                onChange={(e) => setEdits({ ...edits, visual_direction: e.target.value })}
                className="min-h-[90px]"
              />
            </div>

            {/* Read-only, and labelled as such, because it sits among seven
                editable fields in the same visual style and founders will
                otherwise try to type in it. It is also the one block that goes
                STALE the moment the script above is edited — the beats describe
                the plan as generated — so the edits warning is repeated here
                where the damage is visible. */}
            {editValue("beat_timeline", []).length > 0 && (
              <div
                className="rounded-xl border border-[color:var(--hairline)] bg-secondary/20 p-4"
                data-testid="shot-timeline"
              >
                <div className="flex flex-wrap items-center gap-2">
                  <span className="eyebrow block">Shot timeline</span>
                  <Badge variant="outline" className="text-[11px]">read-only</Badge>
                </div>
                <div className="mt-2 space-y-1.5 text-sm">
                  {editValue("beat_timeline", []).map((b, i) => (
                    <div key={i} className="flex gap-2">
                      <Badge variant="secondary" className="shrink-0 text-[11px]">
                        {b.start}&ndash;{b.end}s
                      </Badge>
                      <span className="text-muted-foreground">{b.label}: {b.text}</span>
                    </div>
                  ))}
                </div>
                <p className="mt-2 text-xs text-muted-foreground">
                  {hasEdits
                    ? "This still describes the plan as generated. Edit the script above and regenerate to bring it back in line."
                    : "Written by the plan to fit this length. Regenerate the plan to rewrite it."}
                </p>
              </div>
            )}

            {/* Length is shown, not edited, and it is not a founder choice at
                all. The template declares it, the project seeds from it, and the
                shot timeline above is written to it. The server refuses a
                duration change once a plan exists precisely because the beats
                were clamped to that number, so the only way to a different
                length is a different template and a regenerated plan. */}
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <span className="text-sm font-medium">Length of the generated piece</span>
                <p className="rounded-lg border border-[color:var(--hairline)] px-3 py-2 text-sm">
                  {pieceSeconds} seconds
                </p>
                <p className="text-xs text-muted-foreground">
                  {project?.script_version
                    ? "The shot timeline above is written to this length, and it is rendered in one pass. To change it, pick a different template on the Template & photo step and regenerate the plan."
                    : "Set by the hook template you pick. There is no length to choose."}
                </p>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="review-tone" className="text-sm font-medium">Tone</label>
                <Input
                  id="review-tone"
                  value={editValue("tone", "")}
                  onChange={(e) => editTone(e.target.value)}
                  placeholder="e.g. calm and direct"
                />
              </div>
            </div>

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Voice direction</label>
                <Textarea
                  value={editValue("voice_direction", "")}
                  onChange={(e) => setEdits({ ...edits, voice_direction: e.target.value })}
                  className="min-h-[70px]"
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Sound direction</label>
                <Textarea
                  value={editValue("sound_direction", "")}
                  onChange={(e) => setEdits({ ...edits, sound_direction: e.target.value })}
                  className="min-h-[70px]"
                />
              </div>
            </div>

            <div className="rounded-xl border border-[color:var(--hairline)] p-4">
              <div className="flex items-center justify-between gap-2">
                <span className="eyebrow">On-screen text</span>
                <Button variant="ghost" size="sm" onClick={addOverlay}>
                  <Plus className="h-3.5 w-3.5" /> Add text
                </Button>
              </div>
              <p className="mt-1 text-xs text-muted-foreground">
                Added afterwards from your approved script. Without text overlays a
                video is still the generated video, captioned on demand.
              </p>
              {/* The placeholder used to read "Try it free for 3 days" — a
                  pricing and trial-term claim, in a product that deliberately
                  carries no pricing anywhere, and the exact kind of claim the
                  check above is designed to flag. As an example on an input it
                  taught the founder to write precisely what the app refuses. */}
              <p className="mt-1 text-xs text-muted-foreground">
                Keep it to what the App Profile has verified. Ratings, counts and
                trial terms are not yours to state here.
              </p>
              {editValue("overlays", []).length === 0 ? (
                <p className="mt-2 text-sm text-muted-foreground">No on-screen text.</p>
              ) : (
                <div className="mt-3 space-y-2">
                  {editValue("overlays", []).map((o, i) => (
                    <div key={i} className="flex items-end gap-2">
                      <label className="w-20 shrink-0 space-y-1">
                        <span className="text-[11px] text-muted-foreground">Start (s)</span>
                        <Input
                          type="number"
                          min="0"
                          value={o.start}
                          onChange={(e) => setOverlay(i, { start: Number(e.target.value) })}
                          aria-label={`Overlay ${i + 1} start`}
                        />
                      </label>
                      <label className="w-20 shrink-0 space-y-1">
                        <span className="text-[11px] text-muted-foreground">End (s)</span>
                        <Input
                          type="number"
                          min="0"
                          value={o.end}
                          onChange={(e) => setOverlay(i, { end: Number(e.target.value) })}
                          aria-label={`Overlay ${i + 1} end`}
                        />
                      </label>
                      <label className="min-w-0 flex-1 space-y-1">
                        <span className="text-[11px] text-muted-foreground">Text</span>
                        <Input
                          value={o.text}
                          onChange={(e) => setOverlay(i, { text: e.target.value })}
                          placeholder="e.g. One timer. That's it."
                          aria-label={`Overlay ${i + 1} text`}
                        />
                      </label>
                      <Button
                        variant="ghost"
                        size="sm"
                        onClick={() => removeOverlay(i)}
                        aria-label={`Remove overlay ${i + 1}`}
                      >
                        <Trash2 className="h-3.5 w-3.5" />
                      </Button>
                    </div>
                  ))}
                </div>
              )}
            </div>

            <SafetyPanel
              report={project.safety_report}
              summary={project.safety_summary}
            />

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="brand" onClick={handleSaveEdits} disabled={busy || !hasEdits}>
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Save className="h-4 w-4" />}
                Save edits
              </Button>
              <Button
                variant="secondary"
                onClick={handleMarkReady}
                disabled={busy || hasEdits || project?.status === "ready_for_generation"}
              >
                <CheckCircle2 className="h-4 w-4" />
                {project?.status === "ready_for_generation"
                  ? "Ready for generation"
                  : "Mark ready for generation"}
              </Button>
            </div>
            {hasEdits && (
              <p className="text-xs text-muted-foreground">Save your edits before marking ready.</p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToTemplatePhoto={scrollToTemplatePhoto}
            />

            {/* Nothing that spends money renders on this step. GenerationPanel
                lives on the step below, so the claim check above has been read
                before any render is paid for. */}
            <p className="text-sm text-muted-foreground">
              Read the script, the demo note and the claim check above, then open the Hook &amp;
              middle step to render it. Nothing is generated from this page.
            </p>
          </div>
        )}
        </StepShell>
      );
    }

    // Unreachable: every index in STEPS has a branch above. This is a guard
    // against an index out of range rendering an empty page, so it must not
    // read as a step the founder could have ended up in deliberately.
    return null;
  }

  if (loading) {
    return (
      <p className="flex items-center gap-2 text-sm text-muted-foreground">
        <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading studio...
      </p>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Clapperboard}
        title="Create Video"
        description="Build a short-form promo from an approved App Profile and a hook template. It renders a hook and a middle for you; you record the demo, add the close, and post it. Nothing is published."
        actions={
          project ? (
            <Badge variant="secondary" className="text-xs">
              Draft v{project.script_version}
            </Badge>
          ) : null
        }
      />

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
      <nav aria-label="Progress" className="flex flex-wrap items-center gap-1.5">
        {stepStates.map((s, i) => {
          const active = i === step;
          const Icon = s.state === "done" ? Check : s.step.icon;
          return (
            <button
              key={s.step.key}
              type="button"
              onClick={() => setStep(i)}
              aria-current={active ? "step" : undefined}
              // Announced rather than shown only: the tick is a shape-only cue, and
              // this is the one place the founder looks to answer "what is left".
              aria-label={`${s.step.label}: ${STEP_STATE_COPY[s.state]}`}
              title={STEP_STATE_COPY[s.state]}
              data-state={s.state}
              data-testid={`step-pill-${s.step.key}`}
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? "border-[color:var(--indigo-35)] bg-primary/15 text-[color:var(--brand-indigo)]"
                  : s.state === "done"
                    ? "border-[color:var(--hairline)] text-foreground/80 hover:border-[color:var(--indigo-35)] hover:text-foreground"
                    : "border-dashed border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--indigo-35)] hover:text-foreground"
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
            </button>
          );
        })}
      </nav>

      {/* One sentence saying what is left, rather than making them read the
          pills. This is the "easy tracking" the pills cannot do on their own:
          they show state, this says which one needs them. */}
      {nextUp && (
        <p className="text-xs text-muted-foreground" data-testid="progress-next-up">
          {nextUp}
        </p>
      )}

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Something went wrong</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <div className="surface rounded-2xl p-5 md:p-6">
        {stepContent}
      </div>

      {/* Back and Next used to live here and were pure duplication: every step
          pill above is already a button, and clicking one leaves any step, so
          the `step === 0 && !profileId` guard they carried was bypassable
          anyway. The one thing the pills cannot do is leave the studio, so the
          exit stays — on the last step only, which is where it already was. */}
      {step === STEPS.length - 1 && project && (
        <div className="flex items-center justify-end">
          <Button variant="ghost" onClick={() => navigate("/app-profiles")}>
            Back to your app
          </Button>
        </div>
      )}

      {template && (
        <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
          <Star className="h-3 w-3" />
          Templates are curated structures, not proven performers.
        </p>
      )}

      {/* This line used to live on the Dashboard, which is gone. It is the only
          place in the app that tells the founder their finished video is never
          posted for them, so it moved here — the studio, at the moment they are
          actually making the video — rather than being dropped. The structural
          TestNoPlatformAutomation proves it; this says so where it is read.
          It also names the half of the job that never leaves this page: the
          demo and the close are footage the founder records, not something a
          render can supply. */}
      <p className="text-xs text-muted-foreground">
        Videos are generated here and posted by hand. The render gives you the hook and the
        middle; the demo and the call to action are yours to record and attach. This tool never
        publishes to any platform and never asks for platform credentials.
      </p>
    </div>
  );
}
