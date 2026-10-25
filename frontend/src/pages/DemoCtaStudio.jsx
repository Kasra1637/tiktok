import { useCallback, useEffect, useState } from "react";
import { Link, useParams } from "react-router-dom";
import { Button } from "../components/ui/button";
import { TriangleAlert as AlertTriangle, Smartphone } from "lucide-react";
import { Alert, AlertDescription } from "../components/ui/alert";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import { Skeleton } from "../components/ui/skeleton";
import { api, getErrorMessage, durableMediaUrl } from "../lib/api";
import { DemoCtaEditor } from "../demoCta/DemoCtaEditor";

/**
 * Native Product Demo + CTA studio.
 *
 * One editor, two shapes:
 *
 * - `/demo-cta` — the editor standalone, so Demo + CTA works on the founder's
 *   own footage.
 * - `/demo-cta/:generationId` — the same editor with that render pinned as the
 *   source and the export filed beside it in History.
 *
 * Reached from the sidebar, from a finished render in the studio, and from a
 * finished clip in History. The list of finished renders that used to sit under
 * the standalone editor is gone: History is where a finished clip is chosen,
 * and the editor already takes its own footage, so a second way in below it was
 * a competing entry point rather than a shortcut.
 */
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
            "This render has no saved copy the browser can open. Open this clip in History to retry the durable save, or upload your own footage."
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
        <AlertDescription>
          {error}
          <div className="mt-3 flex flex-wrap gap-2">
            <Button variant="secondary" size="sm" onClick={load}>Try loading again</Button>
            <Button variant="accent" size="sm" asChild>
              <Link to={`/history#generation-${generationId}`}>Review clip in History</Link>
            </Button>
            <Button variant="secondary" size="sm" asChild>
              <Link to="/demo-cta">Upload your own clip</Link>
            </Button>
          </div>
        </AlertDescription>
      </Alert>
    );
  }

  if (!generation) {
    return (
      <Skeleton className="h-96 w-full rounded-2xl" aria-label="Loading the finished render" />
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
    <PageFrame className="space-y-6">
      <PageHeader
        icon={Smartphone}
        title="Demo + CTA"
        description={
          generationId
            ? "Style a finished clip: phone or full-frame, then add CTA."
            : "Style any clip: phone mockup or full-frame for History."
        }
      />
      {generationId ? (
        <EditorRoute generationId={generationId} />
      ) : (
        <DemoCtaEditor />
      )}
    </PageFrame>
  );
}

export default DemoCtaStudio;
