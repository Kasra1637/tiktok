import {
  DEFAULT_DURATION,
  clampHookSeconds,
  readPieceSeconds,
  sectionSplit,
  singlePassCeiling,
  exceedsSinglePass,
  plannedSections,
} from "./videoLength";

describe("clampHookSeconds", () => {
  test("zero means follow the template, not the minimum", () => {
    expect(clampHookSeconds(0)).toBe(0);
  });

  test("out-of-range values clamp to a hook that can land", () => {
    expect(clampHookSeconds(9)).toBe(4);
    expect(clampHookSeconds(1)).toBe(2);
  });

  test("rounds to whole seconds inside the range", () => {
    expect(clampHookSeconds(2.6)).toBe(3);
  });

  test("garbage is zero, never NaN", () => {
    expect(clampHookSeconds("nonsense")).toBe(0);
  });
});

describe("readPieceSeconds", () => {
  test("the project wins once one exists", () => {
    expect(readPieceSeconds({ duration_seconds: 10 }, { default_duration: 15 })).toBe(10);
  });

  test("the template predicts the seed before that", () => {
    expect(readPieceSeconds({}, { default_duration: 12 })).toBe(12);
  });

  test("anything unusable falls back to the default, never NaN", () => {
    expect(readPieceSeconds({}, {})).toBe(DEFAULT_DURATION);
    expect(readPieceSeconds({ duration_seconds: -4 }, {})).toBe(DEFAULT_DURATION);
  });
});

describe("sectionSplit", () => {
  test("the middle is whatever is left", () => {
    expect(sectionSplit(15, 3)).toEqual({ hookSeconds: 3, middleSeconds: 12 });
  });

  test("a boundary longer than the piece cannot make a negative middle", () => {
    expect(sectionSplit(10, 12).middleSeconds).toBeGreaterThanOrEqual(0);
  });
});

describe("single-pass ceiling", () => {
  test("unknown capability is 0, never a guess", () => {
    expect(singlePassCeiling(null)).toBe(0);
    expect(singlePassCeiling({})).toBe(0);
  });

  test("a render past the ceiling is refused, anything else is not", () => {
    expect(exceedsSinglePass(16, { max_duration: 15 })).toBe(true);
    expect(exceedsSinglePass(15, { max_duration: 15 })).toBe(false);
  });

  test("an unknown ceiling fails open", () => {
    expect(exceedsSinglePass(999, null)).toBe(false);
  });
});

describe("plannedSections", () => {
  test("roles come from position, truncated to two", () => {
    const sections = plannedSections({
      segments: [
        { seconds: 3, goal: "hook" },
        { seconds: 12, goal: "middle" },
        { seconds: 5, goal: "cta" },
      ],
    });
    expect(sections.map((s) => s.role)).toEqual(["hook", "middle"]);
  });

  test("missing sections come back present and empty, never absent", () => {
    const sections = plannedSections({});
    expect(sections).toHaveLength(2);
    expect(sections[0]).toMatchObject({ role: "hook", seconds: 0, goal: "" });
  });
});
