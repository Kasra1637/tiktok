import { clipWindow } from "./constants";

test("both trim points define one nonempty source window", () => {
  expect(clipWindow(12, 2, 0.5, 8)).toEqual({ start: 2, end: 8, duration: 6, maxStart: 7.5 });
  expect(clipWindow(12, 9, 0.5, 4)).toEqual({ start: 3.5, end: 4, duration: 0.5, maxStart: 3.5 });
  expect(clipWindow(12, 2, 0.5, null).duration).toBe(10);
  expect(clipWindow(12, 0, 0.5, 99).end).toBe(12);
  expect(clipWindow(0, 2, 0.5, 8).duration).toBe(0);
});
