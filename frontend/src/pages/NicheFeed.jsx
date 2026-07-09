import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import * as LucideIcons from "lucide-react";
import { Compass, Search, SlidersHorizontal, X, BadgeAlert } from "lucide-react";
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

const VIEW_FILTERS = [
  { key: "all", label: "All" },
  { key: "1m", label: "1M+", min: 1000000 },
  { key: "5m", label: "5M+", min: 5000000 },
  { key: "10m", label: "10M+", min: 10000000 },
];

const DURATION_FILTERS = [
  { key: "all", label: "All" },
  { key: "short", label: "<15s", max: 15 },
  { key: "medium", label: "15-60s", min: 15, max: 60 },
  { key: "long", label: "60s+", min: 60 },
];

const SORT_OPTIONS = [
  { key: "virality", label: "Virality" },
  { key: "views", label: "Views" },
  { key: "likes", label: "Likes" },
  { key: "engagement", label: "Engagement" },
  { key: "newest", label: "Newest" },
];

const RECENCY_FILTERS = [
  { key: "all", label: "All time" },
  { key: "7d", label: "7 days", days: 7 },
  { key: "30d", label: "30 days", days: 30 },
  { key: "90d", label: "90 days", days: 90 },
];

function FilterChip({ label, active, onClick }) {
  return (
    <button
      onClick={onClick}
      className={`rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
        active ? "bg-[color:var(--brand-teal)] text-white" : "bg-secondary text-muted-foreground hover:text-foreground"
      }`}
    >
      {label}
    </button>
  );
}

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

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [viewFilter, setViewFilter] = useState("all");
  const [durationFilter, setDurationFilter] = useState("all");
  const [sortBy, setSortBy] = useState("virality");
  const [recencyFilter, setRecencyFilter] = useState("all");
  const [hideSponsored, setHideSponsored] = useState(true);

  const activeFilterCount = [viewFilter !== "all", durationFilter !== "all", sortBy !== "virality", recencyFilter !== "all", !hideSponsored].filter(Boolean).length;

  useEffect(() => {
    api
      .getNiches()
      .then((data) => {
        setNiches(data);
        // Intentionally do NOT auto-select a niche (e.g. "fitness") here.
        // Leave activeNiche as null until the user explicitly picks a niche
        // chip, or searches by keyword/hashtag — this avoids kicking off an
        // unwanted video fetch/generation the moment the page loads.
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

  const resetFilters = () => {
    setViewFilter("all");
    setDurationFilter("all");
    setSortBy("virality");
    setRecencyFilter("all");
    setHideSponsored(true);
  };

  // Apply filters and sorting client-side
  const displayVideos = useMemo(() => {
    let list = searchResults !== null ? [...searchResults] : [...videos];

    // Sponsored / ad post filter
    if (hideSponsored) {
      list = list.filter((v) => !v.is_ad);
    }

    // View count filter
    const viewConfig = VIEW_FILTERS.find((f) => f.key === viewFilter);
    if (viewConfig?.min) {
      list = list.filter((v) => (v.view_count || 0) >= viewConfig.min);
    }

    // Duration filter
    const durConfig = DURATION_FILTERS.find((f) => f.key === durationFilter);
    if (durConfig?.max && !durConfig?.min) {
      list = list.filter((v) => (v.duration || 0) > 0 && (v.duration || 0) <= durConfig.max);
    } else if (durConfig?.min && durConfig?.max) {
      list = list.filter((v) => (v.duration || 0) >= durConfig.min && (v.duration || 0) <= durConfig.max);
    } else if (durConfig?.min && !durConfig?.max) {
      list = list.filter((v) => (v.duration || 0) >= durConfig.min);
    }

    // Recency filter
    const recConfig = RECENCY_FILTERS.find((f) => f.key === recencyFilter);
    if (recConfig?.days) {
      const cutoff = Date.now() - recConfig.days * 24 * 60 * 60 * 1000;
      list = list.filter((v) => {
        const cached = v.cached_at ? new Date(v.cached_at).getTime() : Date.now();
        return cached >= cutoff;
      });
    }

    // Sort
    if (sortBy === "views") {
      list.sort((a, b) => (b.view_count || 0) - (a.view_count || 0));
    } else if (sortBy === "likes") {
      list.sort((a, b) => (b.like_count || 0) - (a.like_count || 0));
    } else if (sortBy === "engagement") {
      const eng = (v) => {
        const views = v.view_count || 1;
        return ((v.like_count || 0) + (v.comment_count || 0) + (v.share_count || 0)) / views;
      };
      list.sort((a, b) => eng(b) - eng(a));
    } else if (sortBy === "newest") {
      list.sort((a, b) => {
        const ta = a.cached_at ? new Date(a.cached_at).getTime() : 0;
        const tb = b.cached_at ? new Date(b.cached_at).getTime() : 0;
        return tb - ta;
      });
    } else {
      list.sort((a, b) => (b.virality_score || 0) - (a.virality_score || 0));
    }

    return list;
  }, [videos, searchResults, viewFilter, durationFilter, sortBy, recencyFilter, hideSponsored]);

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
              className="rounded-lg px-3 py-1.5 text-sm font-medium bg-[color:var(--brand-teal)] hover:bg-[color:var(--brand-teal-dark)] text-white disabled:opacity-50 transition-colors"
              data-testid="search-button"
            >
              {searchLoading ? "..." : "Search"}
            </button>
            {searchResults !== null && (
              <button type="button" onClick={clearSearch} className="rounded-lg px-2.5 py-1.5 text-sm border border-border hover:bg-muted transition-colors">
                <X className="h-3.5 w-3.5" />
              </button>
            )}
          </form>

          <div className="flex items-center gap-2 shrink-0">
            <div className="flex items-center gap-1 rounded-full border border-border p-0.5 bg-secondary" data-testid="mode-toggle">
              {MODES.map((m) => (
                <button
                  key={m.key}
                  onClick={() => setMode(m.key)}
                  data-testid={`mode-${m.key}`}
                  aria-pressed={mode === m.key}
                  className={`rounded-full px-3 py-1 text-[11px] font-medium transition-colors ${
                    mode === m.key ? "bg-[color:var(--brand-teal)] text-white" : "text-muted-foreground hover:text-foreground"
                  }`}
                >
                  {m.label}
                </button>
              ))}
            </div>
            <button
              onClick={() => setShowFilters(!showFilters)}
              className={`flex items-center gap-1.5 rounded-lg px-2.5 py-1.5 text-[11px] font-medium border transition-colors ${
                showFilters || activeFilterCount > 0 ? "border-[color:var(--brand-teal)] text-[color:var(--brand-teal)]" : "border-border text-muted-foreground hover:text-foreground"
              }`}
              data-testid="toggle-filters"
            >
              <SlidersHorizontal className="h-3.5 w-3.5" />
              Filters{activeFilterCount > 0 && ` (${activeFilterCount})`}
            </button>
          </div>
        </div>

        {/* Expandable filters */}
        {showFilters && (
          <div className="space-y-2.5 pt-1 border-t border-border">
            {/* Sort */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide w-14 shrink-0">Sort</span>
              {SORT_OPTIONS.map((s) => <FilterChip key={s.key} label={s.label} active={sortBy === s.key} onClick={() => setSortBy(s.key)} />)}
            </div>
            {/* Views */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide w-14 shrink-0">Views</span>
              {VIEW_FILTERS.map((f) => <FilterChip key={f.key} label={f.label} active={viewFilter === f.key} onClick={() => setViewFilter(f.key)} />)}
            </div>
            {/* Duration */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide w-14 shrink-0">Length</span>
              {DURATION_FILTERS.map((f) => <FilterChip key={f.key} label={f.label} active={durationFilter === f.key} onClick={() => setDurationFilter(f.key)} />)}
            </div>
            {/* Recency */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide w-14 shrink-0">When</span>
              {RECENCY_FILTERS.map((f) => <FilterChip key={f.key} label={f.label} active={recencyFilter === f.key} onClick={() => setRecencyFilter(f.key)} />)}
            </div>
            {/* Sponsored content toggle */}
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-[10px] font-semibold text-muted-foreground uppercase tracking-wide w-14 shrink-0">Ads</span>
              <button
                onClick={() => setHideSponsored((prev) => !prev)}
                data-testid="toggle-hide-sponsored"
                aria-pressed={hideSponsored}
                className={`flex items-center gap-1.5 rounded-full px-2.5 py-1 text-[11px] font-medium transition-colors ${
                  hideSponsored ? "bg-[color:var(--brand-teal)] text-white" : "bg-secondary text-muted-foreground hover:text-foreground"
                }`}
              >
                <BadgeAlert className="h-3 w-3" />
                {hideSponsored ? "Hiding sponsored" : "Showing sponsored"}
              </button>
            </div>
            {activeFilterCount > 0 && (
              <button onClick={resetFilters} className="text-[11px] text-muted-foreground hover:text-foreground underline">Reset all filters</button>
            )}
          </div>
        )}

        {/* Niche chips */}
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
                className={`flex items-center gap-1.5 rounded-full px-3 py-1.5 text-sm font-medium border transition-colors ${
                  isActive
                    ? "bg-[color:var(--brand-teal)] text-white border-transparent"
                    : "bg-secondary border-border hover:border-[color:rgba(129,140,248,0.4)]"
                }`}
              >
                <Icon className="h-3.5 w-3.5" /> {n.label}
              </button>
            );
          })}
        </div>
      </div>

      {/* Results count */}
      {!loadingVideos && !searchLoading && displayVideos.length > 0 && (
        <p className="text-xs text-muted-foreground">{displayVideos.length} video{displayVideos.length !== 1 ? "s" : ""}</p>
      )}

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
      ) : !activeNiche && searchResults === null ? (
        <EmptyState
          icon={Compass}
          title="Pick a niche or search to get started"
          description="Select a niche chip above, or search by keyword/hashtag, to load videos. Nothing loads automatically."
        />
      ) : displayVideos.length === 0 ? (
        <EmptyState
          icon={searchResults !== null ? Search : Compass}
          title={searchResults !== null ? "No results found" : "No videos match your filters"}
          description={
            searchResults !== null
              ? "Try a different keyword or hashtag."
              : activeFilterCount > 0
              ? "Try adjusting your filters or selecting a different niche."
              : "This niche's creators may be temporarily unavailable. Try another niche or paste a TikTok URL above."
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
