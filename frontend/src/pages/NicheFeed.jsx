import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import * as LucideIcons from "lucide-react";
import { Compass } from "lucide-react";
import { Skeleton } from "../components/ui/skeleton";
import { Card } from "../components/ui/card";
import VideoCard from "../components/VideoCard";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import { toast } from "sonner";

export default function NicheFeed() {
  const [niches, setNiches] = useState([]);
  const [activeNiche, setActiveNiche] = useState(null);
  const [videos, setVideos] = useState([]);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [analyzingId, setAnalyzingId] = useState(null);
  const navigate = useNavigate();

  useEffect(() => {
    api
      .getNiches()
      .then((data) => {
        setNiches(data);
        if (data.length) setActiveNiche(data[0].key);
      })
      .catch((err) => toast.error(getErrorMessage(err)));
  }, []);

  const loadVideos = useCallback((nicheKey) => {
    setLoadingVideos(true);
    api
      .getNicheVideos(nicheKey)
      .then(setVideos)
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoadingVideos(false));
  }, []);

  useEffect(() => {
    if (activeNiche) loadVideos(activeNiche);
  }, [activeNiche, loadVideos]);

  const handleAnalyze = async (video) => {
    setAnalyzingId(video.tiktok_url);
    try {
      const ingested = await api.ingestVideo(video.tiktok_url, activeNiche);
      navigate(`/analysis/${ingested.id}`);
    } catch (err) {
      toast.error(getErrorMessage(err));
    } finally {
      setAnalyzingId(null);
    }
  };

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-3xl md:text-4xl font-semibold tracking-tight">Discover trending hooks</h1>
        <p className="text-muted-foreground mt-1 max-w-2xl">
          Pick a niche to browse trending TikTok videos, then analyze the first 2-3 seconds to see exactly what makes
          the hook work.
        </p>
      </div>

      <div className="flex flex-wrap gap-2" data-testid="niche-selector-tabs">
        {niches.map((n) => {
          const Icon = LucideIcons[n.icon] || Compass;
          const isActive = activeNiche === n.key;
          return (
            <button
              key={n.key}
              onClick={() => setActiveNiche(n.key)}
              data-testid={`niche-chip-${n.key}`}
              className={`flex items-center gap-1.5 rounded-full px-3.5 py-2 text-sm font-medium border transition-colors ${
                isActive
                  ? "bg-[color:var(--brand-teal)] text-white border-transparent"
                  : "bg-white border-border hover:border-[color:rgba(13,148,136,0.45)]"
              }`}
            >
              <Icon className="h-4 w-4" /> {n.label}
            </button>
          );
        })}
      </div>

      {loadingVideos ? (
        <div>
          <p className="text-sm text-muted-foreground mb-4">
            Fetching trending videos for this niche... this can take up to 20 seconds the first time.
          </p>
          <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4">
            {Array.from({ length: 6 }).map((_, i) => (
              <Card key={i} className="overflow-hidden rounded-2xl border-border">
                <Skeleton className="h-[280px] w-full" />
                <div className="p-4 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                  <Skeleton className="h-9 w-full rounded-xl" />
                </div>
              </Card>
            ))}
          </div>
        </div>
      ) : videos.length === 0 ? (
        <EmptyState
          icon={Compass}
          title="No trending videos found right now"
          description="This niche's creators may be temporarily unavailable. Try another niche or paste a TikTok URL directly above."
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4" data-testid="video-feed-grid">
          {videos.map((v) => (
            <VideoCard key={v.tiktok_url} video={v} onAnalyze={handleAnalyze} analyzing={analyzingId === v.tiktok_url} />
          ))}
        </div>
      )}
    </div>
  );
}
