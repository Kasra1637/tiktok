import { useState } from "react";
import { motion, useReducedMotion } from "framer-motion";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { AspectRatio } from "./ui/aspect-ratio";
import { Button } from "./ui/button";
import { Eye, Heart, MessageCircle, Sparkles, Flame, ExternalLink } from "lucide-react";

function formatCount(n) {
  if (!n) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function getViralityStyle(score) {
  if (score >= 70) return "bg-[color:var(--brand-coral)] text-white";
  if (score >= 40) return "bg-[color:var(--brand-teal)] text-white";
  return "bg-secondary text-muted-foreground";
}

function proxyThumb(url) {
  if (!url) return null;
  const BACKEND_URL = process.env.REACT_APP_BACKEND_URL || "";
  return `${BACKEND_URL}/api/proxy-thumb?url=${encodeURIComponent(url)}`;
}

function Thumbnail({ url, alt }) {
  const [src, setSrc] = useState(url); // Try direct URL first
  const [failed, setFailed] = useState(false);

  if (!url) return null;
  if (failed) return null;

  return (
    <img
      src={src}
      alt={alt}
      loading="lazy"
      referrerPolicy="no-referrer"
      className="h-full w-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
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

export function VideoCard({ video, onAnalyze, analyzing, index = 0 }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 10 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.24, ease: "easeOut", delay: Math.min(index * 0.04, 0.32) }}
    >
    <Card
      className="group overflow-hidden bg-card border border-border rounded-2xl hover:border-[color:rgba(129,140,248,0.35)] hover:-translate-y-0.5 transition-all duration-200"
      data-testid="video-card"
    >
      <AspectRatio ratio={9 / 16} className="bg-muted overflow-hidden relative">
        <Thumbnail url={video.thumbnail_url} alt={video.title} />
        {/* TikTok link overlay */}
        {video.tiktok_url && (
          <a
            href={video.tiktok_url}
            target="_blank"
            rel="noreferrer"
            className="absolute top-2 left-2 flex items-center gap-1 rounded-full bg-black/70 text-white px-2 py-1 text-[10px] font-medium opacity-0 group-hover:opacity-100 transition-opacity hover:bg-black/90"
            onClick={(e) => e.stopPropagation()}
            data-testid="video-tiktok-link"
          >
            <ExternalLink className="h-2.5 w-2.5" /> TikTok
          </a>
        )}
        {video.virality_score != null && (
          <div className="absolute top-2 right-2">
            <Badge
              className={`border-none gap-1 text-xs font-semibold shadow-md ${getViralityStyle(video.virality_score)}`}
              data-testid="virality-badge"
            >
              <Flame className="h-3 w-3" />
              {Math.round(video.virality_score)}
            </Badge>
          </div>
        )}
        <div className="absolute bottom-2 left-2 right-2 flex items-center gap-1.5 text-[11px] text-white">
          <Badge className="bg-black/70 border-none text-white gap-1" data-testid="video-card-view-count">
            <Eye className="h-3 w-3" />
            {formatCount(video.view_count)}
          </Badge>
          <Badge className="bg-black/70 border-none text-white gap-1" data-testid="video-card-like-count">
            <Heart className="h-3 w-3" />
            {formatCount(video.like_count)}
          </Badge>
          <Badge className="bg-black/70 border-none text-white gap-1" data-testid="video-card-comment-count">
            <MessageCircle className="h-3 w-3" />
            {formatCount(video.comment_count)}
          </Badge>
        </div>
      </AspectRatio>
      <div className="p-4 space-y-2">
        <p className="text-sm font-medium leading-snug line-clamp-2 min-h-[2.5rem]">{video.title}</p>
        <p className="text-xs text-muted-foreground">@{video.creator}</p>
        <Button
          onClick={() => onAnalyze(video)}
          disabled={analyzing}
          className="w-full bg-[color:var(--brand-coral)] hover:bg-[#e0264c] text-white gap-2"
          data-testid="analyze-hook-button"
        >
          <Sparkles className={`h-4 w-4 ${analyzing ? "animate-pulse" : ""}`} /> {analyzing ? "Analyzing..." : "Analyze Hook"}
        </Button>
      </div>
    </Card>
    </motion.div>
  );
}
export default VideoCard;
