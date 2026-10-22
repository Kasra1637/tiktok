import React, { act } from "react";
import { createRoot } from "react-dom/client";
import { toast } from "sonner";
import { copyTextWithToast, useCopyButton } from "./copyClipboard";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

jest.mock("sonner", () => ({
  toast: { success: jest.fn(), error: jest.fn() },
}));

function setClipboard(writeText) {
  Object.defineProperty(window.navigator, "clipboard", {
    value: { writeText },
    configurable: true,
  });
}

function Probe({ resetMs, onCopy }) {
  const { copiedKey, copy } = useCopyButton(resetMs);
  onCopy(copy);
  return <span data-state={copiedKey === "k" ? "copied" : "idle"} />;
}

async function mountProbe(resetMs = 20) {
  let copyFn = null;
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<Probe resetMs={resetMs} onCopy={(fn) => { copyFn = fn; }} />);
  });
  return {
    copy: (...args) => copyFn(...args),
    state: () => container.querySelector("span").getAttribute("data-state"),
    settle: (ms) => act(async () => {
      await new Promise((resolve) => setTimeout(resolve, ms));
    }),
    unmount: async () => {
      await act(async () => { root.unmount(); });
      container.remove();
    },
  };
}

beforeEach(() => {
  jest.clearAllMocks();
});

describe("copyTextWithToast", () => {
  test("a landed write toasts success and reports true", async () => {
    const writeText = jest.fn().mockResolvedValue(undefined);
    setClipboard(writeText);
    await expect(copyTextWithToast("hello", "Thing")).resolves.toBe(true);
    expect(writeText).toHaveBeenCalledWith("hello");
    expect(toast.success).toHaveBeenCalledWith("Thing copied to clipboard");
    expect(toast.error).not.toHaveBeenCalled();
  });

  test("a refused write toasts the manual fallback and reports false", async () => {
    setClipboard(jest.fn().mockRejectedValue(new Error("denied")));
    await expect(copyTextWithToast("hello", "Thing")).resolves.toBe(false);
    expect(toast.error).toHaveBeenCalledWith(
      "Copy failed — select the text manually instead."
    );
    expect(toast.success).not.toHaveBeenCalled();
  });
});

describe("useCopyButton", () => {
  test("a copied key shows, then clears itself", async () => {
    setClipboard(jest.fn().mockResolvedValue(undefined));
    const probe = await mountProbe(20);
    expect(probe.state()).toBe("idle");
    await act(async () => {
      await probe.copy("k", "hello", "Thing");
    });
    expect(probe.state()).toBe("copied");
    expect(toast.success).toHaveBeenCalledWith("Thing copied to clipboard");
    await probe.settle(60);
    expect(probe.state()).toBe("idle");
    await probe.unmount();
  });

  test("a refused write never flips the indicator", async () => {
    setClipboard(jest.fn().mockRejectedValue(new Error("denied")));
    const probe = await mountProbe(20);
    await act(async () => {
      await probe.copy("k", "hello", "Thing");
    });
    expect(probe.state()).toBe("idle");
    expect(toast.error).toHaveBeenCalled();
    expect(toast.success).not.toHaveBeenCalled();
    await probe.unmount();
  });
});
