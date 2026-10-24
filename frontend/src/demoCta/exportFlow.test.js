import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../lib/api";
import { useExportFlow } from "./exportFlow";

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
