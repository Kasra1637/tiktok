import { AudioSampleSink } from "mediabunny";

/**
 * Single-segment AAC passthrough shared by the upscaler and the Demo + CTA
 * export: resample one decoded stretch into the encoder with its timestamps
 * rebased to the output timeline, sample for sample.
 *
 * The joined (two-clip) export keeps its own OfflineAudioContext path — only
 * the single straight copy lives here, so a fix to trim math lands in both
 * single-segment pipelines at once. The caller owns the muted case (close an
 * empty source and return); this function assumes audio must be preserved
 * and closes the source when the copy is complete.
 */
export async function passthroughSegmentAudio({ audioTrack, audioSource, origin, duration, checkCancelled }) {
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
  audioSource.close();
}
