import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import Filmstrip from "../components/Filmstrip";
import HookBreakdown from "../components/HookBreakdown";
import GenerationProgress from "../components/GenerationProgress";
import SaveHookTemplateDialog from "../components/SaveHookTemplateDialog";
import { api, getErrorMessage } from "../lib/api";
import { ArrowLeft, Eye, Heart, MessageCircle, AlertTriangle, RotateCcw, ExternalLink, Repeat2, Music2, FileText, BadgeAlert, Bookmark, BookmarkCheck, Sparkles, ImageOff } from "lucide-react";

const ANALYZE_STAGES = ["Downloading video", "Extracting first 2-3 seconds", "Analyzing hook mechanics with AI"];

function formatCount(n) {
  if (!n) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

/** Score colour ramp mirrors VideoCard's virality thresholds. */
function scoreTone(score) {
  if (score >= 8) return { ring: "var(--brand-coral)", text: "text-[color:var(--brand-coral)]", label: "Strong" };
  if (score >= 5) return { ring: "var(--brand-indigo)", text: "text-[color:var(--brand-indigo)]", label: "Decent" };
  return { ring: "hsl(var(--muted-foreground))", text: "text-muted-foreground", label: "Weak" };
}

/** Radial score dial — replaces the old flat text badge. */
function EffectivenessScore({ score }) {
  const tone = scoreTone(score);
  const pct = Math.max(0, Math.min(100, (score / 10) * 100));

  return (
    <div
      className="flex items-center gap-3.5 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 p-3"
      data-testid="effectiveness-score-badge"
    >
      <div
        className="relative flex h-14 w-14 shrink-0 items-center justify-center rounded-full"
        style={{
          background: `conic-gradient(${tone.ring} ${pct}%, hsl(var(--secondary)) ${pct}% 100%)`,
        }}
      >
        <span className="flex h-11 w-11 flex-col items-center justify-center rounded-full bg-card">
          <span className={`font-display text-base font-bold leading-none ${tone.text}`}>{score}</span>
          <span className="text-xs leading-none text-muted-foreground">/ 10</span>
        </span>
      </div>
      <div className="min-w-0">
        <span className="eyebrow block">Effectiveness</span>
        <p className="mt-0.5 text-sm font-semibold">{tone.label} hook</p>
        <p className="text-xs leading-snug text-muted-foreground">Scroll-stopping potential</p>
      </div>
    </div>
  );
}

/** Small labelled metadata card used for sound + transcript signals. */
function SignalRow({ icon: Icon, label, value, testId, title }) {
  return (
    <div
      className="flex items-center gap-2.5 rounded-xl border border-[color:var(--hairline)] bg-secondary/30 px-3 py-2.5"
      data-testid={testId}
      title={title}
    >
      <span className="flex h-8 w-8 shrink-0 items-center justify-center rounded-lg border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
        <Icon className="h-3.5 w-3.5" />
      </span>
      <div className="min-w-0">
        <p className="eyebrow">{label}</p>
        <p className="truncate text-[13px] font-medium">{value}</p>
      </div>
    </div>
  );
}

export default function AnalysisDetail() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const [video, setVideo] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [selectedFrame, setSelectedFrame] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);
  const [saveTemplateOpen, setSaveTemplateOpen] = useState(false);
  const [savedTemplates, setSavedTemplates] = useState([]);
  const [thumbFailed, setThumbFailed] = useState(false);

  const runAnalysis = useCallback(async () => {
    setAnalyzing(true);
    setError(null);
    try {
      const result = await api.analyzeHook(videoId);
      setAnalysis(result);
      setSelectedFrame(result.key_hook_frame_index);
    } catch (err) {
      setError(getErrorMessage(err));
    } finally {
      setAnalyzing(false);
    }
  }, [videoId]);

  useEffect(() => {
    let cancelled = false;
    api
      .getVideo(videoId)
      .then(async (v) => {
        if (cancelled) return;
        setVideo(v);
        if (v.status === "analyzed") {
          try {
            const a = await api.getAnalysis(videoId);
            if (cancelled) return;
            setAnalysis(a);
            setSelectedFrame(a.key_hook_frame_index);
          } catch (err) {
            runAnalysis();
          }
        } else {
          runAnalysis();
        }
      })
      .catch((err) => setError(getErrorMessage(err)));
    return () => {
      cancelled = true;
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [videoId]);

  // Check if this hook is already bookmarked.
  useEffect(() => {
    let cancelled = false;
    api
      .getBookmarks({ source_video_id: videoId })
      .then((rows) => {
        if (!cancelled) setSavedTemplates(rows || []);
      })
      .catch(() => {});
    return () => {
      cancelled = true;
    };
  }, [videoId]);

  if (error) {
    return (
      <div className="mx-auto max-w-2xl space-y-4">
        <Button variant="ghost" onClick={() => navigate("/discover")} className="-ml-2 gap-1.5" data-testid="back-to-feed-button">
          <ArrowLeft className="h-4 w-4" /> Back to feed
        </Button>
        <Alert variant="destructive" data-testid="analysis-error-alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Hook analysis failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={runAnalysis} disabled={analyzing} variant="accent" className="gap-1.5" data-testid="retry-analysis-button">
          <RotateCcw className="h-4 w-4" /> Retry analysis
        </Button>
      </div>
    );
  }

  if (!video) {
    return (
      <div className="space-y-5" data-testid="analysis-detail-loading">
        <Skeleton className="h-8 w-24 rounded-xl" />
        <div className="grid grid-cols-1 gap-5 lg:grid-cols-[380px_1fr]">
          <div className="surface h-fit space-y-3 rounded-2xl p-4">
            <Skeleton className="aspect-[9/16] w-full rounded-xl" />
            <Skeleton className="h-5 w-4/5 rounded-md" />
            <Skeleton className="h-3 w-1/3 rounded-md" />
            <Skeleton className="h-10 w-full rounded-xl" />
          </div>
          <div className="space-y-4">
            <div className="surface rounded-2xl p-4">
              <div className="flex gap-3">
                {Array.from({ length: 4 }).map((_, i) => (
                  <Skeleton key={i} className="h-[160px] w-[120px] shrink-0 rounded-xl md:h-[190px] md:w-[140px]" />
                ))}
              </div>
            </div>
            <Skeleton className="h-24 w-full rounded-2xl" />
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Button
        variant="ghost"
        size="sm"
        onClick={() => navigate("/discover")}
        className="-ml-2 gap-1 text-muted-foreground"
        data-testid="back-to-feed-button"
      >
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </Button>

      <div className="grid grid-cols-1 gap-5 lg:grid-cols-[380px_1fr]">
        {/* ---------- Left rail: the source video ---------- */}
        <div className="surface h-fit space-y-3.5 rounded-2xl p-4">
          <div className="relative overflow-hidden rounded-xl">
            {video.thumbnail_url && !thumbFailed ? (
              <img
                src={video.thumbnail_url}
                alt={video.title}
                className="aspect-[9/16] w-full object-cover"
                onError={() => setThumbFailed(true)}
              />
            ) : (
              <div className="flex aspect-[9/16] w-full items-center justify-center bg-gradient-to-b from-secondary/60 to-muted">
                <ImageOff className="h-7 w-7 text-muted-foreground/50" />
              </div>
            )}
            {/* Stat strip laid over the poster, matching the feed cards */}
            <div
              aria-hidden="true"
              className="pointer-events-none absolute inset-x-0 bottom-0 h-24 bg-gradient-to-t from-black/85 to-transparent"
            />
            <div className="absolute inset-x-3 bottom-3 flex flex-wrap items-center gap-1.5">
              <span
                className="inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-xs font-semibold text-white backdrop-blur-sm"
                data-testid="analysis-view-count"
              >
                <Eye className="h-3 w-3" /> {formatCount(video.view_count)}
              </span>
              <span
                className="inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-xs font-semibold text-white backdrop-blur-sm"
                data-testid="analysis-like-count"
              >
                <Heart className="h-3 w-3" /> {formatCount(video.like_count)}
              </span>
              <span
                className="inline-flex items-center gap-1 rounded-full bg-black/55 px-2 py-0.5 text-xs font-semibold text-white backdrop-blur-sm"
                data-testid="analysis-comment-count"
              >
                <MessageCircle className="h-3 w-3" /> {formatCount(video.comment_count)}
              </span>
            </div>
            {video.is_ad && (
              <Badge
                className="absolute left-3 top-3 border-transparent bg-amber-500/90 text-xs font-semibold text-white shadow-[var(--shadow-sm)]"
                data-testid="analysis-sponsored-badge"
                title="This post is flagged as an ad or sponsored content"
              >
                <BadgeAlert className="h-2.5 w-2.5" />
                Sponsored
              </Badge>
            )}
          </div>

          <div className="space-y-2">
            <h2 className="font-display text-[17px] font-semibold leading-snug">{video.title}</h2>
            <div className="flex items-center gap-2">
              <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-[color:var(--indigo-10)] text-xs font-bold uppercase text-[color:var(--brand-indigo)]">
                {(video.creator || "?").charAt(0)}
              </span>
              <p className="truncate text-sm text-muted-foreground">@{video.creator}</p>
              <a
                href={video.tiktok_url}
                target="_blank"
                rel="noreferrer"
                className="ml-auto inline-flex shrink-0 items-center gap-1 text-xs font-medium text-[color:var(--brand-indigo)] transition-colors hover:text-[color:var(--brand-indigo-dark)]"
                data-testid="view-on-tiktok-link"
              >
                TikTok <ExternalLink className="h-3 w-3" />
              </a>
            </div>
          </div>

          {(video.song_title || video.song_artist) && (
            <SignalRow
              icon={Music2}
              label="Original sound"
              testId="original-sound-card"
              value={`${video.song_title || "Untitled sound"}${video.song_artist ? ` — ${video.song_artist}` : ""}`}
            />
          )}

          {video.subtitles_url && (
            <SignalRow
              icon={FileText}
              label="Transcript-informed"
              testId="transcript-informed-card"
              title="A transcript was found for this video and was used to ground the hook analysis"
              value="Analysis uses the video's actual spoken words"
            />
          )}

          {analysis && <EffectivenessScore score={analysis.effectiveness_score} />}

          {analysis && selectedFrame && (
            <Button
              onClick={() => {
                const frame = analysis.frames.find((f) => f.index === selectedFrame);
                if (frame) {
                  navigate(`/face-swap?target=${encodeURIComponent(frame.media_url)}&videoId=${videoId}&frame=${selectedFrame}`);
                }
              }}
              variant="brand"
              className="w-full"
              data-testid="face-swap-hook-button"
            >
              <Repeat2 className="h-4 w-4" /> Face Swap This Hook
            </Button>
          )}

          {analysis && (
            <>
              <Button
                variant="outline"
                onClick={() => setSaveTemplateOpen(true)}
                className="w-full"
                data-testid="bookmark-hook-button"
              >
                {savedTemplates.length > 0 ? (
                  <>
                    <BookmarkCheck className="h-4 w-4 text-[color:var(--brand-indigo)]" /> Bookmark Again
                  </>
                ) : (
                  <>
                    <Bookmark className="h-4 w-4" /> Bookmark This Hook
                  </>
                )}
              </Button>
              {savedTemplates.length > 0 && (
                <button
                  onClick={() => navigate("/bookmarks")}
                  className="w-full text-center text-xs text-muted-foreground transition-colors hover:text-[color:var(--brand-indigo)]"
                  data-testid="view-bookmarks-link"
                >
                  Already bookmarked {savedTemplates.length === 1 ? "once" : `${savedTemplates.length} times`} — view bookmarks
                </button>
              )}
            </>
          )}
        </div>

        {/* ---------- Right column: the breakdown ---------- */}
        <div className="min-w-0 space-y-5">
          {analyzing || !analysis ? (
            <div className="surface rounded-2xl p-6">
              <div className="mb-5 flex items-center gap-3">
                <span className="flex h-10 w-10 items-center justify-center rounded-xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)]">
                  <Sparkles className="h-[18px] w-[18px] animate-pulse" />
                </span>
                <div>
                  <h3 className="font-display font-semibold">Analyzing hook...</h3>
                  <p className="text-xs text-muted-foreground">
                    Reading the first 2&ndash;3 seconds frame by frame
                  </p>
                </div>
              </div>
              <GenerationProgress stages={ANALYZE_STAGES} active={true} />
            </div>
          ) : (
            <>
              <Filmstrip frames={analysis.frames} selectedIndex={selectedFrame} onSelect={setSelectedFrame} />
              <HookBreakdown analysis={analysis} />
            </>
          )}
        </div>
      </div>

      <SaveHookTemplateDialog
        open={saveTemplateOpen}
        onOpenChange={setSaveTemplateOpen}
        videoId={videoId}
        analysis={analysis}
        video={video}
        onSaved={(saved) => setSavedTemplates((prev) => [saved, ...prev])}
      />
    </div>
  );
}
