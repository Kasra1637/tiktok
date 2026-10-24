import { useEffect, useRef } from "react";
import { api, getErrorMessage } from "../lib/api";
import { recordSignal } from "../lib/feedback";
import { buildExportFilename, sniffRecordingContainer } from "./constants";
import { exportTikTok, TIKTOK_EXPORT } from "./exportTikTok";
import { prepareHandViewImages } from "./handView";
import { useExportErrors } from "./useExportErrors";

/**
 * Load a recorded blob into a throwaway video element and confirm it has a
 * decoded first frame, expected duration and full TikTok dimensions.
 * A blob that fails never becomes a download link or a History row.
 */
export function probeRecordingPlays(blob, expectedDuration) {
  return new Promise((resolve, reject) => {
    const url = URL.createObjectURL(blob);
    const probe = document.createElement("video");
    const cleanup = () => {
      clearTimeout(timer);
      probe.onloadeddata = null;
      probe.onerror = null;
      URL.revokeObjectURL(url);
      probe.removeAttribute("src");
    };
    const fail = (message) => {
      cleanup();
      reject(new Error(message));
    };
    const timer = setTimeout(
      () => fail("The TikTok MP4 could not be decoded. Try exporting again in a current Chrome or Edge browser."),
      8000
    );
    probe.preload = "auto";
    probe.onloadeddata = () => {
      if (Number.isFinite(probe.duration) && Math.abs(probe.duration - expectedDuration) <= 0.1 &&
          probe.videoWidth === TIKTOK_EXPORT.width && probe.videoHeight === TIKTOK_EXPORT.height) {
        cleanup();
        resolve();
      } else {
        fail("The TikTok MP4 failed its duration or resolution check. Export again; this file will not be offered for download.");
      }
    };
    probe.onerror = () =>
      fail("The TikTok MP4 could not be decoded. Try exporting again in a current Chrome or Edge browser.");
    probe.src = url;
  });
}

/**
 * Export recording, MP4 validation and History save: one owner.
 *
 * The editor only calls `exportVideo` / `saveExport` and reads the outcome
 * states it already owns; everything that records, validates or saves lives
 * here. Failure history is integrated through useExportErrors: the banners
 * still carry the current failure while the hook keeps which stage failed
 * and when. Success paths are untouched — same encode, same gates, same row.
 */
export function useExportFlow(settings) {
  const {
    generation, onSaved,
    videoUrl, videoMeta, device, preset, viewMode, envBg,
    captionFont, ctaFont, fontStack,
    videoRef, paintFrameRef, isExportingRef, dirtyRef, kickPreviewRef,
    resultObjectUrlRef,
    setIsPlaying,
    setRecording, setProgress, setResult,
    setSaving, setSaved, setSaveError, setError,
  } = settings;
  const { exportErrors, recordExportError, clearExportErrors } = useExportErrors();

  const exportAbortRef = useRef(null);
  useEffect(() => () => exportAbortRef.current?.abort(), []);

  const saveExport = async (blob, name) => {
    setSaving(true);
    setSaveError(null);
    clearExportErrors();
    try {
      const savedRow = await api.saveDemoCtaExport(generation?.id, blob, name);
      setSaved(savedRow);
      recordSignal("video_downloaded", "demo_cta_exported", {
        brand_profile_id: generation?.brand_profile_id || "",
        studio_project_id: generation?.studio_project_id || "",
        generation_id: savedRow?.id || "",
        template_id: generation?.template_id || "",
      });
      onSaved?.(savedRow);
      clearExportErrors();
      return savedRow;
    } catch (err) {
      recordExportError("save", err);
      setSaveError(getErrorMessage(err));
      return null;
    } finally {
      setSaving(false);
    }
  };

  const exportVideo = async () => {
    const video = videoRef.current;
    const paintFrame = paintFrameRef.current;
    if (!video || !paintFrame || !videoMeta || isExportingRef.current) return;
    const controller = new AbortController();
    exportAbortRef.current = controller;
    const resumePlayback = !video.paused;
    video.pause();
    setIsPlaying(false);
    setError(null);
    setSaveError(null);
    setSaved(null);
    clearExportErrors();
    setRecording(true);
    setProgress(0);
    setResult(null);
    isExportingRef.current = true;
    try {
      // Freeze settings, assets and fonts for the entire encode. Never capture a live RAF canvas.
      await Promise.all([document.fonts?.ready, ...[captionFont, ctaFont].map((id) =>
        document.fonts?.load(`100px ${fontStack(id)}`))]);
      if (viewMode === "hand") await prepareHandViewImages(envBg);
      const response = await fetch(videoUrl, { signal: controller.signal });
      if (!response.ok) throw new Error("The source clip could not be read. Reload it and export again.");
      const canvas = document.createElement("canvas");
      const { blob, duration } = await exportTikTok({
        source: await response.blob(), canvas, signal: controller.signal,
        drawFrame: (time, frame) => paintFrame(canvas, time, frame),
        onProgress: setProgress,
      });
      const head = new Uint8Array(await blob.slice(0, 8).arrayBuffer());
      if (sniffRecordingContainer(head) !== "mp4") throw new Error("The encoder did not produce a valid MP4. Export again in Chrome or Edge.");
      await probeRecordingPlays(blob, duration);
      controller.signal.throwIfAborted();
      const url = URL.createObjectURL(blob);
      if (resultObjectUrlRef.current) URL.revokeObjectURL(resultObjectUrlRef.current);
      resultObjectUrlRef.current = url;
      const name = buildExportFilename({ device, preset: "tiktok", width: canvas.width, height: canvas.height, ext: "mp4" });
      const mime = "video/mp4";
      setResult({ url, name, size: blob.size, mime, blob });
      await saveExport(blob, name);
    } catch (e) {
      if (!controller.signal.aborted) {
        recordExportError("export", e);
        setError(e?.message || "The TikTok MP4 export failed. Try again in Chrome or Edge.");
      }
    } finally {
      isExportingRef.current = false;
      exportAbortRef.current = null;
      if (!controller.signal.aborted) {
        setRecording(false);
        setProgress(0);
        // The loop parks for the whole encode; repaint the live preview once
        // (the `play` event below re-kicks the loop when playback resumes).
        dirtyRef.current = true;
        kickPreviewRef.current?.();
        if (resumePlayback) video.play().then(() => setIsPlaying(true)).catch(() => {});
      }
    }
  };

  return { saveExport, exportVideo, exportErrors, clearExportErrors };
}
