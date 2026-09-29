import { useCallback, useEffect, useState } from "react";
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
  Clapperboard, Loader2, AlertTriangle, Briefcase, Target, LayoutTemplate,
  Image as ImageIcon, FileText, Check, ChevronLeft, ChevronRight, Sparkles,
  Save, CheckCircle2, Star, Plus, Trash2,
} from "lucide-react";
import { toast } from "sonner";

const STEPS = [
  { key: "profile", label: "App Profile", icon: Briefcase },
  { key: "angle", label: "Audience & goal", icon: Target },
  { key: "template", label: "Hook template", icon: LayoutTemplate },
  { key: "assets", label: "Assets", icon: ImageIcon },
  // The hook is validated before the full script is written, because a 3s
  // concept is the cheapest possible test of whether the strategy works. This
  // step is skippable: the one-pass plan flow below is still a complete path.
  { key: "hook", label: "Influencer hook", icon: Sparkles },
  { key: "plan", label: "Creative plan", icon: FileText },
  { key: "review", label: "Review", icon: CheckCircle2 },
];

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
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
        <span className="shrink-0 text-xs text-muted-foreground">
          {attachment.start ?? 0}&ndash;{attachment.end ?? "end"}s
          {isAudio ? ` · ${attachment.audio_role || "background"}` : ""}
        </span>
        <Button variant="ghost" size="sm" aria-label="Remove from project" onClick={detach}>
          Remove
        </Button>
      </div>
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
  const [duration, setDuration] = useState(20);
  const [tone, setTone] = useState("");
  const [manualTemplate, setManualTemplate] = useState(false);
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
            setDuration(draft.duration_seconds || 20);
            setTone(draft.tone || "");
            setRecommendations([]);
            setEdits({});
            // A duplicate always arrives with its plan intact; an unplanned
            // draft still needs assets before a plan can be generated.
            setStep(draft.script_version > 0 ? 6 : 3);
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

  const loadRecommendations = useCallback(
    async (pid, aid) => {
      if (!pid) return;
      try {
        const rec = await api.getTemplateRecommendations(pid, {
          angle_id: aid || undefined,
          objective: objective || undefined,
          limit: 6,
        });
        setRecommendations(rec.recommendations || []);
      } catch {
        setRecommendations([]);
      }
    },
    [objective]
  );

  useEffect(() => {
    loadRecommendations(profileId, angleId);
  }, [profileId, angleId, loadRecommendations]);

  const selectProfile = async (id) => {
    setSelectedProfileId(id);
    setAngles([]);
    setAngleId("");
    setRecommendations([]);
    setEdits({});
    setProject(null);
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
      const created = project?.id
        ? await api.updateStudioProject(project.id, {
            content_angle_id: angleId || "",
            template_id: templateId || "",
            objective,
            duration_seconds: duration,
            tone,
            ...overrides,
          })
        : await api.createStudioProject({
            brand_profile_id: profileId,
            content_angle_id: angleId || "",
            template_id: templateId || "",
            objective,
            duration_seconds: duration,
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
   * The Influencer hook step writes to a studio project, and the hook is meant
   * to be validated BEFORE the plan is written. Previously the project was only
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
        const updated = await api.updateStudioProject(project.id, {
          content_angle_id: angleId || "",
          template_id: templateId || "",
          objective,
          duration_seconds: duration,
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
        duration_seconds: duration,
        tone,
      });
      setProject(created);
      return created;
    } catch (err) {
      // A failure here is not fatal: the plan step still creates the draft and
      // surfaces the error properly. Swallowing it here would just show an
      // empty hook step with no explanation.
      setError(getErrorMessage(err));
      return null;
    }
  }, [profileId, templateId, angleId, objective, duration, tone, project]);

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
        duration_seconds: duration,
        tone,
      });
      setProject(updated);
      setEdits({});
      setStep(6);
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
  const editValue = (key, fallback) =>
    edits[key] !== undefined ? edits[key] : project?.[key] ?? fallback;
  const hasEdits = Object.keys(edits).length > 0;

  // Duration and tone are edited in the review step but also seed the plan in
  // the previous step, so a change here has to move both or going back and
  // regenerating would silently reinstate the old value.
  const editDuration = (seconds) => {
    setDuration(seconds);
    setEdits((prev) => ({ ...prev, duration_seconds: seconds }));
  };
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

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
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
                <label htmlFor="duration" className="text-sm font-medium">Total video length</label>
                <select
                  id="duration"
                  value={duration}
                  onChange={(e) => setDuration(Number(e.target.value))}
                  className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
                >
                  {(facets?.supported_durations || [10, 15, 20, 30]).map((d) => (
                    <option key={d} value={d}>{d} seconds</option>
                  ))}
                </select>
              </div>
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
          description="Recommendations are a starting point — any compatible template works."
        >
          <div className="space-y-4">
            <Button
              variant={manualTemplate ? "secondary" : "brand"}
              size="sm"
              onClick={() => setManualTemplate((v) => !v)}
            >
              {manualTemplate ? "Showing all templates" : "Browse all templates instead"}
            </Button>

            {recommendations.length > 0 && (
              <div className="space-y-2">
                <span className="eyebrow block">Recommended</span>
                {recommendations.map((r) => (
                  <button
                    key={r.template.id}
                    type="button"
                    onClick={() => setTemplateId(r.template.id)}
                    className={`w-full rounded-xl border p-3 text-left transition-colors ${
                      templateId === r.template.id
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
                        {templateId === r.template.id && (
                          <Check className="h-4 w-4 text-[color:var(--brand-indigo)]" />
                        )}
                      </span>
                    </div>
                    {r.why_it_fits?.[0] && (
                      <p className="mt-1 text-xs text-muted-foreground">{r.why_it_fits[0]}</p>
                    )}
                    {r.limitations?.[0] && (
                      <p className="mt-0.5 text-[11px] text-muted-foreground/80">
                        {r.limitations[0]}
                      </p>
                    )}
                  </button>
                ))}
              </div>
            )}

            {manualTemplate && (
              <div className="space-y-2">
                <span className="eyebrow block">All templates ({templates.length})</span>
                <div className="max-h-80 space-y-2 overflow-y-auto pr-1">
                  {templates.map((t) => (
                    <button
                      key={t.id}
                      type="button"
                      onClick={() => setTemplateId(t.id)}
                      className={`w-full rounded-xl border p-3 text-left transition-colors ${
                        templateId === t.id
                          ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                          : "border-[color:var(--hairline)] hover:border-[color:var(--indigo-35)]"
                      }`}
                    >
                      <div className="flex items-center justify-between gap-2">
                        <span className="text-sm font-medium">{t.name}</span>
                        <Badge variant="secondary" className="text-[11px]">{t.default_duration}s</Badge>
                      </div>
                      <p className="mt-1 line-clamp-2 text-xs text-muted-foreground">
                        {t.opening_structure}
                      </p>
                    </button>
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
                </div>
                <p className="mt-1 text-xs text-muted-foreground">{template.opening_structure}</p>
                {template.required_assets?.length > 0 && (
                  <div className="mt-2 flex flex-wrap gap-1.5">
                    {template.required_assets.map((a) => (
                      <Badge key={a} variant="outline" className="text-[11px]">{humanize(a)}</Badge>
                    ))}
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
          description="Real app visuals get composited onto the video deterministically, so interfaces and text stay accurate."
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
              projectDuration={project?.duration_seconds || duration}
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
                Nothing attached yet. Select assets above to place them on the timeline.
              </p>
            ) : (
              <div className="space-y-2">
                {(project?.assets || []).map((a) => (
                  <AttachmentRow
                    key={`${a.asset_id}-${a.start ?? 0}-${a.end ?? "end"}-${a.audio_role || "none"}-${a.audio_gain ?? "default"}`}
                    project={project}
                    attachment={a}
                    duration={project?.duration_seconds || duration}
                    onChanged={setProject}
                  />
                ))}
              </div>
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 4) {
      return (
        <StepShell
          icon={Sparkles}
          title="Influencer hook"
          description="Build the app-specific strategy, render a short hook with your uploaded person in it, then extend it while the same character and scene carry through. Skippable — the creative plan below still produces a complete one-pass video."
        >
          <div className="space-y-3">
            {!canGenerate ? (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm text-muted-foreground">
                  Pick an App Profile and a hook template first — the strategy is built from
                  both, so the hook has to serve the mechanism you picked.
                </p>
              </div>
            ) : !project ? (
              <div className="rounded-xl border border-[color:var(--hairline)] p-4">
                <p className="text-sm text-muted-foreground">
                  A free draft is created from your profile, angle, and template so the
                  strategy and hook have somewhere to live. Drafts cost nothing; only a
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
              <HookContinuityPanel
                project={project}
                onProjectChange={setProject}
                onGenerationChange={() => {}}
              />
            )}
          </div>
        </StepShell>
      );
    }

    if (step === 5) {
      return (
        <StepShell
          icon={FileText}
          title="Generate the creative plan"
          description="This writes your hook, script, shot timeline, overlays, and CTA. It costs no video generation."
        >
          <div className="space-y-3">
            <Button
              variant="brand"
              onClick={handleGeneratePlan}
              disabled={busy || !canGenerate}
            >
              {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Sparkles className="h-4 w-4" />}
              {project?.script_version ? "Regenerate plan" : "Generate plan"}
            </Button>
            {!templateId && (
              <p className="text-sm text-muted-foreground">Choose a template first.</p>
            )}
            {project?.script_version > 0 && (
              <p className="text-sm text-muted-foreground">
                Current plan is version {project.script_version}. Regenerating replaces it.
              </p>
            )}
          </div>
        </StepShell>
      );
    }

    // Review step
    return (
      <StepShell
        icon={CheckCircle2}
        title="Review and edit"
        description="Everything is editable. The claim check re-runs on every edit."
      >
        {!project?.script_version ? (
          <EmptyState
            icon={FileText}
            title="No plan yet"
            description="Generate a creative plan to review it here."
            action={
              <Button variant="brand" onClick={() => setStep(5)}>
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
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label className="text-sm font-medium">CTA</label>
                <Input
                  value={editValue("cta", "")}
                  onChange={(e) => setEdits({ ...edits, cta: e.target.value })}
                />
              </div>
              <div className="space-y-1.5">
                <label className="text-sm font-medium">Feature emphasis</label>
                <Input
                  value={editValue("feature_emphasis", "")}
                  onChange={(e) => setEdits({ ...edits, feature_emphasis: e.target.value })}
                />
              </div>
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

            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-1.5">
                <label htmlFor="review-duration" className="text-sm font-medium">Total video length</label>
                <select
                  id="review-duration"
                  value={editValue("duration_seconds", 20)}
                  onChange={(e) => editDuration(Number(e.target.value))}
                  className="w-full rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
                >
                  {(facets?.supported_durations || [10, 15, 20, 30]).map((d) => (
                    <option key={d} value={d}>{d} seconds</option>
                  ))}
                </select>
                {editValue("duration_seconds", 20) !== duration && (
                  <p className="text-xs text-muted-foreground">
                    Differs from the plan step. Regenerating the plan will use {duration}s.
                  </p>
                )}
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
                Composited onto the real app footage after generation. Without text overlays a
                video is still made of the generated video and your assets.
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

            {/* The influencer hook, strategy, and segment chain live on their own
                step. The one-pass GenerationPanel stays here. */}
            <GenerationPanel
              project={project}
              onGenerationChange={() => {}}
            />
          </div>
        )}
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
        description="Build a short-form promo from an approved App Profile and a hook template. Nothing is published — you download the MP4 and post it yourself."
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
              className={`inline-flex items-center gap-1.5 rounded-full px-3 py-1.5 text-xs font-medium transition-colors ${
                active
                  ? "bg-primary/15 text-[color:var(--brand-indigo)]"
                  : done
                    ? "text-muted-foreground hover:text-foreground"
                    : "text-muted-foreground/60"
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

      <div className="flex items-center justify-between">
        <Button
          variant="ghost"
          onClick={() => setStep((s) => Math.max(0, s - 1))}
          disabled={step === 0}
        >
          <ChevronLeft className="h-4 w-4" /> Back
        </Button>
        {step < STEPS.length - 1 && (
          <Button
            variant="secondary"
            onClick={() => setStep((s) => Math.min(STEPS.length - 1, s + 1))}
            disabled={step === 0 && !profileId}
          >
            Next <ChevronRight className="h-4 w-4" />
          </Button>
        )}
        {step === STEPS.length - 1 && project && (
          <Button variant="ghost" onClick={() => navigate("/app-profiles")}>
            Back to your app
          </Button>
        )}
      </div>

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
          TestNoPlatformAutomation proves it; this says so where it is read. */}
      <p className="text-xs text-muted-foreground">
        Videos are generated here and posted by hand. This tool never publishes to any
        platform and never asks for platform credentials.
      </p>
    </div>
  );
}
