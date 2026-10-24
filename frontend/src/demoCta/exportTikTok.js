import {
  ALL_FORMATS, AudioSample, AudioSampleSink, AudioSampleSource, BlobSource, BufferTarget,
  CanvasSink, CanvasSource, Input, Mp4OutputFormat, Output, canEncodeAudio, canEncodeVideo,
} from "mediabunny";

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
    if (!segment.audioTrack) continue;
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

/** Decode pinned sources, base then optional upload, on one 30 fps timeline. */
export async function exportTikTok({ source, appendSource, canvas, drawFrame, onProgress, signal }) {
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
    for (const [index, blob] of [source, appendSource].filter(Boolean).entries()) {
      const input = new Input({ source: new BlobSource(blob), formats: ALL_FORMATS });
      inputs.push(input);
      const track = await input.getPrimaryVideoTrack();
      const label = index ? "added clip" : "source clip";
      if (!track || !await track.canDecode()) throw new Error(`The ${label} cannot be decoded. Upload a playable MP4 or WebM video.`);
      const origin = Math.max(0, await track.getFirstTimestamp());
      const length = (await track.computeDuration()) - origin;
      if (!Number.isFinite(length) || length <= 0) throw new Error(`The ${label} has no playable duration. Upload another video.`);
      const audioTrack = await input.getPrimaryAudioTrack();
      if (audioTrack && (!await audioTrack.canDecode() || !await canEncodeAudio("aac", { sampleRate: 48000, numberOfChannels: 2, bitrate: audioBitrate }))) {
        throw new Error("This browser cannot preserve this clip's audio in TikTok MP4. Use a current Chrome or Edge browser; audio will not be silently removed.");
      }
      segments.push({ track, audioTrack, origin, duration: length, start: duration });
      duration += length;
    }
    canvas.width = width;
    canvas.height = height;
    output = new Output({ format: new Mp4OutputFormat({ fastStart: "in-memory" }), target: new BufferTarget() });
    const videoSource = new CanvasSource(canvas, videoConfig);
    output.addVideoTrack(videoSource, { frameRate: fps });
    const hasAudio = segments.some((segment) => segment.audioTrack);
    const audioSource = hasAudio ? new AudioSampleSource(audioConfig) : null;
    if (audioSource) output.addAudioTrack(audioSource);
    await output.start();
    const frameCount = Math.ceil(duration * fps - 1e-6);
    const encodeVideo = async () => {
      for (const [index, segment] of segments.entries()) {
        const first = Math.max(0, Math.ceil(segment.start * fps - 1e-6));
        const last = Math.ceil((segment.start + segment.duration) * fps - 1e-6);
        const timestamps = function* () {
          for (let frame = first; frame < last; frame++) yield segment.origin + frame / fps - segment.start;
        };
        let frame = first;
        for await (const decoded of new CanvasSink(segment.track, { poolSize: 2 }).canvasesAtTimestamps(timestamps())) {
          checkCancelled();
          if (!decoded) throw new Error(`The ${index ? "added" : "source"} video is missing a frame at ${(frame / fps).toFixed(2)}s. Choose another clip.`);
          drawFrame(frame / fps, decoded.canvas, index);
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
        const { audioTrack, origin, duration } = segments[0];
        for await (const sample of new AudioSampleSink(audioTrack).samples(origin, origin + duration)) {
          try {
            checkCancelled();
            const start = Math.max(0, Math.round((origin - sample.timestamp) * sample.sampleRate));
            const end = Math.min(sample.numberOfFrames, Math.round((origin + duration - sample.timestamp) * sample.sampleRate));
            if (end <= start) continue;
            const trimmed = sample.trim(start, end);
            try {
              trimmed.setTimestamp(trimmed.timestamp - origin);
              await audioSource.add(trimmed);
            } finally { trimmed.close(); }
          } finally { sample.close(); }
        }
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
      audioSegments: segments.filter((segment) => segment.audioTrack).map(({ start, duration }) => ({ start, duration })),
    };
  } finally {
    try {
      if (output && !finalized && !failed) await output.cancel();
    } finally { inputs.forEach((input) => input.dispose()); }
  }
}
