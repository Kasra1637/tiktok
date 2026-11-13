import React, { act } from "react";
import { createRoot } from "react-dom/client";
import ScriptLineRewrites, { splitScriptSentences, replaceScriptSentence } from "./ScriptLineRewrites";
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
const SCRIPT = "Typing is the last thing I want to do at night. My head is still loud from the whole day.";

async function mount(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const onChange = jest.fn();
  await act(async () => {
    root.render(<ScriptLineRewrites projectId="p1" hookLine={HOOK} script={SCRIPT} onChange={onChange} {...props} />);
  });
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    q, onChange,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

afterEach(() => jest.clearAllMocks());

describe("splitScriptSentences", () => {
  test("splits on sentence ends and keeps exact spans", () => {
    const spans = splitScriptSentences(SCRIPT);
    expect(spans.map((s) => s.text)).toEqual([
      "Typing is the last thing I want to do at night.",
      "My head is still loud from the whole day.",
    ]);
    for (const span of spans) expect(SCRIPT.slice(span.start, span.end)).toBe(span.text);
  });

  test("keeps decimals whole and keeps a tail without a terminator", () => {
    const spans = splitScriptSentences("It takes 12.5 minutes most days. Then I stop");
    expect(spans.map((s) => s.text)).toEqual(["It takes 12.5 minutes most days.", "Then I stop"]);
  });

  test("replacing one sentence leaves the rest byte-for-byte intact", () => {
    const spans = splitScriptSentences(SCRIPT);
    expect(replaceScriptSentence(SCRIPT, spans[1], "My head stays loud all day."))
      .toBe("Typing is the last thing I want to do at night. My head stays loud all day.");
  });
});

describe("ScriptLineRewrites", () => {
  test("offers a rewrite for every script line", async () => {
    const view = await mount({});
    expect(view.q("script-rewrite-0-button")).not.toBeNull();
    expect(view.q("script-rewrite-1-button")).not.toBeNull();
    await view.unmount();
  });

  test("groups the lines in one row stack, one organised row per line", async () => {
    const view = await mount({});
    const group = view.q("script-line-rewrites").querySelector(".script-line-group");
    expect(group).not.toBeNull();
    const rows = group.querySelectorAll(".script-line-row");
    expect(rows).toHaveLength(2);
    // The buttons themselves are unchanged: same testids, one per row,
    // under the line they rewrite.
    expect(rows[0].querySelector('[data-testid="script-rewrite-0-button"]')).not.toBeNull();
    expect(rows[1].querySelector('[data-testid="script-rewrite-1-button"]')).not.toBeNull();
    expect(rows[0].textContent).toContain("Typing is the last thing I want to do at night.");
    expect(rows[1].textContent).toContain("My head is still loud from the whole day.");
    await view.unmount();
  });

  test("accepting a line's suggestion changes only that sentence", async () => {
    api.rewriteLine.mockResolvedValue({ line: "My head stays loud all day." });
    const view = await mount({});
    await act(async () => { view.q("script-rewrite-1-button").click(); });
    expect(api.rewriteLine).toHaveBeenCalledWith("p1", {
      line: "My head is still loud from the whole day.", role: "middle", hook_line: HOOK, script: SCRIPT,
    });
    expect(view.onChange).not.toHaveBeenCalled();
    await act(async () => { view.q("script-rewrite-1-accept").click(); });
    expect(view.onChange).toHaveBeenCalledWith(
      "Typing is the last thing I want to do at night. My head stays loud all day.");
    await view.unmount();
  });

  test("renders nothing for an empty script", async () => {
    const view = await mount({ script: "" });
    expect(view.q("script-line-rewrites")).toBeNull();
    await view.unmount();
  });
});
