import { useCallback, useEffect, useRef, useState } from "react";
import { WandSparkles, Upload, Download, TriangleAlert as AlertTriangle, RotateCcw } from "lucide-react";
import { Button } from "../components/ui/button";
import { Alert, AlertDescription } from "../components/ui/alert";
import { Progress } from "../components/ui/progress";
import { Skeleton } from "../components/ui/skeleton";
import PageHeader from "../components/PageHeader";
import PageFrame from "../components/PageFrame";
import SectionCard, { GroupLabel } from "../components/SectionCard";
import { enhanceVideo, probeVideo, upscaleTarget } from "../upscale/enhanceVideo";

/**
 * Video Upscaler: upload a sub-1080p clip, enhance it, preview, download.
 *
 * Everything runs in the browser through the same mediabunny pipeline the
 * Demo + CTA export uses: decode each frame, paint it enlarged with
 * high-quality smoothing plus a light contrast/saturation lift, and encode
 * AVC MP4 with the audio carried over. No server round-trip, no new backend.
 */

function formatDims(width, height) {
  return `${width} × ${height}`;
}

export function VideoUpscaler() {
  const [fileName, setFileName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceMeta, setSourceMeta] = useState(null);
  const [status, setStatus] = useState("idle"); // idle | probing | ready | enhancing | done
  const [progress, setProgress] = useState(0);
  const [result, setResult] = useState(null);
  const [error, setError] = useState(null);
  const abortRef = useRef(null);
  const urlsRef = useRef([]);

  const trackUrl = useCallback((url) => {
    urlsRef.current.push(url);
    return url;
  }, []);

  useEffect(() => {
    const urls = urlsRef.current;
    return () => urls.forEach((url) => URL.revokeObjectURL(url));
  }, []);

  const resetSelection = useCallback(() => {
    abortRef.current?.abort();
    abortRef.current = null;
    setFileName("");
    setSourceUrl("");
    setSourceMeta(null);
    setStatus("idle");
    setProgress(0);
    setResult(null);
    setError(null);
  }, []);

  const fail = useCallback((message) => {
    setError(message);
    setStatus((current) => (current === "enhancing" ? "ready" : current));
  }, []);

  const handleFile = useCallback(async (file) => {
    if (!file) return;
    resetSelection();
    if (!file.type.startsWith("video/")) {
      fail("That file is not a video. Choose an MP4 or WebM clip.");
      return;
    }
    if (file.size === 0) {
      fail("That file is empty. Choose a playable video file.");
      return;
    }
    setFileName(file.name);
    setStatus("probing");
    try {
      const meta = await probeVideo(file);
      if (!Number.isFinite(meta.width) || meta.width <= 0) {
        fail("This file could not be read as a video. Upload a playable MP4 or WebM video.");
        return;
      }
      if (!upscaleTarget(meta.width, meta.height)) {
        setStatus("idle");
        fail(
          `This clip is already ${formatDims(meta.width, meta.height)} — HD or higher, so there is nothing to upscale. Pick a clip under 1080p.`
        );
        return;
      }
      setSourceMeta({ ...meta, blob: file });
      setSourceUrl(trackUrl(URL.createObjectURL(file)));
      setStatus("ready");
    } catch (err) {
      fail(err?.message || "This file could not be read as a video. Upload a playable MP4 or WebM video.");
    }
  }, [fail, resetSelection, trackUrl]);

  const handleEnhance = useCallback(async () => {
    if (!sourceMeta || status === "enhancing") return;
    const controller = new AbortController();
    abortRef.current = controller;
    setError(null);
    setProgress(0);
    setStatus("enhancing");
    try {
      const canvas = document.createElement("canvas");
      const enhanced = await enhanceVideo({
        blob: sourceMeta.blob,
        canvas,
        sourceWidth: sourceMeta.width,
        sourceHeight: sourceMeta.height,
        duration: sourceMeta.duration,
        signal: controller.signal,
        onProgress: (fraction) => setProgress(Math.round(fraction * 100)),
      });
      setResult({ ...enhanced, url: trackUrl(URL.createObjectURL(enhanced.blob)) });
      setStatus("done");
    } catch (err) {
      if (controller.signal.aborted) {
        setStatus("ready");
        setProgress(0);
        return;
      }
      fail(err?.message || "Enhancement failed. Try another clip.");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [sourceMeta, status, fail, trackUrl]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const downloadName = (fileName || "video").replace(/\.[^.]+$/, "") + "-upscaled-1080p.mp4";
  const enhancing = status === "enhancing";

  return (
    <PageFrame className="space-y-6">
      <PageHeader
        icon={WandSparkles}
        title="Video Upscaler"
        description="Bring a soft sub-1080p clip up to 1080p: sharper edges, richer colour, same audio."
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
        description="MP4 or WebM, under 1080p on its shorter side. Everything is enhanced on this device — nothing is uploaded."
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
              {status === "probing" ? "Reading your clip…" : "Choose a video to upscale"}
            </span>
            <span className="text-sm text-muted-foreground">
              {fileName || "MP4 or WebM, up to 5 minutes"}
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
                      Your sharpened 1080p preview appears here.
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
                    Enhance to 1080p
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
