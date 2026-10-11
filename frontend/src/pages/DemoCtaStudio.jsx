import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { TriangleAlert as AlertTriangle, Loader as Loader2, Smartphone } from "lucide-react";
import { Button } from "../components/ui/button";
import { Badge } from "../components/ui/badge";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import SectionCard from "../components/SectionCard";
import EmptyState from "../components/EmptyState";
import { api, getErrorMessage, mediaUrl, durableMediaUrl } from "../lib/api";
import { sentenceCase } from "../lib/copyCase";
import { DemoCtaEditor } from "../demoCta/DemoCtaEditor";

/**
 * Native Product Demo + CTA studio.
 *
 * Two shapes, one page:
 *
 * - `/demo-cta` — the editor standalone, so Demo + CTA works without first
 *   generating a Hook + Story. Finished renders are listed below it as a way
 *   in with a clip already attached.
 * - `/demo-cta/:generationId` — the same editor with that render pinned as the
 *   source and the export filed beside it in History.
 *
 * Reached from the sidebar, from a finished render in the studio, and from a
 * finished clip in History. At `/demo-cta` the editor opens standalone so it can
 * be used on its own footage, and the finished renders are offered underneath
 * as a way in with a Hook + Story already attached.
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
        // Only rows that actually carry a fetchable copy: an R2 URL, or a local
        // /api/media/videos/{id}.mp4 path (a signed demo-cta export). A render
        // that still only has its provider link is not openable from the
        // browser, so omitting it avoids a 401 the user cannot recover from.
        const list = (data?.generations || []).filter((r) =>
          r?.r2_url || (r?.video_url && r?.video_url.startsWith("/api/media/videos/"))
        );
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
    <div className="space-y-4">
      <div>
        <h2 className="font-display text-lg font-semibold tracking-tight">Start from a finished render</h2>
        <p className="mt-1 text-sm text-muted-foreground">You can also upload your own clip above—no Hook + Story render is required. This editor styles one source clip; combine your demo and closing CTA in your own editor if needed.</p>
      </div>
      <div className="grid gap-3 [grid-template-columns:repeat(auto-fill,minmax(260px,1fr))]">
        {rows.map((row) => (
          <SectionCard key={row.id} className="flex h-full flex-col !gap-3">
            <div className="flex flex-wrap items-center justify-between gap-2">
              <span className="font-display text-sm font-semibold">
                {row.brand_name || "Unassigned app"}
              </span>
              {typeof row.duration === "number" && (
                <Badge variant="secondary" className="font-mono text-[11px] tabular-nums">
                  {row.duration}s
                </Badge>
              )}
            </div>
            {row.hook_line ? (
              <p className="line-clamp-2 text-xs text-muted-foreground" title={sentenceCase(row.hook_line)}>
                &ldquo;{sentenceCase(row.hook_line)}&rdquo;
              </p>
            ) : (
              <p className="text-xs text-muted-foreground">No hook line recorded.</p>
            )}
            {/* mt-auto pins the actions to the bottom of every card so a row of
                cards with different quote lengths still lines up. */}
            <div className="mt-auto flex flex-wrap gap-2">
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
        if (!row || row.status !== "completed") {
          setError(
            "This render is not a finished clip, so there is nothing to edit. Pick a completed render instead."
          );
          setGeneration(null);
          return;
        }
        // The fetchable copy must be durable. video_url carries the provider's
        // temporary link for a provider render, which the browser can never
        // fetch, so a row that has only that (no durable r2_url copy) is not
        // openable even though the generator is "completed".
        const sourceUrl = durableMediaUrl(row);
        if (!sourceUrl) {
          setError(
            "This render has no durable copy the browser can open. Refresh for a fresh link, or choose a different render."
          );
          setGeneration(null);
          return;
        }
        setGeneration({ ...row, sourceUrl });
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

  // `load()` already chose the durable copy from the row, so the editor just
  // uses what it was given.
  const sourceUrl = generation.sourceUrl;

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
    <PageFrame className="space-y-5">
      <PageHeader
        icon={Smartphone}
        eyebrow="Studio"
        title="Demo + CTA"
        description={
          generationId
            ? "Style a finished Hook + Story clip in a phone mockup, add a hook overlay and CTA, then export it."
            : "Style any clip in a phone mockup, combine clips separately, then export that result to History."
        }
      />
      {generationId ? (
        <EditorRoute generationId={generationId} />
      ) : (
        <DemoCtaEditor />
      )}
      {/* Full-width and below the two-column editor: a second way in, not a
          competing column competing for the same height. */}
      {!generationId && <SourcePicker />}
    </PageFrame>
  );
}

export default DemoCtaStudio;
