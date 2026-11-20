import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  AudioLines,
  Briefcase,
  Clapperboard,
  Compass,
  History as HistoryIcon,
  Layers,
  ListChecks,
  PenLine,
  Sparkles,
} from "lucide-react";
import PageFrame from "../components/PageFrame";
import PageHeader from "../components/PageHeader";
import SectionCard, { GroupLabel } from "../components/SectionCard";
import EmptyState from "../components/EmptyState";
import { AppPicker } from "../components/AppPicker";
import { AppSelect } from "../components/AppSelect";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Skeleton } from "../components/ui/skeleton";
import { Textarea } from "../components/ui/textarea";
import { CONTROL_CLASS } from "../components/formControls";
import { DirectionSelect } from "../components/studio/ReviewPanels";
import { PresenterPhotoControl } from "../components/studio/SelectionPanels";
import HookLineEditor from "../components/studio/HookLineEditor";
import ScriptRewrite from "../components/studio/ScriptRewrite";
import { StoryTypePicker } from "../components/studio/StoryTypePicker";
import StoryScreenTextEditor from "../components/studio/StoryScreenTextEditor";
import StoryPreview from "../components/studio/StoryPreview";
import StoryCraftCheck from "../components/studio/StoryCraftCheck";
import StoryRenderPanel from "../components/studio/StoryRenderPanel";
import StoryKitPanel from "../components/studio/StoryKitPanel";
import { useWizardDirections } from "./useWizardDirections";
import { api, getErrorMessage, durableMediaUrl, mediaUrl } from "../lib/api";
import { BUSY_ETA_SECONDS } from "../lib/busyEta";
import { sentenceCase } from "../lib/copyCase";
import {
  describeEmptySelection,
  describeUnapprovedCount,
  partitionProfiles,
} from "../lib/profileSelection";
import { STORY_FRAME_SECONDS, defaultFrameSeconds, storyTypeById } from "../lib/storyTypes";

/**
 * The Stories page (ADR 0235's shell, completed by ADR 0236; the
 * feature's backend phases are ADRs 0227–0228).
 *
 * One stacked canvas of section cards, NOT the Create Video wizard:
 * a story is a quick, repeatable format, so there are no steps, no
 * rail and no sticky bar — the founder picks an app and a story type,
 * the page holds the saved draft those picks make, and the direction,
 * the plan, the preview and the render stack below as further cards
 * on the same canvas.
 *
 * Saving follows the wizard's pattern, unchanged in shape: a draft
 * reducer owns the picks and every field edit, the draft row is
 * created in the background once both picks exist (a draft calls no
 * model — ADR 0122's click-to-generate rule is about generation, and
 * nothing here generates), and later changes ride the ~1-second
 * debounced, validated server PATCH behind the "All changes saved"
 * line. One deliberate difference from the wizard's save: no
 * mark-ready call follows it. A story has no ready gate (ADR 0228) —
 * its readiness is its plan, and the render panel below says so.
 */

function createStoryDraft({ profileId = "", storyType = "" } = {}) {
  return { profileId, storyType, project: null, edits: {} };
}

