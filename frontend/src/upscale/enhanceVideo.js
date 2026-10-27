import {
  ALL_FORMATS, AudioSampleSource, BlobSource, BufferTarget,
  CanvasSink, CanvasSource, Input, Mp4OutputFormat, Output, canEncodeAudio, canEncodeVideo,
} from "mediabunny";
import { UPSCALE, upscaleTarget } from "./sizing";
import { passthroughSegmentAudio } from "./audio";

const UNSHARP_SVG_ID = "hookforge-upscale-unsharp";
const UNSHARP_FILTER = `url(#${UNSHARP_SVG_ID})`;

/**
 * Ensure a tone-neutral 3x3 unsharp-mask SVG convolution filter exists in the
 * document. Because the kernel weights (0, -0.2, 0, -0.2, 1.8, -0.2, 0, -0.2, 0)
 * sum to exactly 1.0 in sRGB, flat regions, shadow levels, and overall color
 * tone remain 100% unchanged while only high-frequency edges are crisped.
 */
function ensureUnsharpSvgFilter() {
  if (typeof document === "undefined" || !document.body) return false;
  if (document.getElementById(UNSHARP_SVG_ID)) return true;
  const ns = "http://www.w3.org/2000/svg";
  const svg = document.createElementNS(ns, "svg");
  svg.setAttribute("width", "0");
  svg.setAttribute("height", "0");
  svg.setAttribute("aria-hidden", "true");
  svg.style.position = "absolute";
  svg.style.width = "0";
  svg.style.height = "0";
  svg.style.pointerEvents = "none";
  const defs = document.createElementNS(ns, "defs");
  const filter = document.createElementNS(ns, "filter");
  filter.setAttribute("id", UNSHARP_SVG_ID);
  filter.setAttribute("color-interpolation-filters", "sRGB");
  const matrix = document.createElementNS(ns, "feConvolveMatrix");
  matrix.setAttribute("order", "3 3");
  matrix.setAttribute("kernelMatrix", "0 -0.2 0 -0.2 1.8 -0.2 0 -0.2 0");
  matrix.setAttribute("divisor", "1");
  matrix.setAttribute("bias", "0");
  matrix.setAttribute("edgeMode", "duplicate");
  matrix.setAttribute("preserveAlpha", "true");
  filter.appendChild(matrix);
  defs.appendChild(filter);
  svg.appendChild(defs);
  document.body.appendChild(svg);
  return true;
}

function throwCancelled(signal) {
  if (signal?.aborted) throw signal.reason || new DOMException("Enhancement cancelled.", "AbortError");
}

/**
 * Enhance one sub-4K clip: upscale to the 4K target, then MP4.
 *
 * Decoding is per-frame through CanvasSink and every frame is painted with
 * high-quality bicubic smoothing plus a tone-neutral zero-DC unsharp convolution
 * kernel before it reaches the AVC encoder, sharpening high-frequency edges
 * while preserving the source video's exact color tone and shadow levels.
 * Audio is carried over untouched (resampled to AAC), never dropped or stretched.
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
    const hasUnsharp = ensureUnsharpSvgFilter();
    ctx.filter = hasUnsharp ? UNSHARP_FILTER : "none";
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
        ctx.drawImage(decoded.canvas, 0, 0, target.width, target.height);
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

