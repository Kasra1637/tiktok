import { useEffect, useMemo, useState } from "react";
import { createPortal } from "react-dom";
import { Check, ChevronLeft, ChevronRight, Film, Image as ImageIcon, ImageOff, Images, Upload, X } from "lucide-react";
import { Button } from "../components/ui/button";
import { GroupLabel } from "../components/SectionCard";
import { PILL_SELECT_CLASS } from "../components/AppPicker";
import { api, getErrorMessage, mediaUrl } from "../lib/api";

/**
 * The library pop-up for the Demo + CTA editor's two clip slots.
 *
 * Until now the editor could only file copies INTO the Assets library
 * (ADR 0274): every add was a fresh device upload, and media already
 * imported sat unreachable behind a re-upload. This pop-up is the way
 * back in — the same centered, portal-mounted shell the other sections'
 * pop-ups use (the angle sheet, the Focus pop-up), opened from either
 * slot's add buttons. It lists the founder's active clip assets — the
 * screen recordings and screenshots the editor itself files — as
 * tappable thumbnails, grouped the way the library page groups them.
 *
 * The slot decides the pick shape. The base clip takes one video:
 * picking replaces, the current pick stands selected, and images are
 * shown but not pickable — the base has never taken a still. The second
 * clip takes a sequence: every pick stands selected with its order
 * number, tapping a selected asset takes it back out, and the strip
 * across the top carries the standing sequence in order — drag a tile
 * or use the section list's arrows to re-prioritize, tap its Remove to
 * take it out without hunting the grid.
 *
 * Picking is the editor's work (it owns the entries and the bytes), so
 * a tile tap only reports the asset; the editor fetches the file and
 * lands it in the slot. Uploading from the device stays one tap away in
 * the footer — the pop-up is a door to the library, not a wall in front
 * of the file picker.
 */

const CLIP_KINDS = ["screen_recording", "screenshot"];

export function isClipAsset(asset) {
  return Boolean(asset) && asset.status === "active" && CLIP_KINDS.includes(asset.kind);
}

export function isVideoAsset(asset) {
  return asset?.kind === "screen_recording";
}

function formatSeconds(value) {
  const seconds = Number(value);
  if (!Number.isFinite(seconds) || seconds < 0) return "";
  return `${seconds % 1 === 0 ? seconds : seconds.toFixed(1)}s`;
}

function PickerThumb({ asset }) {
  const [failed, setFailed] = useState(false);
  const src = asset.media_url;
  const video = isVideoAsset(asset);
  if (!src || failed) {
    return (
      <div className="flex h-full w-full items-center justify-center text-muted-foreground" aria-hidden="true">
        {video ? <Film className="h-6 w-6" /> : <ImageOff className="h-6 w-6" />}
      </div>
    );
  }
  return video ? (
    <video
      src={mediaUrl(src)}
      className="h-full w-full object-cover"
      muted
      preload="metadata"
      onError={() => setFailed(true)}
    />
  ) : (
    <img
      src={mediaUrl(src)}
      alt={asset.label || asset.name || "Imported image"}
      className="h-full w-full object-cover"
      loading="lazy"
      decoding="async"
      onError={() => setFailed(true)}
    />
  );
}

