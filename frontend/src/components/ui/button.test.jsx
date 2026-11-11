import React, { act } from "react";
import { createRoot } from "react-dom/client";
// The repo's jest setup does not resolve the `@/` webpack alias, so stub it:
// the class-join is irrelevant to the countdown and the surface swap, only
// its pass-through matters.
jest.mock(
  "@/lib/utils",
  () => ({ cn: (...parts) => parts.filter(Boolean).join(" ") }),
  { virtual: true },
);
import { Button } from "./button";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.useFakeTimers();

async function mountButton(props) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Button {...props} />);
  });
  return {
    button: () => container.querySelector("button"),
    rerender: async (nextProps) => {
      await act(async () => {
        root.render(<Button {...nextProps} />);
      });
    },
    unmount: async () => {
      await act(async () => {
        root.unmount();
      });
      container.remove();
    },
  };
}

async function advance(seconds) {
  await act(async () => {
    jest.advanceTimersByTime(seconds * 1000);
  });
}

describe("Button generating state", () => {
  test("a generation wait wears the Use this photo dark surface and counts down", async () => {
    const { button, unmount } = await mountButton({
      busy: true,
      variant: "accent",
      etaSeconds: 30,
      children: "Generating angles",
    });
    try {
      expect(button().getAttribute("data-generating")).toBe("true");
      expect(button().getAttribute("data-eta")).toBe("30");
      // The dark "Use this photo" surface: the secondary fill, never the
      // indigo accent the button wears at rest. Text stays the CTA's own.
      expect(button().className).toContain("bg-secondary/70");
      expect(button().className).toContain("btn-bevel-neutral");
      expect(button().className).not.toContain("btn-bevel-accent");
      expect(button().textContent).toContain("Generating angles");
      expect(button().textContent).toContain("· 30s");
      await advance(1);
      expect(button().textContent).toContain("· 29s");
      await advance(1);
      expect(button().textContent).toContain("· 28s");
    } finally {
      await unmount();
    }
  });

  test("the countdown holds at 0s instead of going negative or restarting", async () => {
    const { button, unmount } = await mountButton({
      busy: true,
      variant: "accent",
      etaSeconds: 12,
      children: "Regenerating copy",
    });
    try {
      await advance(12);
      expect(button().textContent).toContain("· 0s");
      await advance(5);
      expect(button().textContent).toContain("· 0s");
    } finally {
      await unmount();
    }
  });

  test("ending the wait restores the button's own surface and drops the count", async () => {
    const mounted = await mountButton({
      busy: true,
      variant: "accent",
      etaSeconds: 30,
      children: "Generating angles",
    });
    try {
      expect(mounted.button().className).toContain("bg-secondary/70");
      await mounted.rerender({ variant: "accent", etaSeconds: 30, children: "Generate angles" });
      expect(mounted.button().className).toContain("btn-bevel-accent");
      expect(mounted.button().className).not.toContain("bg-secondary/70");
      expect(mounted.button().querySelector('[data-testid="busy-eta"]')).toBeNull();
    } finally {
      await mounted.unmount();
    }
  });

  test("short, idle and determinate busy buttons take no countdown or surface swap", async () => {
    const short = await mountButton({ busy: true, variant: "accent", etaSeconds: 5, children: "Saving" });
    try {
      expect(short.button().querySelector('[data-testid="busy-eta"]')).toBeNull();
      expect(short.button().className).toContain("btn-bevel-accent");
    } finally {
      await short.unmount();
    }
    const idle = await mountButton({ variant: "accent", etaSeconds: 30, children: "Generate angles" });
    try {
      expect(idle.button().querySelector('[data-testid="busy-eta"]')).toBeNull();
      expect(idle.button().className).toContain("btn-bevel-accent");
    } finally {
      await idle.unmount();
    }
    const counted = await mountButton({
      busy: true,
      variant: "accent",
      progress: 0.5,
      etaSeconds: 30,
      children: "Generating angles",
    });
    try {
      expect(counted.button().querySelector('[data-testid="busy-eta"]')).toBeNull();
      expect(counted.button().className).toContain("btn-bevel-accent");
    } finally {
      await counted.unmount();
    }
  });
});
