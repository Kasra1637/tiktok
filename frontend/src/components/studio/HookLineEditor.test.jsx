import React, { act } from "react";
import { createRoot } from "react-dom/client";
import HookLineEditor from "./HookLineEditor";
import { api } from "../../lib/api";

jest.mock("../../lib/api", () => ({
  api: { rewriteLine: jest.fn() },
  getErrorMessage: (err) => err?.message || "Something went wrong",
}));
jest.mock("../ui/button", () => ({
  Button: ({ variant, size, ...props }) => <button {...props} />,
}));
jest.mock("../ui/input", () => ({ Input: (props) => <input {...props} /> }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mount(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const onChange = jest.fn();
  await act(async () => {
    root.render(<HookLineEditor projectId="p1" value="I don't want to type anything" onChange={onChange} {...props} />);
  });
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    q, onChange,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

afterEach(() => jest.clearAllMocks());

describe("HookLineEditor", () => {
  test("offers the rewrite on every hook, with no warning gate", async () => {
    const view = await mount({});
    expect(view.q("hook-rewrite-button")).not.toBeNull();
    expect(view.q("vague-hook-note")).toBeNull();
    await view.unmount();
  });

  test("suggests a clearer hook and applies it only on Use this line", async () => {
    api.rewriteLine.mockResolvedValue({ line: "I don't want to write in my journal today" });
    const view = await mount({});
    await act(async () => { view.q("hook-rewrite-button").click(); });
    expect(api.rewriteLine).toHaveBeenCalledWith("p1", {
      line: "I don't want to type anything", role: "hook", hook_line: "", script: "",
    });
    expect(view.q("hook-rewrite-suggestion").textContent).toContain("write in my journal today");
    expect(view.onChange).not.toHaveBeenCalled();
    await act(async () => { view.q("hook-rewrite-accept").click(); });
    expect(view.onChange).toHaveBeenCalledWith("I don't want to write in my journal today");
    await view.unmount();
  });

  test("Keep mine dismisses without changing the hook", async () => {
    api.rewriteLine.mockResolvedValue({ line: "I don't want to write in my journal today" });
    const view = await mount({});
    await act(async () => { view.q("hook-rewrite-button").click(); });
    await act(async () => { view.q("hook-rewrite-dismiss").click(); });
    expect(view.q("hook-rewrite-suggestion")).toBeNull();
    expect(view.onChange).not.toHaveBeenCalled();
    await view.unmount();
  });

  test("a failed rewrite shows the next step instead of failing silently", async () => {
    api.rewriteLine.mockRejectedValue(new Error("Couldn't write a clearer line just now. Try again."));
    const view = await mount({});
    await act(async () => { view.q("hook-rewrite-button").click(); });
    expect(view.q("hook-rewrite-error").textContent).toContain("Try again");
    expect(view.q("hook-rewrite-suggestion")).toBeNull();
    await view.unmount();
  });

  test("the rewrite stays disabled while the hook is empty", async () => {
    const view = await mount({ value: "" });
    expect(view.q("hook-rewrite-button").disabled).toBe(true);
    await view.unmount();
  });

  test("the Hook + CTA usage drops the editor's rewrite and keeps the editable field (ADR 0249)", async () => {
    // One button does the hook work on Hook + CTA: the page's unified
    // control generates the first line, then becomes the clearer-hook
    // suggestion itself — so the page mounts this editor without its
    // own rewrite, or the card would carry the suggestion twice. The
    // field itself stays — the line is still the founder's to sharpen
    // by hand. Create Video mounts the editor as here by default,
    // rewrite included (the tests above).
    const view = await mount({ suggestClearerHook: false });
    expect(view.q("hook-rewrite-button")).toBeNull();
    const field = document.querySelector("#review-hook_line");
    expect(field).not.toBeNull();
    expect(field.value).toBe("I don't want to type anything");
    await view.unmount();
  });
});
