import { useEffect, useState, useCallback } from "react";
import { useNavigate } from "react-router-dom";
import * as LucideIcons from "lucide-react";
import { Compass, Search, TrendingUp } from "lucide-react";
import { Skeleton } from "../components/ui/skeleton";
import { Card } from "../components/ui/card";
import { Input } from "../components/ui/input";
import VideoCard from "../components/VideoCard";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage } from "../lib/api";
import { toast } from "sonner";

const MODES = [
  { key: "trending", label: "Trending" },
  { key: "curated", label: "Curated" },
  { key: "mixed", label: "Mixed" },
];

export default function NicheFeed() {
  const [niches, setNiches] = useState([]);
  const [activeNiche, setActiveNiche] = useState(null);
  const [videos, setVideos] = useState([]);
  const [loadingVideos, setLoadingVideos] = useState(false);
  const [analyzingId, setAnalyzingId] = useState(null);
  const [mode, setMode] = useState("trending");
  const [searchQuery, setSearchQuery] = useState("");
  const [searchResults, setSearchResults] = useState(null);
  const [searchLoading, setSearchLoading] = useState(false);
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

  const loadVideos = useCallback(
    (nicheKey, currentMode) => {
      setLoadingVideos(true);
      setSearchResults(null);

      let request;
      if (currentMode === "trending") {
        request = api.getTrendingVideos(nicheKey);
      } else if (currentMode === "mixed") {
        request = api.getNicheVideos(nicheKey, "mixed");
      } else {
        request = api.getNicheVideos(nicheKey, "curated");
      }

      request
        .then((data) => {
          if (currentMode === "trending" || currentMode === "mixed") {
            data.sort((a, b) => (b.virality_score || 0) - (a.virality_score || 0));
          }
          setVideos(data);
        })
        .catch((err) => toast.error(getErrorMessage(err)))
        .finally(() => setLoadingVideos(false));
    },
    []
  );

  useEffect(() => {
    if (activeNiche) loadVideos(activeNiche, mode);
  }, [activeNiche, mode, loadVideos]);

  const handleSearch = useCallback(
    (e) => {
      e.preventDefault();
      const query = searchQuery.trim();
      if (!query) return;

      setSearchLoading(true);
      api
        .searchTrending(query, 20)
        .then((data) => {
          data.sort((a, b) => (b.virality_score || 0) - (a.virality_score || 0));
          setSearchResults(data);
        })
        .catch((err) => toast.error(getErrorMessage(err)))
        .finally(() => setSearchLoading(false));
    },
    [searchQuery]
  );

  const clearSearch = useCallback(() => {
    setSearchResults(null);
    setSearchQuery("");
  }, []);

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

  const displayVideos = searchResults !== null ? searchResults : videos;

  const loadingText =
    mode === "trending"
      ? "Finding viral videos..."
      : mode === "mixed"
      ? "Finding viral and curated videos..."
      : "Fetching curated videos...";

  return (
    <div className="space-y-4">
      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight">Discover Hooks</h1>
        <p className="text-muted-foreground text-sm mt-0.5">Browse trending TikToks and analyze what makes their hooks work.</p>
      </div>

      {/* Filter bar */}
      <div className="rounded-xl border border-border bg-card/60 p-3 space-y-3">
        <div className="flex flex-col sm:flex-row sm:items-center gap-2">
          <form onSubmit={handleSearch} className="flex items-center gap-2 flex-1 min-w-0">
            <div className="relative flex-1">
              <Search className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
              <Input
                type="text"
                placeholder="Search by keyword or hashtag..."
                value={searchQuery}
                onChange={(e) => setSearchQuery(e.target.value)}
                className="pl-9 rounded-lg bg-secondary h-9 text-sm"
                data-testid="search-input"
              />
            </div>
            <button
              type="submit"
              disabled={searchLoading || !searchQuery.trim()}
              className="rounded-lg px-3 py-1.5 text-sm font-medium bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white disabled:opacity-50 transition-colors hover:-translate-y-[1px] active:translate-y-0 active:scale-[0.98]"
              data-testid="search-button"
            >
              {searchLoading ? "Searching..." : "Search"}
            </button>
            {searchResults !== null && (
              <button
                type="button"
                onClick={clearSearch}
                className="rounded-lg px-3 py-1.5 text-sm font-medium border border-border hover:bg-muted transition-colors"
              >
                Clear
              </button>
            )}
          </form>

          <div className="flex items-center gap-1 rounded-full border border-border p-0.5 bg-secondary shrink-0" data-testid="mode-toggle">
            {MODES.map((m) => (
              <button
                key={m.key}
                onClick={() => setMode(m.key)}
                data-testid={`mode-${m.key}`}
                aria-pressed={mode === m.key}
                className={`rounded-full px-3 py-1 text-sm font-medium transition-colors active:scale-95 ${
                  mode === m.key
                    ? "bg-[color:var(--brand-teal)] text-white"
                    : "text-muted-foreground hover:text-foreground hover:bg-muted"
                }`}
              >
                {m.label}
              </button>
            ))}
          </div>
        </div>

        {searchResults !== null && (
          <span className="flex items-center gap-1 text-xs text-muted-foreground">
            <Search className="h-3 w-3" />
            Results for &quot;{searchQuery}&quot;
          </span>
        )}

        <div className="flex flex-wrap gap-1.5" data-testid="niche-selector-tabs">
          {niches.map((n) => {
            const Icon = LucideIcons[n.icon] || Compass;
            const isActive = activeNiche === n.key;
            return (
              <button
                key={n.key}
                onClick={() => setActiveNiche(n.key)}
                data-testid={`niche-chip-${n.key}`}
                aria-pressed={isActive}
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium border transition-colors hover:-translate-y-[1px] active:translate-y-0 ${
                  isActive
                    ? "bg-[color:var(--brand-teal)] text-white border-transparent"
                    : "bg-secondary border-border hover:border-[color:rgba(13,148,136,0.45)]"
                }`}
              >
                <Icon className="h-3.5 w-3.5" /> {n.label}
              </button>
            );
          })}
        </div>
      </div>

      {loadingVideos || searchLoading ? (
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
      ) : displayVideos.length === 0 ? (
        <EmptyState
          icon={searchResults !== null ? Search : Compass}
          title={searchResults !== null ? "No results found" : "No trending videos found right now"}
          description={
            searchResults !== null
              ? "Try a different keyword or hashtag."
              : "This niche's creators may be temporarily unavailable. Try another niche or paste a TikTok URL directly above."
          }
        />
      ) : (
        <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4 gap-4" data-testid="video-feed-grid">
          {displayVideos.map((v, i) => (
            <VideoCard
              key={v.tiktok_url}
              video={v}
              onAnalyze={handleAnalyze}
              analyzing={analyzingId === v.tiktok_url}
              index={i}
            />
          ))}
        </div>
      )}
    </div>
  );
}
