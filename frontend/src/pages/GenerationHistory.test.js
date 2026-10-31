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
      Link: ({ to, children, ...rest }) => {
        const href =
          typeof to === "string"
            ? to
            : `${to.pathname || ""}${to.search || ""}${to.hash || ""}`;
        return ReactStub.createElement("a", { href, ...rest }, children);
      },
      // The route is test state: rendering with one query, navigating,
      // then rendering with the navigated query mirrors a real filter turn.
      useNavigate: () => (to) => {
        const route = global.__historyRoute;
        route.navigations.push(to);
        if (to && typeof to === "object" && typeof to.search === "string") {
          route.query = to.search.replace(/^\?/, "");
        }
      },
      useSearchParams: () => [new URLSearchParams(global.__historyRoute?.query || ""), () => {}],
      useLocation: () => ({
        pathname: "/history",
        search: global.__historyRoute?.query ? `?${global.__historyRoute.query}` : "",
        hash: "",
      }),
    };
  },
  { virtual: true }
);

// The repo's jest setup does not resolve the `@/` webpack alias, so stub it:
// the class-join is irrelevant to History, only its pass-through matters.
jest.mock(
  "@/lib/utils",
  () => ({ cn: (...parts) => parts.filter(Boolean).join(" ") }),
  { virtual: true },
);

// The network boundary only: every shipped rule riding on the module
// (durableMediaUrl, getErrorMessage) stays real via requireActual, so this
// mount cannot pass against a stub that has drifted from src/lib/api.js.
jest.mock("../lib/api", () => {
  const actual = jest.requireActual("../lib/api");
  return {
    ...actual,
    api: {
      ...actual.api,
      // Only the endpoints this flow touches: history and profiles on load,
      // verdicts per mounted row, and the kit writer on Generate.
      getGenerationHistory: jest.fn(),
      getAppProfiles: jest.fn(),
      getGeneration: jest.fn(),
      regeneratePostKit: jest.fn(),
    },
  };
});

jest.mock("lucide-react", () => {
  const ReactStub = require("react");
  const Icon = (props) => ReactStub.createElement("span", props);
  // Any icon in the page's tree resolves: the glyphs are irrelevant to
  // History behavior, only their presence as valid elements matters.
  return new Proxy(
    { __esModule: true },
    { get: (target, prop) => (prop in target ? target[prop] : Icon) }
  );
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
import { api } from "../lib/api";
import GenerationHistory from "./GenerationHistory";
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
  jest.clearAllMocks();
  global.__historyRoute = { query: "", navigations: [] };
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
  test.each([
    ["failed", { status: "failed" }, true],
    ["generating with no bytes yet", { status: "generating" }, true],
    ["generating with bytes", { status: "generating", video_url: "/api/media/x.mp4" }, false],
    ["completed with no durable copy", { status: "completed" }, true],
    ["completed with a signed playback copy", { status: "completed", playback_url: "/api/media/x.mp4?sig=1" }, false],
    ["completed with an R2 copy", { status: "completed", r2_url: "https://cdn.example/x.mp4" }, false],
    ["archived", { status: "archived" }, false],
    ["missing row", null, false],
  ])("%s", (_label, row, expected) => {
    expect(needsHistoryRepairRow(row)).toBe(expected);
  });
});

