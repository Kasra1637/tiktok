import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { api } from "../lib/api";
import { describeFraming } from "./zoom";
import { sourceErrorMessage, useHistorySource } from "./useHistorySource";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return { ...actual, api: { getGenerationHistory: jest.fn() } };
});

let hook;
function Probe({ onAttachFile }) {
  hook = useHistorySource({ onAttachFile });
  return null;
}

async function mountProbe(onAttachFile = jest.fn()) {
  hook = null;
  const div = document.createElement("div");
  document.body.appendChild(div);
  const root = createRoot(div);
  await act(async () => {
    root.render(<Probe onAttachFile={onAttachFile} />);
  });
  return { unmount: () => act(() => root.unmount()) };
}

const realFetch = globalThis.fetch;

beforeEach(() => {
  jest.clearAllMocks();
});

afterEach(() => {
  globalThis.fetch = realFetch;
});

test("opening the picker loads only completed renders with a playable copy", async () => {
  api.getGenerationHistory.mockResolvedValueOnce({
    generations: [
      { id: "done-1", status: "completed", r2_url: "https://cdn/x.mp4" },
      { id: "failed-1", status: "failed", r2_url: "https://cdn/y.mp4" },
      { id: "done-nourl", status: "completed" },
    ],
  });
  const { unmount } = await mountProbe();
  expect(hook.historyRows).toBeNull();
  await act(async () => {
    hook.setHistoryOpen(true);
  });
  expect(api.getGenerationHistory).toHaveBeenCalledWith({ limit: 50 });
  expect(hook.historyRows.map((r) => r.id)).toEqual(["done-1"]);
  unmount();
});

test("attach fetches bytes and reuses the upload path, then closes the picker", async () => {
  const onAttachFile = jest.fn();
  const { unmount } = await mountProbe(onAttachFile);
  const blob = new Blob(["bytes"], { type: "video/mp4" });
  globalThis.fetch = jest.fn().mockResolvedValueOnce({ ok: true, blob: async () => blob });
  const row = { id: "abcdef123456", status: "completed", r2_url: "https://cdn/x.mp4" };
  await act(async () => {
    await hook.attachHistoryVideo(row);
  });
  expect(globalThis.fetch).toHaveBeenCalledWith("https://cdn/x.mp4");
  expect(onAttachFile).toHaveBeenCalledTimes(1);
  const file = onAttachFile.mock.calls[0][0];
  expect(file).toBeInstanceOf(File);
  expect(file.name).toBe("history-render-abcdef12.mp4");
  expect(hook.historyOpen).toBe(false);
  expect(hook.historyError).toBeNull();
  expect(hook.attachingId).toBeNull();
  unmount();
});

test("attach without a playable copy names the dead end instead of fetching", async () => {
  const onAttachFile = jest.fn();
  const { unmount } = await mountProbe(onAttachFile);
  globalThis.fetch = jest.fn();
  await act(async () => {
    await hook.attachHistoryVideo({ id: "done-nourl", status: "completed" });
  });
  expect(globalThis.fetch).not.toHaveBeenCalled();
  expect(onAttachFile).not.toHaveBeenCalled();
  expect(hook.historyError).toMatch(/no playable copy/);
  unmount();
});

test("attach maps an expired credential to its remedy", async () => {
  const { unmount } = await mountProbe();
  globalThis.fetch = jest.fn().mockResolvedValueOnce({ ok: false, status: 403 });
  await act(async () => {
    await hook.attachHistoryVideo({ id: "gone-1", status: "completed", r2_url: "https://cdn/z.mp4" });
  });
  expect(hook.historyError).toMatch(/fresh credential/);
  expect(hook.attachingId).toBeNull();
  unmount();
});

test("describeFraming names the zoom the export bakes per mode", () => {
  const entry = { handZoom: 1.5, scale: 0.9, phoneScale: 0.82 };
  expect(describeFraming("hand", entry)).toBe("1.50x hand");
  expect(describeFraming("realistic", entry)).toBe("0.90x full-frame");
  expect(describeFraming("floating", entry)).toBe("82% phone");
  expect(describeFraming("floating", {})).toBe("82% phone");
});

test("sourceErrorMessage maps a network failure to its fix", () => {
  expect(sourceErrorMessage(new TypeError("Failed to fetch"), "fallback")).toMatch(
    /couldn't be reached over the network/
  );
  expect(sourceErrorMessage(new Error("boom"), "fallback")).toBe("boom");
  expect(sourceErrorMessage(null, "fallback")).toBe("fallback");
});
