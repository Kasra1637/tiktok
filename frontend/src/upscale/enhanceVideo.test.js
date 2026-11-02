import { enhanceVideo } from "./enhanceVideo";
import {
  canEncodeAudio,
  canEncodeVideo,
  Input,
  Output,
  CanvasSink,
  CanvasSource,
  AudioSampleSource,
} from "mediabunny";

jest.mock("mediabunny", () => ({
  ALL_FORMATS: [],
  BlobSource: jest.fn(),
  BufferTarget: jest.fn(),
  Mp4OutputFormat: jest.fn(),
  Input: jest.fn(),
  Output: jest.fn(),
  CanvasSink: jest.fn(),
  CanvasSource: jest.fn(),
  AudioSampleSource: jest.fn(),
  canEncodeAudio: jest.fn(),
  canEncodeVideo: jest.fn(),
}));

function fakeCtx() {
  return {
    drawImage: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    filter: "none",
    globalCompositeOperation: "source-over",
    globalAlpha: 1,
    imageSmoothingEnabled: true,
    imageSmoothingQuality: "",
  };
}

function fakeCanvas() {
  const ctx = fakeCtx();
  return {
    width: 0,
    height: 0,
    ctx,
    getContext: () => ctx,
    toBlob: (cb) => cb(new Blob(["pixels"], { type: "image/png" })),
  };
}

beforeEach(() => {
  jest.clearAllMocks();
  canEncodeVideo.mockResolvedValue(true);
  canEncodeAudio.mockResolvedValue(true);
});

test("the video encode path refuses a clip that is already 1080p at its gate", async () => {
  // 1920x1080 is already 1080p: the gate refuses before any decode work.
  await expect(
    enhanceVideo({
      blob: new Blob(["clip"]),
      canvas: fakeCanvas(),
      sourceWidth: 1920,
      sourceHeight: 1080,
      duration: 5,
      signal: new AbortController().signal,
    })
  ).rejects.toThrow(/already 1920 × 1080 — upscaling to 1080p would not add resolution/);
});

test("the video encode path refuses a wide clip whose long side is already capped", async () => {
  // Short side is under 1080, but the long side fills the 1920 ceiling, so the
  // only "1080p" export would be the input's own size.
  await expect(
    enhanceVideo({
      blob: new Blob(["clip"]),
      canvas: fakeCanvas(),
      sourceWidth: 1920,
      sourceHeight: 800,
      duration: 5,
      signal: new AbortController().signal,
    })
  ).rejects.toThrow(/upscaling to 1080p would not add resolution/);
});

test("the video encode path refuses a missing duration before encoding", async () => {
  await expect(
    enhanceVideo({
      blob: new Blob(["clip"]),
      canvas: fakeCanvas(),
      sourceWidth: 640,
      sourceHeight: 480,
      duration: 0,
      signal: new AbortController().signal,
    })
  ).rejects.toThrow(/no playable duration/i);
});

test("upscaling preserves source color tone and shadow levels without overlay blend or contrast/saturation filters", async () => {
  const track = {
    canDecode: async () => true,
    getFirstTimestamp: async () => 0,
  };
  const input = {
    getPrimaryVideoTrack: async () => track,
    getPrimaryAudioTrack: async () => null,
    dispose: jest.fn(),
  };
  const output = {
    target: { buffer: new Uint8Array([1, 2, 3]) },
    addVideoTrack: jest.fn(),
    addAudioTrack: jest.fn(),
    start: jest.fn(),
    finalize: jest.fn(),
    cancel: jest.fn(),
  };
  const videoSource = { add: jest.fn(async () => {}), close: jest.fn() };
  Input.mockImplementation(() => input);
  Output.mockImplementation(() => output);
  CanvasSource.mockImplementation(() => videoSource);
  const decodedFrame = { canvas: { isDecodedFrame: true } };
  CanvasSink.mockImplementation(() => ({
    canvasesAtTimestamps: async function* (timestamps) {
      for (const _ of timestamps) yield decodedFrame;
    },
  }));

  const createdCanvases = [];
  const realCreate = document.createElement.bind(document);
  const spy = jest.spyOn(document, "createElement").mockImplementation((tag) => {
    if (tag === "canvas") {
      const c = fakeCanvas();
      createdCanvases.push(c);
      return c;
    }
    return realCreate(tag);
  });

  try {
    const canvas = fakeCanvas();
    const out = await enhanceVideo({
      blob: new Blob(["clip"]),
      canvas,
      sourceWidth: 540,
      sourceHeight: 960,
      duration: 1 / 30,
      signal: new AbortController().signal,
    });

    expect(out.width).toBe(1080);
    expect(out.height).toBe(1920);
    expect(canvas.ctx.imageSmoothingEnabled).toBe(true);
    expect(canvas.ctx.imageSmoothingQuality).toBe("high");
    expect(canvas.ctx.drawImage).toHaveBeenCalledTimes(1);
    expect(canvas.ctx.drawImage).toHaveBeenCalledWith(decodedFrame.canvas, 0, 0, 1080, 1920);
    expect(canvas.ctx.globalCompositeOperation).toBe("source-over");
    expect(canvas.ctx.filter).toBe("url(#hookforge-upscale-unsharp)");
    expect(canvas.ctx.filter).not.toMatch(/contrast|saturate|brightness/);
    const filterEl = document.getElementById("hookforge-upscale-unsharp");
    expect(filterEl).not.toBeNull();
    expect(filterEl.getAttribute("color-interpolation-filters")).toBe("sRGB");
    const matrix = filterEl.querySelector("feConvolveMatrix");
    const weights = matrix.getAttribute("kernelMatrix").trim().split(/\s+/).map(Number);
    const weightSum = weights.reduce((a, b) => a + b, 0);
    expect(weightSum).toBeCloseTo(1, 6);
    expect(createdCanvases).toHaveLength(0);
  } finally {
    spy.mockRestore();
  }
});

