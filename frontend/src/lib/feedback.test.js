import { verdictFor, classifyScriptEdit } from "./feedback";

describe("verdictFor", () => {
  test("a saved up or down vote restores the highlight", () => {
    expect(verdictFor({ video: 1 }, "video")).toBe(1);
    expect(verdictFor({ plan: -1 }, "plan")).toBe(-1);
  });

  test("a missing entry, a missing map, or a stale shape reads as unvoted", () => {
    expect(verdictFor({ video: 1 }, "script")).toBe(0);
    expect(verdictFor({}, "video")).toBe(0);
    expect(verdictFor(null, "video")).toBe(0);
    expect(verdictFor(undefined, "video")).toBe(0);
    expect(verdictFor({ video: "yes" }, "video")).toBe(0);
    expect(verdictFor({ video: 0 }, "video")).toBe(0);
  });
});

describe("classifyScriptEdit", () => {
  test("an unchanged script classifies as no edit", () => {
    expect(classifyScriptEdit("same words", "same words")).toBe("");
  });

  test("a small tweak is light and a rewrite is heavy", () => {
    expect(classifyScriptEdit("hello world", "hello world!")).toBe("script_edited_light");
    expect(classifyScriptEdit("short", "a completely rewritten script that says much more than before")).toBe(
      "script_edited_heavy"
    );
  });
});
