import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { VideoVerdict } from "./VideoVerdict";
import { api } from "../lib/api";

jest.mock("../lib/api", () => ({
  api: { setVideoVerdict: jest.fn() },
  getErrorMessage: (err) => err?.message || "Something went wrong",
}));
jest.mock("./ui/button", () => ({
  Button: ({ variant, size, ...props }) => <button {...props} />,
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const onChanged = jest.fn();
  await act(async () => {
    root.render(<VideoVerdict generationId="g1" onChanged={onChanged} {...props} />);
  });
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    q, onChanged, container,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

afterEach(() => jest.clearAllMocks());

describe("VideoVerdict", () => {
  test("renders one verdict control for the whole video, unpressed when unrated", async () => {
    const view = await mount({ value: null });
    expect(view.q("history-verdict-g1")).not.toBeNull();
    expect(view.q("history-verdict-g1-up").textContent).toContain("This one worked");
    expect(view.q("history-verdict-g1-down").textContent).toContain("didn");
    expect(view.q("history-verdict-g1-up").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("history-verdict-g1-down").getAttribute("aria-pressed")).toBe("false");
    await view.unmount();
  });

  test("reflects the saved verdict as the pressed side", async () => {
    const view = await mount({ value: "up" });
    expect(view.q("history-verdict-g1-up").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("history-verdict-g1-down").getAttribute("aria-pressed")).toBe("false");
    await view.unmount();
  });

  test("casting a verdict calls the endpoint and reports the confirmed value", async () => {
    api.setVideoVerdict.mockResolvedValue({ video_verdict: "down" });
    const view = await mount({ value: null });
    await act(async () => { view.q("history-verdict-g1-down").click(); });
    expect(api.setVideoVerdict).toHaveBeenCalledWith("g1", "down");
    expect(view.onChanged).toHaveBeenCalledWith("down");
    expect(view.q("history-verdict-g1-down").getAttribute("aria-pressed")).toBe("true");
    expect(view.container.textContent).toContain("Verdict saved");
    await view.unmount();
  });

  test("clicking the active verdict clears it", async () => {
    api.setVideoVerdict.mockResolvedValue({ video_verdict: null });
    const view = await mount({ value: "up" });
    await act(async () => { view.q("history-verdict-g1-up").click(); });
    expect(api.setVideoVerdict).toHaveBeenCalledWith("g1", null);
    expect(view.onChanged).toHaveBeenCalledWith(null);
    expect(view.q("history-verdict-g1-up").getAttribute("aria-pressed")).toBe("false");
    await view.unmount();
  });

  test("a failed save restores the last confirmed verdict", async () => {
    api.setVideoVerdict.mockRejectedValue(new Error("Verdict could not save"));
    const view = await mount({ value: "up" });
    await act(async () => { view.q("history-verdict-g1-down").click(); });
    expect(view.q("history-verdict-g1-up").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("history-verdict-g1-down").getAttribute("aria-pressed")).toBe("false");
    expect(view.container.textContent).toContain("Could not save your verdict");
    expect(view.onChanged).not.toHaveBeenCalled();
    await view.unmount();
  });
});
