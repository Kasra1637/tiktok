import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { AlertTriangle, Loader2, Smartphone } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage, mediaUrl } from "../lib/api";
import { DemoCtaEditor } from "../demoCta/DemoCtaEditor";

/**
 * Native Product Demo + CTA studio.
 *
 * Two shapes, one page:
 *
 * - `/demo-cta` — the editor standalone, so Demo + CTA works without first
 *   generating a Hook + Middle. Finished renders are listed below it as a way
 *   in with a clip already attached.
 * - `/demo-cta/:generationId` — the same editor with that render pinned as the
 *   source and the export filed beside it in History.
 *
 * Reached from the sidebar, from a finished render in the studio, and from a
 * finished clip in History. At `/demo-cta` the editor opens standalone so it can
 * be used on its own footage, and the finished renders are offered underneath
 * as a way in with a Hook + Middle already attached.
 */
function SourcePicker() {
  const [rows, setRows] = useState(null);
  const [error, setError] = useState(null);

  useEffect(() => {
    let cancelled = false;
    api
      .getGenerationHistory({ status: "completed", limit: 50 })
      .then((data) => {
        if (cancelled) return;
        const list = (data?.generations || []).filter((r) => r?.video_url || r?.r2_url);
        setRows(list);
      })
      .catch((err) => {
        if (!cancelled) setError(getErrorMessage(err));
      });
    return () => {
      cancelled = true;
    };
  }, []);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!rows) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Finding finished renders…
      </p>
    );
  }

  // Empty renders nothing at all. The editor above is already usable on its own
  // footage, so an empty-state card under a working editor would be noise, and a
  // "generate one first" prompt would be wrong now that it is not required.
  if (rows.length === 0) {
    return null;
  }

  return (
    <div className="space-y-3">
      <h2 className="eyebrow">Or open a finished render</h2>
      <div className="grid gap-3 sm:grid-cols-2">
        {rows.map((row) => (
          <SectionCard key={row.id} className="space-y-2">
            <div className="flex flex-wrap items-center gap-2">
              <span className="font-display text-sm font-semibold">
                {row.brand_name || "Unassigned app"}
              </span>
              {typeof row.duration === "number" && (
                <span className="font-mono text-[11px] tabular-nums text-muted-foreground">
                  {row.duration}s
                </span>
              )}
            </div>
            {row.hook_line && (
              <p className="truncate text-xs text-muted-foreground">&ldquo;{row.hook_line}&rdquo;</p>
            )}
            <div className="flex flex-wrap gap-2">
              <Button variant="brand" size="sm" asChild>
                <Link to={`/demo-cta/${row.id}`}>
                  <Smartphone className="h-3.5 w-3.5" /> Open in editor
                </Link>
              </Button>
              {(row.video_url || row.r2_url) && (
                <Button variant="secondary" size="sm" asChild>
                  <a href={mediaUrl(row.r2_url || row.video_url)} download>
                    Download original
                  </a>
                </Button>
              )}
            </div>
          </SectionCard>
        ))}
      </div>
    </div>
  );
}

function EditorRoute({ generationId }) {
  const [generation, setGeneration] = useState(null);
  const [error, setError] = useState(null);

  const load = useCallback(() => {
    setError(null);
    api
      .getGeneration(generationId)
      .then((row) => {
        if (!row || row.status !== "completed" || !(row.video_url || row.r2_url)) {
          setError(
            "This render is not a finished clip, so there is nothing to edit. Pick a completed render instead."
          );
          setGeneration(null);
          return;
        }
        setGeneration(row);
      })
      .catch((err) => setError(getErrorMessage(err)));
  }, [generationId]);

  useEffect(() => {
    load();
  }, [load]);

  if (error) {
    return (
      <Alert variant="destructive">
        <AlertTriangle className="h-4 w-4" />
        <AlertDescription>{error}</AlertDescription>
      </Alert>
    );
  }

  if (!generation) {
    return (
      <p className="flex items-center gap-1.5 text-sm text-muted-foreground">
        <Loader2 className="h-4 w-4 animate-spin" /> Loading the finished render…
      </p>
    );
  }

  // Local signed copy first, for the same reason the handoff preferred it: the
  // paid clip stays off public bucket URLs wherever a signed local copy exists.
  const sourceUrl = mediaUrl(generation.video_url || generation.r2_url);

  return (
    <DemoCtaEditor
      key={generation.id}
      generation={generation}
      sourceUrl={sourceUrl}
    />
  );
}

export function DemoCtaStudio() {
  const { generationId } = useParams();
  return (
    <div className="mx-auto w-full max-w-6xl space-y-5">
      <PageHeader
        icon={Smartphone}
        eyebrow="Studio"
        title="Demo + CTA"
        description={
          generationId
            ? "The finished Hook + Middle, wrapped in a phone mockup with your demo and close. The export lands beside the original in History."
            : "Wrap your footage in a phone mockup and add your own call to action. Use your own clip, or open a finished Hook + Middle from below. Exports save to History."
        }
      />
      {generationId ? (
        <EditorRoute generationId={generationId} />
      ) : (
        <>
          <DemoCtaEditor />
          <div className="pt-2">
            <SourcePicker />
          </div>
        </>
      )}
    </div>
  );
}

export default DemoCtaStudio;
