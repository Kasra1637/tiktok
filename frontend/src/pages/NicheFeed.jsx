import { useEffect, useState, useCallback, useMemo } from "react";
import { useNavigate } from "react-router-dom";
import * as LucideIcons from "lucide-react";
import { Compass, Search, SlidersHorizontal, X, BadgeAlert, Loader2, RotateCcw } from "lucide-react";
import { Skeleton } from "../components/ui/skeleton";
import { Input } from "../components/ui/input";
import { Button } from "../components/ui/button";
import VideoCard from "../components/VideoCard";
import EmptyState from "../components/EmptyState";
import PageHeader from "../components/PageHeader";
import Chip from "../components/Chip";
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

/**
 * Resolve a video's actual PUBLISH time in ms, or null if unknown.
 *
 * Two shapes reach this page and they carry the date under different keys:
 *  - niche/trending results come from our DB cache  -> `upload_timestamp`
 *  - keyword search results come straight from the scraper -> `timestamp`
 * Both are Unix epoch SECONDS.
 *
 * Note this is deliberately NOT `cached_at`, which is when *we* fetched the
 * video, not when it was posted — using that made "Newest" and the recency
 * filter meaningless.
 */
function publishedAtMs(video) {
  const secs = Number(video?.upload_timestamp ?? video?.timestamp ?? 0);
  if (!Number.isFinite(secs) || secs <= 0) return null;
  return secs * 1000;
}

