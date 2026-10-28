import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { FitBadge } from "./FitBadge";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

async function mountBadge(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<FitBadge {...props} />);
  });
  return {
    badge: () => container.querySelector("span"),
    unmount: async () => {
      await act(async () => { root.unmount(); });
      container.remove();
    },
  };
}

describe("FitBadge", () => {
  test("shows the score with its basis behind it, never bare", async () => {
    const { badge, unmount } = await mountBadge({
      score: 8,
      basis: "9 wins in 10 · suggested 1st of 6",
      testId: "fit-spot",
    });
    expect(badge().textContent).toBe("Fit 8/10");
    expect(badge().getAttribute("data-testid")).toBe("fit-spot");
    expect(badge().getAttribute("title")).toContain("9 wins in 10");
    expect(badge().getAttribute("aria-label")).toContain("9 wins in 10");
    await unmount();
  });

  test("keeps a fractional server score verbatim instead of rounding it", async () => {
    const { badge, unmount } = await mountBadge({
      score: 9.5,
      basis: "weighted factor sum",
      testId: "fit-frac",
    });
    expect(badge().textContent).toBe("Fit 9.5/10");
    await unmount();
  });
});
