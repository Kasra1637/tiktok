import { rateMetric, initVitals } from "./vitals";

describe("rateMetric", () => {
  test("LCP is good under two and a half seconds, poor past four", () => {
    expect(rateMetric("LCP", 2400)).toBe("good");
    expect(rateMetric("LCP", 3000)).toBe("needs-improvement");
    expect(rateMetric("LCP", 4500)).toBe("poor");
  });

  test("INP is good under a fifth of a second, poor past half", () => {
    expect(rateMetric("INP", 150)).toBe("good");
    expect(rateMetric("INP", 300)).toBe("needs-improvement");
    expect(rateMetric("INP", 600)).toBe("poor");
  });

  test("CLS is good at a tenth, poor past a quarter", () => {
    expect(rateMetric("CLS", 0.05)).toBe("good");
    expect(rateMetric("CLS", 0.15)).toBe("needs-improvement");
    expect(rateMetric("CLS", 0.3)).toBe("poor");
  });

  test("unknown names and non-numbers never rate as real verdicts", () => {
    expect(rateMetric("FCP", 100)).toBe("unknown");
    expect(rateMetric("LCP", Number.NaN)).toBe("unknown");
  });
});

describe("initVitals", () => {
  test("is a no-op where PerformanceObserver does not exist", () => {
    // jsdom has no PerformanceObserver: init must degrade to a cleanup
    // function, never throw, and never invent numbers.
    const stop = initVitals(() => {
      throw new Error("must not report without observers");
    });
    expect(typeof stop).toBe("function");
    expect(() => stop()).not.toThrow();
    expect(window.__hookforgeVitals).toBeUndefined();
  });
});
