import React, { act } from "react";
import { createRoot } from "react-dom/client";
// The repo's jest setup does not resolve the `@/` webpack alias, so stub it:
// the class-join is irrelevant to growth, only its pass-through matters.
jest.mock(
  "@/lib/utils",
  () => ({ cn: (...parts) => parts.filter(Boolean).join(" ") }),
  { virtual: true },
);
import { Textarea } from "./textarea";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function mockScrollHeight(px) {
  Object.defineProperty(window.HTMLTextAreaElement.prototype, "scrollHeight", {
    configurable: true,
    get: () => px,
  });
}

function unmockScrollHeight() {
  delete window.HTMLTextAreaElement.prototype.scrollHeight;
}

async function mountArea(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Textarea {...props} />);
  });
  return {
    area: () => container.querySelector("textarea"),
    unmount: async () => {
      await act(async () => { root.unmount(); });
      container.remove();
    },
  };
}

describe("Textarea", () => {
  afterEach(() => {
    unmockScrollHeight();
  });

  test("grows to fit a full script on mount instead of clipping it", async () => {
    // A sub-180-character script wraps past the default rows, so the field
    // must size itself to its content rather than scroll it.
    mockScrollHeight(150);
    const { area, unmount } = await mountArea({
      value: "just start talking right here in the car. ".repeat(4),
      onChange: () => {},
    });
    expect(area().style.height).toBe("150px");
    await unmount();
  });

  test("grows as the founder types, without taking over the page", async () => {
    function Probe() {
      const [value, setValue] = React.useState("short");
      return <Textarea value={value} onChange={(e) => setValue(e.target.value)} />;
    }
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(<Probe />);
    });
    const area = () => container.querySelector("textarea");
    mockScrollHeight(220);
    const setter = Object.getOwnPropertyDescriptor(
      window.HTMLTextAreaElement.prototype,
      "value",
    ).set;
    await act(async () => {
      setter.call(area(), `${area().value} plus a much longer closing line`);
      area().dispatchEvent(new window.Event("input", { bubbles: true }));
    });
    expect(area().style.height).toBe("220px");
    // Very long copy still caps out and scrolls instead of pushing the page.
    expect(area().className).toContain("max-h-");
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("leaves the height alone when there is no layout to measure", async () => {
    // jsdom reports scrollHeight 0: the min-height class holds the field
    // rather than collapsing it to nothing.
    const { area, unmount } = await mountArea({ value: "short", onChange: () => {} });
    expect(area().style.height).toBe("");
    await unmount();
  });
});
