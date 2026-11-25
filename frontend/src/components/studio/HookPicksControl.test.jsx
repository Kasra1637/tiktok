import React, { act } from "react";
import { createRoot } from "react-dom/client";
import HookPicksControl, { profileOutcomeLines, profileOutcomeMenuStale } from "./HookPicksControl";

globalThis.IS_REACT_ACT_ENVIRONMENT = true;

const OUTCOMES = ["Clearing the day's thoughts out loud", "Fall asleep without replaying the day"];

async function mount(props = {}) {
  const container = document.createElement("div");
  document.body.appendChild(container);
  const root = createRoot(container);
  const handlers = {
    onFocusChange: jest.fn(),
    onToneChange: jest.fn(),
    onShapeChange: jest.fn(),
  };
  await act(async () => {
    root.render(
      <HookPicksControl
        focusOptions={OUTCOMES}
        focus=""
        tone=""
        shape="auto"
        {...handlers}
        {...props}
      />
    );
  });
  const q = (id) => container.querySelector(`[data-testid="${id}"]`);
  return {
    container, q, ...handlers,
    unmount: async () => { await act(async () => root.unmount()); container.remove(); },
  };
}

describe("profileOutcomeLines", () => {
  test("statements first, then the flat outcomes they do not already say", () => {
    const profile = {
      outcome_statements: [
        { outcome: "Clearing the day's thoughts out loud", from_feature: "Voice entries" },
        { outcome: "  ", from_feature: "Ignored" },
      ],
      desired_outcomes: [
        "Clearing the day's thoughts out loud",
        "Fall asleep without replaying the day",
      ],
    };
    expect(profileOutcomeLines(profile)).toEqual(OUTCOMES);
  });

  test("chopped fragments an old profile still stores are never offered", () => {
    const profile = {
      outcome_statements: [
        { outcome: "See your own rhythms", from_feature: "Patterns" },
        { outcome: "triggers", from_feature: "Patterns" },
      ],
      desired_outcomes: [
        "and growth over time",
        "from your own words",
        "Fall asleep without replaying the day",
      ],
    };
    expect(profileOutcomeLines(profile)).toEqual([
      "See your own rhythms",
      "Fall asleep without replaying the day",
    ]);
  });

  test("the pick shows six lines at a time, the first six that stand alone", () => {
    const profile = {
      desired_outcomes: [
        "Fall asleep without replaying the day",
        "See your own rhythms",
        "Name the feeling in plain words",
        "Spot the pattern before it builds",
        "End the day feeling settled",
        "Trust what your body is saying",
        "Carry the calm into the morning",
        "Notice the shift as it happens",
      ],
    };
    expect(profileOutcomeLines(profile)).toEqual([
      "Fall asleep without replaying the day",
      "See your own rhythms",
      "Name the feeling in plain words",
      "Spot the pattern before it builds",
      "End the day feeling settled",
      "Trust what your body is saying",
    ]);
  });

  test("an empty profile offers no lines", () => {
    expect(profileOutcomeLines(null)).toEqual([]);
    expect(profileOutcomeLines({})).toEqual([]);
  });
});

describe("profileOutcomeMenuStale (ADR 0320)", () => {
  test("a stored fragment makes the menu stale", () => {
    expect(profileOutcomeMenuStale({ desired_outcomes: ["and growth over time"] })).toBe(true);
    expect(
      profileOutcomeMenuStale({
        outcome_statements: [{ outcome: "triggers", from_feature: "Patterns" }],
      })
    ).toBe(true);
  });

  test("whole stored lines and empty profiles are not stale", () => {
    expect(profileOutcomeMenuStale({ desired_outcomes: OUTCOMES })).toBe(false);
    expect(profileOutcomeMenuStale(null)).toBe(false);
    expect(profileOutcomeMenuStale({})).toBe(false);
  });
});

describe("HookPicksControl", () => {
  test("the Buffet is staged: absent before a hook on a fresh menu (ADR 0320)", async () => {
    const view = await mount({ onRefreshFocus: jest.fn() });
    expect(view.q("hook-picks-focus-refresh")).toBeNull();
    expect(view.q("hook-picks-focus-stale-note")).toBeNull();
    await view.unmount();
  });

  test("the Buffet stands once a hook exists to steer (ADR 0320)", async () => {
    const view = await mount({ onRefreshFocus: jest.fn(), hasHook: true });
    expect(view.q("hook-picks-focus-refresh")).not.toBeNull();
    expect(view.q("hook-picks-focus-stale-note")).toBeNull();
    await view.unmount();
  });

  test("the Buffet stands early on a stale menu, with its reason (ADR 0320)", async () => {
    const view = await mount({ onRefreshFocus: jest.fn(), focusStale: true });
    expect(view.q("hook-picks-focus-refresh")).not.toBeNull();
    expect(view.q("hook-picks-focus-stale-note")).not.toBeNull();
    await view.unmount();
  });

  test("renders the three picks, each on the app's choice by default", async () => {
    const view = await mount();
    const focus = view.q("hook-picks-focus");
    expect(focus).not.toBeNull();
    expect(focus.textContent).toContain("Let the app choose");
    expect(view.q("hook-picks-tone-auto").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("hook-picks-tone-plain").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("hook-picks-tone-warm").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("hook-picks-tone-bold").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("hook-picks-shape-auto").getAttribute("aria-pressed")).toBe("true");
    expect(view.q("hook-picks-shape-question").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("hook-picks-shape-statement").getAttribute("aria-pressed")).toBe("false");
    expect(view.q("hook-picks-stale-note")).toBeNull();
    await view.unmount();
  });

  test("the focus menu offers the app's own outcome lines", async () => {
    const view = await mount();
    const focus = view.q("hook-picks-focus");
    await act(async () => { focus.click(); });
    const scope = focus.closest(".app-select") || view.container;
    const values = [...scope.querySelectorAll('[role="option"]')].map((o) => o.dataset.value);
    expect(values).toEqual(["", ...OUTCOMES]);
    await view.unmount();
  });

  test("picking a focus reports the outcome line itself", async () => {
    const view = await mount();
    const focus = view.q("hook-picks-focus");
    await act(async () => { focus.click(); });
    const scope = focus.closest(".app-select") || view.container;
    const option = [...scope.querySelectorAll('[role="option"]')]
      .find((o) => o.dataset.value === OUTCOMES[1]);
    await act(async () => { option.click(); });
    expect(view.onFocusChange).toHaveBeenCalledWith(OUTCOMES[1]);
    await view.unmount();
  });

  test("picking a tone and a shape reports each pick", async () => {
    const view = await mount();
    await act(async () => { view.q("hook-picks-tone-warm").click(); });
    expect(view.onToneChange).toHaveBeenCalledWith("warm");
    await act(async () => { view.q("hook-picks-shape-question").click(); });
    expect(view.onShapeChange).toHaveBeenCalledWith("question");
    await view.unmount();
  });

  test("a saved focus the profile no longer carries reads as the app's choice", async () => {
    const view = await mount({ focus: "An outcome the profile dropped" });
    expect(view.q("hook-picks-focus").textContent).toContain("Let the app choose");
    await view.unmount();
  });

  test("the stale note shows only when the line on file predates the picks", async () => {
    const view = await mount({ stale: true });
    const note = view.q("hook-picks-stale-note");
    expect(note).not.toBeNull();
    expect(note.textContent).toContain("suggest a clearer hook");
    await view.unmount();
  });
});
