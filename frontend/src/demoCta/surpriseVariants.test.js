import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { CTA_COPY_VARIANTS } from "./constants";
import { useOverlayTaste } from "./useOverlayTaste";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

let api;
function Probe({ seenCta }) {
  api = useOverlayTaste({
    overlayScope: "surprise",
    videoUrl: null,
    clipDuration: 0,
    recording: false,
    onCtaHeadline: (v) => seenCta.push(v),
  });
  return null;
}

test("surprise CTA always lands on a different preset in the pool", () => {
  window.localStorage.clear();
  const seenCta = [];
  const div = document.createElement("div");
  const root = createRoot(div);
  act(() => root.render(<Probe seenCta={seenCta} />));
  expect(api.ctaVariants).toEqual(CTA_COPY_VARIANTS);
  let prev = null;
  for (let i = 0; i < 20; i += 1) {
    act(() => api.surpriseCtaVariant());
    const cur = seenCta[seenCta.length - 1];
    expect(CTA_COPY_VARIANTS).toContain(cur);
    expect(cur).not.toBe(prev);
    prev = cur;
  }
  act(() => api.updateCtaHeadline("My end card"));
  expect(seenCta[seenCta.length - 1]).toBe("My end card");
  act(() => root.unmount());
});
