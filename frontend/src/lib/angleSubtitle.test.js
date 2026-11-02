import { angleFitScore, formatVerdicts, goalFitScore } from "./angleSubtitle";

describe("formatVerdicts", () => {
  test("names wins and flops as counts, never a rate", () => {
    expect(formatVerdicts({ wins: 3, flops: 1 })).toBe("3 wins · 1 flop");
    expect(formatVerdicts({ wins: 1, flops: 0 })).toBe("1 win");
  });

  test("stays silent with no evidence", () => {
    expect(formatVerdicts({ wins: 0, flops: 0 })).toBe("");
    expect(formatVerdicts({ wins: 0, flops: 0, adoptions: 0 })).toBe("");
    expect(formatVerdicts(null)).toBe("");
    expect(formatVerdicts(undefined)).toBe("");
  });

  test("shows moved-forward momentum beside verdicts, never as a win", () => {
    expect(formatVerdicts({ wins: 0, flops: 0, adoptions: 2 })).toBe("2 moved forward");
    expect(formatVerdicts({ wins: 3, flops: 1, adoptions: 2 })).toBe("3 wins · 1 flop · 2 moved forward");
  });

  test("names posted clips and watched views as the strongest counts", () => {
    expect(formatVerdicts({ wins: 1, posted: 2, views: 12400 })).toBe(
      "1 win · posted in 2 clips · 12.4k views"
    );
    expect(formatVerdicts({ posted: 1, views: 842 })).toBe("posted in 1 clip · 842 views");
    expect(formatVerdicts({ posted: 3, views: 0 })).toBe("posted in 3 clips");
    expect(formatVerdicts({ wins: 0, flops: 0, adoptions: 0, posted: 0, views: 0 })).toBe("");
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

  test("an angle-style two-row list scores the first row from rank and kind tally", () => {
    const { score, basis, thin } = goalFitScore({
      index: 0,
      total: 2,
      evidence: { wins: 2, flops: 1 },
      hasFitReason: false,
    });
    expect(score).toBe(7);
    expect(thin).toBe(false);
    expect(basis).toBe("2 wins in 3 · suggested 1st of 2");
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

  test("posted clips count double toward the tally and name themselves in the basis", () => {
    // rank 3 + tally (0 + 2*3)/(0 + 2*3) * 6 = 9; three posted clips clear
    // the thin threshold, so no cap.
    const { score, basis, thin } = goalFitScore({
      index: 0,
      total: 6,
      evidence: { wins: 0, flops: 0, posted: 3, views: 36800 },
      hasFitReason: false,
    });
    expect(score).toBe(9);
    expect(thin).toBe(false);
    expect(basis).toContain("proven in 3 posted clips");
    expect(basis).toContain("36.8k views");
  });

  test("one posted clip counts toward thin but cannot clear it alone", () => {
    // One clip is two units of evidence: still thin, capped at 6.
    const { score, basis, thin } = goalFitScore({
      index: 0,
      total: 6,
      evidence: { wins: 0, flops: 0, posted: 1, views: 5000 },
      hasFitReason: false,
    });
    expect(thin).toBe(true);
    expect(score).toBe(6);
    expect(basis).toContain("early signal");
    expect(basis).toContain("proven in 1 posted clip");
  });
});

describe("angleFitScore", () => {
  test("an untested angle never reads as Fit 0/10", () => {
    expect(goalFitScore({ index: 5, total: 6 }).score).toBe(0);
    expect(angleFitScore({ index: 5, total: 6 }).score).toBe(3);
    expect(angleFitScore({ index: 0, total: 6 }).score).toBe(4);
  });

  test("evidence still decides a tested angle's score", () => {
    expect(angleFitScore({ index: 5, total: 6, evidence: { wins: 0, flops: 4 } }).score).toBe(1);
  });
});