function storyDraftReducer(state, action) {
  switch (action.type) {
    case "profile-selected":
      // A different app is a different draft: the saved row belongs
      // to the profile it was created under, so the draft resets.
      // The type pick survives the switch — a story type is a format,
      // not a property of one app — and the create effect starts the
      // new app's draft from it.
      return createStoryDraft({ profileId: action.id, storyType: state.storyType });
    case "profile-loaded":
      return { ...state, profileId: action.id };
    case "edit-field": {
      // The wizard draft's field-edit shape (wizardDraft.js), which
      // is what the shared direction hook dispatches: a pick is a
      // local edit until the autosave lands it, and a pick that
      // restates the saved value — or the field's fallback — is no
      // edit at all. The editors ride the same action, so every
      // unsaved change on the page lives in one edits object and one
      // autosave carries them all.
      const edits = { ...state.edits, [action.field]: action.value };
      if (
        action.omitDefault &&
        (!action.value ||
          action.value === state.project?.[action.field] ||
          action.value === action.fallback)
      ) {
        delete edits[action.field];
      }
      return { ...state, edits };
    }
    case "type-selected": {
      const storyType = action.id;
      if (!state.project) return { ...state, storyType };
      if (storyType === (state.project.story_type || "")) {
        // Re-picking the saved type clears the pending type edit
        // and nothing else: the edits object now also carries the
        // editors' fields (ADR 0236), and recomputing it wholesale
        // the way the shell did would drop an unsaved hook line
        // typed a second earlier. Merging is the rule from here.
        const edits = { ...state.edits };
        delete edits.story_type;
        return { ...state, storyType, edits };
      }
      // The type and the frame length move together (ADR 0235):
      // a new type brings its settled default, exactly what creating
      // the draft under that type would have written. The length
      // follows only while the effective length still IS the old
      // type's default; a length picked on purpose — the frame-
      // length pick (ADR 0236) — is the founder's and stays.
      const edits = { ...state.edits, story_type: storyType };
      const oldDefault = defaultFrameSeconds(state.edits.story_type ?? state.project.story_type);
      const effective = state.edits.duration_seconds ?? state.project.duration_seconds;
      if (oldDefault !== null && Number(effective) === oldDefault) {
        edits.duration_seconds = defaultFrameSeconds(storyType);
      }
      return { ...state, storyType, edits };
    }
    case "draft-opened":
      return {
        profileId: action.project.brand_profile_id || "",
        storyType: action.project.story_type || "",
        project: action.project,
        edits: {},
      };
    case "project-received":
      return { ...state, project: action.project };
    case "picks-saved": {
      // A save flight snapshots `edits` when it starts; a pick that
      // lands while the flight is in the air is newer than the
      // snapshot and must survive the adoption (the wizardDraft
      // plan-accepted rule, carried over).
      const saved = action.savedEdits || {};
      const edits = {};
      for (const [field, value] of Object.entries(state.edits || {})) {
        if (!(field in saved) || saved[field] !== value) edits[field] = value;
      }
      return { ...state, project: action.project, edits };
    }
    default:
      throw new Error(`Unknown story draft transition: ${action.type}`);
  }
}

function isStoryProject(project) {
  return (project?.kind || "video") === "story";
}