export function LibraryPicker({
  open,
  slot,
  profileId,
  selectedAssetIds = [],
  sequence = [],
  onToggleAsset,
  onRemoveEntry,
  onMoveEntry,
  onDropEntry,
  onUploadVideo,
  onUploadImages,
  onClose,
}) {
  const [assets, setAssets] = useState([]);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState(null);
  const [query, setQuery] = useState("");
  const [busyAssetId, setBusyAssetId] = useState("");
  const [dragEntryId, setDragEntryId] = useState(null);

  const load = useMemo(
    () => async () => {
      if (!profileId) {
        setAssets([]);
        setError(null);
        setLoading(false);
        return;
      }
      setLoading(true);
      setError(null);
      try {
        const data = await api.getAssets(profileId);
        setAssets((data.assets || []).filter(isClipAsset));
      } catch (err) {
        setAssets([]);
        setError(getErrorMessage(err));
      } finally {
        setLoading(false);
      }
    },
    [profileId]
  );

  useEffect(() => {
    if (!open) return undefined;
    setQuery("");
    setBusyAssetId("");
    load();
    const onKey = (event) => {
      if (event.key === "Escape") onClose?.();
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [open, load, onClose]);

  if (!open) return null;

  const selectedOrder = new Map(selectedAssetIds.map((id, index) => [id, index + 1]));
  const q = query.trim().toLowerCase();
  const listed = q
    ? assets.filter((a) => [a.label, a.name, a.kind].some((v) => String(v || "").toLowerCase().includes(q)))
    : assets;
  const groups = [
    { id: "videos", label: "Videos", icon: Film, rows: listed.filter(isVideoAsset) },
    { id: "images", label: "Images", icon: Images, rows: listed.filter((a) => !isVideoAsset(a)) },
  ].filter((group) => group.rows.length > 0);
  const hasImages = assets.some((a) => !isVideoAsset(a));

  const toggle = async (asset) => {
    if (busyAssetId) return;
    // In the base slot an image is visible but never a pick: the base
    // paints from a video element end to end, and a still there would
    // be a clip that cannot play.
    if (slot === "base" && !isVideoAsset(asset)) return;
    setBusyAssetId(asset.id);
    try {
      await onToggleAsset?.(asset);
    } finally {
      setBusyAssetId("");
    }
  };

  return createPortal(
    <div className="fixed inset-0 z-[100] flex items-center justify-center p-4" data-testid="library-picker">
      <div aria-hidden="true" className="absolute inset-0 pop-scrim" onClick={() => onClose?.()} />
      <div
        role="dialog"
        aria-modal="true"
        aria-label="Choose from your library"
        className="relative flex max-h-[85vh] w-full max-w-2xl flex-col overflow-hidden rounded-xl border border-[color:var(--hairline)] bg-card shadow-lg"
      >
        <div className="flex items-center justify-between gap-2 border-b border-[color:var(--hairline)] row-pad">
          <span className="min-w-0 truncate text-sm font-semibold">Choose from your library</span>
          <button
            type="button"
            aria-label="Close library picker"
            data-testid="library-picker-close"
            onClick={() => onClose?.()}
            className="shrink-0 text-muted-foreground"
          >
            <X aria-hidden="true" className="h-4 w-4" />
          </button>
        </div>

        <div className="min-h-0 flex-1 space-y-4 overflow-y-auto row-pad">
          <p className="text-sm text-muted-foreground">
            {slot === "base"
              ? "Pick the one video for the base clip. Picking another replaces it."
              : "Pick videos and images for the second clip. They play in the order you leave them."}
          </p>

          {slot === "second" && sequence.length > 0 && (
            <div className="space-y-2">
              <GroupLabel icon={Film}>Second clip sequence</GroupLabel>
              <div className="flex flex-wrap gap-2" data-testid="library-picker-sequence">
                {sequence.map((entry, index) => (
                  <div
                    key={entry.entryId}
                    draggable
                    onDragStart={() => setDragEntryId(entry.entryId)}
                    onDragEnd={() => setDragEntryId(null)}
                    onDragOver={(event) => event.preventDefault()}
                    onDrop={(event) => {
                      event.preventDefault();
                      if (dragEntryId && dragEntryId !== entry.entryId) onDropEntry?.(dragEntryId, entry.entryId);
                      setDragEntryId(null);
                    }}
                    data-testid={`library-picker-item-${entry.entryId}`}
                    className={`flex max-w-56 items-center gap-1.5 rounded-xl border px-2.5 py-1.5 text-sm ${
                      dragEntryId === entry.entryId
                        ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)]"
                        : "border-[color:var(--hairline)] bg-secondary/20"
                    }`}
                  >
                    {entry.kind === "video" ? (
                      <Film className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    ) : (
                      <ImageIcon className="h-4 w-4 shrink-0 text-muted-foreground" aria-hidden="true" />
                    )}
                    <span className="shrink-0 font-semibold text-muted-foreground">Item {index + 1}</span>
                    <span className="min-w-0 flex-1 truncate" title={entry.name}>{entry.name}</span>
                    <button
                      type="button"
                      aria-label={`Move ${entry.name} earlier`}
                      title="Move earlier"
                      disabled={index === 0}
                      onClick={() => onMoveEntry?.(entry.entryId, -1)}
                      data-testid={`library-picker-item-up-${entry.entryId}`}
                      className="shrink-0 text-muted-foreground transition hover:text-foreground disabled:opacity-40"
                    >
                      <ChevronLeft className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      aria-label={`Move ${entry.name} later`}
                      title="Move later"
                      disabled={index === sequence.length - 1}
                      onClick={() => onMoveEntry?.(entry.entryId, 1)}
                      data-testid={`library-picker-item-down-${entry.entryId}`}
                      className="shrink-0 text-muted-foreground transition hover:text-foreground disabled:opacity-40"
                    >
                      <ChevronRight className="h-3.5 w-3.5" />
                    </button>
                    <button
                      type="button"
                      aria-label={`Remove ${entry.name} from the second clip`}
                      title="Remove from the second clip"
                      onClick={() => onRemoveEntry?.(entry.entryId)}
                      data-testid={`library-picker-item-remove-${entry.entryId}`}
                      className="shrink-0 text-muted-foreground transition hover:text-foreground"
                    >
                      <X className="h-3.5 w-3.5" />
                    </button>
                  </div>
                ))}
              </div>
            </div>
          )}

          {!profileId ? (
            <p className="text-base text-muted-foreground" role="status">
              Your imported images and videos live with their app, and no app is attached to this edit yet. Uploading from this device still works below.
            </p>
          ) : loading ? (
            <p className="text-base text-muted-foreground" role="status">Loading your library…</p>
          ) : error ? (
            <div className="space-y-2">
              <p className="text-base text-destructive-text" role="alert">{error}</p>
              <Button variant="secondary" size="sm" onClick={load} data-testid="library-picker-retry">
                Try again
              </Button>
            </div>
          ) : assets.length === 0 ? (
            <p className="text-base text-muted-foreground" role="status">
              Nothing here yet. Upload an image or a video in this editor and it is filed here for next time.
            </p>
          ) : (
            <>
              {assets.length > 1 && (
                <div className="flex flex-wrap items-center gap-2">
                  <label className="sr-only" htmlFor="library-picker-search">Search your library</label>
                  <input
                    id="library-picker-search"
                    type="search"
                    value={query}
                    onChange={(event) => setQuery(event.target.value)}
                    placeholder="Search your library…"
                    aria-label="Search your library by name or kind"
                    data-testid="library-picker-search"
                    className={PILL_SELECT_CLASS}
                  />
                  {q && (
                    <span className="text-sm text-muted-foreground" role="status">
                      {listed.length} of {assets.length} match “{query.trim()}”
                    </span>
                  )}
                </div>
              )}
              {listed.length === 0 ? (
                <p className="text-base text-muted-foreground" role="status">
                  No assets match “{query.trim()}”. Clear the search to see everything.
                </p>
              ) : (
                groups.map((group) => (
                  <div key={group.id} className="space-y-2" data-testid={`library-picker-group-${group.id}`}>
                    <GroupLabel icon={group.icon}>{group.label}</GroupLabel>
                    <div className="grid grid-cols-3 gap-2 sm:grid-cols-4">
                      {group.rows.map((asset) => {
                        const order = selectedOrder.get(asset.id);
                        const selected = Boolean(order);
                        const pickable = slot !== "base" || isVideoAsset(asset);
                        const name = asset.label || asset.name || (isVideoAsset(asset) ? "Video clip" : "Image");
                        return (
                          <button
                            key={asset.id}
                            type="button"
                            disabled={!pickable || busyAssetId === asset.id}
                            aria-pressed={selected}
                            aria-label={selected ? `Remove ${name}` : `Use ${name}`}
                            title={pickable ? name : "The base clip takes a video — images go in the second clip"}
                            data-testid={`library-picker-asset-${asset.id}`}
                            data-selected={selected ? "true" : undefined}
                            onClick={() => toggle(asset)}
                            className={`focus-ring group overflow-hidden rounded-xl border text-left transition ${
                              selected
                                ? "border-[color:var(--brand-indigo)] ring-2 ring-[color:var(--brand-indigo)]/40"
                                : "border-[color:var(--hairline)] hover:border-[color:var(--hairline-strong)]"
                            } ${pickable ? "" : "cursor-not-allowed opacity-50"}`}
                          >
                            <span className="relative block aspect-[3/4] bg-secondary/40">
                              <PickerThumb asset={asset} />
                              {selected && (
                                <span className="absolute right-1.5 top-1.5 flex h-6 min-w-6 items-center justify-center gap-0.5 rounded-full bg-[color:var(--brand-indigo-deep)] px-1 text-xs font-semibold text-muted-foreground">
                                  <Check className="h-3.5 w-3.5" aria-hidden="true" />
                                  {slot === "second" && order ? order : null}
                                </span>
                              )}
                            </span>
                            <span className="block truncate px-2 py-1.5 text-xs" title={name}>{name}</span>
                            <span className="block px-2 pb-1.5 text-xs text-muted-foreground">
                              {isVideoAsset(asset) ? "Video clip" : "Image"}
                              {asset.duration_seconds ? ` · ${formatSeconds(asset.duration_seconds)}` : ""}
                            </span>
                          </button>
                        );
                      })}
                    </div>
                  </div>
                ))
              )}
              {slot === "base" && hasImages && (
                <p className="text-sm text-muted-foreground">
                  The base clip takes one video. Your images can be picked for the second clip instead.
                </p>
              )}
            </>
          )}
        </div>

        <div className="flex flex-wrap items-center gap-2 border-t border-[color:var(--hairline)] row-pad">
          <Button
            variant="secondary"
            size="sm"
            className="h-10"
            onClick={() => onUploadVideo?.()}
            data-testid="library-picker-upload-video"
          >
            <Upload className="h-3.5 w-3.5" />
            <span>Upload a video from this device</span>
          </Button>
          {slot === "second" && (
            <Button
              variant="secondary"
              size="sm"
              className="h-10"
              onClick={() => onUploadImages?.()}
              data-testid="library-picker-upload-images"
            >
              <Upload className="h-3.5 w-3.5" />
              <span>Upload images from this device</span>
            </Button>
          )}
        </div>
      </div>
    </div>,
    document.body
  );
}
