import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../lib/api";
import { probeRecordingPlays, useExportFlow } from "./exportFlow";
import { AudioSampleSink, Input } from "mediabunny";

jest.mock("mediabunny", () => ({
  ALL_FORMATS: [], BlobSource: jest.fn(), Input: jest.fn(), AudioSampleSink: jest.fn(),
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("../lib/api", () => ({
  api: { saveDemoCtaExport: jest.fn() },
  getErrorMessage: (err) => err?.message || "Something went wrong.",
}));

jest.mock("../lib/feedback", () => ({
  recordSignal: jest.fn(),
}));

// Silence the failure log this flow intentionally writes.
let warned;
beforeEach(() => {
  jest.clearAllMocks();
  warned = jest.spyOn(console, "warn").mockImplementation(() => {});
});
afterEach(() => {
  warned.mockRestore();
});

function stubRef(value = null) {
  return { current: value };
}

function params(overrides = {}) {
  const noop = () => {};
  return {
    generation: { id: "gen-1", brand_profile_id: "b", studio_project_id: "s", template_id: "t" },
    onSaved: jest.fn(),
    videoUrl: null,
    videoMeta: null,
    device: "s24",
    preset: "tiktok",
    viewMode: "floating",
    envBg: "studio",
    captionFont: "anton",
    ctaFont: "anton",
    fontStack: (id) => id,
    videoRef: stubRef(),
    paintFrameRef: stubRef(),
    isExportingRef: stubRef(false),
    dirtyRef: stubRef(false),
    kickPreviewRef: stubRef(null),
    resultObjectUrlRef: stubRef(null),
    setIsPlaying: noop,
    setRecording: noop,
    setProgress: noop,
    setResult: noop,
    setSaving: noop,
    setSaved: noop,
    setSaveError: noop,
    setError: noop,
    ...overrides,
  };
}

function Probe({ onHook, flowParams }) {
  const hook = useExportFlow(flowParams);
  onHook(hook);
  return <span data-count={hook.exportErrors.length} />;
}

async function mountProbe(flowParams) {
  let hook = null;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Probe onHook={(h) => { hook = h; }} flowParams={flowParams} />);
  });
  return {
    hook: () => hook,
    count: () => container.querySelector("span").getAttribute("data-count"),
    unmount: async () => {
      await act(async () => { root.unmount(); });
      container.remove();
    },
  };
}

test("a failed save is visible as an exportErrors entry with its stage", async () => {
  api.saveDemoCtaExport.mockRejectedValueOnce(new Error("No."));
  const probe = await mountProbe(params());
  let result;
  await act(async () => {
    result = await probe.hook().saveExport(new Blob(["x"]), "demo-cta.mp4");
  });
  expect(result).toBeNull();
  const errors = probe.hook().exportErrors;
  expect(errors).toHaveLength(1);
  expect(errors[0].stage).toBe("save");
  expect(errors[0].message).toBe("No.");
  expect(typeof errors[0].at).toBe("string");
  expect(probe.count()).toBe("1");
  // The log half of the surfacing fired with the same stage.
  expect(warned).toHaveBeenCalledWith("[HookForge] Export failed:", "save", "No.");
  await probe.unmount();
});

test("a retry wipes the prior failure so the banner cannot name it", async () => {
  api.saveDemoCtaExport
    .mockRejectedValueOnce(new Error("No."))
    .mockResolvedValueOnce({ id: "saved-2" });
  const probe = await mountProbe(params());
  await act(async () => {
    await probe.hook().saveExport(new Blob(["x"]), "demo-cta.mp4");
  });
  expect(probe.hook().exportErrors).toHaveLength(1);
  let result;
  await act(async () => {
    result = await probe.hook().saveExport(new Blob(["x"]), "demo-cta.mp4");
  });
  expect(result).toEqual({ id: "saved-2" });
  expect(probe.hook().exportErrors).toEqual([]);
  await probe.unmount();
});

test.each(["missing", "short", "undecodable"])("export gate rejects %s joined audio before offering download", async (failure) => {
  const track = { getCodec: async () => "aac", canDecode: async () => true, getSampleRate: async () => 48000, getNumberOfChannels: async () => 2, computeDuration: async () => failure === "short" ? 10 : 18 };
  const input = { getPrimaryAudioTrack: async () => failure === "missing" ? null : track, dispose: jest.fn() };
  Input.mockImplementation(() => input);
  AudioSampleSink.mockImplementation(() => ({ getSample: async () => null }));
  await expect(probeRecordingPlays(new Blob(), 18, [{ start: 10, duration: 8 }])).rejects.toThrow(/audio/);
  expect(input.dispose).toHaveBeenCalledTimes(1);
});

test("export gate checks AAC coverage for both joined segments and the 18s video length", async () => {
  const sample = { close: jest.fn() };
  const getSample = jest.fn(async () => sample);
  const input = { getPrimaryAudioTrack: async () => ({ getCodec: async () => "aac", canDecode: async () => true, getSampleRate: async () => 48000, getNumberOfChannels: async () => 2, computeDuration: async () => 18 }), dispose: jest.fn() };
  Input.mockImplementation(() => input);
  AudioSampleSink.mockImplementation(() => ({ getSample }));
  const create = document.createElement.bind(document);
  const video = create("video");
  Object.defineProperties(video, { duration: { value: 18 }, videoWidth: { value: 1080 }, videoHeight: { value: 1920 } });
  const spy = jest.spyOn(document, "createElement").mockImplementation((tag) => tag === "video" ? video : create(tag));
  const oldCreate = URL.createObjectURL, oldRevoke = URL.revokeObjectURL;
  URL.createObjectURL = () => "blob:joined";
  URL.revokeObjectURL = jest.fn();
  try {
    const pending = probeRecordingPlays(new Blob(), 18, [{ start: 0, duration: 10 }, { start: 10, duration: 8 }]);
    for (let i = 0; i < 20 && !video.onloadeddata; i++) await Promise.resolve();
    expect(video.onloadeddata).toBeInstanceOf(Function);
    video.onloadeddata();
    await pending;
    expect(getSample.mock.calls).toEqual([[0.05], [10.05]]);
    expect(sample.close).toHaveBeenCalledTimes(2);
    expect(input.dispose).toHaveBeenCalled();
  } finally {
    spy.mockRestore(); URL.createObjectURL = oldCreate; URL.revokeObjectURL = oldRevoke;
  }
});

test("a successful save records nothing", async () => {
  api.saveDemoCtaExport.mockResolvedValueOnce({ id: "saved-1" });
  const saved = jest.fn();
  const probe = await mountProbe(params({ onSaved: saved }));
  let result;
  await act(async () => {
    result = await probe.hook().saveExport(new Blob(["x"]), "demo-cta.mp4");
  });
  expect(result).toEqual({ id: "saved-1" });
  expect(probe.hook().exportErrors).toEqual([]);
  expect(warned).not.toHaveBeenCalled();
  await probe.unmount();
});
