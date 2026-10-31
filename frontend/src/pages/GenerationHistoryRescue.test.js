import React, { act } from "react";
import { createRoot } from "react-dom/client";

// Full-page mount: the rescue flow exercises the page's route state and its
// network boundary together, so both doubles live with their only consumer.
// Router is test state; lib/api is the real module with only the touched
// endpoints replaced, so shipped rules like durableMediaUrl stay real.
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
      // Rendering with one query, navigating, then rendering with the
      // navigated query mirrors a real filter turn.
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

import { api } from "../lib/api";
import GenerationHistory from "./GenerationHistory";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

// No shared setup: the single flow below sets its own mocks, route, and
// api implementations. (CRA resets all mocks before each test anyway.)
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
    // Route state belongs to this mount: no other test in this file navigates.
    global.__historyRoute = { query, navigations: [] };
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

  test("a refused Generate names the next step instead of dying silently", async () => {
    // The draft behind this render is gone, so the endpoint 404s.
    api.regeneratePostKit.mockRejectedValue({
      response: { status: 404, data: { detail: "That draft is gone, so there is no material to write." } },
    });
    const { container, root } = await renderHistoryPage("copy=without");
    const button = container.querySelector(
      '[data-testid="history-generate-post-copy-button-kitless-1"]'
    );

    await act(async () => {
      button.click();
    });

    // The refusal is loud: the row names the next step...
    expect(container.textContent).toContain("That draft is gone");
    // ...the banner still offers the rescue, nothing navigated away...
    expect(container.querySelector('[data-testid="history-attention"]')).not.toBeNull();
    expect(global.__historyRoute.navigations).toHaveLength(0);
    // ...and the button is pressable again.
    expect(button.textContent).toContain("Generate post copy");
    expect(button.disabled).toBe(false);

    await act(async () => {
      root.unmount();
    });
    container.remove();
  });
});
