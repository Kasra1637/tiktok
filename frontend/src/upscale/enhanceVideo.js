import {
  ALL_FORMATS, AudioSampleSink, AudioSampleSource, BlobSource, BufferTarget,
  CanvasSink, CanvasSource, Input, Mp4OutputFormat, Output, canEncodeAudio, canEncodeVideo,
} from "mediabunny";

export const UPSCALE = Object.freeze({
  // Short side grows to 1080; the long side never passes 1920. A sub-1080p
  // portrait phone clip (720x1280) therefore lands on 1080x1920, a 480p
  // landscape clip on 1920x1080, and a square clip on 1080x1080.
  targetMinSide: 1080,
  maxSide: 1920,
  fps: 30,
  videoBitrate: 12_000_000,
  audioBitrate: 192_000,
  // Browser-side AVC encode of a very long clip ties up the tab for many
  // minutes, so overlong files are refused loudly instead of stalling.
  maxDurationSeconds: 300,
});

// Pure function of the source dimensions, so the sizing rule is unit
// testable without decoding anything. Returns null when the source is not
// eligible: already HD, or dimensions that are not usable numbers.
export function upscaleTarget(width, height) {
  if (!Number.isFinite(width) || !Number.isFinite(height) || width <= 0 || height <= 0) return null;
  const minSide = Math.min(width, height);
  if (minSide >= UPSCALE.targetMinSide) return null;
  const maxSide = Math.max(width, height);
  const factor = Math.min(UPSCALE.targetMinSide / minSide, UPSCALE.maxSide / maxSide);
  // AVC needs even dimensions; rounding can only shrink the long side cap,
  // never grow past it by more than a pixel pair, so re-clamp after rounding.
  const even = (n) => Math.max(2, Math.round(n / 2) * 2);
  const scaled = { width: even(width * factor), height: even(height * factor) };
  if (Math.max(scaled.width, scaled.height) > UPSCALE.maxSide + 2) return null;
  return scaled;
}

const ENHANCE_FILTER = "contrast(1.07) saturate(1.15) brightness(1.01)";

function throwCancelled(signal) {
  if (signal?.aborted) throw signal.reason || new DOMException("Enhancement cancelled.", "AbortError");
}

/**
 * Enhance one sub-1080p clip: upscale to the 1080p target, then MP4.
 *
 * Decoding is per-frame through CanvasSink and every frame is painted with
 * high-quality smoothing plus a light contrast/saturation lift before it
 * reaches the AVC encoder, so the output genuinely looks crisper and more
 * vivid than the source rather than a larger copy of the same blur. Audio
 * is carried over untouched (resampled to AAC), never dropped or stretched.
 */