/** One labelled row of filter chips inside the expandable filter panel. */
function FilterRow({ label, children }) {
  return (
    <div className="flex flex-col gap-2 sm:flex-row sm:items-center">
      <span className="eyebrow w-16 shrink-0 text-[10px]">{label}</span>
      <div className="flex flex-wrap gap-1.5">{children}</div>
    </div>
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
  // True only after the user has explicitly clicked Search and a niche fetch
  // (which hits Apify/yt-dlp) has completed for the CURRENT niche+mode combo.
  // Selecting a niche chip or switching Trending/Curated/Mixed never sets
  // this — it only flips to false again, so no video request ever fires
  // without an explicit Search click.
  const [hasLoadedNiche, setHasLoadedNiche] = useState(false);
  const navigate = useNavigate();

  // Filters
  const [showFilters, setShowFilters] = useState(false);
  const [viewFilter, setViewFilter] = useState("all");
  const [durationFilter, setDurationFilter] = useState("all");
  const [sortBy, setSortBy] = useState("virality");
  const [recencyFilter, setRecencyFilter] = useState("all");
  const [hideSponsored, setHideSponsored] = useState(true);

  // Badge count: anything the user changed away from defaults.
  const activeFilterCount = [viewFilter !== "all", durationFilter !== "all", sortBy !== "virality", recencyFilter !== "all", !hideSponsored].filter(Boolean).length;
  // Only these can actually hide results, so only these justify telling the
  // user to "adjust your filters" on an empty feed (a sort never hides
  // anything, and showing sponsored posts widens rather than narrows).
  const narrowingFilterCount = [viewFilter !== "all", durationFilter !== "all", recencyFilter !== "all"].filter(Boolean).length;

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
          setHasLoadedNiche(true);
        })
        .catch((err) => toast.error(getErrorMessage(err)))
        .finally(() => setLoadingVideos(false));
    },
    []
  );

  // Selecting a niche chip or switching Trending/Curated/Mixed only updates
  // local state here — it deliberately does NOT fetch anything. This clears
  // any previously-loaded results for the old niche/mode so stale videos
  // don't linger on screen, and resets hasLoadedNiche so the UI prompts the
  // user to click Search before the next Apify/yt-dlp request is made.
  useEffect(() => {
    setVideos([]);
    setHasLoadedNiche(false);
  }, [activeNiche, mode]);

  const handleSearch = useCallback(
    (e) => {
      if (e && typeof e.preventDefault === "function") e.preventDefault();
      const query = searchQuery.trim();

      // Keyword/hashtag search always takes priority when text is entered.
      if (query) {
        setSearchLoading(true);
        setSearchResults(null);
        api
          .searchTrending(query, 20)
          .then((data) => {
            data.sort((a, b) => (b.virality_score || 0) - (a.virality_score || 0));
            setSearchResults(data);
          })
          .catch((err) => toast.error(getErrorMessage(err)))
          .finally(() => setSearchLoading(false));
        return;
      }

      // No keyword typed — load videos for the currently selected niche.
      // This is the ONLY place a niche's videos are fetched; niche chips and
      // the mode toggle never trigger this on their own.
      if (activeNiche) {
        loadVideos(activeNiche, mode);
        return;
      }

      toast.error("Select a niche chip or type a search term, then click Search.");
    },
    [searchQuery, activeNiche, mode, loadVideos]
  );

  const clearSearch = useCallback(() => {
    setSearchResults(null);
    setSearchQuery("");
  }, []);

  // Niche browsing and keyword search are mutually exclusive contexts, and
  // handleSearch gives a typed keyword priority. So picking a niche (or
  // switching Trending/Curated/Mixed) clears any active search — otherwise
  // clicking a niche chip with text still in the box would look like it did
  // nothing, since Search would just re-run the keyword query.
  const handleSelectNiche = useCallback((nicheKey) => {
    setActiveNiche(nicheKey);
    setSearchQuery("");
    setSearchResults(null);
  }, []);

  const handleSelectMode = useCallback((modeKey) => {
    setMode(modeKey);
    setSearchQuery("");
    setSearchResults(null);
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

    // Recency filter — based on real publish date. Videos with an unknown
    // publish date are excluded rather than silently passed through, so
    // "posted in the last 7 days" actually means that.
    const recConfig = RECENCY_FILTERS.find((f) => f.key === recencyFilter);
    if (recConfig?.days) {
      const cutoff = Date.now() - recConfig.days * 24 * 60 * 60 * 1000;
      list = list.filter((v) => {
        const published = publishedAtMs(v);
        return published !== null && published >= cutoff;
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
      // Newest first, with unknown publish dates sorted to the end.
      list.sort((a, b) => {
        const ta = publishedAtMs(a);
        const tb = publishedAtMs(b);
        if (ta === null && tb === null) return 0;
        if (ta === null) return 1;
        if (tb === null) return -1;
        return tb - ta;
      });
    } else {
      list.sort((a, b) => (b.virality_score || 0) - (a.virality_score || 0));
    }

    // Guard against duplicate tiktok_urls (possible in keyword search results)
    // so React keys in the grid stay unique.
    const seen = new Set();
    return list.filter((v) => {
      const url = v.tiktok_url;
      if (!url) return true;
      if (seen.has(url)) return false;
      seen.add(url);
      return true;
    });
  }, [videos, searchResults, viewFilter, durationFilter, sortBy, recencyFilter, hideSponsored]);

  const busy = loadingVideos || searchLoading;

  return (
    <div className="space-y-6">
      <PageHeader
        icon={Compass}
        title="Discover Hooks"
        description="Browse trending TikToks and analyze what makes their hooks work."
      />

      {/* ---------- Search + filter console ---------- */}
      <div className="surface overflow-hidden rounded-2xl">
        <div className="flex flex-col gap-3 p-4">
          <div className="flex flex-col gap-2.5 lg:flex-row lg:items-center">
            <form onSubmit={handleSearch} className="flex min-w-0 flex-1 items-center gap-2">
              <div className="relative flex-1">
                <Search className="pointer-events-none absolute left-3.5 top-1/2 h-4 w-4 -translate-y-1/2 text-muted-foreground" />
                <Input
                  type="text"
                  placeholder="Search by keyword or hashtag..."
                  value={searchQuery}
                  onChange={(e) => setSearchQuery(e.target.value)}
                  className="h-10 pl-10 text-sm"
                  data-testid="search-input"
                />
              </div>
              <Button
                type="submit"
                variant="accent"
                disabled={busy || (!searchQuery.trim() && !activeNiche)}
                className="shrink-0 px-5"
                data-testid="search-button"
                title={
                  searchQuery.trim()
                    ? "Search TikTok for this keyword/hashtag"
                    : activeNiche
                    ? "Load videos for the selected niche"
                    : "Select a niche or type a keyword first"
                }
              >
                {busy ? <Loader2 className="h-4 w-4 animate-spin" /> : <Search className="h-4 w-4" />}
                <span className="hidden sm:inline">{busy ? "Searching" : "Search"}</span>
              </Button>
              {searchResults !== null && (
                <Button
                  type="button"
                  variant="secondary"
                  size="icon"
                  onClick={clearSearch}
                  title="Clear search results"
                  aria-label="Clear search results"
                  className="shrink-0"
                >
                  <X className="h-4 w-4" />
                </Button>
              )}
            </form>

            <div className="flex items-center gap-2 lg:shrink-0">
              {/* Segmented mode switch */}
              <div
                className="flex items-center gap-0.5 rounded-full border border-[color:var(--hairline)] bg-secondary/40 p-1"
                data-testid="mode-toggle"
              >
                {MODES.map((m) => (
                  <button
                    key={m.key}
                    onClick={() => handleSelectMode(m.key)}
                    data-testid={`mode-${m.key}`}
                    aria-pressed={mode === m.key}
                    className={`rounded-full px-3 py-1.5 text-[11px] font-semibold transition-colors duration-200 ${
                      mode === m.key
                        ? "bg-[color:var(--brand-teal)] text-white shadow-[var(--shadow-sm)]"
                        : "text-muted-foreground hover:text-foreground"
                    }`}
                  >
                    {m.label}
                  </button>
                ))}
              </div>

              <button
                onClick={() => setShowFilters(!showFilters)}
                className={`flex shrink-0 items-center gap-1.5 rounded-xl border px-3 py-2 text-[11px] font-semibold transition-colors duration-200 ${
                  showFilters || activeFilterCount > 0
                    ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-8)] text-[color:var(--brand-teal)]"
                    : "border-[color:var(--hairline)] text-muted-foreground hover:border-[color:var(--indigo-35)] hover:text-foreground"
                }`}
                data-testid="toggle-filters"
                aria-expanded={showFilters}
              >
                <SlidersHorizontal className="h-3.5 w-3.5" />
                Filters
                {activeFilterCount > 0 && (
                  <span className="ml-0.5 inline-flex h-4 min-w-4 items-center justify-center rounded-full bg-[color:var(--brand-teal)] px-1 text-[9px] font-bold text-white">
                    {activeFilterCount}
                  </span>
                )}
              </button>
            </div>
          </div>

          {/* Niche chips — selecting one only sets the filter, it never fetches
              on its own. Click Search to actually load videos for it. */}
          <div className="flex flex-wrap gap-1.5" data-testid="niche-selector-tabs">
            {niches.map((n) => {
              const Icon = LucideIcons[n.icon] || Compass;
              return (
                <Chip
                  key={n.key}
                  icon={Icon}
                  size="md"
                  active={activeNiche === n.key}
                  onClick={() => handleSelectNiche(n.key)}
                  testId={`niche-chip-${n.key}`}
                >
                  {n.label}
                </Chip>
              );
            })}
          </div>

          {activeNiche && !hasLoadedNiche && !loadingVideos && (
            <p
              className="flex items-center gap-1.5 rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-6)] px-3 py-2 text-[11px] text-muted-foreground"
              data-testid="niche-pending-search-hint"
            >
              <Search className="h-3 w-3 shrink-0 text-[color:var(--brand-teal)]" /> Click{" "}
              <span className="font-semibold text-foreground">Search</span> to load videos for this niche.
            </p>
          )}
        </div>

        {/* Expandable filters */}
        {showFilters && (
          <div className="space-y-3 border-t border-[color:var(--hairline)] bg-[hsl(228_14%_6%_/_0.4)] p-4">
            <FilterRow label="Sort">
              {SORT_OPTIONS.map((s) => (
                <Chip key={s.key} active={sortBy === s.key} onClick={() => setSortBy(s.key)}>
                  {s.label}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="Views">
              {VIEW_FILTERS.map((f) => (
                <Chip key={f.key} active={viewFilter === f.key} onClick={() => setViewFilter(f.key)}>
                  {f.label}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="Length">
              {DURATION_FILTERS.map((f) => (
                <Chip key={f.key} active={durationFilter === f.key} onClick={() => setDurationFilter(f.key)}>
                  {f.label}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="When">
              {RECENCY_FILTERS.map((f) => (
                <Chip key={f.key} active={recencyFilter === f.key} onClick={() => setRecencyFilter(f.key)}>
                  {f.label}
                </Chip>
              ))}
            </FilterRow>
            <FilterRow label="Ads">
              <Chip
                icon={BadgeAlert}
                active={hideSponsored}
                onClick={() => setHideSponsored((prev) => !prev)}
                testId="toggle-hide-sponsored"
              >
                {hideSponsored ? "Hiding sponsored" : "Showing sponsored"}
              </Chip>
            </FilterRow>
            {activeFilterCount > 0 && (
              <button
                onClick={resetFilters}
                className="inline-flex items-center gap-1.5 text-[11px] font-medium text-muted-foreground transition-colors hover:text-[color:var(--brand-teal)]"
              >
                <RotateCcw className="h-3 w-3" /> Reset all filters
              </button>
            )}
          </div>
        )}
      </div>

      {/* ---------- Results ---------- */}
      {!busy && displayVideos.length > 0 && (
        <div className="flex items-center justify-between gap-3">
          <p className="text-xs text-muted-foreground">
            <span className="font-semibold text-foreground">{displayVideos.length}</span> video
            {displayVideos.length !== 1 ? "s" : ""}
            {searchResults !== null ? " for your search" : activeNiche ? ` in ${activeNiche}` : ""}
          </p>
          <span className="eyebrow hidden sm:block">
            Sorted by {SORT_OPTIONS.find((s) => s.key === sortBy)?.label}
          </span>
        </div>
      )}

      {busy ? (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div key={i} className="surface overflow-hidden rounded-2xl">
              <Skeleton className="h-[280px] w-full rounded-none border-0" />
              <div className="space-y-2.5 p-4">
                <Skeleton className="h-4 w-3/4 rounded-md" />
                <Skeleton className="h-3 w-1/2 rounded-md" />
                <Skeleton className="h-10 w-full rounded-xl" />
              </div>
            </div>
          ))}
        </div>
      ) : !hasLoadedNiche && searchResults === null ? (
        <EmptyState
          icon={Compass}
          title="Pick a niche, then click Search"
          description="Select a niche chip above (or type a keyword/hashtag), then click the Search button to load videos. Nothing loads automatically — not even when you switch niches or modes."
        />
      ) : displayVideos.length === 0 ? (
        <EmptyState
          icon={searchResults !== null ? Search : Compass}
          title={searchResults !== null ? "No results found" : "No videos match your filters"}
          description={
            narrowingFilterCount > 0
              ? "Your filters are hiding everything that was loaded. Note the date filter only matches videos with a known publish date."
              : searchResults !== null
              ? "Try a different keyword or hashtag."
              : "This niche's creators may be temporarily unavailable. Try another niche or paste a TikTok URL above."
          }
          action={
            narrowingFilterCount > 0 ? (
              <Button variant="outline" onClick={resetFilters} className="gap-1.5">
                <RotateCcw className="h-3.5 w-3.5" /> Reset filters
              </Button>
            ) : null
          }
        />
      ) : (
        <div
          className="grid grid-cols-1 gap-4 sm:grid-cols-2 md:grid-cols-3 xl:grid-cols-4"
          data-testid="video-feed-grid"
        >
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