describe("history deep-link and pager helpers", () => {
  test.each([
    ["a copy-less export resolves to the without side", "with", { post_kit: null, audience: "", demo_brief: "" }, "without"],
    ["a copy-carrying render resolves to the with side", "without", { audience: "QA" }, "with"],
    ["without a target the with side is kept", "with", null, "with"],
    ["without a target the without side is kept", "without", null, "without"],
  ])("deep link %s", (_label, param, row, expected) => {
    expect(effectiveCopyFilter(param, row)).toBe(expected);
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

const FILED_COPY = "https://cdn.example/x.mp4";

describe("history attention contract", () => {
  test("no rows means no banner", () => {
    expect(getHistoryAttention([])).toBeNull();
  });

  test.each([
    ["a repair beats a kit-less render", [{ id: "k1", status: "completed", post_kit: null, r2_url: FILED_COPY }, { id: "f1", status: "failed" }], "repair", "f1"],
    ["a filed copy with no kit", [{ id: "k1", status: "completed", post_kit: null, r2_url: FILED_COPY }], "kitless", "k1"],
    ["an archived filed copy with no kit", [{ id: "a1", status: "archived", post_kit: null, r2_url: FILED_COPY }], "kitless", "a1"],
  ])("selects %s", (_label, rows, kind, firstId) => {
    const attention = getHistoryAttention(rows);
    expect(attention.kind).toBe(kind);
    expect(attention.first.id).toBe(firstId);
  });

  test.each([
    ["kit-less", [{ id: "k1", status: "completed", post_kit: null, r2_url: FILED_COPY }], "1 finished render has no post copy yet.", "Generate post copy", "Review without copy"],
    ["two kit-less", [{ id: "k1", status: "completed", post_kit: null, r2_url: FILED_COPY }, { id: "k2", status: "completed", post_kit: null, r2_url: FILED_COPY }], "2 finished renders have no post copy yet.", "Generate post copy", "Review without copy"],
    ["failed", [{ id: "f1", status: "failed" }], "1 clip needs attention.", "provider reason", "Review repair"],
    ["two failed", [{ id: "f1", status: "failed" }, { id: "f2", status: "failed" }], "2 clips need attention.", "Open each card", "Review repair"],
    ["awaiting", [{ id: "g1", status: "generating" }], "1 clip needs attention.", "Check again", "Review repair"],
    ["missing durable copy", [{ id: "c1", status: "completed" }], "1 clip needs attention.", "Retry durable save", "Review repair"],
  ])("words: %s", (_label, rows, summary, guidance, cta) => {
    const words = describeHistoryAttention(getHistoryAttention(rows));
    expect(words.summary).toContain(summary);
    expect(words.guidance).toContain(guidance);
    expect(words.cta).toBe(cta);
  });

  // The page passes the live URLSearchParams object, not a string.
  test.each([
    ["kit-less links to the without side, keeping server filters", [{ id: "k1", status: "completed", post_kit: null, r2_url: FILED_COPY }], "profile=b1&q=noise", "?profile=b1&copy=without", "#generation-k1"],
    ["repair links to the side holding its first clip", [{ id: "f1", status: "failed", audience: "QA" }], "", "?copy=with", "#generation-f1"],
  ])("link: %s", (_label, rows, params, search, hash) => {
    const link = historyAttentionLink(new URLSearchParams(params), getHistoryAttention(rows));
    expect(link.search).toBe(search);
    expect(link.hash).toBe(hash);
  });

  test("only a 429 reads as throttling", () => {
    expect(isThrottlingError({ response: { status: 429 } })).toBe(true);
    expect(isThrottlingError({ response: { status: 502 } })).toBe(false);
    expect(isThrottlingError(null)).toBe(false);
  });
});

describe("history kit-less rescue flow", () => {
  const KIT = {
    caption: "Stop writing empty pages — one tap starts the session. What stalls you?",
    hashtags: ["#FocusTimer", "#studytok", "#deepwork"],
    cover_text: "Stop writing empty pages",
  };
  const KITLESS_ROW = {
    id: "kitless-1",
    status: "completed",
    hook_line: "Stop writing empty pages",
    model: "Veo 3",
    created_at: "2026-10-20T12:00:00.000Z",
    video_url: "https://example.invalid/clip.mp4",
    playback_url: "https://example.invalid/clip.mp4?sig=1",
    r2_url: "https://cdn.example/kitless-1.mp4",
    post_kit: null,
    audience: "",
    demo_brief: "",
  };

  async function renderHistoryPage(query) {
    global.__historyRoute.query = query;
    api.getGenerationHistory.mockResolvedValue({ generations: [{ ...KITLESS_ROW }] });
    api.getAppProfiles.mockResolvedValue({ profiles: [] });
    // HistoryFeedback refreshes each row's verdicts on mount.
    api.getGeneration.mockResolvedValue({ verdicts: {} });
    const container = document.createElement("div");
    document.body.appendChild(container);
    const root = createRoot(container);
    await act(async () => {
      root.render(<GenerationHistory />);
    });
    return { container, root };
  }

  test("a kit-less finished row is rescued by Generate post copy", async () => {
    api.regeneratePostKit.mockResolvedValue({ post_kit: { ...KIT } });
    const { container, root } = await renderHistoryPage("copy=without");

    // The offer: the banner names the missing copy and the row offers to write it.
    expect(container.querySelector('[data-testid="history-attention"]')).not.toBeNull();
    expect(container.textContent).toContain("has no post copy yet");
    const button = container.querySelector(
      '[data-testid="history-generate-post-copy-button-kitless-1"]'
    );
    expect(button).not.toBeNull();

    await act(async () => {
      button.click();
    });

    // One explicit press writes one kit through the regenerate endpoint.
    expect(api.regeneratePostKit).toHaveBeenCalledTimes(1);
    expect(api.regeneratePostKit).toHaveBeenCalledWith("kitless-1");

    // The kit is written, so the banner clears even before navigation.
    expect(container.querySelector('[data-testid="history-attention"]')).toBeNull();

    // The press follows the row to the with-copy side...
    const [nav] = global.__historyRoute.navigations;
    expect(nav.search).toContain("copy=with");

    // ...where the fresh kit reads as Post copy.
    global.__historyRoute.query = nav.search.replace(/^\?/, "");
    await act(async () => {
      root.render(<GenerationHistory />);
    });
    expect(container.textContent).toContain(KIT.caption);
    expect(container.querySelector('[data-testid="history-attention"]')).toBeNull();

    await act(async () => {
      root.unmount();
    });
    container.remove();
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
