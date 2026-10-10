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
// requiredAssetStatus left with the per-requirement checklist it fed. The photo
// section now reports the one requirement directly, next to the photograph, so
// the template card only has to say whether anything is still owed.
import {
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
  Image as ImageIcon, Check, Sparkles, RefreshCw, ChevronDown,
  Save, CheckCircle2, Star,
} from "lucide-react";
// toast left with AttachedPhoto, the only place on this page that raised one.
// Detaching now happens inside the photo section, which reports its own
// outcome.

// The order is the product, and it is deliberate.
//
//   profile -> angle -> template -> assets -> plan -> review -> Hook + Story
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
 * can stall with nothing to do, and nothing is generated until the last one.
 *
 * Last, because this is the only step that calls the model. The plan is text
 * only, and it is what that step renders.
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
  { key: "hook", label: "Hook + Story", icon: Sparkles },
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
  // The server sorts reasons strongest-first and sends only the strings, so
  // the first reason IS the verdict and the rest is supporting detail. Shown
  // that way rather than as four identical paragraphs, which left the founder
  // unable to tell the decision from its evidence.
  const [verdict, ...detail] = reasons;
  const example =
    typeof r.template.example_preview === "string" && r.template.example_preview.trim()
      ? r.template.example_preview.trim()
      : "";
  // The viewer-facing outcome, when the row carries one. Curated rows always
  // do; tailored rows do once regenerated. Rendered as the card's lead line
  // in body weight so the first thing read is the result, not the mechanic.
  const outcome =
    typeof r.template.outcome === "string" && r.template.outcome.trim()
      ? r.template.outcome.trim()
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
      <div className="flex flex-wrap items-center justify-between gap-2">
        <span className="text-sm font-medium">{r.template.name}</span>
        <span className="flex flex-wrap items-center gap-2">
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
      {outcome && (
        <p className="mt-1 text-sm text-foreground/90" data-testid="template-outcome">
          {outcome}
        </p>
      )}
      {example && (
        <p className="mt-1 text-xs text-foreground/80">
          <span className="text-muted-foreground">Sounds like: </span>
          &ldquo;{example}&rdquo;
        </p>
      )}
      {reasons.length > 0 && (
        <div className="mt-2 space-y-1.5">
          <p className="text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            Why it fits
          </p>
          {/* The verdict: the strongest match, in body weight with the same
              tick the step pills use for "positive", so it reads as the reason
              rather than one of several. */}
          <p
            className="flex items-start gap-1.5 text-sm text-foreground"
            data-testid="template-fit-verdict"
          >
            <Check aria-hidden="true" className="mt-0.5 h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
            <span>{verdict}</span>
          </p>
          {/* Supporting detail: muted, marked as a list, tighter leading. A
              single-reason card renders the verdict alone with no list. */}
          {detail.length > 0 && (
            <ul className="space-y-1">
              {detail.map((reason, i) => (
                <li
                  key={`r-${i + 1}`}
                  className="flex items-start gap-1.5 text-xs leading-relaxed text-muted-foreground"
                >
                  <span aria-hidden="true" className="mt-[7px] h-1 w-1 shrink-0 rounded-full bg-current opacity-60" />
                  <span>{reason}</span>
                </li>
              ))}
            </ul>
          )}
        </div>
      )}
      {limits.length > 0 && (
        // A caveat, not evidence: inset with a left hairline border and a muted
        // warning mark, so shape separates it from the reasons above. Never
        // amber -- on this page amber reads as an error state.
        <div className="mt-2 space-y-1 border-l-2 border-[color:var(--hairline)] pl-2.5">
          <p className="flex items-center gap-1.5 text-[10px] font-semibold uppercase tracking-[0.08em] text-muted-foreground">
            <AlertTriangle aria-hidden="true" className="h-3 w-3" />
            Before you use it
          </p>
          {limits.map((limitation, i) => (
            <p key={`l-${i}`} className="text-[11px] leading-relaxed text-muted-foreground">{limitation}</p>
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
 * before rendering, so this is the early warning rather than the guarantee.
 */
function MissingRequirements({ identity, onGoToTemplatePhoto }) {
  if (!identity || identity.length === 0) return null;

  return (
    <div className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-4">
      <p className="text-sm font-medium">
        This template needs a character reference before it can generate
      </p>
      <p className="text-xs text-muted-foreground">
        The video is generated from your photograph.
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

/**
 * The goal picker, offered on Review when the plan is blocked on it. Same
 * options as the Audience & goal step; choosing one writes it into the same
 * state, so the auto effect fires and the plan starts with no button press.
 */
function ReviewGoalPicker({ value, onPick, options }) {
  return (
    <div className="space-y-1.5">
      <label htmlFor="review-objective" className="text-sm font-medium">
        What is this video for? <span className="text-muted-foreground">(required)</span>
      </label>
      <div className="relative">
        <select
          id="review-objective"
          value={value}
          onChange={(e) => onPick(e.target.value)}
          aria-required="true"
          className="w-full appearance-none rounded-xl border border-[color:var(--hairline)] bg-transparent py-2.5 pl-3 pr-10 text-sm transition-colors hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)] focus:border-[color:var(--indigo-35)]"
        >
          <option value="">Choose an objective</option>
          {(options || []).map((o) => (
            <option key={o} value={o}>{humanize(o)}</option>
          ))}
        </select>
        <ChevronDown
          aria-hidden="true"
          className="pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground"
        />
      </div>
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
      else if (!hasPhoto) state = "blocked";    } else if (step.key === "review") {
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
  if (step === 0) return "Choose an approved App Profile to start. Your free script plan appears in Review; Hook + Story renders in the final step.";
  // "Everything is ready" has to be measured against the steps that CAN be
  // ready. The render step is deliberately never marked done -- it has no
  // completion state, because a project stays renderable and gets re-rendered
  // -- so `every(s => s.state === "done")` was permanently false and this line
  // was unreachable. Comparing only the steps before it makes the message
  // reachable, and says it at the point where it is true.
  if (stepStates.slice(0, step).every((s) => s.state === "done")) {
    return "Everything before this is ready. Review the app-specific strategy here, then render your Hook + Story.";
  }
  const first = stepStates.findIndex((s) => s.state !== "done");
  if (first > step) {
    return `${stepStates[first].step.label} is still ahead of you.`;
  }
  return "The free script plan appears in Review. The Hook + Story video renders in the final step.";
}

export default function CreateVideo() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  // The server's updated_at for each project this wizard has adopted from a
  // server response, so a row that is already current is never re-read or
  // re-adopted. Declared here, above every effect that reads or writes it: a
  // dep array is evaluated during render, and the deep-link load below uses it
  // long before the Review step that first needed it was in view.
  const syncedProjectsRef = useRef({});

  const [step, setStep] = useState(0);
  const [profiles, setProfiles] = useState([]);
  const [angles, setAngles] = useState([]);
  // Angles can be generated from in here, not just on the profile page:
  // sending the founder out of the wizard to make an optional angle usable
  // was a round trip the flow never offered a way back from.
  const [generatingAngles, setGeneratingAngles] = useState(false);
  const [angleError, setAngleError] = useState(null);
  const [facets, setFacets] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
  const [recError, setRecError] = useState(null);
  const [recKey, setRecKey] = useState("");
  const [tailored, setTailored] = useState({ key: "", templates: [] });
  const [templates, setTemplates] = useState([]);
  const [project, setProject] = useState(null);
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
            // This row came from the server, so it is already current: recording
            // it means the Review re-read has nothing to reconcile and does not
            // fire. Without that, every deep link issued a second identical
            // request whose late resolution updated state after the check (or
            // the founder) had moved on.
            syncedProjectsRef.current[draft.id] = draft.updated_at || "";
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
  const recRequestRef = useRef(0);

  const loadRecommendations = useCallback(
    async (pid, aid) => {
      if (!pid) return;
      // Recommendations are keyed to the exact profile/angle/objective that
      // requested them. A slow response for a previous key must never populate
      // the step the founder is now reading, and rows for a previous key must
      // not linger while the new key loads.
      const request = ++recRequestRef.current;
      const key = `${pid || ""}:${aid || ""}:${objective || ""}`;
      setRecKey(key);
      setRecommendations([]);
      setRecError(null);
      try {
        const rec = await api.getTemplateRecommendations(pid, {
          angle_id: aid || undefined,
          objective: objective || undefined,
          limit: 6,
        });
        if (recRequestRef.current !== request) return;
        const rows = rec.recommendations || [];
        setRecKey(key);
        setRecommendations(rows);
        setRecError(null);
        // Preselection moved to its own effect below: it must wait until the
        // tailored set for this key is ready, otherwise the top curated card
        // is picked before the custom templates exist.
      } catch (err) {
        if (recRequestRef.current !== request) return;
        // An empty list used to mean three different things: nothing ranked,
        // nothing compatible, or the request failed. The third one stranded the
        // founder in front of a step that looked merely thin, so the reason is
        // shown rather than absorbed.
        setRecKey(key);
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
    const key = `${profileId}:${objective}`;
    setTailoring(true);
    setTailorError(null);
    try {
      const res = await api.ensureObjectiveTemplates(profileId, {
        objective,
        ...(regenerate ? { regenerate: true } : {}),
      });
      // A response for a previous profile/objective must not mark the current
      // step ready: that is exactly how pre-made cards appeared before the
      // current app's custom set existed.
      if (tailorKeyRef.current !== key) return;
      setTailored({
        key,
        templates: Array.isArray(res?.templates) ? res.templates : [],
      });
      if (res.generated) {
        await loadRecommendations(profileId, angleId);
      }
      if (res.error) setTailorError(res.error);
    } catch (err) {
      if (tailorKeyRef.current !== key) return;
      setTailored({ key, templates: [] });
      setTailorError(getErrorMessage(err));
    } finally {
      if (tailorKeyRef.current === key) setTailoring(false);
    }
  }, [profileId, objective, angleId, loadRecommendations]);

  // Generating this profile's audience angles without leaving the wizard.
  //
  // Offered only when there are none, because the endpoint replaces the whole
  // set: a button on a populated list could silently discard angles the
  // founder wrote by hand on the profile page.
  const handleGenerateAngles = useCallback(async () => {
    if (!profileId) return;
    setGeneratingAngles(true);
    setAngleError(null);
    try {
      const data = await api.generateContentAngles(profileId);
      setAngles(data.angles || []);
      if (!data.angles?.length) {
        setAngleError("The model returned no usable angles. Try again.");
      }
    } catch (err) {
      setAngleError(getErrorMessage(err));
    } finally {
      setGeneratingAngles(false);
    }
  }, [profileId]);

  useEffect(() => {
    if (step !== 2 || !profileId || !objective) return;
    const key = `${profileId}:${objective}`;
    if (tailorKeyRef.current === key) return;
    tailorKeyRef.current = key;
    runTailoring(false);
  }, [step, profileId, objective, runTailoring]);

  // Template cards stay hidden until this profile/objective has its own custom
  // set. Recommendations otherwise arrive first and show pre-made cards before
  // the tailored templates exist. On a tailoring failure with no custom set,
  // the ranked curated fallback is shown instead of an empty step.
  const tailorKey = profileId && objective ? `${profileId}:${objective}` : "";
  const recRequestKey = `${profileId || ""}:${angleId || ""}:${objective || ""}`;
  const tailoredReady = Boolean(
    tailorKey && tailored.key === tailorKey && tailored.templates.length > 0
  );
  const tailorFallbackVisible = Boolean(
    tailorKey &&
      tailored.key === tailorKey &&
      tailored.templates.length === 0 &&
      tailorError &&
      !tailoring
  );
  const recommendationsVisible = Boolean(
    objective &&
      recKey &&
      recKey === recRequestKey &&
      (tailoredReady || tailorFallbackVisible)
  );
  // Once the custom set is ready, only its templates are shown. The ranked
  // curated fallback remains available when tailoring fails with no custom
  // set, so a model outage does not strand the step.
  const tailoredIds = new Set(
    (tailored.templates || []).map((t) => t?.id).filter(Boolean)
  );
  const visibleRecommendations = !recommendationsVisible
    ? []
    : tailoredReady
      ? recommendations.filter((r) => tailoredIds.has(r?.template?.id))
      : recommendations;

  // Preselect the top pick only once its key is displayable. Deliberately not
  // "on every reload": a reload must never move a selection the founder made,
  // so the only conditions are that nothing is selected and nothing has ever
  // been hand-picked.
  useEffect(() => {
    if (!recommendationsVisible) return;
    if (templateId || templateChosenByHand.current) return;
    if (visibleRecommendations.length === 0) return;
    setTemplateId(visibleRecommendations[0].template.id);
  }, [visibleRecommendations, recommendationsVisible, templateId]);

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
   * validated BEFORE anything is rendered. Previously the project was only   * created by the plan step, which forced the Assets step to carry a manual
   * "Create draft" button purely to get out of the way.
   *
   * So: as soon as an App Profile and a hook template are both chosen, the
   * draft is created or updated in the background. A draft calls no model —
   * only a marked-ready generation renders — so doing this eagerly costs
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
  }, [profileId, templateId, angleId, objective, ensureProject]);

  const handleGeneratePlan = async () => {
    const ready = await createProject();
    if (!ready) {
      // createProject already reported the error above. Record the outcome
      // so Review offers the retry instead of the generating spinner.
      setPlanFailed(true);
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
      setProject(settled);
      setEdits({});
      // Straight to the top of Review, which is this step now: the plan is the
      // thing to read, and the render step below it is the first one that
      // calls the model. The old indices were 5 (Review) and 6 (Hook and
      // middle); merging the plan step into Review moved both down by one.
      setStep(3);
    } catch (err) {
      setError(getErrorMessage(err));
      setPlanFailed(true);
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
      setProject(settled);
      setEdits({});
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  

  // A template can be selected either via URL param (templateId) or stored
  // on the project (project.template_id). The URL param wins when present
  // because it reflects the founder's current intent; the project's value is
  // a fallback for cases like auto-generation on Review where the URL param
  // hasn't been set yet but the project already knows its template.
  const effectiveTemplateId = templateId || project?.template_id;
  const canGenerate = Boolean(profileId && effectiveTemplateId);

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
  const effectiveTemplate = template || project?.template_id ? { ...template, id: template?.id || project?.template_id } : null;
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
  useEffect(() => {
    // The plan needs a profile, a template and a goal. The character photo is
    // required to RENDER, not to write the plan, so it does not gate this.
    if (step !== 3 || busy || !canGenerate) return;
    if (!objective && project?.objective) {
      // The draft already holds the goal but this session's state does not:
      // adopt it so the gates below read one consistent choice and the plan
      // starts on arrival. Returned from, not fallen through, because the
      // state update re-runs this effect and the fire happens there — firing
      // here would send the draft's goal while `objective` is still empty.
      setObjective(project.objective);
      return;
    }
    if (!objective) return;
    if (project?.script_version) return;
    const key = `${profileId}:${templateId}:${angleId || ""}:${objective || ""}:${tone || ""}`;
    if (planAutoAttempted.current === key) return;
    planAutoAttempted.current = key;
    handleGeneratePlan();
    // eslint-disable-next-line react-hooks/exhaustive-deps -- handleGeneratePlan is a render-scoped closure, same as handleGenerateStrategy in the auto-build below; the key ref guards re-fires, and listing it would re-run the effect on every render.
  }, [step, busy, canGenerate, objective, profileId, templateId, angleId, tone, project?.id, project?.script_version, project?.objective]);

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
    if (step !== 3 || !project?.id || busy) return;
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
    api
      .getStudioProject(project.id)
      .then((fresh) => {
        if (cancelled || !fresh) return;
        if (Object.keys(editsRef.current).length > 0) return;
        if (project.status === "ready_for_generation" && fresh.status !== "ready_for_generation") {
          return;
        }
        syncedProjectsRef.current[project.id] = fresh.updated_at || "";
        setProject(fresh);
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
          title="Choose an approved app"
          description="Select the App Profile for this video. Its product details and claim guardrails guide the script."
        >
          {approved.length === 0 ? (
            <EmptyState
              icon={Briefcase}
              title="No approved App Profile"
              description={describeEmptySelection(profiles)}
              action={
                <Button variant="brand" asChild>
                  <Link to="/brand">Create or approve an App Profile</Link>
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
                  {unapproved.length > 3 ? (
                    <details className="mt-0.5">
                      <summary className="cursor-pointer text-xs text-muted-foreground">
                        Show all {unapproved.length} apps
                      </summary>
                      <p className="mt-0.5 text-xs text-muted-foreground">
                        {unapproved.map(profileLabel).join(", ")}
                      </p>
                    </details>
                  ) : (
                    <p className="mt-0.5 text-xs text-muted-foreground">
                      {unapproved.map(profileLabel).join(", ")}
                    </p>
                  )}
                  <p className="mt-2 text-xs text-muted-foreground">
                    Draft profiles need review and approval before you can use them in a video.
                  </p>
                  <Button variant="secondary" size="sm" asChild className="mt-3">
                    <Link to="/brand">Review in App Profile</Link>
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
          title="Audience & goal"
          description="Choose a video goal, then optionally focus on an audience angle and tone. These choices shape template suggestions and your script plan."
        >
          <div className="space-y-4" data-testid="audience-goal-step">
            {/* The content angle is optional, and this now says so. It was
                labelled exactly like the objective and read as required, so a
                founder who wanted to move fast reasonably skipped it — then had
                no way to tell that skipping it narrowed the template match. */}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">
                Audience angle{" "}
                <span className="font-normal text-muted-foreground">(optional)</span>
              </label>
              <p className="text-xs text-muted-foreground">
                Choose a saved angle to focus on one audience problem. Skip it for broader template suggestions.
              </p>
              {angles.length === 0 ? (
                <div className="space-y-2">
                  <Alert>
                    <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                    <AlertDescription>
                      This profile has no audience angles yet. Generate them here to focus
                      this video on one audience problem — or skip it and choose a goal
                      below for broader suggestions.
                    </AlertDescription>
                  </Alert>
                  {angleError && (
                    <Alert variant="destructive">
                      <AlertDescription>{angleError}</AlertDescription>
                    </Alert>
                  )}
                  <Button
                    variant="secondary"
                    size="sm"
                    className="gap-1.5"
                    onClick={handleGenerateAngles}
                    disabled={generatingAngles}
                    data-testid="generate-angles-button"
                  >
                    {generatingAngles ? (
                      <Loader2 className="h-3.5 w-3.5 animate-spin" />
                    ) : (
                      <Sparkles className="h-3.5 w-3.5" />
                    )}
                    {generatingAngles ? "Generating…" : "Generate audience angles"}
                  </Button>
                </div>
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
                        <span className="flex items-center gap-1.5">
                          <Badge variant="secondary" className="text-[11px]">
                            {humanize(a.kind)}
                          </Badge>
                          {angleId === a.id && <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />}
                        </span>
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
            <div className="space-y-1.5 rounded-xl border border-[color:var(--hairline)] p-4" data-testid="create-what-you-get">
              <span className="text-sm font-medium">What you get</span>
              <p className="text-sm">
                One {pieceSeconds}s Hook + Story clip: a {pieceSplit.hookSeconds}s hook, then a {pieceSplit.middleSeconds}s story.
              </p>
              <p className="text-xs text-muted-foreground">
                {template
                  ? `Length is set by ${template.name}. Choose a different template to change it.`
                  : "Choose a template to see the clip length."}
              </p>
              <p className="text-xs text-muted-foreground">
                To complete the promo, record the demo yourself and add it after this clip with your own call to action. Neither is generated in this clip.
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
                Video goal <span className="text-muted-foreground">(required)</span>
              </label>
              <div className="relative">
                <select
                  id="objective"
                  value={objective}
                  onChange={(e) => setObjective(e.target.value)}
                  aria-required="true"
                  className={`w-full appearance-none rounded-xl border bg-transparent py-2.5 pl-3 pr-10 text-sm transition-colors focus:border-[color:var(--indigo-35)] ${
                    objective
                      ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-6)]"
                  }`}
                >
                <option value="">Choose an objective</option>
                {(facets?.objectives || []).map((o) => (
                  <option key={o} value={o}>{humanize(o)}</option>
                ))}
                </select>
                <ChevronDown
                  aria-hidden="true"
                  className={`pointer-events-none absolute right-3 top-1/2 h-4 w-4 -translate-y-1/2 transition-colors ${
                    objective ? "text-[color:var(--brand-indigo)]" : "text-muted-foreground"
                  }`}
                />
              </div>
              {!objective && (
                <p className="text-xs text-muted-foreground">
                  Required. This strongly affects template suggestions and the script plan.
                </p>
              )}
            </div>

            <div className="space-y-1.5">
              <label htmlFor="tone" className="text-sm font-medium">Tone (optional)</label>
              <Input
                id="tone"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder="For example: calm and direct"
              />
              <p className="text-xs text-muted-foreground">
                Optional. Guides the script&apos;s voice, not the facts about your app.
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
          description="Compare goal-matched suggestions by fit reasons and caveats. Keep the preselected suggestion or choose another, then add a clear photo of the presenter below."
        >
          <div className="space-y-4">
            {/* No objective means no honest scoring to show. The card list used
                to render anyway with the empty rationale the scorer returns, so a
                founder could pick the top card from reasons that did not mention
                their goal at all. */}
            {!objective && (
              <EmptyState
                icon={Target}
                title="Choose what this video is for before picking a template."
                description="Required before templates can be ranked."
                action={
                  <Button variant="secondary" size="sm" onClick={() => setStep(1)}>
                    <Target className="h-3.5 w-3.5" /> Set the goal
                  </Button>
                }
              />
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
            {objective && recommendationsVisible && visibleRecommendations.length === 0 && (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm">No templates recommended for this app yet.</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  {recError
                    ? `Ranking failed (${recError}).`
                    : "Nothing ranked for this profile and goal."}
                </p>
              </div>
            )}
            {objective && recommendationsVisible && visibleRecommendations.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">
                  {tailoredReady ? "Tailored for this app" : "Recommended"}
                </span>
                <div className="grid grid-cols-1 gap-2 md:grid-cols-2">
                {visibleRecommendations.map((r) => (
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
                {/* The outcome leads; the mechanic badge above stays as the
                    secondary label. Director-speak (opening_structure) follows
                    in muted text for the founder who wants the how. */}
                {typeof template.outcome === "string" && template.outcome.trim() && (
                  <p className="mt-1 text-sm text-foreground/90">{template.outcome.trim()}</p>
                )}
                <p className="mt-1 text-xs text-muted-foreground">{template.opening_structure}</p>
                <TemplateShape template={template} />
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

            {/* The photo upload lives here now rather than on its own step. It
                was the only thing on that step, so a founder picked a template,
                left, uploaded, and came back — and the template step already
                said what was missing and offered a jump. The draft is created
                eagerly from the profile and template (see ensureProject), so by
                the time anyone reaches this there is almost always something to
                attach to. */}
            <div id="template-photo" className="space-y-3 border-t border-[color:var(--hairline)] pt-4">
              <span className="eyebrow block">Presenter photo</span>
              <p className="text-sm text-muted-foreground">
                Upload a clear photo of the person you want on camera. It guides the generated presenter; the scene is created from your App Profile.
              </p>
              {!templateId ? (
                <p className="text-sm text-muted-foreground">
                  Choose a template above to attach a presenter photo to this draft.
                </p>
              ) : !project ? (
                <>
                  <p className="text-sm text-muted-foreground">
                    Preparing the video draft for your photo…
                  </p>
                  <Button variant="secondary" size="sm" disabled={busy} onClick={() => ensureProject()}>
                    {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImageIcon className="h-4 w-4" />}
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
                    onProjectChanged={(fresh) => setProject(fresh || project)}
                    onChanged={() => {
                      // Re-read the project's attached assets so the picker updates.
                      api.getStudioProject(project.id).then(setProject).catch(() => {});
                    }}
                  />
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
          title="Hook + Story"
          description="Review the app-specific strategy, then render the Hook + Story clip. This render does not include your filmed product demo, closing CTA, or on-screen text."
        >
          <div className="space-y-3">
            {!canGenerate ? (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm text-muted-foreground">
                  Choose an approved App Profile, a video goal, and a template first. Review the free script plan before rendering.
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
                  Preparing the video draft for your photo…
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
                      There's no plan yet. Generate one on Review first — it is free.
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
                        step, where it let a render run on text the founder had
                        not read yet, and it sat BELOW the segmented chain, which
                        made the chain look like the product.

                        onProjectChange lets the panel build the strategy itself
                        on the way to a render. It was a button above,
                        which meant a founder could skip it and get a
                        generic take without ever being told the specific one
                        existed. */}                    <GenerationPanel
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
          title="Review your script plan"
          description="Once your app, goal, and template are set, your free script plan appears here. Check the hook, script, and claim review; edit and save what you want to change. The video render happens in Hook + Story."
        >
        {!project?.script_version && planFailed && !busy ? (
          /* A plan attempt ran and failed. The page-level error above says why;
             this offers the retry. Manual and enabled: the auto latch already
             consumed this selection-set, so nothing here fires on its own. The
             photo is not listed: it is required to render, never to plan. */
          <div className="space-y-3 rounded-xl border border-[color:var(--hairline)] p-4">
            <p className="text-sm text-muted-foreground">
              The plan didn't generate. Fix what's missing below, then try again — still free.
            </p>
            {!objective && (
              <ReviewGoalPicker value={objective} onPick={setObjective} options={facets?.objectives || []} />
            )}
            <Button
              variant="brand"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate || !objective}
            >
              <Sparkles className="h-4 w-4" />
              Try again
            </Button>
            <p className="text-xs text-muted-foreground">
              Writes hook, script, shots, and demo note. Editable below.
            </p>
          </div>
        ) : !project?.script_version && (busy || loading || (canGenerate && effectiveObjective)) ? (
          /* No plan and nothing wrong: an attempt is in flight, the draft is
             still loading, or every input is present and the auto effect fires
             next — reading the stored goal too, so a draft that already holds
             one spins instead of flashing the picker. Only these three cases
             may show a spinner. */
          <div className="space-y-3 rounded-xl border border-[color:var(--hairline)] p-4">
            <div className="flex items-center gap-2">
              <Loader2 className="h-4 w-4 animate-spin" />
              <span className="text-sm font-medium">
                {loading && !busy ? "Loading your draft…" : "Generating your plan…"}
              </span>
            </div>
            <p className="text-xs text-muted-foreground">
              {loading && !busy
                ? "Picking up where you left off."
                : "Writing hook, script, shots, and demo note."}
            </p>
          </div>
        ) : !project?.script_version ? (
          /* No plan and the auto effect cannot fire: a profile, a template or
             the goal is missing. Name it and fix it here — choosing the goal
             starts the plan on its own, no button press. */
          <div className="space-y-3 rounded-xl border border-[color:var(--hairline)] p-4">
            <p className="text-sm text-muted-foreground">
              Your free script plan appears once an App Profile, template, and video goal are set. Still missing:
            </p>
            <ul className="space-y-2 text-sm">
              {!profileId && (
                <li>
                  <Button variant="secondary" size="sm" onClick={() => setStep(0)}>
                    Choose an App Profile
                  </Button>
                </li>
              )}
              {!effectiveTemplateId && (
                <li>
                  <Button variant="secondary" size="sm" onClick={() => setStep(2)}>
                    Pick a template
                  </Button>
                </li>
              )}
              {!objective && (
                <li>
                  <ReviewGoalPicker value={objective} onPick={setObjective} options={facets?.objectives || []} />
                </li>
              )}
            </ul>
            <p className="text-xs text-muted-foreground">
              No extra generate button is needed here. The free plan starts when the required choices are set.
            </p>
          </div>
        ) : (
          <div className="space-y-4">
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
                <p className="text-xs text-muted-foreground" data-testid="plan-version-status">
                  Plan v{project.script_version}
                  {(project.hook_line || project.script)
                    ? " · generated ✓"
                    : " · empty — regenerate to write it"}
                </p>
              </div>
            )}
            <span className="eyebrow block">Script</span>
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
              <div className="rounded-xl border border-[color:var(--hairline)] bg-secondary/20 p-4">
                <span className="eyebrow block">What this is aiming to leave them with</span>
                <p className="mt-1 text-sm">{template.outcome.trim()}</p>
                <p className="mt-1 text-xs text-muted-foreground">
                  The outcome this template is built for, in the viewer&apos;s terms. The script
                  below is written to it — a framing, not a result this video can promise.
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
                <p className="text-sm">
                  I shortened your script by {project.plan_trim.dropped_chars} characters so it
                  fits the {project.plan_trim.middle_seconds}-second middle
                  {project.plan_trim.budget
                    ? ` (${project.plan_trim.budget} characters is what that many seconds holds)`
                    : ""}
                  . Everything above is spoken exactly as written.
                </p>
              </div>
            )}
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Hook line</label>
              <p className="text-xs text-muted-foreground">The opening line spoken in your generated Hook + Story clip.</p>
              <Input
                value={editValue("hook_line", "")}
                onChange={(e) => setEdits({ ...edits, hook_line: e.target.value })}
              />
            </div>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Script</label>
              <p className="text-xs text-muted-foreground">The spoken story after the hook. The generated clip does not include your filmed product demo or closing CTA.</p>
              <Textarea
                value={editValue("script", "")}
                onChange={(e) => setEdits({ ...edits, script: e.target.value })}
                className="min-h-[160px]"
              />
            </div>
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
            {project?.strategy?.hook_line && typeof project?.spoken_middle === "string" && project.spoken_middle && (
              <div className="space-y-1.5 rounded-xl border border-[color:var(--hairline)] bg-secondary/20 p-4" data-testid="spoken-partition">
                <span className="eyebrow block">What the middle will say</span>
                <p className="text-sm">{project.spoken_middle}</p>
                {(() => {
                  const current = String(editValue("script", "") || "");
                  const kept = project.spoken_middle;
                  const tail = current.startsWith(kept) ? current.slice(kept.length).trim() : "";
                  if (!tail) {
                    return (
                      <p className="text-xs text-muted-foreground">
                        Your whole script fits in the middle — every word above is spoken.
                      </p>
                    );
                  }
                  return (
                    <p className="text-xs text-muted-foreground">
                      <span className="font-medium">Not spoken: </span>{tail}{" "}
                      {current.length - kept.length} characters past the middle&apos;s spoken
                      budget. Regenerate the plan to have it rewritten to fit, or shorten the
                      script above and rebuild the strategy.
                    </p>
                  );
                })()}
              </div>
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
            <div className="space-y-1.5 rounded-xl border border-[color:var(--hairline)] p-4">
              <label htmlFor="review-demo-brief" className="text-sm font-medium">
                What you record for the demo
              </label>
              <Textarea
                id="review-demo-brief"
                value={editValue("demo_brief", "")}
                onChange={(e) => setEdits({ ...edits, demo_brief: e.target.value })}
                className="min-h-[70px]"
                placeholder="For example: Record yourself tapping the timer once, hands only"
              />
              <p className="text-xs text-muted-foreground">
                A note to you, not the model — never reaches the render.
              </p>
            </div>
            <span className="eyebrow block">Visual and audio direction</span>
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Visual direction</label>
              <p className="text-xs text-muted-foreground">Describe the generated scene and look. This is guidance for the rendered Hook + Story, not footage of your app demo.</p>
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
              <details
                className="rounded-xl border border-[color:var(--hairline)] bg-secondary/20 p-4"
                data-testid="shot-timeline"
              >
                <summary className="flex cursor-pointer flex-wrap items-center gap-2">
                  <span className="eyebrow block">Shot timeline</span>
                  <Badge variant="outline" className="text-[11px]">read-only</Badge>
                </summary>
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
              </details>
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
                    ? "The timeline is written to this length. Pick a different template to change it."
                    : "Set by the hook template you pick."}
                </p>
              </div>
              <div className="space-y-1.5">
                <label htmlFor="review-tone" className="text-sm font-medium">Tone</label>
                <Input
                  id="review-tone"
                  value={editValue("tone", "")}
                  onChange={(e) => editTone(e.target.value)}
                  placeholder="For example: calm and direct"
                />
              </div>
            </div>

            <div className="space-y-1.5">
              <label className="text-sm font-medium">Voice direction</label>
              <Textarea
                value={editValue("voice_direction", "")}
                onChange={(e) => setEdits({ ...edits, voice_direction: e.target.value })}
                className="min-h-[70px]"
              />
            </div>

            <span className="eyebrow block">Checks</span>
            <SafetyPanel
              report={project.safety_report}
              summary={project.safety_summary}
            />

            <div className="flex flex-wrap items-center gap-2">
              <Button variant="brand" onClick={handleSaveEdits} disabled={busy || !hasEdits}>
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
                <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                  <CheckCircle2 className="h-3.5 w-3.5" />
                  Ready for generation.
                </p>
              )}
            </div>
            {hasEdits && (
              <p className="text-xs text-muted-foreground">
                Save your edits before rendering. Your saved changes run through the claim check again.
              </p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToTemplatePhoto={scrollToTemplatePhoto}
            />

            {/* Nothing that calls the model renders on this step. GenerationPanel
                lives on the step below, so the claim check above has been read
                before any render runs. */}
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
      <div className="space-y-6" aria-label="Loading studio" data-testid="studio-loading">
        <div className="flex items-center gap-1.5">
          {STEPS.map((s) => (
            <span key={s.key} className="h-7 w-24 shrink-0 animate-pulse rounded-full border border-[color:var(--hairline)]" />
          ))}
        </div>
        <div className="surface rounded-2xl">
          <div className="mx-auto w-full max-w-6xl space-y-4">
            <div className="flex items-start gap-3">
              <span className="h-10 w-10 shrink-0 animate-pulse rounded-xl border border-[color:var(--hairline)]" />
              <div className="flex-1 space-y-2">
                <div className="h-4 w-40 animate-pulse rounded bg-secondary/60" />
                <div className="h-3 w-full animate-pulse rounded bg-secondary/40" />
              </div>
            </div>
            <div className="h-24 animate-pulse rounded-2xl border border-[color:var(--hairline)]" />
            <div className="h-24 animate-pulse rounded-2xl border border-[color:var(--hairline)]" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-6">
      <PageHeader
        icon={Clapperboard}
        title="Create Video"
        description="Choose an approved app, set a goal, pick a template, then review a free script plan before rendering your Hook + Story. Record and assemble your product demo and call to action separately."
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
      <nav aria-label="Progress" className="flex items-center gap-1.5 overflow-x-auto no-scrollbar">
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
              className={`inline-flex shrink-0 cursor-pointer items-center gap-1.5 rounded-full border px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? "border-[color:var(--indigo-35)] bg-primary/15 text-[color:var(--brand-indigo)]"
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

      <div className="surface rounded-2xl">
        <div className="mx-auto w-full max-w-6xl">{stepContent}</div>
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
      <p className="text-xs text-muted-foreground" data-testid="create-no-autopost-note">
        This studio creates the Hook + Story clip only. Record and assemble your product demo and closing CTA separately; Demo + CTA styles one clip at a time and does not combine clips. Nothing is published for you.
      </p>
    </div>
  );
}
