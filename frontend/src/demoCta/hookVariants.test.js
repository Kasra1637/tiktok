import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { useOverlayTaste } from "./useOverlayTaste";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let api;
function Probe({ seen }) {
  api = useOverlayTaste({
    overlayScope: "rotation",
    videoUrl: null,
    clipDuration: 0,
    recording: false,
    onHookText: (v) => seen.push(v),
    onCtaHeadline: () => {},
  });
  return null;
}

function mount() {
  window.localStorage.clear();
  const seen = [];
  const div = document.createElement("div");
  document.body.appendChild(div);
  const root = createRoot(div);
  act(() => root.render(<Probe seen={seen} />));
  return { seen, unmount: () => act(() => root.unmount()) };
}

test("rotate walks all three defaults and wraps to the first", () => {
  const { seen, unmount } = mount();
  expect(api.hookVariants.length).toBe(3);
  act(() => api.rotateHookVariant());
  expect(seen[seen.length - 1]).toMatch(/Apple Notes/);
  act(() => api.rotateHookVariant());
  expect(seen[seen.length - 1]).toMatch(/10-second/);
  act(() => api.rotateHookVariant());
  expect(seen[seen.length - 1]).toMatch(/journaling in Notes/);
  unmount();
});

test("add duplicates the active message so the list actually grows", () => {
  const { seen, unmount } = mount();
  act(() => api.addHookVariant());
  expect(api.hookVariants.length).toBe(4);
  expect(api.hookVariants[0]).toBe(api.hookVariants[1]);
  // The copy is selected, so typing edits the copy, not the original.
  act(() => api.updateHookText("A brand new fourth message"));
  expect(api.hookVariants[1]).toBe("A brand new fourth message");
  expect(api.hookVariants[0]).toMatch(/journaling in Notes/);
  expect(seen[seen.length - 1]).toBe("A brand new fourth message");
  const stored = JSON.parse(window.localStorage.getItem("hookforge.demoCta.overlayPrefs.v1"));
  expect(stored.global.hookVariants.length).toBe(4);
  unmount();
});

test("remove clamps at one message and rotate is a no-op there", () => {
  const { seen, unmount } = mount();
  act(() => api.removeHookVariant());
  act(() => api.removeHookVariant());
  expect(api.hookVariants.length).toBe(1);
  act(() => api.removeHookVariant());
  expect(api.hookVariants.length).toBe(1);
  const before = seen.length;
  act(() => api.rotateHookVariant());
  expect(api.hookVariants.length).toBe(1);
  expect(seen.length).toBe(before + 1);
  expect(seen[seen.length - 1]).toBe(api.hookVariants[0]);
  unmount();
});
