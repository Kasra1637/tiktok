import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { Link, useParams, useSearchParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import { resolveActiveProfileId, profileLabel, partitionProfiles } from "../lib/profileSelection";
import { readCurrentAppId, rememberCurrentAppId } from "../lib/currentApp";
import {
  Images, Loader2, AlertTriangle, Upload, Trash2, Archive, ArchiveRestore,
  ShieldCheck, Paperclip, Music, Link2, Check,
} from "lucide-react";

// Face-only product: the character reference is the single permitted upload.
// It is the only kind passed to the video model as an identity reference —
// the face the video is generated from. Rows of retired kinds can still sit
// in the library from before; they can be archived or deleted here but never
// attached again.
const KINDS = [
  ["character_reference", "Character reference — the person on camera"],
];

/** What the upload is for, shown under the upload control. */
const KIND_PURPOSE = {
  character_reference:
    "This is the face the model is given. Every video is generated from it: the person on camera is the person in this photograph, and the scene around them is invented from the App Profile.",
};

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function formatSeconds(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  return `${seconds % 1 === 0 ? seconds : seconds.toFixed(1)}s`;
}

function AssetRow({
  asset,
  onDelete,
  onArchive,
  onAttach,
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
  return (
    <div className="space-y-2 rounded-xl border border-[color:var(--hairline)] p-3">
      <div className="flex items-center gap-3">
        <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-secondary/40">
          {asset.media_url ? (
            isVideo ? (
              <video src={mediaUrl(asset.media_url)} className="h-full w-full object-cover" muted />
            ) : isAudio ? (
              <div className="flex h-full w-full items-center justify-center" aria-hidden="true">
                <Music className="h-5 w-5 text-muted-foreground" />
              </div>
            ) : (
              <img
                src={mediaUrl(asset.media_url)}
                alt={asset.label || asset.name || asset.kind}
                className="h-full w-full object-cover"
              />
            )
          ) : null}
        </div>
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-1.5">
            <span className="truncate text-sm font-medium">
              {asset.label || asset.name || humanize(asset.kind)}
            </span>
            <Badge variant="secondary" className="text-[11px]">{humanize(asset.kind)}</Badge>
            {asset.status === "archived" && (
              <Badge variant="outline" className="text-[11px]">Archived</Badge>
            )}
            {!asset.rights_confirmed && (
              <Badge variant="outline" className="text-[11px]">Rights unconfirmed</Badge>
            )}
            {/* Pre-flight face check, counted at upload time. A photo with no
                detectable face — or several competing ones — is what the
                video provider's privacy filter refuses at generation time. */}
            {asset.face_count === 0 && (
              <Badge variant="outline" className="text-[11px]">No face detected — may be refused</Badge>
            )}
            {Number(asset.face_count) >= 2 && (
              <Badge variant="outline" className="text-[11px]">
                {asset.face_count} faces — may be flagged
              </Badge>
            )}
            {attachable && attached && (
              <Badge variant="outline" className="text-[11px]">
                <Check className="mr-1 h-3 w-3" /> Attached
              </Badge>
            )}
          </div>
          {asset.notes && <p className="mt-0.5 text-xs text-muted-foreground">{asset.notes}</p>}
          {(asset.created_at || asset.duration_seconds) && (
            <p className="mt-0.5 text-xs text-muted-foreground">
              {asset.created_at ? `Uploaded ${new Date(asset.created_at).toLocaleDateString()}` : ""}
              {asset.created_at && asset.duration_seconds ? " · " : ""}
              {asset.duration_seconds ? `Duration ${formatSeconds(asset.duration_seconds)}` : ""}
            </p>
          )}
          <UsageHistory uses={uses} />
        </div>
        <div className="flex shrink-0 gap-1">
          {attachable && !isAudio && !isRetired && !attached && (
            <Button
              variant="secondary"
              size="sm"
              disabled={!usable || attachDisabled || attachBusy || busy}
              title={
                attachDisabled && !busy && asset.kind === "character_reference"
                  ? "This project already has the character reference it will render from. Detach that one first."
                  : asset.status !== "active"
                    ? "Restore this asset before attaching it."
                    : !asset.rights_confirmed
                      ? "Confirm rights before using this asset in a project."
                      : "Attach this asset to the current project"
              }
              onClick={() => onAttach(asset)}
            >
              <Link2 className="h-3.5 w-3.5" /> Attach
            </Button>
          )}
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

function UsageHistory({ uses }) {
  if (!uses.length) {
    return (
      <p className="mt-0.5 text-xs text-muted-foreground">Not used in any project yet</p>
    );
  }
  return (
    <div className="mt-1">
      <p className="text-xs text-muted-foreground">
        Used in {uses.length} project{uses.length === 1 ? "" : "s"}:
      </p>
      <ul className="mt-0.5 space-y-0.5">
        {uses.map((use) => (
          <li key={use.studio_project_id} className="flex items-center gap-1.5 text-xs">
            <span className="truncate text-muted-foreground">{use.name}</span>
            <Badge variant="outline" className="shrink-0 text-[10px]">
              {humanize(use.status)}
            </Badge>
          </li>
        ))}
      </ul>
    </div>
  );
}

/**
 * Which app's assets are on screen. The sidebar's Asset Library link carries no
 * profile, so without this the page could not answer that question at all.
 *
 * Every option shows its approval state. Someone looking for a missing app needs
 * to be able to tell "this one is here but not approved yet" from "this one is
 * gone" at a glance, which a bare list of names cannot do.
 */
function ProfilePicker({ profiles, value, onChange }) {
  return (
    <select
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      aria-label="Choose which app these assets belong to"
      data-testid="asset-profile-picker"
      className="rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 py-2 text-sm font-medium"
    >
      <option value="" disabled>
        Choose an app...
      </option>
      {profiles.map((p) => (
        <option key={p.id} value={p.id}>
          {profileLabel(p)}
          {p.status === "approved" ? "" : " (needs approval)"}
        </option>
      ))}
    </select>
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
  const [kind, setKind] = useState("character_reference");
  const [label, setLabel] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const [attachBusyId, setAttachBusyId] = useState("");
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
      form.append("kind", kind);
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
      setNotice(`Added ${humanize(created.kind)} "${created.label || created.name}".${attachedNote}`);
// The server counts faces on upload and warns when the photo will not work
// as a reference -- no face at all, or a group shot. That warning used to die
// in the response object: the row badges only appear after the list reloads,
// and nothing at the moment of upload said the photo was wrong. It rides on
// the notice rather than the error because the upload itself succeeded; the
// 0-face case is still the one to read carefully, since the provider is
// likely to refuse a render built on it and that refusal costs a paid attempt.
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
      setNotice(`Attached ${humanize(asset.kind)} "${asset.label || asset.name || asset.kind}".`);
      await load();
      onProjectChanged?.();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAttachBusyId("");
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

  const counts = useMemo(() => {
    const map = {};
    assets.forEach((a) => {
      map[a.kind] = (map[a.kind] || 0) + 1;
    });
    return map;
  }, [assets]);

  if (!activeProfileId) {
    // This used to be a dead end: EmptyState accepts an action, and none was
    // passed, so the sidebar's Asset Library told you to choose an app and
    // offered no way to choose one. Two different causes need two different
    // next steps, so they are told apart rather than merged into one message.
    const { approved, unapproved } = partitionProfiles(profiles);
    const waiting = unapproved.length > 0;
    return (
      <div className="space-y-4">
        {!embedded && (
          <div data-testid="asset-library-header">
            <PageHeader
              icon={Images}
              title="Asset Library"
              description="Your photograph. Every video is generated from it, so the person on camera is you — the scene around them is invented from the App Profile."
            />
          </div>
        )}
        {loading ? (
          <p className="flex items-center gap-2 text-sm text-muted-foreground">
            <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading your apps...
          </p>
        ) : profiles.length === 0 ? (
          <EmptyState
            icon={Images}
            title="No app yet"
            description="Assets belong to one app and can only be used in that app's videos. Research an app first, then come back to add the face it will be presented by."
            action={
              <Button variant="brand" asChild>
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
                ? `Assets belong to one app. You have ${approved.length} approved and ${unapproved.length} still waiting for approval.`
                : "Assets belong to one app and can only be used in that app's videos."
            }
            action={
              <div className="flex flex-col items-center gap-2">
                {selectableProfiles.length > 1 ? (
                  <ProfilePicker
                    profiles={selectableProfiles}
                    value=""
                    onChange={handleSwitchProfile}
                  />
                ) : (
                  <Button variant="brand" asChild>
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
      </div>
    );
  }

  return (
    <div className="mx-auto w-full max-w-6xl space-y-4">
      {/* Only the standalone route owns a title. Embedded, the wizard step
          header above already says this. */}
      {!embedded && (
        <div data-testid="asset-library-header">
        <PageHeader
          icon={Images}
          title="Asset Library"
          description="Your photograph. Every video is generated from it, so the person on camera is you — the scene around them is invented from the App Profile."
          actions={
            <div className="flex flex-wrap items-center gap-2">
              {/* Shown whenever there is something to switch between. With a
                  single app it would be a one-option menu, which is noise. */}
              {profiles.length > 1 && (
                <ProfilePicker
                  profiles={profiles}
                  value={activeProfileId}
                  onChange={handleSwitchProfile}
                />
              )}
              {/* The approval state is stated here unconditionally, not left to
                  the picker. With exactly one app there is no picker, so this
                  line is the only place it can appear — and "here but not
                  approved" is precisely what someone checking for a missing
                  app needs to be able to see. */}
              {activeProfile && (
                <span className="flex flex-wrap items-center gap-2 text-xs text-muted-foreground">
                  <span>Assets for {profileLabel(activeProfile)}</span>
                  {activeProfile.status === "approved" ? (
                    <Badge variant="outline" className="text-[10px]">Approved</Badge>
                  ) : (
                    <Badge variant="secondary" className="text-[10px]">Needs approval</Badge>
                  )}
                </span>
              )}
            </div>
          }
        />
        </div>
      )}

      <Alert data-testid="asset-rights-alert">
        <ShieldCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" />
        <AlertDescription>
          Only upload assets you have the right to use. Each upload records your
          confirmation, and assets stay scoped to this App Profile.
        </AlertDescription>
      </Alert>

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}
      {notice && <Alert><AlertDescription>{notice}</AlertDescription></Alert>}

      <div className="surface space-y-3 rounded-2xl p-4" data-testid="asset-upload-panel">
        <div className="grid grid-cols-1 gap-2 sm:grid-cols-3">
          <select
            value={kind}
            onChange={(e) => setKind(e.target.value)}
            aria-label="Asset type"
            className="rounded-lg border border-[color:var(--hairline)] bg-transparent px-3 py-2 text-sm"
          >
            {KINDS.map(([value, text]) => (
              <option key={value} value={value}>{text}</option>
            ))}
          </select>
          {KIND_PURPOSE[kind] && (
            <p className="col-span-full text-xs text-muted-foreground">
              {KIND_PURPOSE[kind]}
            </p>
          )}
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label, e.g. Founder face"
            aria-label="Asset label"
          />
          <Button variant="brand" onClick={() => fileRef.current?.click()} disabled={busy}>
            {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Upload className="h-4 w-4" />}
            Upload
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
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {assets.length} asset{assets.length === 1 ? "" : "s"}
            {Object.keys(counts).length > 0 &&
              ` · ${Object.entries(counts).map(([k, n]) => `${n} ${humanize(k).toLowerCase()}`).join(", ")}`}
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
      </div>

      <div data-testid="asset-list">
      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading assets...
        </p>
      ) : assets.length === 0 ? (
        // This was a full EmptyState — dashed 400px box, icon, title, copy —
        // sitting below a toolbar that already has a working Upload button and
        // already says "0 assets". That box is sized for a page that is a dead
        // end; this is a section inside a working page, so the box was
        // disproportionate. The one line below carries the part the toolbar
        // cannot: why uploading is worth doing.
        <p className="text-sm text-muted-foreground">
          {embedded
            ? "Use the Upload button above to add your first one."
            : "Add the character reference photograph the finished video will be generated from."}
        </p>
      ) : (
        <div className="space-y-2">
          {assets.map((a) => (
            <AssetRow
              key={a.id}
              asset={a}
              onDelete={handleDelete}
              onArchive={handleArchive}
              onAttach={handleAttach}
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
    </div>
  );
}
