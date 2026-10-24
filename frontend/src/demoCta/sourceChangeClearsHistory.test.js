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
    unmount: async () => {
      await act(async () => { root.unmount(); });
      container.remove();
    },
  };
}

test("a failed save followed by a source change wipes the history", async () => {
  api.saveDemoCtaExport.mockRejectedValueOnce(new Error("No."));
  const probe = await mountProbe(params());
  await act(async () => {
    await probe.hook().saveExport(new Blob(["x"]), "demo-cta.mp4");
  });
  expect(probe.hook().exportErrors).toHaveLength(1);
  // What handleFile / clearSource / the sourceUrl reload effect do on a
  // source change: wipe the failure history so the next banner starts clean.
  await act(async () => {
    probe.hook().clearExportErrors();
  });
  expect(probe.hook().exportErrors).toEqual([]);
  await probe.unmount();
});
