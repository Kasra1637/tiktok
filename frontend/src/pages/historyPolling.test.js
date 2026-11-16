import React, { act } from "react";
import { createRoot } from "react-dom/client";

// The hook reads api.pollGeneration; every other lib/api export stays real
// so historyRepair's durableMediaUrl keeps working underneath.
jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return { ...actual, api: { ...actual.api, pollGeneration: jest.fn() } };
});

import { api } from "../lib/api";
import { historyPollDelay, useAwaitingHistoryPoll } from "./historyPolling";

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

function stateOf(container, id) {
  return JSON.parse(container.textContent)[id];
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

describe("historyPollDelay", () => {
  test("mirrors the panel's backoff shape (ADR 0171)", () => {
    expect(historyPollDelay({ failures: 0, throttles: 0 })).toBe(10000);
    expect(historyPollDelay({ failures: 2, throttles: 0 })).toBe(10000);
    expect(historyPollDelay({ failures: 3, throttles: 0 })).toBe(20000);
    expect(historyPollDelay({ failures: 0, throttles: 1 })).toBe(20000);
    expect(historyPollDelay({ failures: 0, throttles: 2 })).toBe(30000);
    expect(historyPollDelay({ failures: 0, throttles: 5 })).toBe(60000);
    expect(historyPollDelay({ failures: 0, throttles: 9 })).toBe(60000);
  });
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
    // The throttle stretches the wait (ADR 0174): one base interval is
    // not long enough for the next check.
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
    expect(onUpdated).toHaveBeenCalledWith("a", finished);
  });

  test("throttling stretches the wait per 429 and marks the row slowed, never stopped", async () => {
    api.pollGeneration.mockRejectedValue({ response: { status: 429 } });
    const onUpdated = jest.fn();
    const { container } = await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    await tick(); // t=10s: check 1 throttled, next wait 20s
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    await tick(); // t=20s: still waiting out the stretch
    expect(api.pollGeneration).toHaveBeenCalledTimes(1);
    await tick(); // t=30s: check 2 throttled, next wait 30s
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
    expect(stateOf(container, "a")).toBe("active");
    await tick(); // t=40s
    await tick(); // t=50s
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
    await tick(); // t=60s: check 3 throttled — the row now says checks are slowed
    expect(api.pollGeneration).toHaveBeenCalledTimes(3);
    expect(stateOf(container, "a")).toBe("slowed");
    // And it is still watching: once the provider answers, the finish lands.
    const finished = { id: "a", status: "completed", video_url: "u" };
    api.pollGeneration.mockResolvedValue(finished);
    await tick(); // t=70s
    await tick(); // t=80s
    await tick(); // t=90s
    expect(api.pollGeneration).toHaveBeenCalledTimes(3);
    await tick(); // t=100s: check 4 lands the finish
    expect(api.pollGeneration).toHaveBeenCalledTimes(4);
    expect(onUpdated).toHaveBeenCalledWith("a", finished);
  });

  test("one row settles while a failing row keeps being watched", async () => {
    api.pollGeneration.mockImplementation((id) => id === "a"
      ? Promise.resolve({ id, status: "completed", video_url: "u" })
      : Promise.reject({ response: { status: 500 } }));
    const onUpdated = jest.fn();
    const { container } = await renderProbe([{ id: "a", status: "generating" }, { id: "b", status: "generating" }], onUpdated);
    await tick();
    expect(onUpdated).toHaveBeenCalledWith("a", { id: "a", status: "completed", video_url: "u" });
    expect(stateOf(container, "a")).toBe("settled");
    expect(stateOf(container, "b")).toBe("active");
    await tick();
    await tick();
    // The settled row is never re-polled; the failing row never retires —
    // after three failures it reports the slowed state instead of "error".
    expect(api.pollGeneration.mock.calls.filter(([id]) => id === "a")).toHaveLength(1);
    expect(api.pollGeneration.mock.calls.filter(([id]) => id === "b")).toHaveLength(3);
    expect(stateOf(container, "b")).toBe("slowed");
    // The sustained failure settled b's cadence to twice the base wait,
    // so one base interval passes with no check before the next lands.
    api.pollGeneration.mockImplementation((id) => Promise.resolve({ id, status: "completed", video_url: "u" }));
    await tick();
    expect(api.pollGeneration.mock.calls.filter(([id]) => id === "b")).toHaveLength(3);
    await tick();
    expect(onUpdated).toHaveBeenCalledWith("b", { id: "b", status: "completed", video_url: "u" });
  });

  test("past the old 20-attempt limit the row is still watched and a late finish lands", async () => {
    const finished = { id: "a", status: "completed", video_url: "u" };
    api.pollGeneration.mockResolvedValue({ id: "a", status: "generating" });
    const onUpdated = jest.fn();
    const { container } = await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    for (let i = 0; i < 20; i += 1) await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(20);
    // The old code retired the row here as "paused". There is no such state.
    expect(stateOf(container, "a")).toBe("active");
    api.pollGeneration.mockResolvedValue(finished);
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(21);
    expect(onUpdated).toHaveBeenCalledWith("a", finished);
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

  test("a generic error backs off instead of stopping the loop", async () => {
    api.pollGeneration.mockRejectedValue({ response: { status: 500 } });
    const onUpdated = jest.fn();
    const { container } = await renderProbe([{ id: "a", status: "generating" }], onUpdated);
    await tick();
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(2);
    await tick(); // third failure: slowed, and the wait doubles
    expect(api.pollGeneration).toHaveBeenCalledTimes(3);
    expect(stateOf(container, "a")).toBe("slowed");
    await tick(); // still waiting out the doubled wait — no check, no stop
    expect(api.pollGeneration).toHaveBeenCalledTimes(3);
    const finished = { id: "a", status: "completed", video_url: "u" };
    api.pollGeneration.mockResolvedValue(finished);
    await tick();
    expect(api.pollGeneration).toHaveBeenCalledTimes(4);
    expect(onUpdated).toHaveBeenCalledWith("a", finished);
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
