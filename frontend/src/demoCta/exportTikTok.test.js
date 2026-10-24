import { exportTikTok } from "./exportTikTok";
import { canEncodeAudio, canEncodeVideo, Input, Output, CanvasSink, CanvasSource, AudioSample, AudioSampleSink, AudioSampleSource } from "mediabunny";

jest.mock("mediabunny", () => ({
  ALL_FORMATS: [], BlobSource: jest.fn(), BufferTarget: jest.fn(), Mp4OutputFormat: jest.fn(),
  Input: jest.fn(), Output: jest.fn(), CanvasSink: jest.fn(), CanvasSource: jest.fn(), AudioSample: { fromAudioBuffer: jest.fn() },
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
  videoSource = { add: jest.fn(async () => { await new Promise((r) => setTimeout(r, 1)); }), close: jest.fn() };
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

test("slow encoding retains 30 fps timestamps and every source frame", async () => {
  const drawFrame = jest.fn(), onProgress = jest.fn(), canvas = {};
  const result = await encode({ drawFrame, onProgress, canvas });
  expect(canvas).toEqual({ width: 1080, height: 1920 });
  expect(frames).toEqual([0.5, 0.5 + 1 / 30, 0.5 + 2 / 30, 0.6]);
  expect(videoSource.add.mock.calls.map(([time]) => time)).toEqual([0, 1 / 30, 2 / 30, 0.1]);
  expect(drawFrame.mock.calls.map(([time]) => time)).toEqual([0, 1 / 30, 2 / 30, 0.1]);
  expect(onProgress).toHaveBeenLastCalledWith(1);
  expect(result.duration).toBe(4 / 30);
  expect(result.blob.type).toBe("video/mp4");
  expect(output.finalize).toHaveBeenCalledTimes(1);
  expect(output.cancel).not.toHaveBeenCalled();
  expect(input.dispose).toHaveBeenCalledTimes(1);
});

test("single-source audio is trimmed and rebased, never preview mute or volume", async () => {
  const trimmed = { timestamp: 0.5, setTimestamp: jest.fn(), close: jest.fn() };
  const sample = { timestamp: 0.48, sampleRate: 48000, numberOfFrames: 9600, trim: jest.fn(() => trimmed), close: jest.fn() };
  AudioSampleSink.mockImplementation(() => ({ samples: async function* () { yield sample; } }));
  await encode();
  expect(sample.trim).toHaveBeenCalledWith(960, 6240);
  expect(trimmed.setTimestamp).toHaveBeenCalledWith(0);
  expect(audioSource.add).toHaveBeenCalledWith(trimmed);
  expect(trimmed.close).toHaveBeenCalledTimes(1);
  expect(sample.close).toHaveBeenCalledTimes(1);
});

function addClip({ audio = false, duration = 0.08, decodes = true } = {}) {
  const second = {
    getPrimaryVideoTrack: async () => ({ canDecode: async () => decodes, getFirstTimestamp: async () => 0.2, computeDuration: async () => 0.2 + duration }),
    getPrimaryAudioTrack: async () => audio ? { canDecode: async () => true, second: true } : null,
    dispose: jest.fn(),
  };
  Input.mockImplementationOnce(() => input).mockImplementationOnce(() => second);
  return second;
}

test("added clip follows the complete base once, with summed duration and no overlapping frames", async () => {
  input.getPrimaryAudioTrack = async () => null;
  const second = addClip();
  const drawFrame = jest.fn();
  const result = await encode({ appendSource: new Blob(), drawFrame });
  expect(result.duration).toBeCloseTo(0.19);
  expect(drawFrame.mock.calls.map(([, , segment]) => segment)).toEqual([0, 0, 0, 0, 1, 1]);
  const times = videoSource.add.mock.calls.map(([time]) => time);
  expect(times).toEqual([0, 1 / 30, 2 / 30, 3 / 30, 4 / 30, 5 / 30]);
  expect(drawFrame.mock.calls[4][1].sourceTime).toBeCloseTo(0.2 + 4 / 30 - 0.11);
  expect(videoSource.add.mock.calls[5][1]).toBeCloseTo(0.19 - 5 / 30);
  expect(second.dispose).toHaveBeenCalledTimes(1);
  expect(output.addAudioTrack).not.toHaveBeenCalled();
});

test("10s plus 8s exports 18s, not a loop or the longer input duration", async () => {
  videoSource.add.mockImplementation(async () => {});
  track.computeDuration = async () => 10.5;
  input.getPrimaryAudioTrack = async () => null;
  addClip({ duration: 8 });
  const result = await encode({ appendSource: new Blob() });
  expect(result.duration).toBe(18);
  expect(videoSource.add).toHaveBeenCalledTimes(540);
});

test.each([true, false])("joined AAC schedules both rates/channels without retiming (base audio: %s)", async (baseAudio) => {
  if (!baseAudio) input.getPrimaryAudioTrack = async () => null;
  addClip({ audio: true });
  const nodes = [], decoded = [], normalized = { close: jest.fn() };
  const pcm = new Float32Array(9120).fill(0.4);
  const rendered = { numberOfChannels: 2, getChannelData: () => pcm };
  global.OfflineAudioContext = jest.fn().mockImplementation(() => ({
    destination: {},
    createBufferSource: () => { const node = { connect: jest.fn(), start: jest.fn() }; nodes.push(node); return node; },
    startRendering: async () => rendered,
  }));
  AudioSample.fromAudioBuffer.mockReturnValue([normalized]);
  AudioSampleSink.mockImplementation((track) => ({ samples: async function* () {
    const sample = { timestamp: track.second ? 0.2 : 0.5, duration: track.second ? 0.08 : 0.11,
      toAudioBuffer: () => ({ sampleRate: track.second ? 44100 : 48000, numberOfChannels: track.second ? 1 : 2 }), close: jest.fn() };
    decoded.push(sample); yield sample;
  } }));
  try {
    const result = await encode({ appendSource: new Blob() });
    expect(OfflineAudioContext).toHaveBeenCalledWith(2, 9120, 48000);
    expect(nodes[nodes.length - 1].start.mock.calls[0][0]).toBeCloseTo(0.11);
    expect(nodes[nodes.length - 1].buffer.sampleRate).toBe(44100);
    if (baseAudio) {
      expect(nodes[0].start.mock.calls[0].slice(0, 2)).toEqual([0, 0]);
      expect(nodes[0].start.mock.calls[0][2]).toBeCloseTo(0.11);
    }
    expect(AudioSample.fromAudioBuffer).toHaveBeenCalledWith(rendered, 0);
    expect(audioSource.add).toHaveBeenCalledWith(normalized);
    expect(normalized.close).toHaveBeenCalled();
    decoded.forEach((sample) => expect(sample.close).toHaveBeenCalled());
    expect(result.audioSegments).toHaveLength(baseAudio ? 2 : 1);
    expect(AudioSampleSource).toHaveBeenCalledWith(expect.objectContaining({ codec: "aac", transform: { sampleRate: 48000, numberOfChannels: 2 } }));
  } finally { delete global.OfflineAudioContext; }
});

test("unsupported H.264 or AAC fails rather than silently dropping audio", async () => {
  canEncodeVideo.mockResolvedValueOnce(false);
  await expect(encode()).rejects.toThrow(/Chrome or Edge/);
  canEncodeAudio.mockResolvedValueOnce(false);
  await expect(encode()).rejects.toThrow(/audio will not be silently removed/);
  expect(Output).not.toHaveBeenCalled();
});

test("undecodable added clip releases both sources and refuses partial output", async () => {
  const second = addClip({ decodes: false });
  await expect(encode({ appendSource: new Blob() })).rejects.toThrow(/added clip cannot be decoded/);
  expect(second.dispose).toHaveBeenCalledTimes(1);
  expect(input.dispose).toHaveBeenCalledTimes(1);
  expect(output.finalize).not.toHaveBeenCalled();
});

test("missing frames and cancellation never finalize partial output", async () => {
  CanvasSink.mockImplementationOnce(() => ({ canvasesAtTimestamps: async function* () { yield null; } }));
  await expect(encode()).rejects.toThrow(/missing a frame/);
  const controller = new AbortController();
  await expect(encode({ signal: controller.signal, onProgress: () => controller.abort() })).rejects.toThrow();
  expect(output.cancel).toHaveBeenCalledTimes(2);
  expect(output.finalize).not.toHaveBeenCalled();
});
