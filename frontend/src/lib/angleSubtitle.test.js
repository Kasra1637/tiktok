import { stripTrailingPeriod, angleSubtitle, angleDetails, formatVerdicts } from "./angleSubtitle";

describe("stripTrailingPeriod", () => {
  test("drops one terminal full stop", () => {
    expect(stripTrailingPeriod("Ends here.")).toBe("Ends here");
  });

  test("keeps emphasis and abbreviations intact", () => {
    expect(stripTrailingPeriod("Wait for it...")).toBe("Wait for it...");
    expect(stripTrailingPeriod("Something e.g.")).toBe("Something e.g.");
  });
});

describe("angleSubtitle", () => {
  test("picks the kind's most relevant field first", () => {
    expect(
      angleSubtitle({ kind: "feature_demonstration", app_feature: "mood graphs.", hook_promise: "a promise." })
    ).toBe("Mood graphs");
  });

  test("falls back through the other fields when the preferred is empty", () => {
    expect(angleSubtitle({ kind: "feature_demonstration", hook_promise: "a promise." })).toBe("A promise");
  });

  test("a sparse angle still gets a line, an empty one gets none", () => {
    expect(angleSubtitle({ kind: "unknown_kind", target_audience: "night owls." })).toBe("Night owls");
    expect(angleSubtitle({})).toBe("");
    expect(angleSubtitle(null)).toBe("");
  });
});

describe("angleDetails", () => {
  test("only fields with text travel", () => {
    const rows = angleDetails({ target_audience: "Founders.", hook_promise: "" });
    expect(rows).toEqual([{ label: "Audience", value: "Founders" }]);
  });

  test("boundaries join into one line, skipped when absent", () => {
    expect(angleDetails({ claims_to_respect: ["No income claims.", ""] })).toEqual([
      { label: "Bounded by", value: "No income claims" },
    ]);
    expect(angleDetails({})).toEqual([]);
  });
});

describe("formatVerdicts", () => {
  test("counts, never a rate", () => {
    expect(formatVerdicts({ wins: 3, flops: 1 })).toBe("3 wins · 1 flop");
    expect(formatVerdicts({ wins: 1 })).toBe("1 win");
  });

  test("no evidence is an empty string, not a zero tally", () => {
    expect(formatVerdicts({})).toBe("");
    expect(formatVerdicts(null)).toBe("");
  });
});
