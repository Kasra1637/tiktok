import {
  ALL_FORMATS, AudioSampleSink, AudioSampleSource, BlobSource, BufferTarget,
  CanvasSink, CanvasSource, Input, Mp4OutputFormat, Output, canEncodeAudio, canEncodeVideo,
} from "mediabunny";

export const TIKTOK_EXPORT = Object.freeze({
  width: 1080, height: 1920, fps: 30, videoBitrate: 8_000_000, audioBitrate: 192_000,
});

/** No playback clock: decoding/encoding can take as long as needed without moving the timeline. */
export async function exportTikTok({ source, canvas, drawFrame, onProgress, signal }) {
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
  const input = new Input({ source: new BlobSource(source), formats: ALL_FORMATS });
  let output;
  let finalized = false;
  try {
    const track = await input.getPrimaryVideoTrack();
    if (!track || !await track.canDecode()) throw new Error("This clip cannot be decoded. Upload a playable MP4 or WebM video.");
    const origin = Math.max(0, await track.getFirstTimestamp());
    const duration = (await track.computeDuration()) - origin;
    if (!Number.isFinite(duration) || duration <= 0) throw new Error("The source clip has no playable duration. Upload another video.");
    const audioTrack = await input.getPrimaryAudioTrack();
    if (audioTrack && (!await audioTrack.canDecode() || !await canEncodeAudio("aac", { sampleRate: 48000, numberOfChannels: 2, bitrate: audioBitrate }))) {
      throw new Error("This browser cannot preserve this clip's audio in TikTok MP4. Use a current Chrome or Edge browser; audio will not be silently removed.");
    }
    canvas.width = width;
    canvas.height = height;
    output = new Output({ format: new Mp4OutputFormat({ fastStart: "in-memory" }), target: new BufferTarget() });
    const videoSource = new CanvasSource(canvas, videoConfig);
    output.addVideoTrack(videoSource, { frameRate: fps });
    const audioSource = audioTrack ? new AudioSampleSource(audioConfig) : null;
    if (audioSource) output.addAudioTrack(audioSource);
    await output.start();
    const frameCount = Math.ceil(duration * fps - 1e-6);
    const timestamps = function* () {
      for (let frame = 0; frame < frameCount; frame++) yield origin + frame / fps;
    };
    const encodeVideo = async () => {
      const sink = new CanvasSink(track, { poolSize: 2 });
      let frame = 0;
      for await (const decoded of sink.canvasesAtTimestamps(timestamps())) {
        checkCancelled();
        if (!decoded) throw new Error(`The source video is missing a frame at ${(frame / fps).toFixed(2)}s. Choose another clip.`);
        const time = frame / fps;
        drawFrame(time, decoded.canvas);
        await videoSource.add(time, 1 / fps);
        frame++;
        onProgress?.(frame / frameCount);
      }
      videoSource.close();
    };
    const encodeAudio = async () => {
      if (!audioSource) return;
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
          } finally {
            trimmed.close();
          }
        } finally {
          sample.close();
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
      // Both decoders must settle before disposing their shared input.
      await Promise.allSettled(jobs);
      throw error;
    }
    checkCancelled();
    await output.finalize();
    finalized = true;
    return { blob: new Blob([output.target.buffer], { type: "video/mp4" }), duration: frameCount / fps };
  } finally {
    try {
      if (output && !finalized && !failed) await output.cancel();
    } finally {
      input.dispose();
    }
  }
}
