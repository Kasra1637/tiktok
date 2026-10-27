import { TRANSITIONS, TRANSITION_IDS, transitionAt, effectiveTransition, hash01 } from "./transitions";

describe("clip transitions", () => {
  test("the catalog holds six trends plus a hard cut", () => {
    expect(TRANSITION_IDS).toEqual(["none", "whip", "zoom", "spin", "glitch", "flash", "fade"]);
    expect(TRANSITIONS).toHaveLength(7);
  });

  test("every trend lasts a TikTok beat, never a linger", () => {
    for (const t of TRANSITIONS.filter((t) => t.id !== "none")) {
      expect(t.duration).toBeGreaterThanOrEqual(0.2);
      expect(t.duration).toBeLessThanOrEqual(0.5);
    }
  });

  test("a hard cut is never a transition window", () => {
    expect(transitionAt(5, 5, 5, "none").active).toBe(false);
    expect(transitionAt(5, 5, 5, "bogus").active).toBe(false);
  });

  test("the window straddles the cut: out before, in after", () => {
    const out = transitionAt(10 - 0.1, 10, 8, "whip");
    const inn = transitionAt(10 + 0.1, 10, 8, "whip");
    expect(out.active).toBe(true);
    expect(out.side).toBe("out");
    expect(inn.active).toBe(true);
    expect(inn.side).toBe("in");
  });

  test("progress runs 0 to 1 across the window and sleeps outside it", () => {
    const start = transitionAt(10 - 0.175, 10, 8, "whip");
    const mid = transitionAt(10, 10, 8, "whip");
    const end = transitionAt(10 + 0.175 - 0.001, 10, 8, "whip");
    expect(start.progress).toBeCloseTo(0, 2);
    expect(mid.progress).toBeCloseTo(0.5, 2);
    expect(end.progress).toBeCloseTo(1, 2);
    expect(transitionAt(2, 10, 8, "whip").active).toBe(false);
    expect(transitionAt(17, 10, 8, "whip").active).toBe(false);
  });

  test("a short clip shrinks the window instead of eating the clip", () => {
    const t = transitionAt(0.4, 0.4, 0.4, "spin");
    expect(t.active).toBe(true);
    expect(transitionAt(0.05, 0.4, 0.4, "spin").active).toBe(false);
  });

  test("reduced motion parks strobes and spins as cuts, keeps the gentle fade", () => {
    for (const id of ["whip", "zoom", "spin", "glitch", "flash"]) {
      expect(effectiveTransition(id, true)).toBe("none");
    }
    expect(effectiveTransition("fade", true)).toBe("fade");
    expect(effectiveTransition("none", true)).toBe("none");
  });

  test("without reduced motion every pick plays as chosen", () => {
    for (const id of TRANSITION_IDS) {
      expect(effectiveTransition(id, false)).toBe(id);
    }
    expect(effectiveTransition("bogus", false)).toBe("bogus");
  });

  test("a reduced-motion pick leaves no transition window", () => {
    const resolved = effectiveTransition("flash", true);
    expect(transitionAt(10, 10, 8, resolved).active).toBe(false);
  });

  test("glitch randomness is deterministic per frame", () => {
    expect(hash01(7)).toBe(hash01(7));
    expect(hash01(7)).toBeGreaterThanOrEqual(0);
    expect(hash01(7)).toBeLessThan(1);
    expect(hash01(8)).not.toBe(hash01(7));
  });
});
