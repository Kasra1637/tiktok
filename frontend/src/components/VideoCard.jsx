import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Badge } from "./ui/badge";
import { AspectRatio } from "./ui/aspect-ratio";
import { Button } from "./ui/button";
import { Eye, Heart, MessageCircle, Sparkles, Flame, ExternalLink, Music2, BadgeAlert, ImageOff } from "lucide-react";

function formatCount(n) {
  if (!n) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function getViralityStyle(score) {
  if (score >= 70) return "bg-[color:var(--brand-coral)] text-white border-transparent";
  if (score >= 40) return "bg-[color:var(--brand-indigo)] text-white border-transparent";
  return "bg-black/70 text-white border-transparent";
}

function proxyThumb(url) {
  if (!url) return null;
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
  return `${BACKEND_URL}/api/proxy-thumb?url=${encodeURIComponent(url)}`;
}

function Thumbnail({ url, alt }) {
  const [src, setSrc] = useState(url); // Try direct URL first
  const [failed, setFailed] = useState(false);

  if (!url || failed) {
    // Placeholder instead of an empty box, so the card keeps its shape when a
    // TikTok CDN cover can't be loaded at all.
    return (
      <div className="flex h-full w-full items-center justify-center bg-gradient-to-b from-secondary/60 to-muted">
        <ImageOff className="h-6 w-6 text-muted-foreground/50" />
      </div>
    );
  }

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      className="h-full w-full object-cover transition-transform duration-500 ease-out-expo group-hover:scale-[1.06]"
      onError={() => {
        if (src === url) {
          // Direct load failed — try proxy
          setSrc(proxyThumb(url));
        } else {
          // Proxy also failed — give up
          setFailed(true);
        }
      }}
    />
  );
}

/**
 * A stat chip over the thumbnail. The icon is the only thing distinguishing
 * views from likes from comments, and lucide marks icons aria-hidden, so
 * without `label` a screen reader just hears three bare numbers in a row.
 * Visually-hidden text is used rather than aria-label because it is announced
 * reliably on a non-interactive element.
 */
function StatPill({ icon: Icon, value, label, testId }) {
  return (
    <span
      className="inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-xs font-semibold text-white backdrop-blur-sm"
      data-testid={testId}
    >
      <Icon className="h-3 w-3" />
      {value}
      {label && <span className="sr-only"> {label}</span>}
    </span>
  );
}

export function VideoCard({ video, onAnalyze, analyzing, index = 0 }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut", delay: Math.min(index * 0.04, 0.32) }}
    >
      <div
        className="surface surface-interactive group flex flex-col overflow-hidden rounded-2xl"
        data-testid="video-card"
      >
        <AspectRatio ratio={9 / 16} className="relative overflow-hidden bg-muted">
          <Thumbnail url={video.thumbnail_url} alt={video.title} />

          {/* Bottom scrim so the stat pills stay legible on bright thumbnails */}
          <div
            aria-hidden="true"
            className="pointer-events-none absolute inset-x-0 bottom-0 h-28 bg-gradient-to-t from-black/80 via-black/25 to-transparent"
          />

          {/* TikTok link overlay */}
          {video.tiktok_url && (
            <a
              href={video.tiktok_url}
              target="_blank"
              rel="noreferrer"
              className={`absolute left-2.5 flex items-center gap-1 rounded-full bg-black/70 px-2 py-1 text-xs font-semibold text-white opacity-0 backdrop-blur-sm transition-opacity hover:bg-black/90 group-hover:opacity-100 ${
                video.is_ad ? "top-10" : "top-2.5"
              }`}
              onClick={(e) => e.stopPropagation()}
              data-testid="video-tiktok-link"
            >
              <ExternalLink className="h-2.5 w-2.5" /> TikTok
              <span className="sr-only"> — open original video on TikTok in a new tab</span>
            </a>
          )}

          {video.is_ad && (
            <div className="absolute left-2.5 top-2.5">
              <Badge
                className="border-transparent bg-amber-500/90 text-xs font-semibold text-white shadow-[var(--shadow-sm)]"
                data-testid="sponsored-badge"
                title="This post is flagged as an ad or sponsored content"
              >
                <BadgeAlert className="h-2.5 w-2.5" />
                Sponsored
              </Badge>
            </div>
          )}

          {video.virality_score != null && (
            <div className="absolute right-2.5 top-2.5">
              <Badge
                className={`text-xs font-bold shadow-[var(--shadow-sm)] backdrop-blur-sm ${getViralityStyle(video.virality_score)}`}
                data-testid="virality-badge"
                title={`Virality score ${Math.round(video.virality_score)} out of 100`}
              >
                <Flame className="h-3 w-3" />
                {Math.round(video.virality_score)}
                <span className="sr-only"> virality score out of 100</span>
              </Badge>
            </div>
          )}

          <div className="absolute inset-x-2.5 bottom-2.5 flex flex-wrap items-center gap-1.5">
            <StatPill icon={Eye} value={formatCount(video.view_count)} label="views" testId="video-card-view-count" />
            <StatPill icon={Heart} value={formatCount(video.like_count)} label="likes" testId="video-card-like-count" />
            <StatPill icon={MessageCircle} value={formatCount(video.comment_count)} label="comments" testId="video-card-comment-count" />
          </div>
        </AspectRatio>

        <div className="flex flex-1 flex-col gap-2.5 p-4">
          <p className="line-clamp-2 min-h-[2.5rem] text-sm font-medium leading-snug">{video.title}</p>

          <div className="flex items-center gap-2">
            {/* Initial-letter avatar: decorative duplicate of the handle
                beside it, so it would otherwise announce a stray letter. */}
            <span
              aria-hidden="true"
              className="flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-[color:var(--indigo-10)] text-xs font-bold uppercase text-[color:var(--brand-indigo)]"
            >
              {(video.creator || "?").charAt(0)}
            </span>
            <p className="truncate text-xs text-muted-foreground">@{video.creator}</p>
          </div>

          {(video.song_title || video.song_artist) && (
            <div
              className="flex max-w-full items-center gap-1.5 rounded-full border border-[color:var(--hairline)] bg-secondary/40 px-2.5 py-1 text-xs text-muted-foreground"
              data-testid="video-card-sound-badge"
              title={`${video.song_title || "Original sound"}${video.song_artist ? ` — ${video.song_artist}` : ""}`}
            >
              <Music2 className="h-3 w-3 shrink-0 text-[color:var(--brand-indigo)]" />
              <span className="truncate">
                {video.song_title || "Original sound"}
                {video.song_artist ? ` · ${video.song_artist}` : ""}
              </span>
            </div>
          )}

          <Button
            onClick={() => onAnalyze(video)}
            disabled={analyzing}
            variant="brand"
            className="mt-auto w-full"
            data-testid="analyze-hook-button"
          >
            <Sparkles className={`h-4 w-4 ${analyzing ? "animate-pulse" : ""}`} />{" "}
            {analyzing ? "Analyzing..." : "Analyze Hook"}
          </Button>
        </div>
      </div>
    </motion.div>
  );
}
export default VideoCard;