export async function enhanceVideo({ blob, canvas, sourceWidth, sourceHeight, duration, onProgress, signal }) {
  throwCancelled(signal);
  const target = upscaleTarget(sourceWidth, sourceHeight);
  if (!target) {
    throw new Error(
      "This video is already 1080p or higher on its shorter side, so there is nothing to upscale. Pick a clip under 1080p."
    );
  }
  if (!(duration > 0) || !Number.isFinite(duration)) {
    throw new Error("This video has no playable duration. Choose another clip.");
  }
  if (duration > UPSCALE.maxDurationSeconds) {
    throw new Error(
      `This clip is ${Math.round(duration)}s; the upscaler handles clips up to ${UPSCALE.maxDurationSeconds / 60} minutes in the browser. Trim it shorter first.`
    );
  }
  const { fps, videoBitrate, audioBitrate } = UPSCALE;
  const videoConfig = { codec: "avc", bitrate: videoBitrate, fullCodecString: "avc1.640028", latencyMode: "quality" };
  const audioConfig = { codec: "aac", bitrate: audioBitrate, transform: { sampleRate: 48000, numberOfChannels: 2 } };
  if (!await canEncodeVideo("avc", { ...videoConfig, width: target.width, height: target.height, frameRate: fps })) {
    throw new Error("MP4 encoding is unavailable in this browser. Open this page in a current Chrome or Edge browser.");
  }
  const input = new Input({ source: new BlobSource(blob), formats: ALL_FORMATS });
  let output;
  let finalized = false;
  let failed = false;
  try {
    const track = await input.getPrimaryVideoTrack();
    if (!track || !await track.canDecode()) {
      throw new Error("This video cannot be decoded. Upload a playable MP4 or WebM video.");
    }
    const first = Math.max(0, await track.getFirstTimestamp());
    const audioTrack = await input.getPrimaryAudioTrack();
    if (audioTrack && (!await audioTrack.canDecode() || !await canEncodeAudio("aac", { sampleRate: 48000, numberOfChannels: 2, bitrate: audioBitrate }))) {
      throw new Error("This browser cannot keep this clip's audio in MP4. Use a current Chrome or Edge browser; audio will not be silently removed.");
    }
    canvas.width = target.width;
    canvas.height = target.height;
    const ctx = canvas.getContext("2d");
    ctx.imageSmoothingEnabled = true;
    ctx.imageSmoothingQuality = "high";
    output = new Output({ format: new Mp4OutputFormat({ fastStart: "in-memory" }), target: new BufferTarget() });
    const videoSource = new CanvasSource(canvas, videoConfig);
    output.addVideoTrack(videoSource, { frameRate: fps });
    const audioSource = audioTrack ? new AudioSampleSource(audioConfig) : null;
    if (audioSource) output.addAudioTrack(audioSource);
    await output.start();
    const frameCount = Math.ceil(duration * fps - 1e-6);
    const encodeVideo = async () => {
      const timestamps = function* () {
        for (let frame = 0; frame < frameCount; frame++) yield first + frame / fps;
      };
      let frame = 0;
      for await (const decoded of new CanvasSink(track, { poolSize: 2 }).canvasesAtTimestamps(timestamps())) {
        throwCancelled(signal);
        if (!decoded) throw new Error(`The video is missing a frame at ${(frame / fps).toFixed(2)}s. Choose another clip.`);
        ctx.filter = ENHANCE_FILTER;
        ctx.drawImage(decoded.canvas, 0, 0, target.width, target.height);
        ctx.filter = "none";
        await videoSource.add(frame / fps, Math.min(1 / fps, duration - frame / fps));
        frame++;
        onProgress?.(frame / frameCount);
      }
      if (frame !== frameCount) throw new Error("The video decoder stopped before the clip ended. Choose another clip.");
      videoSource.close();
    };
    const encodeAudio = async () => {
      if (!audioSource) return;
      for await (const sample of new AudioSampleSink(audioTrack).samples(first, first + duration)) {
        try {
          throwCancelled(signal);
          const start = Math.max(0, Math.round((first - sample.timestamp) * sample.sampleRate));
          const end = Math.min(sample.numberOfFrames, Math.round((first + duration - sample.timestamp) * sample.sampleRate));
          if (end <= start) continue;
          const trimmed = sample.trim(start, end);
          try {
            trimmed.setTimestamp(trimmed.timestamp - first);
            await audioSource.add(trimmed);
          } finally { trimmed.close(); }
        } finally { sample.close(); }
      }
      audioSource.close();
    };
    const jobs = [encodeVideo(), encodeAudio()];
    try {
      await Promise.all(jobs);
    } catch (error) {
      failed = true;
      await output.cancel();
      await Promise.allSettled(jobs);
      throw error;
    }
    throwCancelled(signal);
    await output.finalize();
    finalized = true;
    return {
      blob: new Blob([output.target.buffer], { type: "video/mp4" }),
      width: target.width,
      height: target.height,
      duration: frameCount / fps,
    };
  } finally {
    try {
      if (output && !finalized && !failed) await output.cancel();
    } finally { input.dispose(); }
  }
}

/**
 * Read dimensions and duration without decoding: a metadata-only probe, so
 * an ineligible file is refused before any heavy work starts.
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
