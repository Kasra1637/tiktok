import { formatVerdicts, goalFitScore } from "./angleSubtitle";

describe("formatVerdicts", () => {
  test("names wins and flops as counts, never a rate", () => {
    expect(formatVerdicts({ wins: 3, flops: 1 })).toBe("3 wins · 1 flop");
    expect(formatVerdicts({ wins: 1, flops: 0 })).toBe("1 win");
  });

  test("stays silent with no evidence", () => {
    expect(formatVerdicts({ wins: 0, flops: 0 })).toBe("");
    expect(formatVerdicts(null)).toBe("");
    expect(formatVerdicts(undefined)).toBe("");
  });
});

describe("goalFitScore", () => {
  test("a proven goal suggested first with a fit reason scores high", () => {
    const { score, basis, thin } = goalFitScore({
      index: 0,
      total: 6,
      evidence: { wins: 9, flops: 1 },
      hasFitReason: true,
    });
    expect(score).toBe(9);
    expect(thin).toBe(false);
    expect(basis).toContain("9 wins in 10");
    expect(basis).toContain("1st of 6");
    expect(basis).not.toContain("%");
  });

  test("floors instead of rounding up, and caps a perfect tally at 10", () => {
    const { score } = goalFitScore({
      index: 1,
      total: 6,
      evidence: { wins: 9, flops: 1 },
      hasFitReason: true,
    });
    // rank (5/6)*3 = 2.5 + tally 5.4 + 1 = 8.9 -> 8, not 9.
    expect(score).toBe(8);
    expect(
      goalFitScore({ index: 0, total: 6, evidence: { wins: 10, flops: 0 }, hasFitReason: true }).score
    ).toBe(10);
  });

  test("thin evidence caps at 6 and says early signal", () => {
    const { score, basis, thin } = goalFitScore({
      index: 0,
      total: 6,
      evidence: { wins: 2, flops: 0 },
      hasFitReason: true,
    });
    expect(thin).toBe(true);
    expect(score).toBe(6);
    expect(basis).toContain("early signal");
  });

  test("no evidence is unproven, not an error — rank alone, low", () => {
    const first = goalFitScore({ index: 0, total: 6, evidence: null, hasFitReason: true });
    expect(first.score).toBe(4);
    expect(first.basis).toContain("no results yet");
    const last = goalFitScore({ index: 5, total: 6, evidence: null, hasFitReason: false });
    expect(last.score).toBe(0);
  });

  test("an all-flop goal scores at the floor", () => {
    const { score } = goalFitScore({
      index: 5,
      total: 6,
      evidence: { wins: 0, flops: 5 },
      hasFitReason: false,
    });
    expect(score).toBe(0);
  });
});
