import React, { act } from "react";
import { createRoot } from "react-dom/client";

// react-router-dom v7 and lucide-react cannot be resolved by this repo's
// jest version, so the card's visual imports are stubbed: the tests assert
// copy, controls, and outbox behavior, never icon glyphs or navigation.
jest.mock(
  "react-router-dom",
  () => {
    const ReactStub = require("react");
    return {
      Link: ({ to, children, ...rest }) =>
        ReactStub.createElement("a", { href: to, ...rest }, children),
    };
  },
  { virtual: true }
);

jest.mock("lucide-react", () => {
  const ReactStub = require("react");
  const Icon = () => ReactStub.createElement("span", null);
  return {
    AlertTriangle: Icon,
    ChevronRight: Icon,
    Download: Icon,
    RotateCcw: Icon,
  };
});

jest.mock("../components/ui/button", () => {
  const ReactStub = require("react");
  return {
    Button: ({ asChild, variant, size, children, ...rest }) =>
      ReactStub.createElement("button", rest, children),
  };
});

jest.mock("../components/ui/alert", () => {
  const ReactStub = require("react");
  return {
    Alert: ({ children, ...rest }) => ReactStub.createElement("div", rest, children),
    AlertDescription: ({ children, ...rest }) =>
      ReactStub.createElement("div", rest, children),
  };
});

import { historyActionError, needsHistoryRepairRow } from "./historyRepair";
import { PendingSaveCard } from "./PendingSaveCard";
import {
  __resetPendingSavesForTests,
  listPendingSaves,
  recordFailedSave,
} from "../demoCta/saveOutbox";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

beforeEach(() => {
  __resetPendingSavesForTests();
  global.URL.createObjectURL = jest.fn(() => "blob:mock-card");
  global.URL.revokeObjectURL = jest.fn();
});

async function renderCard(entry, onResolved) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  await act(async () => {
    root.render(<PendingSaveCard entry={entry} onResolved={onResolved} />);
  });
  const text = container.textContent;
  return { container, root, text };
}

describe("historyActionError", () => {
  test("a handler detail wins over the action wording", () => {
    expect(
      historyActionError({ response: { status: 413, data: { detail: "Too large." } } }, "retry this save")
    ).toBe("Too large.");
  });

  test("a bodyless 413 names the Download-first remedy, not the status code", () => {
    const message = historyActionError(
      { response: { status: 413 }, message: "Request failed with status code 413" },
      "retry this save"
    );
    expect(message).toContain("Download");
    expect(message).not.toContain("413");
  });

  test("an offline failure names the action and the retry", () => {
    const message = historyActionError({ message: "Network Error" }, "recover this clip's copy");
    expect(message).toContain("recover this clip's copy");
    expect(message).toContain("try again");
  });

  test("anything else falls back with the action attached", () => {
    expect(historyActionError(null, "load History")).toContain("load History");
  });
});

describe("needsHistoryRepairRow", () => {
  test("failed rows need repair", () => {
    expect(needsHistoryRepairRow({ status: "failed" })).toBe(true);
  });

  test("stuck generating rows need repair only without bytes", () => {
    expect(needsHistoryRepairRow({ status: "generating" })).toBe(true);
    expect(needsHistoryRepairRow({ status: "generating", video_url: "/api/media/x.mp4" })).toBe(false);
  });

  test("completed rows need repair only without a durable copy", () => {
    expect(needsHistoryRepairRow({ status: "completed" })).toBe(true);
    expect(needsHistoryRepairRow({ status: "completed", playback_url: "/api/media/x.mp4?sig=1" })).toBe(false);
  });

  test("healthy rows never need repair", () => {
    expect(needsHistoryRepairRow({ status: "completed", r2_url: "https://cdn.example/x.mp4" })).toBe(false);
    expect(needsHistoryRepairRow({ status: "archived" })).toBe(false);
    expect(needsHistoryRepairRow(null)).toBe(false);
  });
});

describe("PendingSaveCard", () => {
  test("a same-tab failure offers Download and Retry save", async () => {
    const entry = recordFailedSave({
      generationId: "gen-1",
      filename: "demo-cta.mp4",
      message: "Too large to save in one request.",
      blob: new Blob(["bytes"], { type: "video/mp4" }),
    });
    const { container, root, text } = await renderCard(entry);
    expect(text).toContain("couldn't be saved");
    expect(text).toContain("Too large to save in one request.");
    expect(text).toContain("Download it here so nothing is lost");
    expect(container.querySelector('[data-testid^="pending-save-download-"]')).not.toBeNull();
    expect(container.querySelector('[data-testid^="pending-save-retry-"]')).not.toBeNull();
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("a reloaded-tab failure sends the founder back to re-export", async () => {
    const entry = recordFailedSave({ generationId: null, filename: "demo-cta.mp4", message: "Too large." });
    const { container, root, text } = await renderCard(entry);
    expect(text).toContain("re-export it from Demo + CTA");
    expect(container.querySelector('[data-testid^="pending-save-reexport-"]')).not.toBeNull();
    expect(container.querySelector('[data-testid^="pending-save-retry-"]')).toBeNull();
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });

  test("dismissing drops the entry and resolves", async () => {
    const onResolved = jest.fn();
    const entry = recordFailedSave({ filename: "demo-cta.mp4", blob: new Blob(["x"]) });
    const { container, root } = await renderCard(entry, onResolved);
    await act(async () => {
      container.querySelector('[data-testid^="pending-save-dismiss-"]').click();
    });
    expect(listPendingSaves()).toHaveLength(0);
    expect(onResolved).toHaveBeenCalled();
    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
