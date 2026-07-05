import { useEffect, useState, useCallback } from "react";
import { useParams, useNavigate } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Button } from "../components/ui/button";
import { Skeleton } from "../components/ui/skeleton";
import { Alert, AlertTitle, AlertDescription } from "../components/ui/alert";
import Filmstrip from "../components/Filmstrip";
import HookBreakdown from "../components/HookBreakdown";
import GenerationProgress from "../components/GenerationProgress";
import { api, getErrorMessage } from "../lib/api";
import { ArrowLeft, Eye, Heart, MessageCircle, AlertTriangle, RotateCcw, ExternalLink, Repeat2 } from "lucide-react";

const ANALYZE_STAGES = ["Downloading video", "Extracting first 2-3 seconds", "Analyzing hook mechanics with AI"];

function formatCount(n) {
  if (!n) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

export default function AnalysisDetail() {
  const { videoId } = useParams();
  const navigate = useNavigate();
  const [video, setVideo] = useState(null);
  const [analysis, setAnalysis] = useState(null);
  const [selectedFrame, setSelectedFrame] = useState(null);
  const [analyzing, setAnalyzing] = useState(false);
  const [error, setError] = useState(null);

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

  if (error) {
    return (
      <div className="max-w-2xl mx-auto space-y-4">
        <Button variant="ghost" onClick={() => navigate("/discover")} className="gap-1.5" data-testid="back-to-feed-button">
          <ArrowLeft className="h-4 w-4" /> Back to feed
        </Button>
        <Alert variant="destructive" className="rounded-2xl" data-testid="analysis-error-alert">
          <AlertTriangle className="h-4 w-4" />
          <AlertTitle>Hook analysis failed</AlertTitle>
          <AlertDescription>{error}</AlertDescription>
        </Alert>
        <Button onClick={runAnalysis} disabled={analyzing} className="gap-1.5" data-testid="retry-analysis-button">
          <RotateCcw className="h-4 w-4" /> Retry analysis
        </Button>
      </div>
    );
  }

  if (!video) {
    return (
      <div className="space-y-5" data-testid="analysis-detail-loading">
        <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
          <Card className="p-3 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-2 h-fit">
            <Skeleton className="w-full aspect-[9/16] rounded-xl" />
            <Skeleton className="h-5 w-4/5" />
            <Skeleton className="h-3 w-1/3" />
          </Card>
          <div className="space-y-4">
            <div className="flex gap-3">
              {Array.from({ length: 4 }).map((_, i) => (
                <Skeleton key={i} className="w-[120px] md:w-[140px] h-[160px] md:h-[190px] rounded-xl shrink-0" />
              ))}
            </div>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <Button variant="ghost" size="sm" onClick={() => navigate("/discover")} className="gap-1 -ml-2 text-muted-foreground" data-testid="back-to-feed-button">
        <ArrowLeft className="h-3.5 w-3.5" /> Back
      </Button>

      <div className="grid grid-cols-1 lg:grid-cols-[360px_1fr] gap-5">
        <Card className="p-3 rounded-2xl border-border shadow-[var(--shadow-soft)] space-y-2.5 h-fit">
          {video.thumbnail_url && (
            <img
              src={video.thumbnail_url}
              alt={video.title}
              className="w-full rounded-xl object-cover aspect-[9/16]"
              onError={(e) => {
                e.currentTarget.style.display = "none";
              }}
            />
          )}
          <h2 className="font-display text-lg font-semibold leading-snug">{video.title}</h2>
          <p className="text-sm text-muted-foreground">@{video.creator}</p>
          <div className="flex items-center gap-3 text-sm text-muted-foreground">
            <span className="flex items-center gap-1" data-testid="analysis-view-count">
              <Eye className="h-3.5 w-3.5" /> {formatCount(video.view_count)}
            </span>
            <span className="flex items-center gap-1" data-testid="analysis-like-count">
              <Heart className="h-3.5 w-3.5" /> {formatCount(video.like_count)}
            </span>
            <span className="flex items-center gap-1" data-testid="analysis-comment-count">
              <MessageCircle className="h-3.5 w-3.5" /> {formatCount(video.comment_count)}
            </span>
          </div>
          <a
            href={video.tiktok_url}
            target="_blank"
            rel="noreferrer"
            className="inline-flex items-center gap-1.5 text-sm text-[color:var(--brand-teal-dark)] hover:underline"
            data-testid="view-on-tiktok-link"
          >
            View on TikTok <ExternalLink className="h-3.5 w-3.5" />
          </a>
          {analysis && (
            <div className="pt-2 border-t border-border">
              <div className="flex items-center justify-between">
                <span className="text-sm font-medium">Effectiveness Score</span>
                <Badge
                  className="rounded-full px-2.5 py-1 text-xs font-semibold bg-[color:rgba(244,63,94,0.15)] text-[color:#9F1239] border-none"
                  data-testid="effectiveness-score-badge"
                >
                  {analysis.effectiveness_score}/10
                </Badge>
              </div>
            </div>
          )}
          {analysis && selectedFrame && (
            <Button
              onClick={() => {
                const frame = analysis.frames.find((f) => f.index === selectedFrame);
                if (frame) {
                  navigate(`/face-swap?target=${encodeURIComponent(frame.media_url)}&videoId=${videoId}&frame=${selectedFrame}`);
                }
              }}
              className="w-full gap-2 rounded-xl bg-[color:var(--brand-coral)] hover:bg-[#E11D48] text-white"
              data-testid="face-swap-hook-button"
            >
              <Repeat2 className="h-4 w-4" /> Face Swap
            </Button>
          )}
        </Card>

        <div className="space-y-5">
          {analyzing || !analysis ? (
            <Card className="p-6 rounded-2xl border-border shadow-[var(--shadow-soft)]">
              <h3 className="font-display font-semibold mb-3">Analyzing hook...</h3>
              <GenerationProgress stages={ANALYZE_STAGES} active={true} />
            </Card>
          ) : (
            <>
              <Filmstrip frames={analysis.frames} selectedIndex={selectedFrame} onSelect={setSelectedFrame} />
              <HookBreakdown analysis={analysis} />
            </>
          )}
        </div>
      </div>
    </div>
  );
}
