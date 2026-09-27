import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import { useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { Input } from "../components/ui/input";
import { Badge } from "../components/ui/badge";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import {
  Images, Loader2, AlertTriangle, Upload, Trash2, Archive, ArchiveRestore,
  Plus, ShieldCheck, Paperclip,
} from "lucide-react";

const KINDS = [
  ["screenshot", "Screenshot"],
  ["screen_recording", "Screen recording"],
  ["logo", "Logo"],
  ["product_image", "Product image"],
  ["character_reference", "Character reference"],
  ["creator_photo", "Creator photo"],
  ["background_image", "Background image"],
];

function humanize(value) {
  return String(value || "").replace(/[-_]/g, " ").replace(/\b\w/g, (c) => c.toUpperCase());
}

function AssetRow({ asset, onDelete, onArchive, busy }) {
  const isVideo = asset.kind === "screen_recording" || asset.kind === "background_video";
  return (
    <div className="flex items-center gap-3 rounded-xl border border-[color:var(--hairline)] p-3">
      <div className="h-14 w-14 shrink-0 overflow-hidden rounded-lg bg-secondary/40">
        {asset.media_url ? (
          isVideo ? (
            <video src={mediaUrl(asset.media_url)} className="h-full w-full object-cover" muted />
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
        </div>
        {asset.notes && <p className="mt-0.5 text-xs text-muted-foreground">{asset.notes}</p>}
      </div>
      <div className="flex shrink-0 gap-1">
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
  );
}

export default function AssetLibrary({ profileId, onChanged }) {
  // Usable as a route (/app-profiles/:profileId/assets) or embedded in the
  // wizard, which already knows which profile it is working on.
  const params = useParams();
  const activeProfileId = profileId || params.profileId || "";
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(true);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState(null);
  const [notice, setNotice] = useState(null);
  const [kind, setKind] = useState("screenshot");
  const [label, setLabel] = useState("");
  const [includeArchived, setIncludeArchived] = useState(false);
  const fileRef = useRef(null);

  const load = useCallback(async () => {
    if (!activeProfileId) return;
    setLoading(true);
    try {
      const data = await api.getAssets(activeProfileId, {
        include_archived: includeArchived || undefined,
      });
      setAssets(data.assets || []);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setLoading(false);
    }
  }, [activeProfileId, includeArchived]);

  useEffect(() => {
    load();
  }, [load]);

  const handleUpload = async (event) => {
    const file = event.target.files?.[0];
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
      setNotice(`Added ${humanize(created.kind)} "${created.label || created.name}".`);
      setLabel("");
      if (fileRef.current) fileRef.current.value = "";
      load();
      onChanged?.();
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setBusy(false);
    }
  };

  const handleDelete = async (asset) => {
    setBusy(true);
    try {
      await api.deleteAsset(asset.id);
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
    return (
      <EmptyState
        icon={Images}
        title="Choose an App Profile first"
        description="Assets belong to one app and can only be used in that app's videos."
      />
    );
  }

  return (
    <div className="space-y-4">
      <PageHeader
        icon={Images}
        title="Asset Library"
        description="Real app visuals. These are composited onto the video deterministically, so interfaces, text, and pricing stay accurate."
      />

      <Alert>
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

      <div className="surface space-y-3 rounded-2xl p-4">
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
          <Input
            value={label}
            onChange={(e) => setLabel(e.target.value)}
            placeholder="Label, e.g. Onboarding"
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
          accept="image/png,image/jpeg,image/webp,image/gif,video/mp4,video/quicktime,video/webm"
          onChange={handleUpload}
          aria-label="Asset file"
        />
        <div className="flex flex-wrap items-center justify-between gap-2">
          <span className="text-xs text-muted-foreground">
            {assets.length} asset{assets.length === 1 ? "" : "s"}
            {Object.keys(counts).length > 0 &&
              ` Â· ${Object.entries(counts).map(([k, n]) => `${n} ${humanize(k).toLowerCase()}`).join(", ")}`}
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

      {loading ? (
        <p className="flex items-center gap-2 text-sm text-muted-foreground">
          <Loader2 className="h-3.5 w-3.5 animate-spin" /> Loading assets...
        </p>
      ) : assets.length === 0 ? (
        <EmptyState
          icon={Images}
          title="No assets yet"
          description="Add screenshots, screen recordings, and your logo so the finished video shows the real app instead of a generated approximation."
          action={
            <Button variant="brand" onClick={() => fileRef.current?.click()}>
              <Plus className="h-4 w-4" /> Upload your first asset
            </Button>
          }
        />
      ) : (
        <div className="space-y-2">
          {assets.map((a) => (
            <AssetRow key={a.id} asset={a} onDelete={handleDelete} onArchive={handleArchive} busy={busy} />
          ))}
        </div>
      )}
    </div>
  );
}
