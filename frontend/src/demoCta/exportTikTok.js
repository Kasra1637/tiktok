import {
  ALL_FORMATS, AudioSample, AudioSampleSink, AudioSampleSource, BlobSource, BufferTarget,
  CanvasSink, CanvasSource, Input, Mp4OutputFormat, Output, canEncodeAudio, canEncodeVideo,
} from "mediabunny";
import { clipWindow } from "./constants";
import { passthroughSegmentAudio } from "./audio";
import { composeImageFrame, imageSequenceDuration } from "./imageSequence";

export const TIKTOK_EXPORT = Object.freeze({
  width: 1080, height: 1920, fps: 30, videoBitrate: 8_000_000, audioBitrate: 192_000,
});

// One PCM timeline and one AAC encoder avoid codec priming or rate/channel changes
// at the join. Offline rendering preserves sample timestamps (including genuine
// source silence), resamples each input, and never changes playback speed.
async function encodeJoinedAudio(segments, audioSource, checkCancelled) {
  const rate = 48000;
  const duration = segments.reduce((sum, segment) => sum + segment.duration, 0);
  const context = new OfflineAudioContext(2, Math.round(duration * rate), rate);
  for (const segment of segments) {
    if (!segment.audioTrack || segment.muted) continue;
    for await (const sample of new AudioSampleSink(segment.audioTrack).samples(segment.origin, segment.origin + segment.duration)) {
      try {
        checkCancelled();
        const local = sample.timestamp - segment.origin;
        const offset = Math.max(0, -local);
        const length = Math.min(sample.duration - offset, segment.duration - Math.max(0, local));
        if (length <= 0) continue;
        const node = context.createBufferSource();
        node.buffer = sample.toAudioBuffer();
        node.connect(context.destination);
        node.start(segment.start + Math.max(0, local), offset, length);
      } finally {
        sample.close();
      }
    }
  }
  const buffer = await context.startRendering();
  checkCancelled();
  // De-click only the first 2 ms of the added segment; never alter the base,
  // overlap clips, extend the file, or insert a silent gap.
  const cut = Math.round(segments[1].start * rate);
  for (let channel = 0; channel < buffer.numberOfChannels; channel++) {
    const data = buffer.getChannelData(channel);
    const count = Math.min(96, data.length - cut);
    const previous = data[cut - 1] || 0;
    for (let i = 0; i < count; i++) {
      const mix = (i + 1) / count;
      data[cut + i] = previous * (1 - mix) + data[cut + i] * mix;
    }
  }
  const samples = AudioSample.fromAudioBuffer(buffer, 0);
  try {
    for (const sample of samples) {
      checkCancelled();
      await audioSource.add(sample);
    }
  } finally {
    samples.forEach((sample) => sample.close());
  }
}

/** Decode pinned sources, base then optional upload, on one 30 fps timeline.
 * A muted segment keeps its video length; only its audio is left out.
 * Each clip's start point is where decoding begins, so the file opens on the
 * frame the preview shows — never on footage the founder skipped.
 * The added segment may instead be an image sequence (ADR 0237): stills
 * have no track to decode, so its frames are composed — each still's
 * picked motion (ADR 0354) and the crossfades included — at the same
 * 30 fps, and it carries no audio. A real
 * added clip wins if both are somehow passed; the editor never sends both.
 * The added slot may instead carry a mixed sequence — clips and stills in
 * one ordered run. Each clip decodes as its own segment and each unbroken
 * run of stills composes as one image segment, every one of them painted
 * through the added slot's single paint seat (paintIndex 1), so the
 * sequence wears the second clip's one style, framing and overlays. The
 * start/end window trims the whole run, exactly as it trims one clip. */
