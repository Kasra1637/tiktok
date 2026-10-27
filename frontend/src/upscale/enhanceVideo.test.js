import { enhanceVideo } from "./enhanceVideo";

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
