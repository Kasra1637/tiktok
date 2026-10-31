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
    Button: ({ asChild, variant, size, busy, children, ...rest }) =>
      ReactStub.createElement(
        "button",
        { ...rest, ...(busy ? { "data-busy": "true", "aria-busy": "true" } : {}) },
        children
      ),
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

import {
  historyActionError,
  needsHistoryRepairRow,
  isAwaitingProvider,
  isThrottlingError,
  effectiveCopyFilter,
  getHistoryAttention,
  describeHistoryAttention,
  historyAttentionLink,
  shouldShowHistoryEmpty,
  shouldOfferDraftLink,
  shouldApplyDeepLinkPage,
  pageForRowIndex,
} from "./historyRepair";
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

describe("history deep-link and pager helpers", () => {
  test("a deep link to a copy-less export resolves to the without side", () => {
    expect(effectiveCopyFilter("with", { post_kit: null, audience: "", demo_brief: "" })).toBe("without");
  });

  test("a deep link to a copy-carrying render resolves to the with side", () => {
    expect(effectiveCopyFilter("without", { audience: "QA" })).toBe("with");
  });

  test("without a deep-link target the chosen filter is kept", () => {
    expect(effectiveCopyFilter("with", null)).toBe("with");
    expect(effectiveCopyFilter("without", null)).toBe("without");
  });

  test("a deep link jumps to its page exactly once", () => {
    expect(shouldApplyDeepLinkPage(null, "abc")).toBe(true);
    expect(shouldApplyDeepLinkPage("abc", "abc")).toBe(false);
    expect(shouldApplyDeepLinkPage("abc", "")).toBe(false);
  });

  test("row 50 of 50-per-page lives on page 2", () => {
    expect(pageForRowIndex(0)).toBe(1);
    expect(pageForRowIndex(49)).toBe(1);
    expect(pageForRowIndex(50)).toBe(2);
  });
});

describe("history attention selection", () => {
  test("no rows means no banner", () => {
    expect(getHistoryAttention([])).toBeNull();
  });

  test("repairs beat kit-less finished renders", () => {
    const attention = getHistoryAttention([
      { id: "k1", status: "completed", post_kit: null, r2_url: "https://cdn.example/k1.mp4" },
      { id: "f1", status: "failed" },
    ]);
    expect(attention.kind).toBe("repair");
    expect(attention.first.id).toBe("f1");
  });

  test("kit-less finished renders surface only when nothing needs repair", () => {
    // A durable copy is filed, so this is not a repair — it merely lacks kits.
    const attention = getHistoryAttention([
      { id: "k1", status: "completed", post_kit: null, r2_url: "https://cdn.example/k1.mp4" },
    ]);
    expect(attention.kind).toBe("kitless");
    const words = describeHistoryAttention(attention);
    expect(words.summary).toContain("no post copy yet");
    expect(words.guidance).toContain("Generate post copy");
    expect(words.cta).toBe("Review without copy");
  });

  test("repair words name the failed-row next step", () => {
    const words = describeHistoryAttention(
      getHistoryAttention([{ id: "f1", status: "failed" }])
    );
    expect(words.summary).toContain("needs attention");
    expect(words.guidance).toContain("provider reason");
    expect(words.cta).toBe("Review repair");
  });

  test("an archived render with a filed copy is kit-less, not repair", () => {
    const attention = getHistoryAttention([
      { id: "a1", status: "archived", post_kit: null, r2_url: "https://cdn.example/a1.mp4" },
    ]);
    expect(attention.kind).toBe("kitless");
  });

  test("an awaiting row names Check again, a copy-less filed row names Retry save", () => {
    const awaiting = describeHistoryAttention(
      getHistoryAttention([{ id: "g1", status: "generating" }])
    );
    expect(awaiting.guidance).toContain("Check again");
    const undurable = describeHistoryAttention(
      getHistoryAttention([{ id: "c1", status: "completed" }])
    );
    expect(undurable.guidance).toContain("Retry durable save");
  });

  test("the banner link selects its clip's side and clears the search", () => {
    const kitless = getHistoryAttention([{ id: "k1", status: "completed", post_kit: null, r2_url: "https://cdn.example/k1.mp4" }]);
    // The page passes the live URLSearchParams object, not a string.
    const kitLink = historyAttentionLink(new URLSearchParams("profile=b1&q=noise"), kitless);
    expect(kitLink.search).toContain("copy=without");
    expect(kitLink.search).not.toContain("q=");
    expect(kitLink.search).toContain("profile=b1");
    expect(kitLink.hash).toBe("#generation-k1");
    const failed = getHistoryAttention([{ id: "f1", status: "failed", audience: "QA" }]);
    expect(historyAttentionLink("", failed).search).toContain("copy=with");
  });

  test("only a 429 reads as throttling", () => {
    expect(isThrottlingError({ response: { status: 429 } })).toBe(true);
    expect(isThrottlingError({ response: { status: 502 } })).toBe(false);
    expect(isThrottlingError(null)).toBe(false);
  });
});

describe("history queued repair", () => {
  test("submitted rows without bytes are awaiting the provider", () => {
    expect(isAwaitingProvider({ status: "submitted" })).toBe(true);
    expect(isAwaitingProvider({ status: "submitted", video_url: "/api/media/x.mp4" })).toBe(false);
  });

  test("submitted rows without bytes need repair", () => {
    expect(needsHistoryRepairRow({ status: "submitted" })).toBe(true);
  });
});

describe("history empty state", () => {
  test("a load failure never reads as an empty account", () => {
    expect(shouldShowHistoryEmpty({ loading: false, error: "boom", rowsLength: 0 })).toBe(false);
    expect(shouldShowHistoryEmpty({ loading: false, error: null, rowsLength: 0 })).toBe(true);
  });
});

describe("history draft links", () => {
  test("a confirmed-gone draft offers no link, even for non-winners", () => {
    expect(shouldOfferDraftLink("gone", new Set(["kept"]))).toBe(false);
  });

  test("an unverified list fails open to the draft link", () => {
    expect(shouldOfferDraftLink("maybe", null)).toBe(true);
    expect(shouldOfferDraftLink("kept", new Set(["kept"]))).toBe(true);
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