export async function exportTikTok({ source, appendSource, appendImages = null, appendSequence = null, reduceMotion = false, canvas, drawFrame, onProgress, signal, baseMuted = false, appendMuted = false, baseStart = 0, appendStart = 0, baseEnd = null, appendEnd = null }) {
  const { width, height, fps, videoBitrate, audioBitrate } = TIKTOK_EXPORT;
  const videoConfig = { codec: "avc", bitrate: videoBitrate, fullCodecString: "avc1.640028", latencyMode: "quality" };
  const audioConfig = { codec: "aac", bitrate: audioBitrate, transform: { sampleRate: 48000, numberOfChannels: 2 } };
  let failed = false;
  const checkCancelled = () => {
    if (signal?.aborted) throw signal.reason || new DOMException("Export cancelled.", "AbortError");
    if (failed) throw new Error("Export stopped after an encoding failure.");
  };
  checkCancelled();
  if (!await canEncodeVideo("avc", { ...videoConfig, width, height, frameRate: fps })) {
    throw new Error("TikTok MP4 encoding is unavailable in this browser. Open this editor in a current Chrome or Edge browser.");
  }
  const inputs = [];
  let output;
  let finalized = false;
  try {
    const segments = [];
    let duration = 0;
    for (const [index, blob] of (appendSource ? [source, appendSource] : [source]).entries()) {
      const input = new Input({ source: new BlobSource(blob), formats: ALL_FORMATS });
      inputs.push(input);
      const track = await input.getPrimaryVideoTrack();
      const label = index ? "added clip" : "source clip";
      if (!track || !await track.canDecode()) throw new Error(`The ${label} cannot be decoded. Upload a playable MP4 or WebM video.`);
      const first = Math.max(0, await track.getFirstTimestamp());
      const full = (await track.computeDuration()) - first;
      if (!Number.isFinite(full) || full <= 0) throw new Error(`The ${label} has no playable duration. Upload another video.`);
      const run = clipWindow(full, index ? appendStart : baseStart, undefined, index ? appendEnd : baseEnd);
      if (!(run.duration > 0)) throw new Error(`The ${label} has nothing left after its start point. Move the start point earlier.`);
      const origin = first + run.start;
      const length = run.duration;
      const audioTrack = await input.getPrimaryAudioTrack();
      if (audioTrack && (!await audioTrack.canDecode() || !await canEncodeAudio("aac", { sampleRate: 48000, numberOfChannels: 2, bitrate: audioBitrate }))) {
        throw new Error("This browser cannot preserve this clip's audio in TikTok MP4. Use a current Chrome or Edge browser; audio will not be silently removed.");
      }
      segments.push({ track, audioTrack, origin, duration: length, start: duration, muted: index ? appendMuted : baseMuted });
      duration += length;
    }
    if (!appendSource && appendImages?.length) {
      const total = imageSequenceDuration(appendImages);
      if (!(total > 0)) throw new Error("The added images have no playable duration. Give each image at least a second on screen.");
      const run = clipWindow(total, appendStart, undefined, appendEnd);
      if (!(run.duration > 0)) throw new Error("The image sequence has nothing left after its start point. Move the start point earlier.");
      segments.push({ kind: "images", images: appendImages, audioTrack: null, origin: run.start, duration: run.duration, start: duration, muted: true });
      duration += run.duration;
    }
    if (!appendSource && !appendImages?.length && appendSequence?.length) {
      // Measure the run first: a clip contributes its decoded length, a
      // still its hold. The window then slices items the way it slices
      // one clip — an item the window starts inside contributes from
      // that point, an item outside it contributes nothing.
      const itemRuns = [];
      let total = 0;
      for (const item of appendSequence) {
        if (item.kind === "video") {
          const input = new Input({ source: new BlobSource(item.blob), formats: ALL_FORMATS });
          inputs.push(input);
          const track = await input.getPrimaryVideoTrack();
          if (!track || !await track.canDecode()) throw new Error("One of the added clips cannot be decoded. Upload a playable MP4 or WebM video.");
          const first = Math.max(0, await track.getFirstTimestamp());
          const full = (await track.computeDuration()) - first;
          if (!Number.isFinite(full) || full <= 0) throw new Error("One of the added clips has no playable duration. Upload another video.");
          const audioTrack = await input.getPrimaryAudioTrack();
          if (audioTrack && (!await audioTrack.canDecode() || !await canEncodeAudio("aac", { sampleRate: 48000, numberOfChannels: 2, bitrate: audioBitrate }))) {
            throw new Error("This browser cannot preserve this clip's audio in TikTok MP4. Use a current Chrome or Edge browser; audio will not be silently removed.");
          }
          itemRuns.push({ kind: "video", track, audioTrack, first, duration: full });
          total += full;
        } else {
          itemRuns.push({ kind: "image", item, duration: item.seconds });
          total += item.seconds;
        }
      }
      if (!(total > 0)) throw new Error("The second clip sequence has no playable duration. Give each image at least a second on screen.");
      const run = clipWindow(total, appendStart, undefined, appendEnd);
      if (!(run.duration > 0)) throw new Error("The second clip sequence has nothing left after its start point. Move the start point earlier.");
      let cursor = 0;
      let placed = duration;
      // One pending image segment per unbroken run of stills: the
      // compositor lays its entries out from the run's own start, so
      // the segment's origin is the window's offset into the run and
      // its span is the run's sliced span, however many stills of the
      // run fall outside the window.
      let imageGroup = null;
      const flushImageGroup = () => {
        if (imageGroup?.sliced) {
          segments.push({ kind: "images", images: imageGroup.entries, audioTrack: null, origin: imageGroup.firstSlice - imageGroup.start, duration: imageGroup.lastSlice - imageGroup.firstSlice, start: imageGroup.placedStart, muted: true, paintIndex: 1 });
        }
        imageGroup = null;
      };
      for (const itemRun of itemRuns) {
        const itemStart = cursor;
        const itemEnd = cursor + itemRun.duration;
        cursor = itemEnd;
        const sliceStart = Math.max(itemStart, run.start);
        const sliceEnd = Math.min(itemEnd, run.start + run.duration);
        const hasSlice = sliceEnd > sliceStart;
        if (itemRun.kind === "video") {
          flushImageGroup();
          if (hasSlice) {
            segments.push({ track: itemRun.track, audioTrack: itemRun.audioTrack, origin: itemRun.first + (sliceStart - itemStart), duration: sliceEnd - sliceStart, start: placed, muted: appendMuted, paintIndex: 1 });
            placed += sliceEnd - sliceStart;
          }
        } else {
          if (!imageGroup) imageGroup = { entries: [], start: itemStart, sliced: false, firstSlice: 0, lastSlice: 0, placedStart: 0 };
          imageGroup.entries.push({ source: itemRun.item.source, seconds: itemRun.duration, motion: itemRun.item.motion });
          if (hasSlice) {
            if (!imageGroup.sliced) {
              imageGroup.sliced = true;
              imageGroup.firstSlice = sliceStart;
              imageGroup.placedStart = placed;
            }
            imageGroup.lastSlice = sliceEnd;
            placed += sliceEnd - sliceStart;
          }
        }
      }
      flushImageGroup();
      duration = placed;
    }
    canvas.width = width;
    canvas.height = height;
    output = new Output({ format: new Mp4OutputFormat({ fastStart: "in-memory" }), target: new BufferTarget() });
    const videoSource = new CanvasSource(canvas, videoConfig);
    output.addVideoTrack(videoSource, { frameRate: fps });
    const hasAudio = segments.some((segment) => segment.audioTrack && !segment.muted);
    const audioSource = hasAudio ? new AudioSampleSource(audioConfig) : null;
    if (audioSource) output.addAudioTrack(audioSource);
    await output.start();
    const frameCount = Math.ceil(duration * fps - 1e-6);
    const encodeVideo = async () => {
      for (const [index, segment] of segments.entries()) {
        const first = Math.max(0, Math.ceil(segment.start * fps - 1e-6));
        const last = Math.ceil((segment.start + segment.duration) * fps - 1e-6);
        if (segment.kind === "images") {
          // No track to decode: compose each frame from the stills at the
          // frame's own sequence time, the same composition the preview
          // paints, and hand it to the painter like a decoded frame.
          const scratch = document.createElement("canvas");
          const drawables = segment.images.map((entry) => entry.source);
          for (let frame = first; frame < last; frame++) {
            checkCancelled();
            composeImageFrame(scratch, drawables, segment.images, segment.origin + frame / fps - segment.start, { reduceMotion: !!reduceMotion });
            drawFrame(frame / fps, scratch, segment.paintIndex ?? index);
            await videoSource.add(frame / fps, segments.length > 1 ? Math.min(1 / fps, duration - frame / fps) : 1 / fps);
            onProgress?.((frame + 1) / frameCount);
          }
          continue;
        }
        const timestamps = function* () {
          for (let frame = first; frame < last; frame++) yield segment.origin + frame / fps - segment.start;
        };
        let frame = first;
        for await (const decoded of new CanvasSink(segment.track, { poolSize: 2 }).canvasesAtTimestamps(timestamps())) {
          checkCancelled();
          if (!decoded) throw new Error(`The ${index ? "added" : "source"} video is missing a frame at ${(frame / fps).toFixed(2)}s. Choose another clip.`);
          drawFrame(frame / fps, decoded.canvas, segment.paintIndex ?? index);
          await videoSource.add(frame / fps, segments.length > 1 ? Math.min(1 / fps, duration - frame / fps) : 1 / fps);
          frame++;
          onProgress?.(frame / frameCount);
        }
        if (frame !== last) throw new Error("The video decoder stopped before the clip ended. Choose another clip.");
      }
      videoSource.close();
    };
    const encodeAudio = async () => {
      if (!audioSource) return;
      if (segments.length > 1) {
        await encodeJoinedAudio(segments, audioSource, checkCancelled);
      } else {
        const { audioTrack, origin, duration, muted } = segments[0];
        if (muted) { audioSource.close(); return; }
        await passthroughSegmentAudio({ audioTrack, audioSource, origin, duration, checkCancelled });
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
    checkCancelled();
    await output.finalize();
    finalized = true;
    return {
      blob: new Blob([output.target.buffer], { type: "video/mp4" }), duration: segments.length > 1 ? duration : frameCount / fps,
      audioSegments: segments.filter((segment) => segment.audioTrack && !segment.muted).map(({ start, duration }) => ({ start, duration })),
    };
  } finally {
    try {
      if (output && !finalized && !failed) await output.cancel();
    } finally { inputs.forEach((input) => input.dispose()); }
  }
}
