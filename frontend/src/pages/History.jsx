import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import EmptyState from "../components/EmptyState";
import JsonSpecPanel from "../components/JsonSpecPanel";
import PageHeader from "../components/PageHeader";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { Clock, Eye, Heart, MessageCircle, ImageOff, History as HistoryIcon, Clapperboard, Film, ArrowRight } from "lucide-react";
import { toast } from "sonner";

function formatCount(n) {
  if (!n) return "0";
  if (n >= 1000000) return `${(n / 1000000).toFixed(1)}M`;
  if (n >= 1000) return `${(n / 1000).toFixed(1)}K`;
  return `${n}`;
}

function MetaItem({ icon: Icon, children, testId }) {
  return (
    <span className="inline-flex items-center gap-1 text-xs text-muted-foreground" data-testid={testId}>
      <Icon className="h-3 w-3" />
      {children}
    </span>
  );
}

export default function History() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeCustomization, setActiveCustomization] = useState(null);
  const [activeVideoJob, setActiveVideoJob] = useState(null);

  useEffect(() => {
    api
      .getHistory()
      .then(setItems)
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) {
    return (
      <div className="space-y-6" data-testid="history-loading">
        <Skeleton className="h-10 w-52 rounded-xl" />
        <div className="space-y-3">
          {Array.from({ length: 3 }).map((_, i) => (
            <div key={i} className="surface rounded-2xl p-4">
              <div className="flex flex-col gap-4 md:flex-row">
                <Skeleton className="h-32 w-full shrink-0 rounded-xl md:h-28 md:w-28" />
                <div className="flex-1 space-y-2.5">
                  <Skeleton className="h-4 w-3/4 rounded-md" />
                  <Skeleton className="h-3 w-1/2 rounded-md" />
                  <Skeleton className="h-3 w-2/5 rounded-md" />
                </div>
              </div>
            </div>
          ))}
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <div className="space-y-6">
        <PageHeader
          icon={HistoryIcon}
          title="History"
          description="Every hook you've analyzed, face-swapped, or turned into a video brief."
        />
        <EmptyState
          icon={HistoryIcon}
          title="No analyses yet"
          description="Analyze your first hook from the niche feed to see it appear here."
        />
      </div>
    );
  }

  return (
    <div className="space-y-6">
      <PageHeader
        icon={HistoryIcon}
        title="History"
        description="Every hook you've analyzed, face-swapped, or turned into a video brief — nothing is lost between sessions."
        actions={
          <Badge variant="secondary" className="px-3 py-1">
            {items.length} {items.length === 1 ? "video" : "videos"}
          </Badge>
        }
      />

      <div className="space-y-3" data-testid="history-list">
        {items.map(({ video, customizations, video_jobs }) => (
          <div key={video.id} className="surface surface-interactive rounded-2xl p-4">
            <div className="flex flex-col gap-4 md:flex-row">
              <Link
                to={`/analysis/${video.id}`}
                className="relative block h-40 w-full shrink-0 overflow-hidden rounded-xl md:h-28 md:w-28"
              >
                {video.thumbnail_url ? (
                  <img
                    src={video.thumbnail_url}
                    alt={video.title}
                    className="h-full w-full object-cover transition-transform duration-500 ease-out-expo hover:scale-[1.06]"
                    onError={(e) => {
                      e.currentTarget.style.display = "none";
                    }}
                  />
                ) : (
                  <div className="flex h-full w-full items-center justify-center bg-gradient-to-b from-secondary/60 to-muted">
                    <ImageOff className="h-5 w-5 text-muted-foreground/50" />
                  </div>
                )}
              </Link>

              <div className="min-w-0 flex-1 space-y-2.5">
                <div className="flex items-start justify-between gap-3">
                  <Link
                    to={`/analysis/${video.id}`}
                    className="font-display line-clamp-2 block font-semibold leading-snug transition-colors hover:text-[color:var(--brand-teal)]"
                    data-testid="history-video-link"
                  >
                    {video.title}
                  </Link>
                  {video.status === "failed" && (
                    <Badge variant="destructive" className="shrink-0 text-[10px]">
                      Analysis failed
                    </Badge>
                  )}
                </div>

                <div className="flex flex-wrap items-center gap-x-3.5 gap-y-1.5">
                  <span className="text-xs font-medium text-foreground/80">@{video.creator}</span>
                  <MetaItem icon={Eye} testId="history-view-count">{formatCount(video.view_count)}</MetaItem>
                  <MetaItem icon={Heart} testId="history-like-count">{formatCount(video.like_count)}</MetaItem>
                  <MetaItem icon={MessageCircle} testId="history-comment-count">{formatCount(video.comment_count)}</MetaItem>
                  {video.niche && (
                    <Badge variant="indigo" className="text-[10px]">
                      {video.niche}
                    </Badge>
                  )}
                  <MetaItem icon={Clock}>{new Date(video.created_at).toLocaleDateString()}</MetaItem>
                </div>

                <div className="grid gap-3 border-t border-[color:var(--hairline)] pt-3 sm:grid-cols-2">
                  {/* Face swaps */}
                  <div className="space-y-2">
                    <p className="eyebrow flex items-center gap-1.5">
                      <Film className="h-3 w-3" /> Face swaps
                    </p>
                    {customizations.length > 0 ? (
                      <div className="flex flex-wrap gap-2">
                        {customizations.map((c) =>
                          (c.generated_images && c.generated_images.length > 0 ? c.generated_images : [{ id: c.id, image_url: c.generated_image_url }]).map(
                            (img) => (
                              <button
                                key={img.id}
                                onClick={() => setActiveCustomization(c)}
                                className="group h-16 w-16 overflow-hidden rounded-xl border border-[color:var(--hairline)] transition-colors hover:border-[color:var(--brand-teal)]"
                                data-testid="history-customization-thumb"
                              >
                                <img
                                  src={mediaUrl(img.image_url)}
                                  alt="Customization preview"
                                  className="h-full w-full object-cover transition-transform duration-300 group-hover:scale-[1.1]"
                                />
                              </button>
                            )
                          )
                        )}
                      </div>
                    ) : (
                      <p className="flex items-center gap-1.5 text-xs text-muted-foreground">
                        <ImageOff className="h-3 w-3" /> No face swaps yet
                      </p>
                    )}
                  </div>

                  {/* Video briefs */}
                  {video_jobs && video_jobs.length > 0 && (
                    <div className="space-y-2">
                      <p className="eyebrow flex items-center gap-1.5">
                        <Clapperboard className="h-3 w-3" /> Video briefs
                      </p>
                      <div className="flex flex-wrap gap-2">
                        {video_jobs.map((j) => (
                          <button
                            key={j.id}
                            onClick={() => setActiveVideoJob(j)}
                            data-testid="history-video-job-item"
                            className="inline-flex items-center gap-1.5 rounded-full border border-[color:var(--hairline)] bg-secondary/40 px-3 py-1.5 text-xs transition-colors hover:border-[color:var(--brand-teal)] hover:bg-[color:var(--indigo-8)]"
                          >
                            <span className="max-w-[140px] truncate font-medium">
                              {j.brand_name || "Untitled brief"}
                            </span>
                            <span
                              className={`inline-block h-1.5 w-1.5 rounded-full ${
                                j.status === "pending_provider_selection" ? "bg-emerald-400" : "bg-amber-400"
                              }`}
                            />
                            <span className="text-muted-foreground">
                              {j.status === "pending_provider_selection" ? "Ready" : "Draft"}
                            </span>
                            <ArrowRight className="h-3 w-3 text-muted-foreground" />
                          </button>
                        ))}
                      </div>
                    </div>
                  )}
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      <Dialog open={!!activeCustomization} onOpenChange={(o) => !o && setActiveCustomization(null)}>
        <DialogContent className="max-h-[85vh] max-w-3xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Face swap detail</DialogTitle>
          </DialogHeader>
          {activeCustomization && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
                {(activeCustomization.generated_images || []).map((img) => (
                  <div
                    key={img.id}
                    className="overflow-hidden rounded-2xl border border-[color:var(--hairline)] bg-black/20"
                  >
                    <img
                      src={mediaUrl(img.image_url)}
                      alt="Generated preview"
                      className="max-h-[400px] w-full object-contain"
                    />
                  </div>
                ))}
              </div>
              <JsonSpecPanel spec={activeCustomization.generation_spec} />
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!activeVideoJob} onOpenChange={(o) => !o && setActiveVideoJob(null)}>
        <DialogContent className="max-h-[85vh] max-w-2xl overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Video brief detail</DialogTitle>
          </DialogHeader>
          {activeVideoJob && (
            <div className="space-y-3.5">
              <div className="flex flex-wrap items-center gap-2">
                <Badge variant="indigo">{activeVideoJob.target_duration_seconds}s</Badge>
                <Badge variant="secondary">{activeVideoJob.status}</Badge>
              </div>
              <div>
                <p className="font-display text-base font-semibold">{activeVideoJob.brand_name}</p>
                <p className="mt-0.5 text-xs text-muted-foreground">{activeVideoJob.brand_goal}</p>
              </div>
              <div className="surface-sunken rounded-xl">
                <pre className="max-h-[300px] overflow-y-auto whitespace-pre-wrap break-words p-3.5 font-mono text-xs leading-relaxed text-muted-foreground">
                  {activeVideoJob.full_prompt_text}
                </pre>
              </div>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
