import React, { act } from "react";
import { createRoot } from "react-dom/client";

// The hook reads api.pollGeneration; every other lib/api export stays real
// so historyRepair's durableMediaUrl keeps working underneath.
jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return { ...actual, api: { ...actual.api, pollGeneration: jest.fn() } };
});

import { api } from "../lib/api";
import { useAwaitingHistoryPoll } from "./historyPolling";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function Probe({ rows, onUpdated }) {
  const states = useAwaitingHistoryPoll(rows, onUpdated);
  return <output>{JSON.stringify(states)}</output>;
}

const mounted = [];

async function renderProbe(rows, onUpdated) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  mounted.push({ container, root });
  await act(async () => {
    root.render(<Probe rows={rows} onUpdated={onUpdated} />);
  });
  return { container, root };
}

async function tick(ms = 10000) {
  await act(async () => {
    jest.advanceTimersByTime(ms);
  });
}

beforeEach(() => {
  jest.useFakeTimers();
  api.pollGeneration.mockReset();
});

afterEach(async () => {
  while (mounted.length > 0) {
    const { container, root } = mounted.pop();
    await act(async () => {
      root.unmount();
    });
    container.remove();
  }
  jest.useRealTimers();
});

describe("useAwaitingHistoryPoll", () => {
  test("polls awaiting rows and applies the finished update", async () => {
    const finished = { id: "a", status: "completed", video_url: "u" };
    api.pollGeneration.mockResolvedValue(finished);
    const onUpdated = jest.fn();
    await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    expect(api.pollGeneration).not.toHaveBeenCalled();
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    expect(api.pollGeneration).toHaveBeenCalledWith("a");
    expect(onUpdated).toHaveBeenCalledWith("a", finished);
  });

  test("a 429 never stops the loop", async () => {
    const finished = { id: "a", status: "completed", video_url: "u" };
    api.pollGeneration
      .mockRejectedValueOnce({ response: { status: 429 } })
      .mockResolvedValue(finished);
    const onUpdated = jest.fn();
    await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    expect(onUpdated).not.toHaveBeenCalled();
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
    expect(onUpdated).toHaveBeenCalledWith("a", finished);
  });

  test("successful rows settle even when another fails, with per-row stopped state", async () => {
    api.pollGeneration.mockImplementation((id) => id === "a"
      ? Promise.resolve({ id, status: "completed", video_url: "u" })
      : Promise.reject({ response: { status: 500 } }));
    const onUpdated = jest.fn();
    const { container } = await renderProbe([{ id: "a", status: "generating" }, { id: "b", status: "generating" }], onUpdated);
    await tick();
    expect(onUpdated).toHaveBeenCalledWith("a", { id: "a", status: "completed", video_url: "u" });
    expect(JSON.parse(container.textContent).b).toBe("error");
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
  });

  test("reports the attempt limit without marking the provider job failed", async () => {
    api.pollGeneration.mockResolvedValue({ id: "a", status: "generating" });
    const onUpdated = jest.fn();
    const { container } = await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    for (let i = 0; i < 20; i += 1) await tick();
    expect(JSON.parse(container.textContent).a).toBe("paused");
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(20);
    expect(onUpdated).not.toHaveBeenCalledWith("a", expect.objectContaining({ status: "failed" }));
  });

  test("slow requests never overlap rounds", async () => {
    let finish;
    api.pollGeneration.mockImplementation(() => new Promise((resolve) => { finish = resolve; }));
    const onUpdated = jest.fn();
    await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    await tick();
    await tick();
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    await act(async () => { finish({ id: "a", status: "generating" }); });
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
  });

  test("any other error stops the loop quietly", async () => {
    api.pollGeneration.mockRejectedValue({ response: { status: 500 } });
    const onUpdated = jest.fn();
    await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    await tick();
    await tick();
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    expect(onUpdated).not.toHaveBeenCalled();
  });

  test("settled rows never start the timer", async () => {
    const onUpdated = jest.fn();
    await renderProbe(
      [{ id: "b", status: "completed", video_url: "u", r2_url: "https://cdn.example/b.mp4" }],
      onUpdated
    );
    await tick();
    await tick();
    expect(api.pollGeneration).not.toHaveBeenCalled();
    expect(onUpdated).not.toHaveBeenCalled();
  });

  test("unmounting clears the timer", async () => {
    api.pollGeneration.mockResolvedValue({ id: "a", status: "completed", video_url: "u" });
    const onUpdated = jest.fn();
    const { container, root } = await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    await act(async () => {
      root.unmount();
    });
    container.remove();
    mounted.pop();
    await tick();
    expect(api.pollGeneration).not.toHaveBeenCalled();
  });
});
