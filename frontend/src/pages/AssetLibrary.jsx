import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import EmptyState from "../components/EmptyState";
import { SectionCard } from "../components/SectionCard";
import { AppPicker } from "../components/AppPicker";
import { Skeleton } from "../components/ui/skeleton";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import { FactChip, FactList } from "../components/FactChip";
import { resolveActiveProfileId, profileLabel, partitionProfiles } from "../lib/profileSelection";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import {
  Images, Loader2, AlertTriangle, Upload, Trash2, Archive, ArchiveRestore,
  ShieldCheck, Paperclip, UserRound, Music, Link2, Check, ImageOff, X, Info,
} from "lucide-react";

// Face-only product: the character reference is the single permitted upload.
// It is the only kind passed to the video model as an identity reference —
// the face the video is generated from. Rows of retired kinds can still sit
// in the library from before; they can be archived or deleted here but never
// attached again.
//
// Uploads are therefore unconditional rather than chosen. This used to be a
// one-option <select>: a dropdown whose only possible answer was the only
// possible value, which read as a choice the founder had to get right and
// changed nothing. The kind is now sent as a constant.
const UPLOAD_KIND = "character_reference";

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatSeconds(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  return `${seconds % 1 === 0 ? seconds : seconds.toFixed(1)}s`;
}

/**
 * An asset's thumbnail, which degrades instead of breaking.
 *
 * A failed image load paints the ALT TEXT across the frame, so a photo whose
 * `media_url` 404s rendered its own filename spilling out of a 56px box — which
 * reads as a layout bug rather than a missing file, and hides the real cause.
 * `onError` swaps in a neutral placeholder that keeps the box's exact shape, so
 * a broken source looks broken on purpose and the name stays where it belongs,
 * in the row's text.
 */
function AssetThumb({ asset, isVideo, isAudio }) {
  const [failed, setFailed] = useState(false);
  const src = asset.media_url;
  useEffect(() => {
    setFailed(false);
  }, [src]);
  return (
    <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-secondary/40">
      {!src ? null : failed || isAudio ? (
        <div
          className="flex h-full w-full items-center justify-center text-muted-foreground"
          aria-hidden="true"
        >
          {isAudio ? <Music className="h-5 w-5" /> : <ImageOff className="h-5 w-5" />}
        </div>
      ) : isVideo ? (
        <video src={mediaUrl(src)} className="h-full w-full object-cover" muted />
      ) : (
        <img
          src={mediaUrl(src)}
          alt={asset.label || asset.name || asset.kind}
          className="h-full w-full object-cover"
          loading="lazy"
          onError={() => setFailed(true)}
        />
      )}
    </div>
  );
}

/**
 * The photograph a draft uses, when the library cannot describe it.
 *
 * The draft's own attachment list is the authority on whether a photo is
 * attached — it is what the render will actually use. The library row is only a
 * richer view of the same file, and it is not always available: the list can be
 * empty, still loading, or the asset can have been archived since it was
 * attached. Promoting the library row alone therefore made the section claim no
 * photo was attached while one demonstrably was, which is worse than showing less
 * detail. So when the file cannot be described, the attachment itself is still
 * reported — name, what it is used for, and the control that detaches it.
 */
function AttachedReference({ attachment, onDetach, busy }) {
  const name = attachment.label || String(attachment.asset_id || "").slice(0, 8);
  return (
    <div className="flex flex-wrap items-center gap-3 rounded-xl border border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] p-5">
      <span className="min-w-0 flex-1 truncate text-sm font-semibold">{name}</span>
      <span className="shrink-0 text-xs text-muted-foreground">Used for the whole video</span>
      {onDetach && (
        <Button
          variant="ghost"
          size="sm"
          disabled={busy}
          onClick={() => onDetach({ id: attachment.asset_id, label: name, kind: attachment.kind })}
          title="Stops using this photo for the video you are building"
        >
          <X className="h-3.5 w-3.5" /> Remove
        </Button>
      )}
    </div>
  );
}

