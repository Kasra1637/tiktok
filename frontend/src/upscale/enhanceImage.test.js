import { enhanceImage, enhanceVideo } from "./enhanceVideo";
import { UPSCALE } from "./sizing";
import { probeImage } from "./useUpscaler";

function fakeCtx() {
  return {
    drawImage: jest.fn(),
    save: jest.fn(),
    restore: jest.fn(),
    filter: "",
    globalCompositeOperation: "",
    globalAlpha: 1,
    imageSmoothingEnabled: true,
    imageSmoothingQuality: "",
  };
}

function fakeCanvas() {
  return {
    width: 0,
    height: 0,
    getContext: () => fakeCtx(),
    toBlob: (cb) => cb(new Blob(["pixels"], { type: "image/png" })),
  };
}

beforeEach(() => {
  global.URL.createObjectURL = jest.fn(() => "blob:mock");
  global.URL.revokeObjectURL = jest.fn();
  global.Image = function () {
    const el = {};
    Object.defineProperty(el, "src", {
      set() {
        setTimeout(() => el.onload && el.onload(), 0);
      },
    });
    return el;
  };
});

function mockScratchCanvases() {
  const scratch = fakeCanvas();
  const realCreate = document.createElement.bind(document);
  const spy = jest.spyOn(document, "createElement").mockImplementation((tag) => {
    if (tag === "canvas") return scratch;
    return realCreate(tag);
  });
  return { scratch, spy };
}

async function enhancePicture(sourceWidth, sourceHeight) {
  const { spy } = mockScratchCanvases();
  try {
    return await enhanceImage({
      blob: new Blob(["pic"], { type: "image/png" }),
      canvas: fakeCanvas(),
      sourceWidth,
      sourceHeight,
      signal: new AbortController().signal,
    });
  } finally {
    spy.mockRestore();
  }
}

test("a portrait picture lands on 2160x3840 PNG", async () => {
  const out = await enhancePicture(540, 960);
  expect(out.width).toBe(2160);
  expect(out.height).toBe(3840);
  expect(out.blob.type).toBe("image/png");
});

test("a landscape picture lands on 3840x2160", async () => {
  const out = await enhancePicture(960, 540);
  expect(out.width).toBe(3840);
  expect(out.height).toBe(2160);
});

test("a square picture lands on 2160x2160", async () => {
  const out = await enhancePicture(540, 540);
  expect(out.width).toBe(2160);
  expect(out.height).toBe(2160);
});

test("odd dimensions stay even and under the long-side ceiling", async () => {
  const out = await enhancePicture(853, 480);
  expect(out.width % 2).toBe(0);
  expect(out.height % 2).toBe(0);
  expect(Math.max(out.width, out.height)).toBeLessThanOrEqual(UPSCALE.maxSide + 1);
  expect(Math.min(out.width, out.height)).toBeGreaterThanOrEqual(UPSCALE.targetMinSide - 1);
});

test("an already-4K picture is refused before any work starts", async () => {
  await expect(
    enhanceImage({
      blob: new Blob(["pic"]),
      canvas: fakeCanvas(),
      sourceWidth: 3840,
      sourceHeight: 2160,
      signal: new AbortController().signal,
    })
  ).rejects.toThrow(/already 4K/);
});

test("the video encode path refuses already-4K dimensions at its gate", async () => {
  await expect(
    enhanceVideo({
      blob: new Blob(["clip"]),
      canvas: fakeCanvas(),
      sourceWidth: 3840,
      sourceHeight: 2160,
      duration: 5,
      signal: new AbortController().signal,
    })
  ).rejects.toThrow(/already 4K/);
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

test("probeImage resolves natural dimensions", async () => {
  const realImage = global.Image;
  const instances = [];
  global.Image = function () {
    const el = {};
    instances.push(el);
    Object.defineProperty(el, "src", {
      set() {
        el.naturalWidth = 540;
        el.naturalHeight = 960;
        setTimeout(() => el.onload && el.onload(), 0);
      },
    });
    return el;
  };
  try {
    const meta = await probeImage(new Blob(["pic"], { type: "image/png" }));
    expect(meta).toEqual({ width: 540, height: 960 });
  } finally {
    global.Image = realImage;
  }
});

test("probeImage rejects an unreadable file with a picture next step", async () => {
  const realImage = global.Image;
  global.Image = function () {
    const el = {};
    Object.defineProperty(el, "src", {
      set() {
        setTimeout(() => el.onerror && el.onerror(), 0);
      },
    });
    return el;
  };
  try {
    await expect(probeImage(new Blob(["nope"], { type: "image/png" }))).rejects.toThrow(/picture/i);
  } finally {
    global.Image = realImage;
  }
});
