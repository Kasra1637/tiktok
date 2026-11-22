import { useCallback, useEffect, useReducer, useRef, useState } from "react";
import { Link, useSearchParams } from "react-router-dom";
import {
  AlertTriangle,
  AudioLines,
  Briefcase,
  Clapperboard,
  Compass,
  Film,
  History as HistoryIcon,
  PenLine,
  Share2,
  Sparkles,
  Zap,
} from "lucide-react";
import PageFrame from "../components/PageFrame";
import PageHeader from "../components/PageHeader";
import SectionCard, { GroupLabel } from "../components/SectionCard";
import EmptyState from "../components/EmptyState";
import { AppPicker } from "../components/AppPicker";
import { AppSelect } from "../components/AppSelect";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { CONTROL_CLASS } from "../components/formControls";
import { DirectionSelect } from "../components/studio/ReviewPanels";
import { PresenterPhotoControl } from "../components/studio/SelectionPanels";
import HookLineEditor from "../components/studio/HookLineEditor";
import LineRewriteAction from "../components/studio/LineRewriteAction";
import HookRenderPanel from "../components/studio/HookRenderPanel";
import VoiceModeControl from "../components/studio/VoiceModeControl";
import HookPicksControl, { profileOutcomeLines } from "../components/studio/HookPicksControl";
import PostKitSection from "../components/PostKitSection";
import { DemoCtaGenerationEditor } from "./DemoCtaStudio";
import { useWizardDirections } from "./useWizardDirections";
import { useTourEligibility } from "../components/onboarding/OnboardingProvider";
import { api, getErrorMessage } from "../lib/api";
import { sentenceCase } from "../lib/copyCase";
import {
  describeEmptySelection,
  describeUnapprovedCount,
  partitionProfiles,
} from "../lib/profileSelection";

/**
 * The Hook + CTA page (ADR 0244), built where the Stories page stood
 * before ADR 0243 removed it.
 *
 * One job: the founder picks an app and gets ONE feed-ready video —
 * a 4–5 second presenter hook flowing straight into their demo and
 * call to action — plus its post kit. A short hook + demo + CTA
 * posted as a regular TikTok/Reel beats standalone stories for views,
 * clicks and installs, so the page is shaped for that outcome and
 * nothing else: no script, no screen text, no sticker plan.
 *
 * One stacked canvas of section cards, NOT the Create Video wizard:
 * the founder picks an app, the page holds the saved draft that pick
 * makes, and the direction, the hook, the render, the demo finish and
 * the post kit stack below as further cards on the same canvas. A
 * plain visit starts fresh on a blank draft (ADR 0262): earlier
 * drafts wait in the list at the foot of the page and open only when
 * the founder clicks one.
 *
 * The draft is a VIDEO project carrying the hook_cta surface marker
 * (ADR 0244): its renders are ordinary video generations, so History,
 * post kits and analytics treat them as video renders. Saving follows
 * the wizard's pattern, unchanged in shape: a draft reducer owns the
 * picks and every field edit, the draft row is created in the
 * background once an app is picked (a draft calls no model — ADR
 * 0122's click-to-generate rule is about generation, and nothing here
 * generates), and later changes ride the ~1-second debounced,
 * validated server PATCH behind the "All changes saved" line. No
 * mark-ready call follows it: the hook has no ready gate — its
 * readiness is its line, and the render panel below says so.
 */

// The hook's length pick (ADR 0244): the backend's SHORT_HOOK_SECONDS,
// mirrored — the pick is the whole set, there is no third length.
const HOOK_FRAME_SECONDS = [4, 5];

function createHookCtaDraft({ profileId = "" } = {}) {
  return { profileId, project: null, edits: {} };
}

