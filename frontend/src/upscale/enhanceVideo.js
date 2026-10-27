import {
  ALL_FORMATS, AudioSampleSource, BlobSource, BufferTarget,
  CanvasSink, CanvasSource, Input, Mp4OutputFormat, Output, canEncodeAudio, canEncodeVideo,
} from "mediabunny";
import { UPSCALE, upscaleTarget } from "./sizing";
import { passthroughSegmentAudio } from "./audio";

const ENHANCE_FILTER = "contrast(1.07) saturate(1.15) brightness(1.01)";

// Clarity pass: a softly blurred copy of the upscaled frame, composited back
// over itself in overlay blend, lifts local contrast (edges, texture) without
// moving a single pixel — geometry cannot drift, and with no denoise pass
// there is nothing to wax over fine detail. Alpha stays low so flat areas
// keep no halo.
const CLARITY_ALPHA = 0.3;
const CLARITY_BLUR_PX = 2;

function throwCancelled(signal) {
  if (signal?.aborted) throw signal.reason || new DOMException("Enhancement cancelled.", "AbortError");
}

/**
 * Enhance one sub-4K clip: upscale to the 4K target, then MP4.
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
      "This video is already 4K on its shorter side, so there is nothing to upscale. Pick a clip under 4K."
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
  const videoConfig = { codec: "avc", bitrate: videoBitrate, fullCodecString: "avc1.640033", latencyMode: "quality" };
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
    // Scratch holds the upscaled base so the clarity pass never reads from
    // the canvas it is painting to (self-drawImage snapshot semantics differ
    // across browsers; a scratch copy is unambiguous everywhere).
    const scratch = document.createElement("canvas");
    scratch.width = target.width;
    scratch.height = target.height;
    const scratchCtx = scratch.getContext("2d");
    scratchCtx.imageSmoothingEnabled = true;
    scratchCtx.imageSmoothingQuality = "high";
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
        scratchCtx.filter = ENHANCE_FILTER;
        scratchCtx.drawImage(decoded.canvas, 0, 0, target.width, target.height);
        // No state resets: a fresh 2d context already starts at filter none,
        // source-over, alpha 1, and save/restore below preserves exactly that
        // across frames — while scratchCtx always sets its filter first.
        ctx.drawImage(scratch, 0, 0);
        ctx.save();
        ctx.globalCompositeOperation = "overlay";
        ctx.globalAlpha = CLARITY_ALPHA;
        ctx.filter = `blur(${CLARITY_BLUR_PX}px)`;
        ctx.drawImage(scratch, 0, 0);
        ctx.restore();
        await videoSource.add(frame / fps, Math.min(1 / fps, duration - frame / fps));
        frame++;
        onProgress?.(frame / frameCount);
      }
      if (frame !== frameCount) throw new Error("The video decoder stopped before the clip ended. Choose another clip.");
      videoSource.close();
    };
    const encodeAudio = async () => {
      if (!audioSource) return;
      await passthroughSegmentAudio({
        audioTrack, audioSource, origin: first, duration,
        checkCancelled: () => throwCancelled(signal),
      });
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

