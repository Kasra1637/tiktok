import React, { act } from "react";
import { createRoot } from "react-dom/client";
// The repo's jest setup does not resolve the `@/` webpack alias, so stub it:
// the shared tooltip's class-join is irrelevant to the badge's contract,
// only its pass-through matters (same stub as ui/button.test.jsx).
jest.mock(
  "@/lib/utils",
  () => ({ cn: (...parts) => parts.filter(Boolean).join(" ") }),
  { virtual: true },
);
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
    // No native title: it never reaches keyboard or touch users. The basis
    // rides the shared tooltip instead (next test), and the aria-label
    // carries it for screen readers either way.
    expect(badge().getAttribute("title")).toBeNull();
    expect(badge().getAttribute("aria-label")).toContain("9 wins in 10");
    await unmount();
  });

  test("explains the score in a tooltip the keyboard can reach", async () => {
    const { badge, unmount } = await mountBadge({
      score: 8,
      basis: "9 wins in 10 · suggested 1st of 6",
      testId: "fit-tip",
    });
    expect(badge().getAttribute("tabindex")).toBe("0");
    await act(async () => { badge().focus(); });
    await act(async () => { await new Promise((resolve) => setTimeout(resolve, 400)); });
    const tip = document.body.querySelector('[role="tooltip"]');
    expect(tip).not.toBeNull();
    expect(tip.textContent).toContain("9 wins in 10");
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
