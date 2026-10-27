import { useCallback, useEffect, useRef, useState } from "react";
import { enhanceImage, enhanceVideo } from "./enhanceVideo";
import { formatDims, upscaleTarget } from "./sizing";

/**
 * The upscaler's state machine, owned here so the page stays presentation.
 *
 * States: idle → probing → ready → enhancing → done, with any failure
 * landing back where retry makes sense (mid-enhance failures return to
 * ready, probe failures to idle) and the message naming the next step.
 * Object URLs and the encode's AbortController live here too: URLs are
 * revoked on unmount, and aborting mid-enhance returns to ready with the
 * previous result intact rather than an error, because cancelling is not
 * a failure.
 */
export function useUpscaler() {
  const [fileName, setFileName] = useState("");
  const [sourceUrl, setSourceUrl] = useState("");
  const [sourceMeta, setSourceMeta] = useState(null);
  const [status, setStatus] = useState("idle");
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
    if (file.size === 0) {
      fail("That file is empty. Choose a playable video or picture file.");
      return;
    }
    const isImage = file.type.startsWith("image/");
    const isVideo = file.type.startsWith("video/");
    if (!isImage && !isVideo) {
      fail("That file is not a video or picture. Choose an MP4, WebM, PNG or JPEG file.");
      return;
    }
    setFileName(file.name);
    setStatus("probing");
    try {
      const meta = isImage ? await probeImage(file) : await probeVideo(file);
      if (!Number.isFinite(meta.width) || meta.width <= 0) {
        fail(
          isImage
            ? "This file could not be read as a picture. Upload a playable PNG or JPEG picture."
            : "This file could not be read as a video. Upload a playable MP4 or WebM video."
        );
        return;
      }
      if (!upscaleTarget(meta.width, meta.height)) {
        setStatus("idle");
        fail(
          isImage
            ? `This picture is already ${formatDims(meta.width, meta.height)} — 4K, so there is nothing to upscale. Pick a picture under 4K.`
            : `This clip is already ${formatDims(meta.width, meta.height)} — 4K, so there is nothing to upscale. Pick a clip under 4K.`
        );
        return;
      }
      setSourceMeta({ ...meta, blob: file, kind: isImage ? "image" : "video" });
      setSourceUrl(trackUrl(URL.createObjectURL(file)));
      setStatus("ready");
    } catch (err) {
      fail(err?.message || "This file could not be read. Upload a playable video or picture file.");
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
      const isImage = sourceMeta.kind === "image";
      const enhanced = isImage
        ? await enhanceImage({
          blob: sourceMeta.blob,
          canvas,
          sourceWidth: sourceMeta.width,
          sourceHeight: sourceMeta.height,
          signal: controller.signal,
        })
        : await enhanceVideo({
          blob: sourceMeta.blob,
          canvas,
          sourceWidth: sourceMeta.width,
          sourceHeight: sourceMeta.height,
          duration: sourceMeta.duration,
          signal: controller.signal,
          onProgress: (fraction) => setProgress(Math.round(fraction * 100)),
        });
      if (isImage) setProgress(100);
      const mime = isImage ? "image/png" : "video/mp4";
      setResult({ ...enhanced, mime, kind: sourceMeta.kind, url: trackUrl(URL.createObjectURL(enhanced.blob)) });
      setStatus("done");
    } catch (err) {
      if (controller.signal.aborted) {
        setStatus("ready");
        setProgress(0);
        return;
      }
      fail(err?.message || "Enhancement failed. Try another file.");
    } finally {
      if (abortRef.current === controller) abortRef.current = null;
    }
  }, [sourceMeta, status, fail, trackUrl]);

  const handleCancel = useCallback(() => {
    abortRef.current?.abort();
  }, []);

  const downloadName =
    (fileName || "file").replace(/\.[^.]+$/, "") +
    (sourceMeta?.kind === "image" ? "-upscaled-4k.png" : "-upscaled-4k.mp4");

  return {
    fileName, sourceUrl, sourceMeta, status, progress, result, error,
    downloadName, enhancing: status === "enhancing",
    handleFile, handleEnhance, handleCancel, resetSelection,
  };
}

/**
 * Read dimensions and duration without decoding: a metadata-only probe, so
 * an ineligible file is refused before any heavy work starts. Lives here
 * (not in its own module) because the hook is its only caller and already
 * owns every other DOM handle and object URL in this flow.
 */
// Exported as a test seam: the hook is its only caller, sizing stays pure.
export function probeImage(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const img = new Image();
    const done = (fn) => () => {
      URL.revokeObjectURL(url);
      fn();
    };
    img.onload = done(() => resolve({
      width: img.naturalWidth,
      height: img.naturalHeight,
    }));
    img.onerror = done(() => reject(new Error("This file could not be read as a picture. Upload a playable PNG or JPEG picture.")));
    img.src = url;
  });
}

function probeVideo(blob) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const video = document.createElement("video");
    video.preload = "metadata";
    video.muted = true;
    const done = (fn) => () => {
      URL.revokeObjectURL(url);
      fn();
    };
    video.onloadedmetadata = done(() => resolve({
      width: video.videoWidth,
      height: video.videoHeight,
      duration: video.duration,
    }));
    video.onerror = done(() => reject(new Error("This file could not be read as a video. Upload a playable MP4 or WebM video.")));
    video.src = url;
  });
}
