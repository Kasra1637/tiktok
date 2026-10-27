/**
 * Read dimensions and duration without decoding: a metadata-only probe, so
 * an ineligible file is refused before any heavy work starts.
 *
 * DOM-bound (object URL plus a <video> element) and deliberately separate
 * from the pure sizing rules and the mediabunny pipeline.
 */
export function probeVideo(blob) {
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