export default function Stories() {
  const [params] = useSearchParams();
  const requestedProjectId = params.get("project") || "";

  const [profiles, setProfiles] = useState([]);
  const [loadState, setLoadState] = useState("loading");
  const [loadError, setLoadError] = useState(null);
  const [error, setError] = useState(null);
  const [drafts, setDrafts] = useState([]);
  const [saveStatus, setSaveStatus] = useState("");
  const [autosaving, setAutosaving] = useState(false);
  const [draft, dispatch] = useReducer(storyDraftReducer, undefined, () => createStoryDraft());
  const { profileId, storyType, project, edits } = draft;

  const adoptOpenedDraft = useCallback((opened) => {
    if (!isStoryProject(opened)) {
      setError("That project is a hook video, not a story — it opens in Create Video instead.");
      return false;
    }
    dispatch({ type: "draft-opened", project: opened });
    setSaveStatus("All changes saved");
    return true;
  }, []);

  const loadPage = useCallback(async () => {
    setLoadState("loading");
    setLoadError(null);
    try {
      const data = await api.getAppProfiles();
      const list = data.profiles || [];
      setProfiles(list);
      if (requestedProjectId) {
        const opened = await api.getStudioProject(requestedProjectId);
        adoptOpenedDraft(opened);
      } else {
        const { approved } = partitionProfiles(list);
        if (approved[0]) dispatch({ type: "profile-loaded", id: approved[0].id });
      }
      setLoadState("ready");
    } catch (err) {
      setLoadError(getErrorMessage(err));
      setLoadState("failed");
    }
  }, [requestedProjectId, adoptOpenedDraft]);

  useEffect(() => {
    loadPage();
  }, [loadPage]);

  // The picked app's story drafts, newest first (the list endpoint's
  // own order). Refetched when the app changes and when a draft is
  // created or opened, so the list the founder sees is the server's.
  const openProjectId = project?.id || "";
  useEffect(() => {
    if (!profileId) {
      setDrafts([]);
      return undefined;
    }
    let cancelled = false;
    api
      .getStoryProjects(profileId)
      .then((data) => {
        if (!cancelled) setDrafts(data.projects || []);
      })
      .catch(() => {
        // The list is a convenience beside the pickers, not the
        // page's load: a failed read empties it quietly rather than
        // failing the page over a sidebar.
        if (!cancelled) setDrafts([]);
      });
    return () => {
      cancelled = true;
    };
  }, [profileId, openProjectId]);

  // Make sure a draft exists without the founder having to ask, the
  // wizard's ensureProject rule: as soon as an app and a story type
  // are both chosen, the draft is created in the background. A draft
  // calls no model, so doing this eagerly costs nothing.
  const creatingKeyRef = useRef("");
  useEffect(() => {
    if (!profileId || !storyType || project) return undefined;
    const key = `${profileId}:${storyType}`;
    if (creatingKeyRef.current === key) return undefined;
    creatingKeyRef.current = key;
    let cancelled = false;
    (async () => {
      try {
        const created = await api.createStoryProject({
          brand_profile_id: profileId,
          story_type: storyType,
        });
        if (cancelled) return;
        dispatch({ type: "project-received", project: created });
        setSaveStatus("All changes saved");
      } catch (err) {
        if (!cancelled) setError(getErrorMessage(err));
      }
    })();
    return () => {
      cancelled = true;
      // Unlatch this flight's key: if the picks changed mid-flight and
      // change back, the page must be able to create again rather than
      // sit on a key whose draft it never adopted.
      if (creatingKeyRef.current === key) creatingKeyRef.current = "";
    };
  }, [profileId, storyType, project]);

  // Autosave: save ~1s after the last pick change, through the same
  // validated PATCH every draft edit rides. Silent saves never block
  // the pickers — the status line narrates them instead.
  const savePicks = useCallback(async () => {
    if (!project) return;
    const savedEdits = { ...edits };
    if (!Object.keys(savedEdits).length) return;
    setAutosaving(true);
    setSaveStatus("Saving…");
    try {
      const updated = await api.updateStudioProject(project.id, savedEdits);
      dispatch({ type: "picks-saved", project: updated, savedEdits });
      setSaveStatus("All changes saved");
    } catch (err) {
      setSaveStatus(`Could not autosave: ${getErrorMessage(err)}`);
    } finally {
      setAutosaving(false);
    }
  }, [project, edits]);

  const savePicksRef = useRef(null);
  savePicksRef.current = savePicks;
  const hasEdits = Object.keys(edits).length > 0;
  const editsSignature = JSON.stringify(edits);
  const autosaveProjectId = project?.id || "";
  useEffect(() => {
    if (!hasEdits || !autosaveProjectId || autosaving) return undefined;
    setSaveStatus("");
    const timer = setTimeout(() => {
      savePicksRef.current?.();
    }, 1000);
    return () => clearTimeout(timer);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [editsSignature, autosaveProjectId, hasEdits]);

  const selectProfile = (id) => {
    if (!id || id === profileId) return;
    setError(null);
    dispatch({ type: "profile-selected", id });
  };

  const selectType = (id) => {
    setError(null);
    dispatch({ type: "type-selected", id });
  };

  const openDraft = async (id) => {
    if (!id || id === project?.id) return;
    setError(null);
    try {
      const opened = await api.getStudioProject(id);
      adoptOpenedDraft(opened);
    } catch (err) {
      setError(getErrorMessage(err));
    }
  };

  // The effective value of any draft field: a pending edit wins,
  // then the saved row, then the caller's fallback. Every control
  // below reads through this, so what the founder sees is always
  // what the autosave is about to write.
  const editValue = (field, fallback = "") =>
    edits[field] !== undefined ? edits[field] : project?.[field] ?? fallback;
  const editField = useCallback(
    (field, value, options = {}) =>
      dispatch({ type: "edit-field", field, value, ...options }),
    []
  );

  // The page's copy of the newest generation for the open draft —
  // the render panel writes it, the preview and the kit panel read
  // it, the same shape Create Video keeps.
  const [generation, setGeneration] = useState(null);
  useEffect(() => {
    setGeneration(null);
  }, [openProjectId]);

  // Direction, through the wizard's own hook (ADR 0236): the same
  // option reads, the same fixed-camera indoor rule (ADR 0220), the
  // same dispatch shape — the hook only ever dispatches on a pick,
  // never on load, so opening a draft cannot rewrite its direction.
  const dispatchDraft = useCallback((action) => dispatch(action), []);
  const cameraSetup = editValue("camera_setup", "handheld");
  const {
    directionOptions,
    dirSel,
    pickScenePart,
    refreshError: directionRefreshError,
    refreshProps: directionRefreshProps,
  } = useWizardDirections({
    profileId,
    project,
    angle: null,
    dispatchDraft,
    cameraSetup,
  });
  // ADR 0220's rule, computed the way the wizard computes it: the
  // setup is fixed, the lists are loaded, a place is saved, and the
  // hook's derivation offered no match for it — so the pick reads
  // empty and the section names why, instead of the value being
  // rewritten behind the founder's back. Flipping back to handheld
  // restores the pick.
  const directionLocationIneligible =
    cameraSetup === "fixed" &&
    Boolean(directionOptions) &&
    !dirSel.location &&
    Boolean(String(editValue("location", "") || "").trim());

  const refreshProject = useCallback(async () => {
    if (!project?.id) return;
    try {
      const fresh = await api.getStudioProject(project.id);
      dispatch({ type: "project-received", project: fresh });
    } catch {
      /* the photo control narrates its own failures; a stale row is
         better than a failed page */
    }
  }, [project?.id]);

  // The plan, on its click only (ADR 0122): pending edits are
  // flushed first so the plan is written from the saved direction
  // and length, then the returned row is adopted whole — it carries
  // the spoken lines, the screen text, the sticker plan and the
  // recomputed craft check.
  const [planBusy, setPlanBusy] = useState(false);
  const [planError, setPlanError] = useState(null);
  const [countdownDate, setCountdownDate] = useState("");
  const generatePlan = async () => {
    if (!project || planBusy) return;
    setPlanBusy(true);
    setPlanError(null);
    try {
      await savePicksRef.current?.();
      const planned = await api.generateStoryPlan(project.id, {
        story_type: editValue("story_type", storyType) || undefined,
        frame_seconds: Number(editValue("duration_seconds", 0)) || undefined,
        countdown_date:
          editValue("story_type", storyType) === "announcement_countdown" && countdownDate
            ? countdownDate
            : undefined,
      });
      dispatch({ type: "project-received", project: planned });
      setSaveStatus("All changes saved");
    } catch (err) {
      setPlanError(getErrorMessage(err));
    } finally {
      setPlanBusy(false);
    }
  };

  const { approved, unapproved } = partitionProfiles(profiles);
  const activeType = storyTypeById(editValue("story_type", storyType));
  const hasPlan = Boolean(
    String(editValue("hook_line")).trim() && String(editValue("script")).trim()
  );
  const stickerPlan = Array.isArray(project?.sticker_plan) ? project.sticker_plan : [];
  const previewVideoUrl = generation?.status === "completed" ? durableMediaUrl(generation) : "";
  const previewPosterUrl = generation?.poster_url ? mediaUrl(generation.poster_url) : "";

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Layers}
        title="Stories"
        description="Short vertical clips for Instagram and TikTok Stories."
        data-testid="stories-header"
      />

      {error && (
        <p role="alert" className="text-sm text-destructive-text" data-testid="stories-error">
          {error}
        </p>
      )}

      {loadState === "loading" && (
        <div className="surface" role="status" aria-label="Loading Stories" data-testid="stories-loading">
          <div className="space-y-3">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
          <span className="sr-only">Loading…</span>
        </div>
      )}

      {loadState === "failed" && (
        <div className="surface space-y-4" data-testid="stories-load-failed">
          <p role="alert" className="text-sm text-destructive-text">
            {loadError || "Stories could not load."}
          </p>
          <Button variant="secondary" onClick={loadPage}>
            Try again
          </Button>
        </div>
      )}

      {loadState === "ready" && approved.length === 0 && (
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
      )}

      {loadState === "ready" && approved.length > 0 && (
        <>
          <SectionCard title="App and story type" icon={ListChecks} data-testid="stories-setup-card">
            <div className="space-y-4">
              <GroupLabel icon={Briefcase}>Choose an app</GroupLabel>
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Only approved App Profiles can make a story in this studio.
              </p>
              <AppPicker
                profiles={approved}
                value={profileId}
                onChange={selectProfile}
                placeholder="Choose an app"
                testId="stories-app-picker"
              />
              {unapproved.length > 0 && (
                <div className="inset-panel" data-testid="stories-unapproved-panel">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="text-base font-semibold">
                        {describeUnapprovedCount(unapproved.length)}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground" data-subtitle="">
                        Draft profiles need review before a story can use them.
                      </p>
                      <Button variant="secondary" size="sm" asChild className="mt-3">
                        <Link to="/brand">Review in App Profile</Link>
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            <div className="space-y-4">
              <GroupLabel icon={Layers}>Choose a story type</GroupLabel>
              <p className="text-sm text-muted-foreground" data-subtitle="">
                The type is the story&apos;s aim: it sets the frame&apos;s length too.
              </p>
              <StoryTypePicker value={storyType} onChange={selectType} />
            </div>

            {(project || saveStatus) && (
              <p
                role="status"
                data-testid="stories-autosave-status"
                className="text-sm text-muted-foreground"
              >
                {saveStatus}
              </p>
            )}
          </SectionCard>

          {project && (
            <SectionCard title="Moment and direction" icon={Compass} data-testid="stories-direction-card">
              <div className="space-y-4">
                <GroupLabel icon={Compass}>Camera, place and wardrobe</GroupLabel>
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  Camera, place and wardrobe — the plan is written from them.
                </p>

                <div className="space-y-2">
                  <label htmlFor="story-camera-setup" className="text-sm font-semibold">Camera setup</label>
                  <AppSelect
                    id="story-camera-setup"
                    testId="story-camera-setup"
                    block
                    value={cameraSetup}
                    onChange={(value) => editField("camera_setup", value, { omitDefault: true, fallback: "handheld" })}
                    className={CONTROL_CLASS}
                    options={[
                      { value: "handheld", label: "Handheld selfie" },
                      { value: "fixed", label: "Fixed camera" },
                    ]}
                  />
                  <p className="text-sm text-muted-foreground">
                    {cameraSetup === "fixed"
                      ? "Phone on a shelf or tripod. Head to mid-thigh, natural gestures, no camera movement or automatic zoom. A face reference guides identity, not exact body proportions."
                      : "Mid-chest handheld framing with headroom, subtle sway, and the current centered zoom."}
                  </p>
                </div>

                <DirectionSelect
                  id="story-location-direction"
                  testId="story-location-direction"
                  label="Location"
                  value={dirSel.location}
                  onPick={pickScenePart("location")}
                  options={directionOptions?.location}
                  placeholder="Choose a Location…"
                  refresh={directionRefreshProps("location", "story-location-refresh")}
                />
                {directionLocationIneligible && (
                  <p className="text-sm text-muted-foreground" data-testid="story-direction-location-ineligible">
                    The saved place is not an indoor location, so it is not offered for a fixed
                    camera. Pick an indoor location — the plan is written from the pick saved here.
                  </p>
                )}
                <DirectionSelect
                  id="story-wardrobe"
                  testId="story-wardrobe"
                  label="Wardrobe"
                  value={dirSel.wardrobe}
                  onPick={pickScenePart("wardrobe")}
                  options={directionOptions?.wardrobe}
                  placeholder="Choose wardrobe…"
                  refresh={directionRefreshProps("wardrobe", "story-wardrobe-refresh")}
                />
                {project?.visual_direction && !edits.visual_direction && (
                  <p className="text-sm text-muted-foreground">
                    Plan default: {sentenceCase(project.visual_direction)}
                  </p>
                )}
                <p className="text-sm text-muted-foreground">
                  Location and wardrobe apply together in the plan written from them. Lighting
                  is set from this story&apos;s scene.
                </p>
                {directionRefreshError && (
                  <p role="alert" data-testid="story-direction-refresh-error" className="text-sm text-destructive-text">
                    {directionRefreshError}
                  </p>
                )}
              </div>

              <div className="space-y-4">
                <PresenterPhotoControl
                  project={project}
                  profileId={profileId}
                  busy={false}
                  onEnsureProject={async () => project}
                  onProjectChanged={(updated) => dispatch({ type: "project-received", project: updated })}
                  onRefreshProject={refreshProject}
                />
              </div>
            </SectionCard>
          )}

          {project && (
            <SectionCard title="Script and screen text" icon={PenLine} data-testid="stories-plan-card">
              <div className="space-y-4">
                <GroupLabel icon={Clapperboard}>The frame</GroupLabel>
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  The frame&apos;s length, and its date when the story announces.
                </p>
                <div className="space-y-2">
                  <label htmlFor="story-frame-length" className="text-sm font-semibold">Frame length</label>
                  <AppSelect
                    id="story-frame-length"
                    testId="story-frame-length"
                    block
                    value={String(editValue("duration_seconds", activeType?.defaultSeconds ?? ""))}
                    onChange={(value) =>
                      editField("duration_seconds", Number(value), { omitDefault: true })
                    }
                    className={CONTROL_CLASS}
                    options={STORY_FRAME_SECONDS.map((seconds) => ({
                      value: String(seconds),
                      label: `${seconds} seconds`,
                    }))}
                  />
                  <p className="text-sm text-muted-foreground">
                    {activeType
                      ? `${activeType.name} frames default to ${activeType.defaultSeconds} seconds — the pick above is the length the frame renders at.`
                      : "The length the frame renders at."}
                  </p>
                </div>
                {editValue("story_type", storyType) === "announcement_countdown" && (
                  <div className="space-y-2">
                    <label htmlFor="story-countdown-date" className="text-sm font-semibold">
                      Countdown date (optional)
                    </label>
                    <Input
                      id="story-countdown-date"
                      type="date"
                      value={countdownDate}
                      onChange={(event) => setCountdownDate(event.target.value)}
                      data-testid="story-countdown-date"
                    />
                    <p className="text-sm text-muted-foreground">
                      The date the announcement counts down to — the plan and the kit&apos;s
                      countdown sticker are written from it.
                    </p>
                  </div>
                )}
                <div className="space-y-2">
                  <Button
                    variant="accent"
                    onClick={generatePlan}
                    disabled={planBusy}
                    busy={planBusy}
                    etaSeconds={BUSY_ETA_SECONDS.plan}
                    data-testid="story-plan-generate"
                  >
                    <Sparkles className="h-4 w-4" />
                    {planBusy ? "Writing the plan" : hasPlan ? "Regenerate the plan" : "Generate plan"}
                  </Button>
                  {planError && (
                    <p role="alert" className="text-sm text-destructive-text" data-testid="story-plan-error">
                      {planError}
                    </p>
                  )}
                  <p className="text-sm text-muted-foreground">
                    One click writes the spoken lines, the screen text and the sticker plan
                    from the direction above. Nothing is written until you press it.
                  </p>
                </div>
              </div>

              {hasPlan && (
                <div className="space-y-4">
                  <GroupLabel icon={AudioLines}>Spoken lines and screen text</GroupLabel>
                  <p className="text-sm text-muted-foreground" data-subtitle="">
                    The spoken lines and the sticker text, checked as you edit.
                  </p>

                  <HookLineEditor
                    projectId={project.id}
                    value={editValue("hook_line")}
                    onChange={(next) => editField("hook_line", next)}
                  />

                  <div className="space-y-2">
                    <div className="flex flex-wrap items-center justify-between gap-2">
                      <span className="text-sm font-semibold">Script</span>
                      <ScriptRewrite
                        projectId={project.id}
                        hookLine={editValue("hook_line")}
                        script={editValue("script")}
                        onChange={(next) => editField("script", next)}
                      />
                    </div>
                    <div className="post-kit-cover spoken-line-frame">
                      <Textarea
                        value={editValue("script")}
                        onChange={(event) => editField("script", event.target.value)}
                        rows={4}
                        aria-label="Story script"
                        data-testid="story-script-input"
                      />
                    </div>
                    <p className="text-sm text-muted-foreground">
                      The story is heard as much as read — the spoken line carries it, and
                      the screen text below must carry the same message on mute.
                    </p>
                  </div>

                  <StoryScreenTextEditor
                    projectId={project.id}
                    value={editValue("screen_text")}
                    hookLine={editValue("hook_line")}
                    script={editValue("script")}
                    onChange={(next) => editField("screen_text", next)}
                  />

                  {stickerPlan.length > 0 && (
                    <div className="space-y-2" data-testid="story-sticker-plan">
                      <span className="text-sm font-semibold">Sticker plan</span>
                      <ul className="space-y-2">
                        {stickerPlan.map((entry, i) => (
                          <li key={i} className="text-base leading-relaxed text-foreground/90">
                            <span className="font-semibold">{String(entry?.sticker || "Sticker")}</span>
                            {entry?.platform && (
                              <span className="text-muted-foreground"> · {String(entry.platform)}</span>
                            )}
                            {entry?.wording && <span> — {String(entry.wording)}</span>}
                            {entry?.placement && (
                              <span className="block text-sm text-muted-foreground">{String(entry.placement)}</span>
                            )}
                          </li>
                        ))}
                      </ul>
                      <p className="text-sm text-muted-foreground">
                        Stickers are placed at posting from the story kit — nothing here is
                        burned into the video.
                      </p>
                    </div>
                  )}

                  <StoryCraftCheck report={project.story_quality} />
                </div>
              )}

              <div className="space-y-4">
                <StoryPreview
                  screenText={editValue("screen_text")}
                  videoUrl={previewVideoUrl}
                  posterUrl={previewPosterUrl}
                />
              </div>
            </SectionCard>
          )}

          {project && (
            <SectionCard title="Render" icon={Clapperboard} data-testid="stories-render-card">
              <div className="space-y-4">
                <GroupLabel icon={Clapperboard}>The finished frame</GroupLabel>
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  One press renders this frame at the length picked above.
                </p>
                <StoryRenderPanel
                  project={{ ...project, duration_seconds: editValue("duration_seconds", project.duration_seconds) }}
                  generation={generation}
                  onGenerationChange={setGeneration}
                  hasUnsavedEdits={hasEdits}
                  autosaving={autosaving}
                />
                {generation?.status === "completed" && !generation.story_kit && (
                  <p role="status" className="text-sm text-muted-foreground">
                    The frame is finished — its story kit is being written and will appear
                    here in a moment.
                  </p>
                )}
                <StoryKitPanel
                  storyKit={generation?.story_kit || null}
                  generationId={generation?.id || ""}
                  onUpdated={(kit) =>
                    setGeneration((current) => (current ? { ...current, story_kit: kit } : current))
                  }
                />
              </div>
            </SectionCard>
          )}

          {drafts.length > 0 && (
            <SectionCard title="Story drafts for this app" icon={HistoryIcon} data-testid="stories-drafts-card">
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Open a draft to keep working on the story you started here.
              </p>
              <div className="space-y-2">
                {drafts.map((row) => {
                  const type = storyTypeById(row.story_type);
                  const isCurrent = project?.id === row.id;
                  const body = (
                    <>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-display text-sm font-semibold">
                          {type ? type.name : "Story draft"}
                        </span>
                        {isCurrent && (
                          <span className="text-xs font-semibold text-[color:var(--brand-indigo)]">
                            Open now
                          </span>
                        )}
                      </div>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {row.duration_seconds}s frame · Updated{" "}
                        {new Date(row.updated_at).toLocaleDateString("en-US", {
                          month: "short",
                          day: "numeric",
                        })}
                      </p>
                    </>
                  );
                  return isCurrent ? (
                    <div
                      key={row.id}
                      className="row-pad w-full rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                      data-testid={`story-draft-${row.id}`}
                      aria-current="true"
                    >
                      {body}
                    </div>
                  ) : (
                    <button
                      key={row.id}
                      type="button"
                      onClick={() => openDraft(row.id)}
                      className="card-pickable row-pad w-full rounded-xl border border-[color:var(--hairline)] text-left hover:border-[color:var(--indigo-35)]"
                      data-testid={`story-draft-${row.id}`}
                    >
                      {body}
                    </button>
                  );
                })}
              </div>
            </SectionCard>
          )}
        </>
      )}
    </PageFrame>
  );
}
