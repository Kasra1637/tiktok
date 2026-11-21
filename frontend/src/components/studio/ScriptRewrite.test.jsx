import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ScriptRewrite from "./ScriptRewrite";
import { api } from "../../lib/api";

jest.mock("../../lib/api", () => ({
  api: { rewriteLine: jest.fn() },
  getErrorMessage: (err) => err?.message || "Something went wrong",
}));
jest.mock("../ui/button", () => ({
  Button: ({ variant, size, ...props }) => <button {...props} />,
}));

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const HOOK = "I don't want to type anything";
const SCRIPT = "Typing is the last thing I want to do at night. My head is still loud from the whole day. I say it out loud so it can quiet down.";
const REMADE = "Writing is the last thing I want at night. My head stays loud all day. Saying it out loud is how it settles.";

async function mount(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const onChange = jest.fn();
  const render = async (nextProps) => {
    await act(async () => {
      root.render(
        <ScriptRewrite projectId="p1" hookLine={HOOK} script={SCRIPT} onChange={onChange} {...nextProps} />);
    });
  };
  await render(props);
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    q, onChange, container, render,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

afterEach(() => jest.clearAllMocks());

describe("ScriptRewrite", () => {
  test("offers exactly one remake button however many sentences the script has", async () => {
    const view = await mount({});
    // The script above has three sentences; the per-sentence buttons
    // are gone (ADR 0205) — one button remakes the whole script.
    expect(view.q("script-rewrite-button")).not.toBeNull();
    expect(view.q("script-rewrite-button").textContent).toContain("Remake the script");
    expect(view.q("script-rewrite-0-button")).toBeNull();
    expect(view.q("script-rewrite-1-button")).toBeNull();
    expect(view.q("script-rewrite-2-button")).toBeNull();
    expect(view.container.querySelectorAll("button")).toHaveLength(1);
    await view.unmount();
  });

  test("accepting the suggestion replaces the whole script at once", async () => {
    api.rewriteLine.mockResolvedValue({ line: REMADE });
    const view = await mount({});
    await act(async () => { view.q("script-rewrite-button").click(); });
    expect(api.rewriteLine).toHaveBeenCalledWith("p1", {
      line: SCRIPT, role: "script", hook_line: HOOK, script: SCRIPT,
    });
    expect(view.onChange).not.toHaveBeenCalled();
    const suggestion = view.q("script-rewrite-suggestion");
    expect(suggestion).not.toBeNull();
    expect(suggestion.textContent).toContain(REMADE);
    expect(view.q("script-rewrite-accept").textContent).toContain("Use this script");
    expect(view.q("script-rewrite-dismiss").textContent).toContain("Keep mine");
    await act(async () => { view.q("script-rewrite-accept").click(); });
    expect(view.onChange).toHaveBeenCalledTimes(1);
    expect(view.onChange).toHaveBeenCalledWith(REMADE);
    await view.unmount();
  });

  test("a suggestion made before an edit hides instead of overwriting it", async () => {
    api.rewriteLine.mockResolvedValue({ line: REMADE });
    const view = await mount({});
    await act(async () => { view.q("script-rewrite-button").click(); });
    expect(view.q("script-rewrite-suggestion")).not.toBeNull();
    // The founder edits the script in the textarea: the suggestion was
    // made for the older words, so it stales and hides — the button
    // returns, and the newer words are never overwritten by it.
    await view.render({ script: `${SCRIPT} One more line of mine.` });
    expect(view.q("script-rewrite-suggestion")).toBeNull();
    expect(view.q("script-rewrite-button")).not.toBeNull();
    expect(view.onChange).not.toHaveBeenCalled();
    await view.unmount();
  });

  test("carries no explainer line — the button speaks for itself", async () => {
    const view = await mount({});
    // ADR 0242: the "Or remake the script in one go…" explainer is
    // gone. The hook's assist carries no such line and is understood;
    // the suggestion itself shows accept/dismiss when it arrives, so
    // the safety the line described is visible at the moment it
    // matters instead of narrated beside the button.
    expect(view.container.textContent).not.toContain("remake the script in one go");
    expect(view.container.textContent).not.toContain("nothing changes until you accept it");
    expect(view.q("script-rewrite-button")).not.toBeNull();
    await view.unmount();
  });

  test("renders nothing for an empty script", async () => {
    const view = await mount({ script: "" });
    expect(view.q("script-rewrite")).toBeNull();
    await view.unmount();
  });
});
