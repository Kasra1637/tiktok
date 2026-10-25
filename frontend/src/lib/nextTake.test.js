import { isWinnerRow, pickNextTake, nextTakeFor } from "./nextTake";

const winner = (extra = {}) => ({
  id: "w1",
  status: "completed",
  tiktok_url: "https://www.tiktok.com/@founder/video/1",
  tiktok_views: 9000,
  verdicts: { video: 1 },
  studio_project_id: "draft1",
  ...extra,
});

describe("isWinnerRow", () => {
  test("a thumbs up plus a posted link is a winner", () => {
    expect(isWinnerRow(winner())).toBe(true);
  });

  test("a link alone carries no weight", () => {
    expect(isWinnerRow(winner({ verdicts: {} }))).toBe(false);
  });

  test("a vote alone is judgment without proof of shipping", () => {
    expect(isWinnerRow(winner({ tiktok_url: "" }))).toBe(false);
  });

  test("a thumbs down plus a link is not a winner", () => {
    expect(isWinnerRow(winner({ verdicts: { video: -1 } }))).toBe(false);
  });

  test("missing rows and verdicts read as not winners, never crash", () => {
    expect(isWinnerRow(null)).toBe(false);
    expect(isWinnerRow({})).toBe(false);
  });
});

describe("pickNextTake", () => {
  test("picks the highest reach among finished winners", () => {
    const pick = pickNextTake([
      winner({ id: "low", tiktok_views: 100 }),
      winner({ id: "high", tiktok_views: 50000 }),
    ]);
    expect(pick.id).toBe("high");
  });

  test("shelved, failed, unvoted, unposted and uncounted rows never qualify", () => {
    expect(pickNextTake([
      winner({ id: "shelf", status: "archived", tiktok_views: 99999 }),
      winner({ id: "bad", status: "failed", tiktok_views: 99999 }),
      winner({ id: "quiet", verdicts: {} }),
      winner({ id: "drawer", tiktok_url: "" }),
      winner({ id: "fresh", tiktok_views: null }),
    ])).toBeNull();
  });

  test("no rows means no recommendation", () => {
    expect(pickNextTake([])).toBeNull();
    expect(pickNextTake(null)).toBeNull();
  });
});

describe("nextTakeFor", () => {
  test("a winner with a live draft names the take", () => {
    expect(nextTakeFor(winner(), "/history", new Set(["draft1"]))).toEqual({
      label: "Another take like this",
      to: "/create?project=draft1",
    });
  });

  test("a non-winner with a draft keeps Reuse draft", () => {
    expect(nextTakeFor(winner({ verdicts: {} }), "/history", new Set(["draft1"])).label).toBe("Reuse draft");
  });

  test("an unverified list fails open to the draft link", () => {
    expect(nextTakeFor(winner(), "/history", null).to).toBe("/create?project=draft1");
  });

  test("a verified-gone draft falls through to styling the finished clip", () => {
    expect(nextTakeFor(winner(), "/history", new Set(["other"]))).toEqual({
      label: "Style clip",
      to: "/demo-cta/w1",
    });
  });

  test("a verified-gone draft on an archived row falls back to reviewing it", () => {
    expect(nextTakeFor(winner({ status: "archived", studio_project_id: "ghost" }), "/history", new Set())).toEqual({
      label: "Review clip",
      to: "/history#generation-w1",
    });
  });
});
