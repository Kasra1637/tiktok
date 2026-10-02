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
import {
  Clapperboard, Loader2, AlertTriangle, Briefcase, Target, LayoutTemplate,
  Image as ImageIcon, FileText, Check, Sparkles, RefreshCw,
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
const STEPS = [
  { key: "profile", label: "App Profile", icon: Briefcase },
  { key: "angle", label: "Audience & goal", icon: Target },
  { key: "template", label: "Hook template", icon: LayoutTemplate },
  { key: "assets", label: "Assets", icon: ImageIcon },
  { key: "plan", label: "Creative plan", icon: FileText },
  { key: "review", label: "Review", icon: CheckCircle2 },
  // Last, because this is the only step that spends money. The plan above is
  // free text, and it is what this step renders.
  //
  // Named for what it produces rather than for the old hook-first workflow: one
  // render containing a hook and a middle. The demo and the close are the
  // founder's own footage, added afterwards in their editor.
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
function MissingRequirements({ identity, onGoToAssets }) {
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
      {onGoToAssets && (
        <Button variant="secondary" size="sm" onClick={onGoToAssets}>
          <ImageIcon className="h-3.5 w-3.5" /> Attach in the Assets step
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

function AttachmentRow({ project, attachment, duration, onChanged }) {
  const isAudio = attachment.kind === "audio";
  // The face rides to the video model as an input reference for the whole
  // generation — it has no on-screen timing. Start/end/save exist for legacy
  // overlay rows only, so a face row is a confirmation plus a Remove button
  // and nothing that implies unfinished work.
  const isFace = attachment.kind === "character_reference";
  const [start, setStart] = useState(String(attachment.start ?? 0));
  const [end, setEnd] = useState(attachment.end ?? duration ?? "");
  const [role, setRole] = useState(attachment.audio_role || "background");
  const [gain, setGain] = useState(String(attachment.audio_gain ?? (role === "voiceover" ? 1 : 0.25)));
  const [saving, setSaving] = useState(false);

  const save = async () => {
    setSaving(true);
    try {
      const fresh = await api.getStudioProject(project.id);
      const next = (fresh.assets || []).map((a) => {
        if (a.asset_id !== attachment.asset_id) return a;
        const updated = {
          ...a,
          start: start === "" ? 0 : Number(start),
          end: end === "" ? undefined : Number(end),
        };
        if (isAudio) {
          updated.audio_role = role;
          updated.audio_gain = gain === "" ? undefined : Number(gain);
        } else {
          delete updated.audio_role;
          delete updated.audio_gain;
        }
        return updated;
      });
      const saved = await api.updateStudioProject(project.id, { assets: next });
      onChanged(saved);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setSaving(false);
    }
  };

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
    <div className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-3">
      <div className="flex items-center gap-3">
        <Badge variant="secondary" className="shrink-0 text-[11px]">
          {humanize(attachment.kind)}
        </Badge>
        <span className="min-w-0 flex-1 truncate text-sm">
          {attachment.label || attachment.asset_id.slice(0, 8)}
        </span>
        {!isFace && (
          <span className="shrink-0 text-xs text-muted-foreground">
            {attachment.start ?? 0}&ndash;{attachment.end ?? "end"}s
            {isAudio ? ` · ${attachment.audio_role || "background"}` : ""}
          </span>
        )}
        <Button variant="ghost" size="sm" aria-label="Remove from project" onClick={detach}>
          Remove
        </Button>
      </div>
      {!isFace && (
      <div className="grid grid-cols-2 gap-2 sm:grid-cols-5">
        <label className="space-y-1">
          <span className="text-[11px] text-muted-foreground">Start (s)</span>
          <Input type="number" min="0" value={start} onChange={(e) => setStart(e.target.value)} />
        </label>
        <label className="space-y-1">
          <span className="text-[11px] text-muted-foreground">End (s)</span>
          <Input
            type="number"
            min="0"
            value={end}
            onChange={(e) => setEnd(e.target.value)}
            placeholder={duration ? String(duration) : "End"}
          />
        </label>
        {isAudio && (
          <>
            <label className="space-y-1">
              <span className="text-[11px] text-muted-foreground">Use as</span>
              <select
                value={role}
                onChange={(e) => {
                  setRole(e.target.value);
                  setGain(e.target.value === "voiceover" ? "1" : "0.25");
                }}
                className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-2 py-1.5 text-xs"
              >
                <option value="background">Background</option>
                <option value="voiceover">Voiceover</option>
              </select>
            </label>
            <label className="space-y-1">
              <span className="text-[11px] text-muted-foreground">Gain</span>
              <Input
                type="number"
                min="0"
                max="2"
                step="0.05"
                value={gain}
                onChange={(e) => setGain(e.target.value)}
              />
            </label>
          </>
        )}
        <div className="flex items-end">
          <Button variant="secondary" size="sm" disabled={saving} onClick={save}>
            {saving ? <Loader2 className="h-3.5 w-3.5 animate-spin" /> : <Check className="h-3.5 w-3.5" />}
            Save timing
          </Button>
        </div>
      </div>
      )}
    </div>
  );
}

export default function CreateVideo() {
  const [params] = useSearchParams();
  const navigate = useNavigate();

  const [step, setStep] = useState(0);
  const [profiles, setProfiles] = useState([]);
  const [angles, setAngles] = useState([]);
  const [facets, setFacets] = useState(null);
  const [recommendations, setRecommendations] = useState([]);
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
            setEdits({});
            // A duplicate always arrives with its plan intact, so it opens on
            // Review; an unplanned draft still needs assets before a plan can
            // be written.
            setStep(draft.script_version > 0 ? 5 : 3);
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
      } catch {
        setRecommendations([]);
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
    setEdits({});
    setProject(null);
    // The template is cleared with everything else, because it was chosen
    // against the previous app's profile. This was latent before; auto-selection
    // made it reachable, since a template preselected for one app would survive
    // the switch and the new profile's recommendations would then see a
    // selection already made and decline to preselect theirs.
    setTemplateId("");
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
      // Straight to Review: the plan is the thing to read, and the render step
      // below it is the first one that spends money.
      setStep(5);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
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
          description="Pick the audience segment and what this video is meant to achieve."
        >
          <div className="space-y-4">
            <div className="space-y-1.5">
              <label className="text-sm font-medium">Content angle</label>
              {angles.length === 0 ? (
                <Alert>
                  <AlertTriangle className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                  <AlertDescription>
                    No content angles yet. Generate them on the profile page first.
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
                  : "Choose a hook template and its length is used."}{" "}
                There is no product demo in the generated video and no closing
                card: you record the demo yourself, add your own call to action
                after it, then post the result.
              </p>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="objective" className="text-sm font-medium">Objective</label>
              <select
                id="objective"
                value={objective}
                onChange={(e) => setObjective(e.target.value)}
                className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
              >
                <option value="">Choose an objective</option>
                {(facets?.objectives || []).map((o) => (
                  <option key={o} value={o}>{humanize(o)}</option>
                ))}
              </select>
            </div>

            <div className="space-y-1.5">
              <label htmlFor="tone" className="text-sm font-medium">Tone (optional)</label>
              <Input
                id="tone"
                value={tone}
                onChange={(e) => setTone(e.target.value)}
                placeholder="e.g. calm and direct"
              />
            </div>
          </div>
        </StepShell>
      );
    }

    if (step === 2) {
      return (
        <StepShell
          icon={LayoutTemplate}
          title="Choose a hook template"
          description="Scored for this app profile and angle — select the one that fits."
        >
          <div className="space-y-4">
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
            {recommendations.length > 0 && (
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
                      <Button variant="secondary" size="sm" className="mt-1" onClick={() => setStep(3)}>
                        <ImageIcon className="h-3.5 w-3.5" /> Attach in the Assets step
                      </Button>
                    )}
                  </div>
                )}
              </div>
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 3) {
      return (
        <StepShell
          icon={ImageIcon}
          title="Assets"
          description="Your photograph. Every video is generated from it — the person on camera is the person in the reference."
        >
          {!project ? (
            <div className="rounded-xl border border-[color:var(--hairline)] p-4">
              <p className="text-sm text-muted-foreground">
                {canGenerate
                  ? "A free draft from the selected profile, angle, and template is created for you, so assets can be attached straight away. Drafts cost nothing; only a marked-ready generation spends money."
                  : "Pick an App Profile and a hook template first — a draft is created from those two as soon as they are set, and assets attach to it."}
              </p>
              {canGenerate && (
                <Button
                  variant="brand"
                  size="sm"
                  className="mt-3"
                  disabled={busy}
                  onClick={() => ensureProject()}
                >
                  {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <ImageIcon className="h-4 w-4" />}
                  Create the draft now
                </Button>
              )}
            </div>
          ) : (
            <AssetLibrary
              embedded
              profileId={profileId}
              projectId={project?.id}
              projectAssets={project?.assets}
              projectDuration={pieceSeconds}
              onProjectChanged={() => {
                if (!project?.id) return;
                api.getStudioProject(project.id).then(setProject).catch(() => {});
              }}
              onChanged={() => {
                // Re-read the project's attached assets so the picker updates.
                if (!project?.id) return;
                api.getStudioProject(project.id).then(setProject).catch(() => {});
              }}
            />
          )}

          <div className="space-y-2 border-t border-[color:var(--hairline)] pt-4">
            <span className="eyebrow block">Attached to this project</span>
            {!project ? (
              <p className="text-sm text-muted-foreground">
                Create a draft above before attaching assets.
              </p>
            ) : (project?.assets || []).length === 0 ? (
              <p className="text-sm text-muted-foreground">
                Nothing attached yet. Attach the character reference above — every video is
                generated from it.
              </p>
            ) : (
              <div className="space-y-2">
                {(project?.assets || []).map((a) => (
                  <AttachmentRow
                    key={`${a.asset_id}-${a.start ?? 0}-${a.end ?? "end"}-${a.audio_role || "none"}-${a.audio_gain ?? "default"}`}
                    project={project}
                    attachment={a}
                    duration={pieceSeconds}
                    onChanged={setProject}
                  />
                ))}
              </div>
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 6) {
      return (
        <StepShell
          icon={Sparkles}
          title="Hook and middle"
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
                onGoToAssets={() => setStep(3)}
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
                      There is no plan yet, so there are no approved words to render. Generate
                      and review a creative plan first — it costs nothing, and it is what the
                      strategy below is built from.
                    </p>
                    <Button
                      variant="secondary"
                      size="sm"
                      className="mt-3"
                      disabled={busy}
                      onClick={() => setStep(4)}
                    >
                      Go to the plan step
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

    if (step === 4) {
      return (
        <StepShell
          icon={FileText}
          title="Generate the creative plan"
          description="This writes your hook, script, shot timeline, overlays, and a note on what to record for your own demo, then checks every claim in it. Free — no video is generated until you have read it on the next step."
        >
          <div className="space-y-3">
            <Button
              variant="brand"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate || blockedOnAssets}
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {project?.script_version ? "Regenerate plan" : "Generate plan"}
            </Button>
            {!templateId && (
              <p className="text-sm text-muted-foreground">Choose a template first.</p>
            )}
            <MissingRequirements
              identity={missingIdentity}
              onGoToAssets={() => setStep(3)}
            />
            {project?.script_version > 0 && (
              <p className="text-sm text-muted-foreground">
                Current plan is version {project.script_version}. Regenerating replaces it.
              </p>
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 5) {
      return (
        <StepShell
          icon={CheckCircle2}
          title="Review and edit"
          description="Everything is editable. The claim check re-runs on every edit, and the render step below turns this script into a hook and a middle rather than replacing it."
        >
        {!project?.script_version ? (
          <EmptyState
            icon={FileText}
            title="No plan yet"
            description="Generate a creative plan to review it here."
            action={
              <Button variant="brand" onClick={() => setStep(4)}>
                Go to plan step
              </Button>
            }
          />
        ) : (
          <div className="space-y-4">
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

            {editValue("beat_timeline", []).length > 0 && (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <span className="eyebrow block">Shot timeline</span>
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
                    ? "The shot timeline above is written to this length, and it is rendered in one pass. To change it, pick a different template on the Hook template step and regenerate the plan."
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
                          placeholder="e.g. Try it free for 3 days"
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
              onGoToAssets={() => setStep(3)}
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

    // The render step is the last one, and the only one that spends money. A
    // founder cannot reach it by falling through from Review; the explicit
    // `step === 6` above handles it, and this guards against a step index that
    // is out of range rendering nothing at all.
    return (
      <StepShell
        icon={Sparkles}
        title="Hook and middle"
        description="Read the strategy, then render the piece."
      >
        <p className="text-sm text-muted-foreground">This step is unavailable.</p>
      </StepShell>
    );
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

      <nav aria-label="Progress" className="flex flex-wrap items-center gap-1.5">
        {STEPS.map((s, i) => {
          const active = i === step;
          const done = i < step;
          return (
            <button
              key={s.key}
              type="button"
              onClick={() => setStep(i)}
              className={`inline-flex cursor-pointer items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? "bg-primary/15 text-[color:var(--brand-indigo)]"
                  : "text-muted-foreground hover:bg-[color:var(--indigo-8)] hover:text-foreground"
              }`}
              aria-current={active ? "step" : undefined}
            >
              {done ? <Check className="h-3 w-3" /> : <s.icon className="h-3 w-3" />}
              {s.label}
            </button>
          );
        })}
      </nav>

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
