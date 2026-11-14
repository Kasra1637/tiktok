// The desktop-width hook behind the wizard's paged layout (ADR 0141):
// it answers the Tailwind lg question — at or above 1024px the Create
// wizard stands one step at a time — and it must degrade to "not desktop"
// (the stacked canvas, the long-standing shape) wherever matchMedia is
// missing, never throw.
import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useDesktopWidth, DESKTOP_PAGES_QUERY } from "./desktopWidth";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

function mountProbe() {
  const sink = { value: undefined };
  function Probe() {
    sink.value = useDesktopWidth();
    return null;
  }
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  return {
    sink,
    async render() {
      await act(async () => {
        root.render(<Probe />);
      });
    },
    async unmount() {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

const realMatchMedia = window.matchMedia;

afterEach(() => {
  window.matchMedia = realMatchMedia;
});

test("no matchMedia reads as not desktop, so the canvas stacks", async () => {
  window.matchMedia = undefined;
  const probe = mountProbe();
  await probe.render();
  expect(probe.sink.value).toBe(false);
  await probe.unmount();
});

test("a matching desktop query reads as desktop, asked at the lg breakpoint", async () => {
  const asked = [];
  window.matchMedia = (query) => {
    asked.push(query);
    return {
      matches: true,
      media: query,
      addEventListener: () => {},
      removeEventListener: () => {},
      addListener: () => {},
      removeListener: () => {},
    };
  };
  const probe = mountProbe();
  await probe.render();
  expect(probe.sink.value).toBe(true);
  expect(asked).toContain(DESKTOP_PAGES_QUERY);
  expect(DESKTOP_PAGES_QUERY).toBe("(min-width: 1024px)");
  await probe.unmount();
});

test("crossing the breakpoint while mounted swaps the answer", async () => {
  const listeners = new Set();
  const mql = {
    matches: false,
    media: DESKTOP_PAGES_QUERY,
    addEventListener: (type, fn) => listeners.add(fn),
    removeEventListener: (type, fn) => listeners.delete(fn),
    addListener: (fn) => listeners.add(fn),
    removeListener: (fn) => listeners.delete(fn),
  };
  window.matchMedia = () => mql;
  const probe = mountProbe();
  await probe.render();
  expect(probe.sink.value).toBe(false);
  await act(async () => {
    mql.matches = true;
    listeners.forEach((fn) => fn({ matches: true }));
  });
  expect(probe.sink.value).toBe(true);
  await probe.unmount();
});
