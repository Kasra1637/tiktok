import React, { act } from "react";
import { createRoot } from "react-dom/client";
import HookLineEditor from "./HookLineEditor";
import { api } from "../../lib/api";

jest.mock("../../lib/api", () => ({
  api: { rewriteHook: jest.fn() },
  getErrorMessage: (err) => err?.message || "Something went wrong",
}));
jest.mock("../ui/button", () => ({
  Button: ({ variant, size, ...props }) => <button {...props} />,
}));
jest.mock("../ui/input", () => ({ Input: (props) => <input {...props} /> }));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const VAGUE = { risk_warnings: [{ claim: "type anything", reason: "is vague: name the real action" }] };

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
  test("offers no rewrite when the hook is not vague", async () => {
    const view = await mount({ report: { risk_warnings: [{ claim: "4.8 stars", reason: "needs a source" }] } });
    expect(view.q("vague-hook-note")).toBeNull();
    await view.unmount();
  });

  test("suggests a clearer hook and applies it only on Use this line", async () => {
    api.rewriteHook.mockResolvedValue({ hook_line: "I don't want to write in my journal today" });
    const view = await mount({ report: VAGUE });
    expect(view.q("vague-hook-note").textContent).toContain("type anything");
    await act(async () => { view.q("hook-rewrite-button").click(); });
    expect(api.rewriteHook).toHaveBeenCalledWith("p1", "I don't want to type anything");
    expect(view.q("hook-rewrite-suggestion").textContent).toContain("write in my journal today");
    expect(view.onChange).not.toHaveBeenCalled();
    await act(async () => { view.q("hook-rewrite-accept").click(); });
    expect(view.onChange).toHaveBeenCalledWith("I don't want to write in my journal today");
    await view.unmount();
  });

  test("Keep mine dismisses without changing the hook", async () => {
    api.rewriteHook.mockResolvedValue({ hook_line: "I don't want to write in my journal today" });
    const view = await mount({ report: VAGUE });
    await act(async () => { view.q("hook-rewrite-button").click(); });
    await act(async () => { view.q("hook-rewrite-dismiss").click(); });
    expect(view.q("hook-rewrite-suggestion")).toBeNull();
    expect(view.onChange).not.toHaveBeenCalled();
    await view.unmount();
  });

  test("a failed rewrite shows the next step instead of failing silently", async () => {
    api.rewriteHook.mockRejectedValue(new Error("Couldn't write a clearer hook just now. Try again."));
    const view = await mount({ report: VAGUE });
    await act(async () => { view.q("hook-rewrite-button").click(); });
    expect(view.q("hook-rewrite-error").textContent).toContain("Try again");
    expect(view.q("hook-rewrite-suggestion")).toBeNull();
    await view.unmount();
  });
});
