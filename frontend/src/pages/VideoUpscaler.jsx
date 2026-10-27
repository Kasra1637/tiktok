import { WandSparkles, Upload, Download, TriangleAlert as AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Progress } from "../components/ui/progress";
import { Skeleton } from "../components/ui/skeleton";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import SectionCard, { GroupLabel } from "../components/SectionCard";
import { formatDims } from "../upscale/sizing";
import { useUpscaler } from "../upscale/useUpscaler";

/**
 * Video Upscaler: upload a sub-4K clip, enhance it, preview, download.
 *
 * Presentation only — the upload/probe/enhance state machine lives in
 * useUpscaler, and the encode pipeline in upscale/enhanceVideo. Everything
 * runs in the browser: decode each frame, paint it enlarged with
 * high-quality smoothing plus a clarity pass, and encode AVC MP4 with the
 * audio carried over (pictures encode to PNG stills). No server round-trip,
 * no new backend.
 */
export function VideoUpscaler() {
  const {
    fileName, sourceUrl, sourceMeta, status, progress, result, error,
    downloadName, enhancing, handleFile, handleEnhance, handleCancel, resetSelection,
  } = useUpscaler();

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={WandSparkles}
        title="Video Upscaler"
        description="Bring a soft sub-4K clip up to 4K: sharper edges, richer colour, same audio."
      />

      {error && (
        <Alert variant="destructive">
          <AlertTriangle className="h-4 w-4" />
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      <SectionCard
        title="Your clip"
        icon={Upload}
        description="MP4 or WebM, under 4K on its shorter side. Everything is enhanced on this device — nothing is uploaded."
        actions={
          (status === "ready" || status === "done") && (
            <Button variant="secondary" size="sm" onClick={resetSelection}>
              <RotateCcw className="h-3.5 w-3.5" />
              Start over
            </Button>
          )
        }
      >
        {status === "idle" || status === "probing" ? (
          <label
            className="flex cursor-pointer flex-col items-center justify-center gap-3 rounded-2xl border border-dashed border-[color:var(--hairline-strong)] bg-card/40 px-6 py-14 text-center transition-colors hover:border-[color:var(--indigo-35)]"
          >
            <Upload className="h-6 w-6 text-muted-foreground" />
            <span className="font-display text-base font-semibold tracking-tight">
              {status === "probing" ? "Reading your file…" : "Choose a video to upscale"}
            </span>
            <span className="text-sm text-muted-foreground">
              {fileName || "MP4 or WebM — videos up to 5 minutes"}
            </span>
            <input
              type="file"
              accept="video/mp4,video/webm,video/quicktime"
              className="sr-only"
              data-testid="upscaler-file-input"
              disabled={status === "probing"}
              onChange={(event) => handleFile(event.target.files?.[0])}
            />
          </label>
        ) : (
          <div className="space-y-5">
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
              <div className="space-y-2">
                <GroupLabel>Original · {formatDims(sourceMeta.width, sourceMeta.height)}</GroupLabel>
                <video
                  src={sourceUrl}
                  controls
                  playsInline
                  preload="metadata"
                  className="aspect-video w-full rounded-xl border border-[color:var(--hairline)] bg-black"
                  data-testid="upscaler-original-video"
                />
              </div>
              <div className="space-y-2">
                <GroupLabel>
                  {result ? `Enhanced · ${formatDims(result.width, result.height)}` : "Enhanced"}
                </GroupLabel>
                {result ? (
                  <video
                    src={result.url}
                    controls
                    playsInline
                    preload="metadata"
                    className="aspect-video w-full rounded-xl border border-[color:var(--hairline)] bg-black"
                    data-testid="upscaler-enhanced-video"
                  />
                ) : enhancing ? (
                  <Skeleton className="aspect-video w-full rounded-xl" aria-label="Enhancing your video" />
                ) : (
                  <div className="flex aspect-video w-full flex-col items-center justify-center gap-2 rounded-xl border border-dashed border-[color:var(--hairline-strong)] bg-card/40 px-6 text-center">
                    <WandSparkles className="h-5 w-5 text-muted-foreground" />
                    <p className="text-sm text-muted-foreground">
                      Your sharpened 4K preview appears here.
                    </p>
                  </div>
                )}
              </div>
            </div>

            {enhancing ? (
              <div className="space-y-3">
                <div className="flex items-center justify-between gap-3">
                  <p className="text-sm text-muted-foreground" role="status">
                    Enhancing frame by frame — {progress}% so the tab stays responsive.
                  </p>
                  <Button variant="secondary" size="sm" onClick={handleCancel}>
                    Cancel
                  </Button>
                </div>
                <Progress value={progress} data-testid="upscaler-progress" />
              </div>
            ) : (
              <div className="flex flex-wrap items-center gap-2">
                {!result && (
                  <Button variant="accent" onClick={handleEnhance} data-testid="upscaler-enhance">
                    <WandSparkles className="h-4 w-4" />
                    Enhance to 4K
                  </Button>
                )}
                {result && (
                  <>
                    <Button variant="accent" asChild>
                      <a href={result.url} download={downloadName} data-testid="upscaler-download">
                        <Download className="h-4 w-4" />
                        Download enhanced video
                      </a>
                    </Button>
                    <Button variant="secondary" onClick={handleEnhance}>
                      <RotateCcw className="h-4 w-4" />
                      Enhance again
                    </Button>
                  </>
                )}
              </div>
            )}
          </div>
        )}
      </SectionCard>
    </PageFrame>
  );
}

export default VideoUpscaler;