function AssetRow({
  asset,
  onDelete,
  onArchive,
  onAttach,
  onDetach,
  embedded = false,
  projectId,
  attached,
  attachDisabled,
  attachBusy,
  busy,
}) {
  const isVideo = asset.kind === "screen_recording" || asset.kind === "background_video";
  const isAudio = asset.kind === "audio";
  // Rows of retired kinds still render — archive and delete stay available so
  // the library can be cleaned — but they can never be attached again.
  const isRetired = asset.kind !== "character_reference";
  const uses = asset.used_in || [];
  const attachable = Boolean(projectId && onAttach);
  const usable = attachable && asset.status === "active" && asset.rights_confirmed;
  // "Attach" named the mechanism, not the outcome: nothing on screen said what
  // attaching did, so the button read as a mystery action. It links this
  // photograph to the draft the founder is working on, which is what the studio
  // needs and what the section is for.
  //
  // It is also hidden, not merely disabled, when the draft already holds a
  // face. Embedded in the wizard an upload attaches itself (see handleUpload),
  // so on the row that matters this button was a second route to something the
  // app had already done — and a permanently disabled control invites the
  // question of what went wrong.
  const slotHeldByAnother = attachDisabled && !busy && asset.kind === "character_reference";
  return (
    <div className="inset-panel space-y-2">
      <div className="flex items-center gap-3">
        <AssetThumb asset={asset} isVideo={isVideo} isAudio={isAudio} />
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2">
            <span className="truncate text-sm font-semibold">
              {asset.label || asset.name || humanize(asset.kind)}
            </span>
            {asset.status === "archived" && (
              <Badge variant="outline" className="text-xs">Archived</Badge>
            )}
            {!asset.rights_confirmed && (
              <Badge variant="outline" className="text-xs">Rights unconfirmed</Badge>
            )}
            {/* Pre-flight face check, counted at upload time. A photo with no
                detectable face — or several competing ones — is what the
                video provider's privacy filter refuses at generation time. */}
            {asset.face_count === 0 && (
              <Badge variant="outline" className="text-xs">No face detected — may be refused</Badge>
            )}
            {Number(asset.face_count) >= 2 && (
              <Badge variant="outline" className="text-xs">
                Faces detected: {asset.face_count} — may be flagged
              </Badge>
            )}
            {/* The embedded row states it beside Remove instead, so the
                same attached photo never claims it twice. */}
            {attachable && attached && !embedded && (
              <Badge variant="outline" className="text-xs">
                <Check className="mr-1 h-3 w-3" /> Attached
              </Badge>
            )}
          </div>
          {asset.notes && <p className="mt-0.5 text-xs text-muted-foreground">{asset.notes}</p>}
          {/* Facts as chips, not a middot sentence. The badges above are status
              ("Archived", "Rights unconfirmed") and stay badges; a date and a
              duration are measurements, and this is the same vocabulary the
              generation row uses for them. */}
          {(asset.created_at || asset.duration_seconds) && (
            <FactList className="mt-1">
              {asset.created_at ? (
                <FactChip>Uploaded {new Date(asset.created_at).toLocaleDateString()}</FactChip>
              ) : null}
              {asset.duration_seconds ? (
                <FactChip>{formatSeconds(asset.duration_seconds)}</FactChip>
              ) : null}
            </FactList>
          )}
          <UsageHistory uses={uses} />
        </div>
        <div className="flex shrink-0 gap-1">
          {attachable && !isAudio && !isRetired && !attached && !slotHeldByAnother && (
            <Button
              variant="secondary"
              size="sm"
              disabled={!usable || attachDisabled || attachBusy || busy}
              title={
                asset.status !== "active"
                    ? "Restore this asset before using it."
                    : !asset.rights_confirmed
                      ? "Confirm rights before using this asset in a project."
                      : "Uses this photograph as the face for the video you are building"
              }
              onClick={() => onAttach(asset)}
            >
              <Link2 className="h-3.5 w-3.5" /> Use this photo
            </Button>
          )}
          {/* Detaching lives on the photograph itself, so the one card that says
              which photo this video uses is also where that photo is removed
              from the video. It used to be a second card further down the step
              with its own Remove, which meant the photo the founder was looking
              at and the control that changed it were never in the same place. */}
          {/* The attached state reads beside Remove, not up in the title:
              a green branded check to the left of the control that undoes it,
              so the photo that is on the video says so where it is removed. */}
          {embedded && attached && onDetach && (
            <>
              <span className="inline-flex shrink-0 items-center gap-1 text-xs font-semibold text-muted-foreground">
                <Check className="h-3.5 w-3.5 text-green-500" aria-hidden="true" /> Attached
              </span>
              <Button
                variant="ghost"
                size="sm"
                disabled={busy}
                onClick={() => onDetach(asset)}
                title="Stops using this photo for the video you are building"
              >
                <X className="h-3.5 w-3.5" /> Remove
              </Button>
            </>
          )}
          {/* Archive and Delete are held at the right edge with a gap before
              them, so they cannot be reached by muscle memory on the way to
              "Use this photo" — the same rule the generation card's action bar
              follows. No hairline here: this is a compact row in a list, and a
              divider between a one-line description and three small buttons
              repeated down the page reads as scaffolding rather than
              structure. The divider belongs on the card, not the row. */}
          <span className="ml-auto flex items-center gap-1 pl-2">
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => onArchive(asset)}
              aria-label={asset.status === "archived" ? "Restore asset" : "Archive asset"}
            >
              {asset.status === "archived" ? (
                <ArchiveRestore className="h-3.5 w-3.5" />
              ) : (
                <Archive className="h-3.5 w-3.5" />
              )}
            </Button>
            <Button
              variant="ghost"
              size="sm"
              disabled={busy}
              onClick={() => onDelete(asset)}
              aria-label="Delete asset"
            >
              <Trash2 className="h-3.5 w-3.5" />
            </Button>
          </span>
        </div>
      </div>
      {isAudio && asset.media_url && (
        <audio
          src={mediaUrl(asset.media_url)}
          controls
          preload="metadata"
          className="h-9 w-full"
          aria-label={`Preview ${asset.label || asset.name || "audio asset"}`}
        />
      )}
      {isRetired && (
        <p className="text-xs text-muted-foreground">
          Retired kind — uploads went face-only. Archive or delete it to clean up;
          it can no longer be attached to a project.
        </p>
      )}
      {attachable && !usable && !attached && (
        <p className="text-xs text-muted-foreground">
          {asset.status !== "active"
            ? "Restore this asset before attaching it."
            : "Confirm rights before attaching this asset to a project."}
        </p>
      )}
    </div>
  );
}

