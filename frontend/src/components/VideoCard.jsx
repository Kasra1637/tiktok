import { motion, useReducedMotion } from "framer-motion";
import { Card } from "./ui/card";
import { Badge } from "./ui/badge";
import { AspectRatio } from "./ui/aspect-ratio";
import { Button } from "./ui/button";
import { Eye, Heart, Sparkles, Flame } from "lucide-react";

function formatCount(n) {
  if (!n) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function getViralityStyle(score) {
  if (score >= 70) return "bg-[color:var(--brand-coral)] text-white";
  if (score >= 40) return "bg-[color:var(--brand-teal)] text-white";
  return "bg-gray-500/80 text-white";
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
      className="group overflow-hidden bg-[color:var(--card)] border border-border rounded-2xl shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-tight)] hover:border-[color:rgba(99,102,241,0.35)] hover:-translate-y-0.5 transition-shadow transition-colors transition-transform"
      data-testid="video-card"
    >
      <AspectRatio ratio={9 / 16} className="bg-muted overflow-hidden relative">
        {video.thumbnail_url ? (
          <img
            src={video.thumbnail_url}
            alt={video.title}
            loading="lazy"
            className="h-full w-full object-cover group-hover:scale-[1.03] transition-transform duration-300"
            onError={(e) => {
              e.currentTarget.style.display = "none";
            }}
          />
        ) : null}
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
          <Badge className="bg-black/70 border-none text-white gap-1">
            <Eye className="h-3 w-3" />
            {formatCount(video.view_count)}
          </Badge>
          <Badge className="bg-black/70 border-none text-white gap-1">
            <Heart className="h-3 w-3" />
            {formatCount(video.like_count)}
          </Badge>
        </div>
      </AspectRatio>
      <div className="p-4 space-y-2">
        <p className="text-sm font-medium leading-snug line-clamp-2 min-h-[2.5rem]">{video.title}</p>
        <p className="text-xs text-muted-foreground">@{video.creator}</p>
        <Button
          onClick={() => onAnalyze(video)}
          disabled={analyzing}
          className="w-full bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white gap-2"
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