function hookCtaDraftReducer(state, action) {
  switch (action.type) {
    case "profile-selected":
      // A different app is a different draft: the saved row belongs
      // to the profile it was created under, so the draft resets and
      // the create effect starts the new app's draft.
      return createHookCtaDraft({ profileId: action.id });
    case "profile-loaded":
      return { ...state, profileId: action.id };
    case "edit-field": {
      // The wizard draft's field-edit shape (wizardDraft.js), which
      // is what the shared direction hook dispatches: a pick is a
      // local edit until the autosave lands it, and a pick that
      // restates the saved value is no edit at all. The fallback
      // stands in for the saved value only when the row carries
      // none — it is not a second value a pick can restate. This
      // reducer once deleted any edit equal to the fallback even
      // when the saved row held the other value, so a draft saved
      // silent could never be switched back to talking: the tap
      // produced no edit, no save, and no visible change (Kasra's
      // live report, Nov 21 2026 — the repair in ADR 0248). The
      // editors ride the same action, so every unsaved change on
      // the page lives in one edits object and one autosave
      // carries them all.
      const edits = { ...state.edits, [action.field]: action.value };
      if (
        action.omitDefault &&
        (!action.value ||
          action.value === (state.project?.[action.field] || action.fallback || ""))
      ) {
        delete edits[action.field];
      }
      return { ...state, edits };
    }
    case "draft-opened":
      return {
        profileId: action.project.brand_profile_id || "",
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
      throw new Error(`Unknown hook-cta draft transition: ${action.type}`);
  }
}

function isHookCtaProject(project) {
  return (project?.kind || "video") === "video" && (project?.surface || "") === "hook_cta";
}

// A draft nothing has touched since the create endpoint wrote it
// (ADR 0262): no hook and no script, no strategy, no photo attached,
// and every pick the page offers still at its create-time value —
// the voice on silent (ADR 0248), the length at the create's 5
// seconds, no place, wardrobe, focus or tone chosen. A render cannot
// hide behind these fields either: a render needs a hook, and a
// hook writes the line, the strategy and the script version. Such a
// row is indistinguishable from a brand-new draft, so it is the one
// row a fresh visit may stand on as its blank canvas; anything with
// a mark on it is the founder's work and opens only on its own
// click. The test reads only what this page itself can move — the
// create's audience copy from the profile is the profile's, not a
// pick.
function isUntouchedHookCtaDraft(project) {
  if (!isHookCtaProject(project)) return false;
  const strategy = project.strategy;
  return (
    !String(project.hook_line || "").trim() &&
    !String(project.script || "").trim() &&
    (!strategy || (typeof strategy === "object" && Object.keys(strategy).length === 0)) &&
    (project.script_version || 0) === 0 &&
    !(project.assets || []).length &&
    !String(project.location || "").trim() &&
    !String(project.visual_direction || "").trim() &&
    !String(project.tone || "").trim() &&
    !String(project.hook_focus || "").trim() &&
    (project.hook_shape || "auto") === "auto" &&
    (project.voice_mode || "") === "silent" &&
    Number(project.duration_seconds || 5) === 5
  );
}

export default function HookCta() {
  const [params] = useSearchParams();
  const requestedProjectId = params.get("project") || "";

  const [profiles, setProfiles] = useState([]);
  const [loadState, setLoadState] = useState("loading");
  const [loadError, setLoadError] = useState(null);
  const [error, setError] = useState(null);
  const [drafts, setDrafts] = useState([]);
  // Whether the drafts read for the current app has settled. The tour
  // eligibility below reads the drafts list as its "nothing made yet"
  // signal, and an unsettled read also reports an empty list — the
  // settled flag is what separates "no drafts" from "not known yet",
  // the same loading guard the other tour pages register behind.
  const [draftsSettled, setDraftsSettled] = useState(false);
  // Which app the settled drafts belong to. A pick change leaves the
  // previous app's list on screen until the new read lands, and the
  // create effect below must not mistake that stale list (or its
  // settled flag) for the new app's answer.
  const [draftsFor, setDraftsFor] = useState("");
  const [saveStatus, setSaveStatus] = useState("");
  const [autosaving, setAutosaving] = useState(false);
  const [draft, dispatch] = useReducer(hookCtaDraftReducer, undefined, () => createHookCtaDraft());
  const { profileId, project, edits } = draft;

  const adoptOpenedDraft = useCallback((opened) => {
    if (!isHookCtaProject(opened)) {
      setError(
        (opened?.kind || "video") === "story"
          ? "That project is a story draft from the retired Stories page — its renders stay in History."
          : "That project is a hook video, not a Hook + CTA draft — it opens in Create Video instead."
      );
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

  // The picked app's Hook + CTA drafts, newest first (the list
  // endpoint's own order). Refetched when the app changes and when a
  // draft is created or opened, so the list the founder sees is the
  // server's.
  const openProjectId = project?.id || "";
  const projectRef = useRef(null);
  projectRef.current = project;
  useEffect(() => {
    if (!profileId) {
      setDrafts([]);
      setDraftsFor("");
      setDraftsSettled(true);
      return undefined;
    }
    setDraftsSettled(false);
    let cancelled = false;
    api
      .getHookCtaProjects(profileId)
      .then((data) => {
        if (!cancelled) {
          const rows = data.projects || [];
          setDrafts(rows);
          setDraftsFor(profileId);
          setDraftsSettled(true);
          // A plain visit opens FRESH (ADR 0262, superseding the
          // reopen ADR 0246 added): Kasra's page kept landing on his
          // last draft — its hook in the editor, its picks set, its
          // finished render standing in the frame — "the fucking
          // shit is still fucking showing here from before. It
          // didn't clear out." So no worked draft is ever adopted
          // here: the only row a visit may stand on is a completely
          // untouched one, which reads exactly like the new draft
          // it is, and when none exists the create effect below
          // mints the canvas instead. Worked drafts open only on
          // their own click in the list below, or by a ?project=
          // link, which names its draft and wins. A draft already
          // open is never swapped under the founder.
          if (!requestedProjectId && !projectRef.current) {
            const fresh = rows.find(isUntouchedHookCtaDraft);
            if (fresh) adoptOpenedDraft(fresh);
          }
        }
      })
      .catch(() => {
        // The list is a convenience beside the pickers, not the
        // page's load: a failed read empties it quietly rather than
        // failing the page over a sidebar.
        if (!cancelled) {
          setDrafts([]);
          setDraftsFor(profileId);
          setDraftsSettled(true);
        }
      });
    return () => {
      cancelled = true;
    };
  }, [profileId, openProjectId, requestedProjectId, adoptOpenedDraft]);

  // Make sure a draft exists without the founder having to ask, the
  // wizard's ensureProject rule: as soon as an app is chosen, the
  // draft is created in the background. A draft calls no model, so
  // doing this eagerly costs nothing. It waits for the drafts read
  // above to settle for THIS app, and it stands down when that read
  // found a completely untouched draft: the read adopts that row as
  // the visit's blank canvas (ADR 0262), and creating anyway would
  // mint a duplicate empty beside it — creating first and asking
  // later is how every visit used to mint one (ADR 0246). Worked
  // drafts in the list do NOT stand it down: a fresh visit beside
  // them mints its one canvas, and the next visit reuses that row.
  const creatingKeyRef = useRef("");
  useEffect(() => {
    if (!profileId || project) return undefined;
    if (!draftsSettled || draftsFor !== profileId || drafts.some(isUntouchedHookCtaDraft)) {
      return undefined;
    }
    const key = profileId;
    if (creatingKeyRef.current === key) return undefined;
    creatingKeyRef.current = key;
    let cancelled = false;
    (async () => {
      try {
        const created = await api.createHookCtaProject({
          brand_profile_id: profileId,
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
      // Unlatch this flight's key: if the pick changed mid-flight and
      // changes back, the page must be able to create again rather
      // than sit on a key whose draft it never adopted.
      if (creatingKeyRef.current === key) creatingKeyRef.current = "";
    };
  }, [profileId, project, draftsSettled, draftsFor, drafts]);

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
  // the render panel writes it, the finish step and the post kit
  // read it, the same shape Create Video keeps.
  const [generation, setGeneration] = useState(null);
  useEffect(() => {
    setGeneration(null);
  }, [openProjectId]);

  // The picked app's full profile, read for its outcome lines: the
  // profiles list is a trimmed picker projection without them, so
  // the focus pick's options (ADR 0247) come from this detail read.
  // A failed read leaves the focus on the app's choice — the tone
  // and shape picks do not depend on it — rather than failing the
  // page over one control's options (the drafts read's rule).
  const [profileDetail, setProfileDetail] = useState(null);
  useEffect(() => {
    setProfileDetail(null);
    if (!profileId) return undefined;
    let cancelled = false;
    (async () => {
      try {
        const detail = await api.getAppProfile(profileId);
        if (!cancelled) setProfileDetail(detail);
      } catch {
        if (!cancelled) setProfileDetail(null);
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [profileId]);
  const focusOptions = profileOutcomeLines(profileDetail);

  // A steering pick changed while a hook is on file (ADR 0247): the
  // line predates the picks until the founder regenerates it
  // themselves — a pick never regenerates on its own.
  const [picksStale, setPicksStale] = useState(false);
  useEffect(() => {
    setPicksStale(false);
  }, [openProjectId]);

  // Direction, through the wizard's own hook: the same option reads,
  // the same dispatch shape — the hook only ever dispatches on a
  // pick, never on load, so opening a draft cannot rewrite its
  // direction. The camera is not a pick on this page (ADR 0252):
  // every hook here shoots handheld selfie, so the hook is handed
  // the literal and the fixed-camera indoor rule (ADRs 0219/0233)
  // never engages — the location list is the full handheld set, a
  // stored "fixed" value on an older draft changes nothing here,
  // and the submit forces handheld again on the server side.
  const dispatchDraft = useCallback((action) => dispatch(action), []);
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
    cameraSetup: "handheld",
  });

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

  // The hook, on its click only (ADR 0122): pending edits are
  // flushed first so the hook is written from the saved direction
  // and length, then the returned row is adopted whole — it carries
  // the line and the strategy the render reads.
  const [hookBusy, setHookBusy] = useState(false);
  const [hookError, setHookError] = useState(null);
  const generateHook = async () => {
    if (!project || hookBusy) return;
    setHookBusy(true);
    setHookError(null);
    try {
      await savePicksRef.current?.();
      const hooked = await api.generateHookLine(project.id, {
        frame_seconds: Number(editValue("duration_seconds", 0)) || undefined,
      });
      dispatch({ type: "project-received", project: hooked });
      setPicksStale(false);
      setSaveStatus("All changes saved");
    } catch (err) {
      setHookError(getErrorMessage(err));
    } finally {
      setHookBusy(false);
    }
  };

  const { approved, unapproved } = partitionProfiles(profiles);
  // The Hook + CTA tour's first-run state (ADR 0244, on ADR 0118's
  // fork-page rule): the page has loaded, an approved app is picked,
  // no draft is open or created yet, and the app's draft list has
  // settled empty — the founder has not made a hook. A page with
  // drafts, an open draft, or a read still in flight never offers it.
  useTourEligibility(
    "hook-cta",
    loadState === "ready" && approved.length > 0 && !project && draftsSettled && drafts.length === 0
  );
  const hasHook = Boolean(String(editValue("hook_line")).trim());
  const hookFinished = generation?.status === "completed";
  // The steering picks (ADR 0247) ride the same draft edits as every
  // other pick on the page; changing one over a written hook marks
  // the line as predating them — the note in the picks control says
  // so, and nothing rewrites the line until the founder presses the
  // one hook button (Suggest a clearer hook, ADR 0249).
  const changePick = (field, value, options = {}) => {
    if (hasHook) setPicksStale(true);
    editField(field, value, options);
  };

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Zap}
        title="Hook + CTA"
        description="A short hook that flows straight into your demo and call to action."
        data-testid="hook-cta-header"
      />

      {error && (
        <p role="alert" className="text-sm text-destructive-text" data-testid="hook-cta-error">
          {error}
        </p>
      )}

      {loadState === "loading" && (
        <div className="surface" role="status" aria-label="Loading Hook + CTA" data-testid="hook-cta-loading">
          <div className="space-y-3">
            <Skeleton className="h-4 w-1/3" />
            <Skeleton className="h-10 w-full rounded-xl" />
            <Skeleton className="h-24 w-full rounded-xl" />
          </div>
          <span className="sr-only">Loading…</span>
        </div>
      )}

      {loadState === "failed" && (
        <div className="surface space-y-4" data-testid="hook-cta-load-failed">
          <p role="alert" className="text-sm text-destructive-text">
            {loadError || "Hook + CTA could not load."}
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
          <SectionCard title="Choose an app" icon={Briefcase} data-testid="hook-cta-setup-card">
            <div className="space-y-4">
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Pick an approved app to start a fresh hook.
              </p>
              <AppPicker
                profiles={approved}
                value={profileId}
                onChange={selectProfile}
                placeholder="Choose an app"
                testId="hook-cta-app-picker"
              />
              {unapproved.length > 0 && (
                <div className="inset-panel" data-testid="hook-cta-unapproved-panel">
                  <div className="flex items-start gap-2">
                    <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0 text-muted-foreground" />
                    <div className="min-w-0 flex-1">
                      <p className="text-base font-semibold">
                        {describeUnapprovedCount(unapproved.length)}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground" data-subtitle="">
                        Approve draft profiles first so they can generate hooks.
                      </p>
                      <Button variant="secondary" size="sm" asChild className="mt-3">
                        <Link to="/brand">Review in App Profile</Link>
                      </Button>
                    </div>
                  </div>
                </div>
              )}
            </div>

            {(project || saveStatus) && (
              <p
                role="status"
                data-testid="hook-cta-autosave-status"
                className="text-sm text-muted-foreground"
              >
                {saveStatus}
              </p>
            )}
          </SectionCard>

          {project && (
            <SectionCard title="Place and wardrobe" icon={Compass} data-testid="hook-cta-direction-card">
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  Place and wardrobe — the hook is written from these picks.
                </p>

                {/* The voice pick sits with the direction controls it
                    belongs with (ADR 0246): the character talks, or
                    stays silent and TikTok's text-to-speech carries
                    the line instead. */}
                <VoiceModeControl
                  value={editValue("voice_mode", "silent")}
                  onChange={(value) => editField("voice_mode", value, { omitDefault: true, fallback: "silent" })}
                  silentText={String(editValue("hook_line", "") || "").trim()}
                  silentTextName="the hook line"
                />

                <DirectionSelect
                  id="hook-cta-location-direction"
                  testId="hook-cta-location-direction"
                  label="Location"
                  value={dirSel.location}
                  onPick={pickScenePart("location")}
                  options={directionOptions?.location}
                  placeholder="Choose a Location…"
                  refresh={directionRefreshProps("location", "hook-cta-location-refresh")}
                />
                <DirectionSelect
                  id="hook-cta-wardrobe"
                  testId="hook-cta-wardrobe"
                  label="Wardrobe"
                  value={dirSel.wardrobe}
                  onPick={pickScenePart("wardrobe")}
                  options={directionOptions?.wardrobe}
                  placeholder="Choose wardrobe…"
                  refresh={directionRefreshProps("wardrobe", "hook-cta-wardrobe-refresh")}
                />
                {project?.visual_direction && !edits.visual_direction && (
                  <p className="text-sm text-muted-foreground">
                    Plan default: {sentenceCase(project.visual_direction)}
                  </p>
                )}
                <p className="text-sm text-muted-foreground">
                  Location and wardrobe apply together in the hook written from them. Lighting
                  is set from this hook&apos;s scene.
                </p>
                {directionRefreshError && (
                  <p role="alert" data-testid="hook-cta-direction-refresh-error" className="text-sm text-destructive-text">
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
                  onProjectChanged={(updated) => dispatch({ type: "project-received", project: updated || project })}
                  onRefreshProject={refreshProject}
                />
              </div>
            </SectionCard>
          )}

          {project && (
            <SectionCard title="The hook" icon={PenLine} data-testid="hook-cta-hook-card">
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  One line, written from your app and the direction you set.
                </p>
                <div className="space-y-2">
                  <label htmlFor="hook-cta-frame-length" className="text-sm font-semibold">Hook length</label>
                  <AppSelect
                    id="hook-cta-frame-length"
                    testId="hook-cta-frame-length"
                    block
                    value={String(editValue("duration_seconds", 5))}
                    onChange={(value) =>
                      editField("duration_seconds", Number(value), { omitDefault: true })
                    }
                    className={CONTROL_CLASS}
                    options={HOOK_FRAME_SECONDS.map((seconds) => ({
                      value: String(seconds),
                      label: `${seconds} seconds`,
                    }))}
                  />
                </div>
                {/* The steering picks (ADR 0247) stand above the
                    generate action they steer: the focus, tone and
                    shape the hook is written with, each defaulting
                    to the app's own choice. */}
                <HookPicksControl
                  focusOptions={focusOptions}
                  focus={editValue("hook_focus", "")}
                  onFocusChange={(value) => changePick("hook_focus", value, { omitDefault: true, fallback: "" })}
                  tone={editValue("tone", "")}
                  onToneChange={(value) => changePick("tone", value, { omitDefault: true, fallback: "" })}
                  shape={editValue("hook_shape", "auto")}
                  onShapeChange={(value) => changePick("hook_shape", value, { omitDefault: true, fallback: "auto" })}
                  stale={picksStale && hasHook}
                />
              </div>

              {/* The spoken line area (ADR 0254): the label, the line
                  itself and the card's one hook button at the area's
                  foot, in that order in BOTH states. Kasra ruled the
                  button refines the line, so it stands inside this
                  area under the editor — it used to render ahead of
                  the area, above the line it refines. The area
                  stands before a line exists too: the editor renders
                  gracefully empty (a labelled field, no checks or
                  warnings of its own), so the order — line first,
                  button under it — holds from the first visit and
                  the control never changes home. */}
              <div className="space-y-4" data-testid="hook-editors">
                <GroupLabel icon={AudioLines}>The spoken line</GroupLabel>
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  The hook line, checked as you edit — sharpen it if you like.
                </p>

                <HookLineEditor
                  projectId={project.id}
                  value={editValue("hook_line")}
                  onChange={(next) => editField("hook_line", next)}
                  clipLabel="short hook clip"
                  suggestClearerHook={false}
                />

                {/* The card's ONE hook button (ADR 0249): before a
                    line exists it is Generate the hook, driving the
                    generation flow from the picks above; once a line
                    exists the same control is Suggest a clearer hook,
                    the suggestion offered beside the founder's words
                    and written only on accept. There is no second
                    regenerate button — Kasra tested both and kept the
                    suggestion as the one control. The editor above
                    mounts without its own rewrite, so the suggestion
                    stands exactly once in the card. The generate busy
                    state is plain: no countdown rides this wait
                    (Kasra's order) — the plan and angle countdowns
                    elsewhere keep theirs. */}
                <div className="space-y-2">
                  {hasHook ? (
                    <LineRewriteAction
                      projectId={project.id}
                      line={editValue("hook_line")}
                      role="hook"
                      onAccept={(next) => editField("hook_line", next)}
                      testIdPrefix="hook-rewrite"
                      buttonLabel="Suggest a clearer hook"
                      busyLabel="Writing hook"
                    />
                  ) : (
                    <Button
                      variant="accent"
                      onClick={generateHook}
                      disabled={hookBusy}
                      busy={hookBusy}
                      data-testid="hook-generate"
                    >
                      <Sparkles className="h-4 w-4" />
                      {hookBusy ? "Writing the hook" : "Generate the hook"}
                    </Button>
                  )}
                  {hookError && (
                    <p role="alert" className="text-sm text-destructive-text" data-testid="hook-generate-error">
                      {hookError}
                    </p>
                  )}
                </div>
              </div>
            </SectionCard>
          )}

          {project && (
            <SectionCard title="Render the hook" icon={Clapperboard} data-testid="hook-cta-render-card">
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  One press renders the finished hook at its picked length.
                </p>
                <HookRenderPanel
                  project={{
                    ...project,
                    duration_seconds: editValue("duration_seconds", project.duration_seconds),
                    voice_mode: editValue("voice_mode", project.voice_mode || "silent"),
                  }}
                  generation={generation}
                  onGenerationChange={setGeneration}
                  hasUnsavedEdits={hasEdits}
                  autosaving={autosaving}
                />
              </div>
            </SectionCard>
          )}

          {project && (
            <SectionCard title="Demo + CTA" icon={Film} data-testid="hook-cta-finish-card">
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  Your demo and call to action, joined onto the hook&apos;s end.
                </p>
                {hookFinished ? (
                  <>
                    <DemoCtaGenerationEditor key={generation.id} generationId={generation.id} />
                    <p className="text-sm text-muted-foreground">
                      The export is saved beside the hook in History, ready to post as one
                      video — hook first, then your demo and call to action.
                    </p>
                  </>
                ) : (
                  <p className="text-sm text-muted-foreground">
                    Render the hook above first — the demo and call to action are joined
                    onto the finished hook here, and the combined video is what you post.
                  </p>
                )}
              </div>
            </SectionCard>
          )}

          {project && (
            <SectionCard title="Post kit" icon={Share2} data-testid="hook-cta-post-kit">
              <div className="space-y-4">
                <p className="text-sm text-muted-foreground" data-subtitle="">
                  The caption and hashtags for posting the finished video.
                </p>
                {hookFinished ? (
                  generation.post_kit ? (
                    <PostKitSection
                      postKit={generation.post_kit}
                      generationId={generation.id}
                      ttsText={
                        editValue("voice_mode", "silent") === "silent"
                          ? String(editValue("hook_line", "") || "").trim()
                          : ""
                      }
                      onUpdated={(kit) =>
                        setGeneration((current) =>
                          current ? { ...current, post_kit: kit } : current
                        )
                      }
                    />
                  ) : (
                    <p role="status" className="text-sm text-muted-foreground">
                      The hook is finished — its post copy is being written and will appear
                      here in a moment.
                    </p>
                  )
                ) : (
                  <p className="text-sm text-muted-foreground">
                    The post kit is written when the hook finishes rendering — the same
                    caption and hashtags the render carries in History.
                  </p>
                )}
              </div>
            </SectionCard>
          )}

          {drafts.length > 0 && (
            <SectionCard title="Hook + CTA drafts for this app" icon={HistoryIcon} data-testid="hook-cta-drafts-card">
              <p className="text-sm text-muted-foreground" data-subtitle="">
                Open a draft to keep working on the hook you started here.
              </p>
              <div className="space-y-2">
                {drafts.map((row) => {
                  const isCurrent = project?.id === row.id;
                  const body = (
                    <>
                      <div className="flex items-center justify-between gap-2">
                        <span className="font-display text-sm font-semibold">
                          Hook + CTA draft
                        </span>
                        {isCurrent && (
                          <span className="text-xs font-semibold text-[color:var(--brand-indigo)]">
                            Open now
                          </span>
                        )}
                      </div>
                      {/* A draft is told apart by its own hook line
                          (ADR 0242's pattern): length and date made
                          two drafts read as the same draft twice. A
                          draft with no hook yet says so. */}
                      <p className="mt-1 text-sm text-muted-foreground">
                        {String(row.hook_line || "").trim()
                          ? String(row.hook_line).trim()
                          : "No hook yet"}
                      </p>
                      <p className="mt-1 text-sm text-muted-foreground">
                        {row.duration_seconds}s hook · Updated{" "}
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
                      data-testid={`hook-cta-draft-${row.id}`}
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
                      data-testid={`hook-cta-draft-${row.id}`}
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
