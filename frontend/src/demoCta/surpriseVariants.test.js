import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { HOOK_COPY_VARIANTS, CTA_COPY_VARIANTS } from "./constants";
import { useOverlayTaste } from "./useOverlayTaste";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let api;
function Probe({ seen, seenCta }) {
  api = useOverlayTaste({
    overlayScope: "surprise",
    videoUrl: null,
    clipDuration: 0,
    recording: false,
    onHookText: (v) => seen.push(v),
    onCtaHeadline: (v) => seenCta.push(v),
  });
  return null;
}

function mount() {
  window.localStorage.clear();
  const seen = [];
  const seenCta = [];
  const div = document.createElement("div");
  document.body.appendChild(div);
  const root = createRoot(div);
  act(() => root.render(<Probe seen={seen} seenCta={seenCta} />));
  return { seen, seenCta, unmount: () => act(() => root.unmount()) };
}

test("surprise hook always lands on a different preset in the pool", () => {
  const { seen, unmount } = mount();
  expect(api.hookVariants).toEqual(HOOK_COPY_VARIANTS);
  let prev = null;
  for (let i = 0; i < 20; i += 1) {
    act(() => api.surpriseHookVariant());
    const cur = seen[seen.length - 1];
    expect(HOOK_COPY_VARIANTS).toContain(cur);
    expect(cur).not.toBe(prev);
    prev = cur;
  }
  unmount();
});

test("surprise CTA always lands on a different preset in the pool", () => {
  const { seenCta, unmount } = mount();
  expect(api.ctaVariants).toEqual(CTA_COPY_VARIANTS);
  let prev = null;
  for (let i = 0; i < 20; i += 1) {
    act(() => api.surpriseCtaVariant());
    const cur = seenCta[seenCta.length - 1];
    expect(CTA_COPY_VARIANTS).toContain(cur);
    expect(cur).not.toBe(prev);
    prev = cur;
  }
  unmount();
});

test("typing still edits the active slot in place", () => {
  const { seen, unmount } = mount();
  act(() => api.updateHookText("My own edited line"));
  expect(seen[seen.length - 1]).toBe("My own edited line");
  unmount();
});
