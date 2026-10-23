import { exportTikTok } from "./exportTikTok";
import { canEncodeAudio, canEncodeVideo, Input, Output, CanvasSink, CanvasSource, AudioSampleSink, AudioSampleSource } from "mediabunny";

jest.mock("mediabunny", () => ({
  ALL_FORMATS: [], BlobSource: jest.fn(), BufferTarget: jest.fn(), Mp4OutputFormat: jest.fn(),
  Input: jest.fn(), Output: jest.fn(), CanvasSink: jest.fn(), CanvasSource: jest.fn(),
  AudioSampleSink: jest.fn(), AudioSampleSource: jest.fn(), canEncodeAudio: jest.fn(), canEncodeVideo: jest.fn(),
}));

let input, output, videoSource, audioSource, track, audioTrack, frames;
const encode = (options = {}) => exportTikTok({ source: new Blob(), canvas: {}, drawFrame: jest.fn(), ...options });

beforeEach(() => {
  jest.clearAllMocks();
  canEncodeVideo.mockResolvedValue(true);
  canEncodeAudio.mockResolvedValue(true);
  track = { canDecode: async () => true, getFirstTimestamp: async () => 0.5, computeDuration: async () => 0.61 };
  audioTrack = { canDecode: async () => true };
  input = { getPrimaryVideoTrack: async () => track, getPrimaryAudioTrack: async () => audioTrack, dispose: jest.fn() };
  output = { target: { buffer: new Uint8Array([1, 2, 3]) }, addVideoTrack: jest.fn(), addAudioTrack: jest.fn(), start: jest.fn(), finalize: jest.fn(), cancel: jest.fn() };
  videoSource = { add: jest.fn(async () => { await new Promise((r) => setTimeout(r, 5)); }), close: jest.fn() };
  audioSource = { add: jest.fn(), close: jest.fn() };
  frames = [];
  Input.mockImplementation(() => input);
  Output.mockImplementation(() => output);
  CanvasSource.mockImplementation(() => videoSource);
  AudioSampleSource.mockImplementation(() => audioSource);
  CanvasSink.mockImplementation(() => ({ canvasesAtTimestamps: async function* (timestamps) {
    for (const time of timestamps) { frames.push(time); yield { canvas: { sourceTime: time } }; }
  } }));
  AudioSampleSink.mockImplementation(() => ({ samples: async function* () {} }));
});

test("slow encoding retains exact 30 fps timestamps and every source frame", async () => {
  const drawFrame = jest.fn(), onProgress = jest.fn(), canvas = {};
  const result = await encode({ drawFrame, onProgress, canvas });
  expect(canvas).toEqual({ width: 1080, height: 1920 });
  expect(frames).toEqual([0.5, 0.5 + 1 / 30, 0.5 + 2 / 30, 0.6]);
  expect(videoSource.add.mock.calls).toEqual([0, 1, 2, 3].map((i) => [i / 30, 1 / 30]));
  expect(drawFrame.mock.calls.map(([time]) => time)).toEqual([0, 1 / 30, 2 / 30, 0.1]);
  expect(onProgress).toHaveBeenLastCalledWith(1);
  expect(result.duration).toBe(4 / 30);
  expect(result.blob.type).toBe("video/mp4");
  expect(output.finalize).toHaveBeenCalledTimes(1);
  expect(output.cancel).not.toHaveBeenCalled();
  expect(input.dispose).toHaveBeenCalledTimes(1);
});

test("audio is trimmed and rebased to video origin, never preview mute or volume", async () => {
  const trimmed = { timestamp: 0.5, setTimestamp: jest.fn(), close: jest.fn() };
  const sample = { timestamp: 0.48, sampleRate: 48000, numberOfFrames: 9600, trim: jest.fn(() => trimmed), close: jest.fn() };
  AudioSampleSink.mockImplementation(() => ({ samples: async function* () { yield sample; } }));
  await encode();
  expect(sample.trim).toHaveBeenCalledWith(960, 6240);
  expect(trimmed.setTimestamp).toHaveBeenCalledWith(0);
  expect(audioSource.add).toHaveBeenCalledWith(trimmed);
  expect(trimmed.close).toHaveBeenCalledTimes(1);
  expect(sample.close).toHaveBeenCalledTimes(1);
  expect(AudioSampleSource).toHaveBeenCalledWith(expect.objectContaining({ codec: "aac", bitrate: 192000, transform: { sampleRate: 48000, numberOfChannels: 2 } }));
});

test("silent clips stay silent without an invented audio track", async () => {
  input.getPrimaryAudioTrack = async () => null;
  await encode();
  expect(output.addAudioTrack).not.toHaveBeenCalled();
});

test("unsupported H.264 fails with a next step and no container fallback", async () => {
  canEncodeVideo.mockResolvedValue(false);
  await expect(encode()).rejects.toThrow(/Chrome or Edge/);
  expect(Output).not.toHaveBeenCalled();
});

test("unsupported AAC refuses the export rather than dropping source audio", async () => {
  canEncodeAudio.mockResolvedValue(false);
  await expect(encode()).rejects.toThrow(/audio will not be silently removed/);
  expect(Output).not.toHaveBeenCalled();
  expect(input.dispose).toHaveBeenCalled();
});

test("a missing frame cancels the muxer and never finalizes partial output", async () => {
  CanvasSink.mockImplementation(() => ({ canvasesAtTimestamps: async function* () { yield null; } }));
  await expect(encode()).rejects.toThrow(/missing a frame/);
  expect(output.cancel).toHaveBeenCalledTimes(1);
  expect(output.finalize).not.toHaveBeenCalled();
  expect(input.dispose).toHaveBeenCalled();
});

test("cancel stops encoding and releases the source", async () => {
  const controller = new AbortController();
  await expect(encode({ signal: controller.signal, onProgress: () => controller.abort() })).rejects.toThrow();
  expect(videoSource.add).toHaveBeenCalledTimes(1);
  expect(output.cancel).toHaveBeenCalledTimes(1);
  expect(output.finalize).not.toHaveBeenCalled();
  expect(input.dispose).toHaveBeenCalled();
});
