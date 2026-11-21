import { useState } from "react";

/**
 * The platform phone-frame preview (ADR 0245): a CSS phone frame
 * holding a finished clip as the founder will post it, with each
 * platform's safe zones drawn as quiet guides and a toggle between
 * the two platforms' furniture.
 *
 * The geometry is RECOVERED, not reinvented: it is the retired
 * Stories preview's (ADR 0236, removed with that page in ADR 0243),
 * whose numbers Kasra approved — on the 1080x1920 canvas, Instagram
 * keeps the top 250px for the handle, the bottom 340px for the
 * caption, and 65px at the sides; TikTok's overlay takes the top
 * 240px, the bottom 660px and 120px at the sides, with its right
 * rail (300px wide, from y≈840) over the frame's right edge.
 *
 * A viewer, nothing more: the toggle switches only the overlay
 * zones and the platform label — never the video. The zones are
 * guides, not masks: the clip stays fully visible beneath them, and
 * nothing is burned in. Before a render exists the frame holds the
 * same honest placeholder the retired preview used, never a fake
 * video. A clip the browser cannot play says so inside the frame,
 * in the panels' own words; the host panel owns that state and any
 * retry it offers.
 */
const CANVAS_W = 1080;
const CANVAS_H = 1920;

const ZONES = {
  instagram: {
    label: "Instagram",
    top: 250, bottom: 340, side: 65, rail: null,
  },
  tiktok: {
    label: "TikTok",
    top: 240, bottom: 660, side: 120, rail: { width: 300, fromY: 840 },
  },
};

const heightPct = (px) => `${(px / CANVAS_H) * 100}%`;
const widthPct = (px) => `${(px / CANVAS_W) * 100}%`;

function ZoneBand({ style, label }) {
  return (
    <div
      aria-hidden="true"
      className="pointer-events-none absolute border border-dashed border-white/35 bg-white/5"
      style={style}
    >
      <span className="absolute left-1 top-1 text-xs font-semibold uppercase tracking-wide text-white/60">
        {label}
      </span>
    </div>
  );
}

export default function PlatformPreview({
  videoUrl = "",
  posterUrl = "",
  videoBroken = false,
  onVideoError,
}) {
  const [platform, setPlatform] = useState("instagram");
  const zones = ZONES[platform];

  return (
    <div className="space-y-3" data-testid="platform-preview">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-sm font-semibold">Preview</p>
        <div className="flex gap-2" role="group" aria-label="Safe zones for">
          {Object.entries(ZONES).map(([key, zone]) => (
            <button
              key={key}
              type="button"
              aria-pressed={platform === key}
              onClick={() => setPlatform(key)}
              data-testid={`platform-preview-platform-${key}`}
              className={`rounded-full border px-3 py-1 text-xs font-semibold ${
                platform === key
                  ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-[color:var(--brand-indigo)]"
                  : "border-[color:var(--hairline)] text-muted-foreground"
              }`}
            >
              {zone.label}
            </button>
          ))}
        </div>
      </div>

      <div className="relative mx-auto aspect-[9/16] w-full max-w-[280px] overflow-hidden rounded-[1.6rem] border border-[color:var(--hairline-strong)] bg-neutral-900 shadow-lg">
        {videoBroken ? (
          <div className="absolute inset-0 flex items-center justify-center px-6">
            <p className="text-center text-sm text-white/60">
              Preview unavailable — download it to view.
            </p>
          </div>
        ) : videoUrl ? (
          <video
            key={videoUrl}
            src={videoUrl}
            poster={posterUrl || undefined}
            controls
            playsInline
            controlsList="nodownload noremoteplayback"
            disablePictureInPicture
            preload="none"
            onError={() => onVideoError?.()}
            className="absolute inset-0 h-full w-full object-cover"
            data-testid="platform-preview-video"
          />
        ) : posterUrl ? (
          <img
            src={posterUrl}
            alt=""
            className="absolute inset-0 h-full w-full object-cover"
          />
        ) : (
          <div className="absolute inset-0 flex items-center justify-center px-6">
            <p className="text-center text-sm text-white/50">
              The frame previews here once it renders.
            </p>
          </div>
        )}

        {/* The safe zones for the picked platform, as quiet guides. */}
        <div data-testid="platform-preview-zones" data-platform={platform}>
          <ZoneBand
            label="Handle zone"
            style={{ top: 0, left: 0, right: 0, height: heightPct(zones.top) }}
          />
          <ZoneBand
            label="Caption zone"
            style={{ bottom: 0, left: 0, right: 0, height: heightPct(zones.bottom) }}
          />
          <ZoneBand
            label=""
            style={{ top: 0, bottom: 0, left: 0, width: widthPct(zones.side) }}
          />
          <ZoneBand
            label=""
            style={{ top: 0, bottom: 0, right: 0, width: widthPct(zones.side) }}
          />
          {zones.rail && (
            <ZoneBand
              label="Rail"
              style={{
                right: 0,
                top: heightPct(zones.rail.fromY),
                height: heightPct(CANVAS_H - zones.bottom - zones.rail.fromY),
                width: widthPct(zones.rail.width),
              }}
            />
          )}
        </div>
      </div>

      <p className="text-sm text-muted-foreground">
        The dashed zones are {zones.label}&rsquo;s own furniture — handle,
        caption and buttons. Keep the presenter clear of them.
      </p>
    </div>
  );
}