/**
 * Where this asset is already in use, on one line.
 *
 * This listed one project per row with its own status badge, so a single use
 * wrapped to three lines and the project name out-shouted the asset it
 * described. The names still drive the delete warning (which reads `used_in`
 * directly), so nothing is lost by rendering them inline and truncating.
 */
function UsageHistory({ uses }) {
  if (!uses.length) {
    return (
      <p className="mt-0.5 text-xs text-muted-foreground">Not used in any video yet</p>
    );
  }
  const names = uses.map((u) => u.name).filter(Boolean);
  return (
    <p className="mt-0.5 truncate text-xs text-muted-foreground">
      Used in {uses.length} project{uses.length === 1 ? "" : "s"}
      {names.length > 0 ? ` · ${names.join(", ")}` : ""}
    </p>
  );
}

export default function AssetLibrary({
  profileId,
  projectId,
  projectAssets,
  onProjectChanged,
  onChanged,
  /**
   * True when rendered inside the Create Video wizard, which already supplies
   * a step header ("Assets" + why assets matter) directly above. In that case
   * this component must not restate it: two headers saying the same thing is
   * the duplication you see stacked at the top of the step.
   */
  embedded = false,
}) {
  // Usable as a route (/app-profiles/:profileId/assets), embedded in the
  // wizard, which already knows which profile it is working on, or opened from
  // the sidebar at plain /assets — where nothing supplied a profile at all and
  // the page dead-ended. The standalone case resolves its own below.
  const params = useParams();
  const [searchParams, setSearchParams] = useSearchParams();
  const [profiles, setProfiles] = useState([]);
  const [rememberedId, setRememberedId] = useState(() => readCurrentAppId());

  const activeProfileId = resolveActiveProfileId({
    propId: profileId,
    paramId: params.profileId,
    queryId: searchParams.get("profile") || "",
    rememberedId,
    profiles,
  });

  const selectableProfiles = useMemo(
    () => (profiles.length > 0 ? profiles : activeProfileId ? [{ id: activeProfileId }] : []),
    [profiles, activeProfileId]
  );

  // The active profile as a record, when it is one we know about. Embedded in
  // the studio the profile list is deliberately not fetched, so this is null
  // there and the approval state is left to the wizard, which already gates on
  // it and would not have let the step render.
  const activeProfile = useMemo(
    () => profiles.find((p) => p.id === activeProfileId) || null,
    [profiles, activeProfileId]
  );

  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [label, setLabel] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [attachBusyId, setAttachBusyId] = useState("");
  const [showAllPhotos, setShowAllPhotos] = useState(false);
  const fileRef = useRef(null);
  const attachedIds = new Set(
    (projectAssets || []).map((a) => a?.asset_id).filter(Boolean)
  );
  // One project carries exactly one character reference: the server refuses a
  // render with two rather than guess which face is on camera. Offering a
  // second Attach button would only produce a 409 at the expensive moment, so
  // the control is disabled and says which photo already holds the slot.
  const attachedCharacterCount = (projectAssets || []).filter(
    (a) => a?.kind === "character_reference"
  ).length;
  const characterSlotTaken = attachedCharacterCount >= 1;

  // The one photograph this video renders from, and everything else.
  //
  // Embedded, the studio needs exactly one face, so the attached asset is the
  // subject of the section and the rest are a footnote. The founder's complaint
  // was that an upload appeared in one component and then "showed up" somewhere
  // else below it, so the photo and the control that manages it now sit in one
  // surface with the other assets behind a count. Standalone, the library is
  // genuinely a library of many assets, so nothing is collapsed there.
  const attachedAsset = embedded
    ? assets.find((a) => attachedIds.has(a.id) && a.kind === "character_reference") || null
    : null;
  const otherAssets = embedded
    ? assets.filter((a) => !(attachedIds.has(a.id) && a.kind === "character_reference"))
    : assets;
  // The attachment the draft itself reports. Preferred over anything derived
  // from the library list, which can be empty or lagging.
  const attachedReference =
    embedded && !attachedAsset
      ? (projectAssets || []).find((a) => a && a.kind === "character_reference") || null
      : null;

  const load = useCallback(async () => {
    if (!activeProfileId) return;
    setLoading(true);
    try {
      const data = await api.getAssets(activeProfileId, {
        include_archived: includeArchived || undefined,
      });
      setAssets(data.assets || []);
    } catch (err) {
      // A profile that no longer exists, or belongs to someone else, arrives as
      // a 404 with a bare "App Profile not found". On the standalone page the
      // founder can fix that by picking another app, so say so instead of
      // leaving a dead end. Embedded in the studio there is nothing to pick, so
      // the raw error is the honest thing to show.
      if (!embedded && err?.response?.status === 404) {
        setAssets([]);
        setError(
          "That app is no longer available. Pick one of your apps below to see its assets."
        );
      } else {
        setError(getErrorMessage(err));
      }
    } finally {
      setLoading(false);
    }
  }, [activeProfileId, includeArchived, embedded]);

  useEffect(() => {
    load();
  }, [load]);

  // The standalone page has to discover which apps exist, because the sidebar
  // link carries no profile. Only there: embedded in the studio the profile is
  // already known and this would be a wasted request on every step render.
  useEffect(() => {
    if (embedded) return;
    let cancelled = false;
    api
      .getAppProfiles()
      .then((d) => {
        if (!cancelled) setProfiles(d.profiles || []);
      })
      .catch(() => {
        // Leave the list empty; the page falls back to its empty state, which
        // now links to the editor rather than stranding anyone.
        if (!cancelled) setProfiles([]);
      });
    return () => {
      cancelled = true;
    };
  }, [embedded]);

  // Choosing an app here is the same choice the editor makes, so it is
  // remembered and becomes the default the next time /assets is opened with no
  // profile in the URL.
  const handleSwitchProfile = (nextId) => {
    setAssets([]);
    setError(null);
    setNotice(null);
    rememberCurrentAppId(nextId);
    setRememberedId(nextId);
    setSearchParams(nextId ? { profile: nextId } : {}, { replace: true });
  };

  const handleUpload = async (event) => {    const file = event.target.files?.[0];
    if (!file || !activeProfileId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      const form = new FormData();
      form.append("kind", UPLOAD_KIND);
      form.append("file", file);
      form.append("label", label);
      // The operator asserts they have the right to use this asset.
      form.append("rights_confirmed", "true");
      const created = await api.uploadAsset(activeProfileId, form);
      setLabel("");
      if (fileRef.current) fileRef.current.value = "";
      // Embedded in the wizard with an open draft that has no face yet, the
      // upload IS the intent — link it at once instead of demanding a second
      // click on Attach. Scoped tightly: embedded only, face kind only, and
      // never a replacement (a draft that already has a face is untouched, as
      // is the standalone library page, which has no draft at all).
      let attachedNote = "";
      const draftHasFace = (projectAssets || []).some(
        (a) => a && a.kind === "character_reference"
      );
      if (embedded && projectId && created && created.kind === "character_reference" && !draftHasFace) {
        try {
          await api.attachAsset(projectId, { asset_id: created.id });
          attachedNote = " It is attached to this draft.";
          onProjectChanged?.();
        } catch (attachErr) {
          // The upload itself succeeded, so this is additive: the photo is
          // in the library and can still be attached by hand.
          setError(getErrorMessage(attachErr));
        }
      }
      setNotice(`Added "${created.label || created.name}".${attachedNote}`);
// The server counts faces on upload and warns when the photo will not work
// as a reference -- no face at all, or a group shot. That warning used to die
// in the response object: the row badges only appear after the list reloads,
// and nothing at the moment of upload said the photo was wrong. It rides on
// the notice rather than the error because the upload itself succeeded; the
// 0-face case is still the one to read carefully, since the provider is
// likely to refuse a render built on it and that refusal costs an attempt.
      if (created?.face_warning) {
        setNotice((current) => `${current || ""} ${created.face_warning}`.trim());
      }
      load();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  // No options. The old builder forwarded start/end/audio_role/audio_gain from
  // the retired time-range controls; no caller set them and the server had
  // stopped reading them, so keeping the loop implied an attachment could carry
  // a trim or a mix that would be silently dropped.
  const handleAttach = async (asset) => {
    if (!projectId) return;
    setAttachBusyId(asset.id);
    setError(null);
    setNotice(null);
    try {
      await api.attachAsset(projectId, { asset_id: asset.id });
      setNotice(`Now using "${asset.label || asset.name || asset.kind}" for this video.`);
      await load();
      onProjectChanged?.();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAttachBusyId("");
    }
  };

  const handleDetach = async (asset) => {
    if (!projectId) return;
    setBusy(true);
    setError(null);
    setNotice(null);
    try {
      await api.detachAsset(projectId, asset.id);
      setNotice(`Removed "${asset.label || asset.name || asset.kind}" from this video.`);
      await load();
      onProjectChanged?.();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (asset) => {
    // Deleting the file does not rewrite the projects that referenced it, so
    // the founder is warned first: those projects lose their reference until
    // a new photograph is attached.
    const uses = asset.used_in || [];
    if (
      uses.length &&
      !window.confirm(
        `This asset is used in ${uses.length} project${uses.length === 1 ? "" : "s"} ` +
          `(${uses.map((u) => u.name).join(", ")}). Deleting it removes the face ` +
          `reference from those projects until a new one is attached. Delete anyway?`
      )
    ) {
      return;
    }
    setBusy(true);
    try {
      const result = await api.deleteAsset(asset.id);
      if (result?.note) setNotice(result.note);
      load();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleArchive = async (asset) => {
    setBusy(true);
    try {
      await api.updateAsset(asset.id, {
        status: asset.status === "archived" ? "active" : "archived",
      });
      load();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  if (!activeProfileId) {
    // This used to be a dead end: EmptyState accepts an action, and none was
    // passed, so the sidebar's Asset Library told you to choose an app and
    // offered no way to choose one. Two different causes need two different
    // next steps, so they are told apart rather than merged into one message.
    const { approved, unapproved } = partitionProfiles(profiles);
    const waiting = unapproved.length > 0;
    return (
      <PageFrame className="space-y-6">
        {!embedded && (
          <PageHeader
            data-testid="asset-library-header"
            icon={Images}
            title="Asset Library"
            description="Upload one presenter photo per app — the face on camera."
          />
        )}
        {loading ? (
          <Skeleton className="h-48 w-full rounded-2xl" aria-label="Loading your apps" />
        ) : profiles.length === 0 ? (
          <EmptyState
            icon={Images}
            title="No app yet"
            description="Assets belong to one App Profile and are used only in that app's videos. Create an app profile first, then add a photo of the person you want on camera."
            action={
              <Button variant="accent" asChild>
                <Link to="/brand">Set up your app</Link>
              </Button>
            }
          />
        ) : (
          <EmptyState
            icon={Images}
            title="Choose an App Profile"
            description={
              waiting
                ? `Assets belong to one app. You have ${approved.length} approved and ${unapproved.length} still waiting for approval. Select an app below to manage its photos.`
                : "Choose an app below to manage the presenter photos used in its videos."
            }
            action={
              <div className="flex flex-col items-center gap-2">
                {selectableProfiles.length > 1 ? (
                  <AppPicker
                    profiles={selectableProfiles}
                    value=""
                    onChange={handleSwitchProfile}
                    placeholder="Choose an app..."
                    showStatus
                    ariaLabel="Choose which app these assets belong to"
                    testId="asset-profile-picker"
                  />
                ) : (
                  <Button variant="accent" asChild>
                    <Link to={`/app-profiles/${selectableProfiles[0].id}`}>
                      Open {profileLabel(selectableProfiles[0])}
                    </Link>
                  </Button>
                )}
                {waiting && (
                  <p className="text-xs text-muted-foreground">
                    Approval is needed before a video can be generated, not before
                    you can upload visuals.
                  </p>
                )}
              </div>
            }
          />
        )}
      </PageFrame>
    );
  }

  return (
    <PageFrame className="space-y-6">
      {/* Only the standalone route owns a title. Embedded, the wizard step
          header above already says this. */}
      {!embedded && (
        <PageHeader
          data-testid="asset-library-header"
          icon={Images}
          title="Asset Library"
          description="Upload one presenter photo per app — the face on camera."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {/* Shown whenever there is something to switch between. With a
                  single app it would be a one-option menu, which is noise. */}
              {profiles.length > 1 && (
                <AppPicker
                  profiles={profiles}
                  value={activeProfileId}
                  onChange={handleSwitchProfile}
                  placeholder="Choose an app..."
                  showStatus
                  ariaLabel="Choose which app these assets belong to"
                  testId="asset-profile-picker"
                />
              )}
              {/* The approval state is stated here unconditionally, not left to
                  the picker. With exactly one app there is no picker, so this
                  line is the only place it can appear — and "here but not
                  approved" is precisely what someone checking for a missing
                  app needs to be able to see. */}
              {activeProfile && (
                <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  {profiles.length === 1 && <span>Assets for {profileLabel(activeProfile)}</span>}
                  {activeProfile.status === "approved" ? (
                    <Badge variant="outline" className="text-xs">Approved</Badge>
                  ) : (
                    <Badge variant="secondary" className="text-xs">Needs approval</Badge>
                  )}
                </span>
              )}
            </div>
          }
        />
      )}

      {/* Rights. A full Alert box for one sentence made the section read as a
          warning before it read as a photo control.

          The line now leads with what the photo is FOR rather than with the
          confirmation machinery behind it. "Upload the person you want on
          camera" is the answer to the question the founder actually has at
          this point in the step, and it is the one thing the upload cannot be
          used without. The compliance half stays, and it stays first — it is
          still a statement about what is allowed, not decoration. What was
          dropped is the storage detail: the per-upload confirmation and the
          per-App-Profile scoping are real and still enforced, but they read as
          a receipt rather than as an instruction, so they now live where the
          enforcement is visible instead: the "Rights unconfirmed" badge on an
          unconfirmed row, and the refusal to attach one to a project. */}
      <p
        className="flex items-center gap-2 text-xs text-muted-foreground"
        data-testid="asset-rights-alert"
      >
        <ShieldCheck className="h-3.5 w-3.5 shrink-0 text-[color:var(--brand-indigo)]" />
        Upload only an image you have the right to use.
      </p>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && (
        <Alert>
          <Info className="h-4 w-4 text-[color:var(--brand-indigo)]" />
          <AlertDescription>{notice}</AlertDescription>
        </Alert>
      )}

      {/* One surface: the upload control and the photograph it produces sit
          together, so an upload no longer appears to "turn up" in a separate
          component further down the step. */}
      <SectionCard
        title={embedded ? undefined : "Presenter photos"}
        icon={UserRound}
        description={embedded ? undefined : "A clear photo of the person you want on camera. It becomes the video's presenter reference."}
        data-testid="asset-upload-panel"
      >
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-[1fr_auto]">
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Optional label — for example: Founder photo"
            aria-label="Optional photo label"
          />
          <Button variant="accent" onClick={() => fileRef.current?.click()} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            {attachedAsset ? "Upload a different photo" : "Upload"}
          </Button>
        </div>
        <input
          ref={fileRef}
          type="file"
          className="hidden"
          accept="image/png,image/jpeg,image/webp,image/gif"
          onChange={handleUpload}
          aria-label="Asset file"
        />

        {/* The photograph this video renders from, in the same surface as the
            control that put it there. */}
        {attachedReference && (
          <div className="border-t border-[color:var(--hairline)] pt-4">
            <AttachedReference
              attachment={attachedReference}
              onDetach={handleDetach}
              busy={busy}
            />
          </div>
        )}
        {attachedAsset && (
          <div className="border-t border-[color:var(--hairline)] pt-4">
            <AssetRow
              asset={attachedAsset}
              onDelete={handleDelete}
              onArchive={handleArchive}
              onAttach={handleAttach}
              onDetach={handleDetach}
              embedded
              projectId={projectId}
              attached
              attachDisabled={busy || characterSlotTaken}
              attachBusy={attachBusyId === attachedAsset.id}
              busy={busy}
            />
          </div>
        )}

        {/* Everything else stays out of the way until it is asked for: the
            studio needs one face, and a wall of unused photographs read as
            more to do. */}
        {embedded && otherAssets.length > 0 && (
          <div className="border-t border-[color:var(--hairline)] pt-4">
            {!showAllPhotos ? (
              <Button
                variant="ghost"
                size="sm"
                onClick={() => setShowAllPhotos(true)}
              >
                {otherAssets.length} other photo{otherAssets.length === 1 ? "" : "s"}
              </Button>
            ) : (
              <div className="space-y-4">
                {otherAssets.map((a) => (
                  <AssetRow
                    key={a.id}
                    asset={a}
                    onDelete={handleDelete}
                    onArchive={handleArchive}
                    onAttach={handleAttach}
                    onDetach={handleDetach}
                    embedded
                    projectId={projectId}
                    attached={attachedIds.has(a.id)}
                    attachDisabled={busy || characterSlotTaken}
                    attachBusy={attachBusyId === a.id}
                    busy={busy}
                  />
                ))}
              </div>
            )}
          </div>
        )}

        {!embedded && (
          <div className="flex flex-wrap items-center justify-between gap-2 border-t border-[color:var(--hairline)] pt-4">
            <span className="text-xs text-muted-foreground">
              {assets.length} asset{assets.length === 1 ? "" : "s"}
            </span>
            <Button
              variant="ghost"
              size="sm"
              onClick={() => setIncludeArchived((v) => !v)}
              aria-pressed={includeArchived}
            >
              <Paperclip className="h-3.5 w-3.5" />
              {includeArchived ? "Hide archived" : "Show archived"}
            </Button>
          </div>
        )}
      </SectionCard>

      <div data-testid="asset-list">
      {loading ? (
        <div className="space-y-4" aria-label="Loading assets">
          <Skeleton className="h-20 w-full rounded-xl" />
          <Skeleton className="h-20 w-full rounded-xl" />
        </div>
      ) : assets.length === 0 ? (
        // Nothing here. This was a line telling an embedded reader to press the
        // Upload button sitting directly above it, which is a pointer to a
        // control they can already see, next to an input they can already type
        // into. On the standalone route the equivalent line earns its place —
        // it says what the photo is for — so that branch stays.
        embedded ? null : (
          <p className="text-sm text-muted-foreground">
            No photos yet. In Create Video, an uploaded photo attaches to your draft and guides its presenter.
          </p>
        )
      ) : embedded ? (
        // Already rendered above, inside the upload surface, so it is not
        // repeated here. The empty case above is the only copy the section
        // shows when there is nothing attached yet.
        null
      ) : (
        <div className="space-y-4">
          {assets.map((a) => (
            <AssetRow
              key={a.id}
              asset={a}
              onDelete={handleDelete}
              onArchive={handleArchive}
              onAttach={handleAttach}
              onDetach={handleDetach}
              projectId={projectId}
              attached={attachedIds.has(a.id)}
              attachDisabled={busy || (characterSlotTaken && a.kind === "character_reference")}
              attachBusy={attachBusyId === a.id}
              busy={busy}
            />
          ))}
        </div>
      )}
      </div>
    </PageFrame>
  );
}
