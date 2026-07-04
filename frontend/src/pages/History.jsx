import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Skeleton } from "../components/ui/skeleton";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import EmptyState from "../components/EmptyState";
import JsonSpecPanel from "../components/JsonSpecPanel";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { Clock, Eye, Heart, ImageOff, History as HistoryIcon, Clapperboard, Film } from "lucide-react";
import { toast } from "sonner";

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
        <div>
          <Skeleton className="h-8 w-40" />
          <Skeleton className="h-4 w-72 mt-2" />
        </div>
        <div className="space-y-4">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)]">
              <div className="flex flex-col md:flex-row gap-4">
                <Skeleton className="w-full md:w-28 h-40 md:h-28 rounded-xl shrink-0" />
                <div className="flex-1 space-y-2">
                  <Skeleton className="h-4 w-3/4" />
                  <Skeleton className="h-3 w-1/2" />
                  <Skeleton className="h-3 w-2/3" />
                </div>
              </div>
            </Card>
          ))}
        </div>
      </div>
    );
  }

  if (items.length === 0) {
    return (
      <EmptyState
        icon={HistoryIcon}
        title="No analyses yet"
        description="Analyze your first hook from the niche feed to see it appear here."
      />
    );
  }

  return (
    <div className="space-y-6">
      <div>
        <h1 className="font-display text-2xl md:text-3xl font-semibold tracking-tight">History</h1>
        <p className="text-muted-foreground mt-1">Revisit past hook analyses, face swaps, and video briefs.</p>
      </div>

      <div className="space-y-4" data-testid="history-list">
        {items.map(({ video, customizations, video_jobs }) => (
          <Card
            key={video.id}
            className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)] hover:shadow-[var(--shadow-tight)] hover:border-[color:rgba(13,148,136,0.3)] transition-shadow transition-colors"
          >
            <div className="flex flex-col md:flex-row gap-4">
              {video.thumbnail_url && (
                <img
                  src={video.thumbnail_url}
                  alt={video.title}
                  className="w-full md:w-28 h-40 md:h-28 rounded-xl object-cover shrink-0"
                  onError={(e) => {
                    e.currentTarget.style.display = "none";
                  }}
                />
              )}
              <div className="flex-1 space-y-2">
                <Link
                  to={`/analysis/${video.id}`}
                  className="font-medium hover:text-[color:var(--brand-teal-dark)] hover:underline line-clamp-2 block transition-colors"
                  data-testid="history-video-link"
                >
                  {video.title}
                </Link>
                <div className="flex flex-wrap items-center gap-3 text-xs text-muted-foreground">
                  <span>@{video.creator}</span>
                  <span className="flex items-center gap-1">
                    <Eye className="h-3 w-3" /> {video.view_count}
                  </span>
                  <span className="flex items-center gap-1">
                    <Heart className="h-3 w-3" /> {video.like_count}
                  </span>
                  {video.niche && (
                    <Badge variant="secondary" className="rounded-full text-[10px]">
                      {video.niche}
                    </Badge>
                  )}
                  <span className="flex items-center gap-1">
                    <Clock className="h-3 w-3" /> {new Date(video.created_at).toLocaleDateString()}
                  </span>
                </div>
                {video.status === "failed" && (
                  <Badge variant="destructive" className="rounded-full text-[10px]">
                    Analysis failed
                  </Badge>
                )}

                {customizations.length > 0 ? (
                  <div className="space-y-1.5 pt-1">
                    <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <Film className="h-3 w-3" /> Face swaps
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {customizations.map((c) =>
                        (c.generated_images && c.generated_images.length > 0 ? c.generated_images : [{ id: c.id, image_url: c.generated_image_url }]).map(
                          (img) => (
                            <button
                              key={img.id}
                              onClick={() => setActiveCustomization(c)}
                              className="group rounded-xl overflow-hidden border border-border hover:border-[color:var(--brand-teal)] hover:shadow-[var(--shadow-tight)] transition-shadow transition-colors w-16 h-16"
                              data-testid="history-customization-thumb"
                            >
                              <img
                                src={mediaUrl(img.image_url)}
                                alt="Customization preview"
                                className="w-full h-full object-cover transition-transform duration-300 group-hover:scale-[1.08]"
                              />
                            </button>
                          )
                        )
                      )}
                    </div>
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <ImageOff className="h-3 w-3" /> No face swaps yet
                  </p>
                )}

                {video_jobs && video_jobs.length > 0 && (
                  <div className="space-y-1.5 pt-1">
                    <p className="text-xs font-medium text-muted-foreground flex items-center gap-1">
                      <Clapperboard className="h-3 w-3" /> Video briefs
                    </p>
                    <div className="flex flex-wrap gap-2">
                      {video_jobs.map((j) => (
                        <button
                          key={j.id}
                          onClick={() => setActiveVideoJob(j)}
                          data-testid="history-video-job-item"
                          className="text-xs rounded-full border border-border hover:border-[color:var(--brand-teal)] hover:bg-[color:rgba(13,148,136,0.06)] px-3 py-1.5 transition-colors"
                        >
                          {j.brand_name || "Untitled brief"} • {j.status === "pending_provider_selection" ? "Ready" : "Draft"}
                        </button>
                      ))}
                    </div>
                  </div>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!activeCustomization} onOpenChange={(o) => !o && setActiveCustomization(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Face swap detail</DialogTitle>
          </DialogHeader>
          {activeCustomization && (
            <div className="space-y-4">
              <div className="grid grid-cols-1 sm:grid-cols-2 gap-4">
                {(activeCustomization.generated_images || []).map((img) => (
                  <div key={img.id} className="rounded-2xl overflow-hidden border border-border">
                    <img src={mediaUrl(img.image_url)} alt="Generated preview" className="w-full object-contain bg-black/5 max-h-[400px]" />
                  </div>
                ))}
              </div>
              <JsonSpecPanel spec={activeCustomization.generation_spec} />
            </div>
          )}
        </DialogContent>
      </Dialog>

      <Dialog open={!!activeVideoJob} onOpenChange={(o) => !o && setActiveVideoJob(null)}>
        <DialogContent className="max-w-2xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Video brief detail</DialogTitle>
          </DialogHeader>
          {activeVideoJob && (
            <div className="space-y-3">
              <div className="flex items-center gap-2 text-xs text-muted-foreground">
                <Badge variant="secondary" className="rounded-full">{activeVideoJob.target_duration_seconds}s</Badge>
                <Badge variant="secondary" className="rounded-full">{activeVideoJob.status}</Badge>
              </div>
              <p className="text-sm font-medium">{activeVideoJob.brand_name}</p>
              <p className="text-xs text-muted-foreground">{activeVideoJob.brand_goal}</p>
              <pre className="font-mono text-xs leading-relaxed p-3 rounded-xl bg-muted whitespace-pre-wrap break-words max-h-[300px] overflow-y-auto">
                {activeVideoJob.full_prompt_text}
              </pre>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
