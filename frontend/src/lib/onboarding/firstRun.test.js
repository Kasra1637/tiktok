import {
  isFirstRunDone, markFirstRunDone, isFirstRunDismissed, dismissFirstRun, shouldShowChecklist,
} from "./firstRun";

function fakeStorage(initial) {
  const data = new Map(Object.entries(initial || {}));
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k),
  };
}

test("a fresh visitor still has the whole path ahead", () => {
  const s = fakeStorage();
  expect(shouldShowChecklist(s)).toBe(true);
  expect(isFirstRunDone(s)).toBe(false);
  expect(isFirstRunDismissed(s)).toBe(false);
});

test("the first saved export retires the checklist", () => {
  const s = fakeStorage();
  markFirstRunDone(s);
  expect(isFirstRunDone(s)).toBe(true);
  expect(shouldShowChecklist(s)).toBe(false);
});

test("dismissing hides the card without claiming an export", () => {
  const s = fakeStorage();
  dismissFirstRun(s);
  expect(isFirstRunDismissed(s)).toBe(true);
  expect(isFirstRunDone(s)).toBe(false);
  expect(shouldShowChecklist(s)).toBe(false);
});

test("unreadable storage degrades to showing the card", () => {
  const broken = { getItem: () => { throw new Error("denied"); }, setItem: () => { throw new Error("denied"); } };
  expect(shouldShowChecklist(broken)).toBe(true);
  expect(() => markFirstRunDone(broken)).not.toThrow();
  expect(() => dismissFirstRun(broken)).not.toThrow();
});
