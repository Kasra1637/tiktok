import { useEffect, useState } from "react";
import { Link } from "react-router-dom";
import { Card } from "../components/ui/card";
import { Badge } from "../components/ui/badge";
import { Dialog, DialogContent, DialogHeader, DialogTitle } from "../components/ui/dialog";
import EmptyState from "../components/EmptyState";
import SideBySideCompare from "../components/SideBySideCompare";
import JsonSpecPanel from "../components/JsonSpecPanel";
import { api, mediaUrl, getErrorMessage } from "../lib/api";
import { Clock, Eye, Heart, ImageOff, History as HistoryIcon } from "lucide-react";
import { toast } from "sonner";

export default function History() {
  const [items, setItems] = useState([]);
  const [loading, setLoading] = useState(true);
  const [activeCustomization, setActiveCustomization] = useState(null);

  useEffect(() => {
    api
      .getHistory()
      .then(setItems)
      .catch((err) => toast.error(getErrorMessage(err)))
      .finally(() => setLoading(false));
  }, []);

  if (loading) return <p className="text-muted-foreground">Loading history...</p>;

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
        <p className="text-muted-foreground mt-1">Revisit past hook analyses and customizations.</p>
      </div>

      <div className="space-y-4" data-testid="history-list">
        {items.map(({ video, analysis_count, customizations }) => (
          <Card key={video.id} className="p-4 md:p-5 rounded-2xl border-border shadow-[var(--shadow-soft)]">
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
                  className="font-medium hover:text-[color:var(--brand-teal-dark)] hover:underline line-clamp-2 block"
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
                  <div className="flex flex-wrap gap-2 pt-1">
                    {customizations.map((c) => (
                      <button
                        key={c.id}
                        onClick={() => setActiveCustomization(c)}
                        className="rounded-xl overflow-hidden border border-border hover:border-[color:var(--brand-teal)] transition-colors w-16 h-16"
                        data-testid="history-customization-thumb"
                      >
                        <img src={mediaUrl(c.generated_image_url)} alt="Customization preview" className="w-full h-full object-cover" />
                      </button>
                    ))}
                  </div>
                ) : (
                  <p className="text-xs text-muted-foreground flex items-center gap-1">
                    <ImageOff className="h-3 w-3" /> No customizations yet
                  </p>
                )}
              </div>
            </div>
          </Card>
        ))}
      </div>

      <Dialog open={!!activeCustomization} onOpenChange={(o) => !o && setActiveCustomization(null)}>
        <DialogContent className="max-w-3xl max-h-[85vh] overflow-y-auto">
          <DialogHeader>
            <DialogTitle>Customization detail</DialogTitle>
          </DialogHeader>
          {activeCustomization && (
            <div className="space-y-4">
              <SideBySideCompare
                originalUrl={activeCustomization.reference_frame_url}
                generatedUrl={activeCustomization.generated_image_url}
              />
              <JsonSpecPanel spec={activeCustomization.generation_spec} />
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
}
