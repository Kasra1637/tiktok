import { verdictFor, classifyScriptEdit, recordBehavior } from "./feedback";
import { api } from "./api";

jest.mock("./api", () => ({
  api: { recordFeedback: jest.fn().mockResolvedValue({}) },
}));

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

describe("recordBehavior", () => {
  beforeEach(() => {
    api.recordFeedback.mockClear();
  });

  test("records adopted, abandoned and generated with the component and refs", async () => {
    await expect(
      recordBehavior("generated", "template", {
        brand_profile_id: "p1",
        studio_project_id: "s1",
        template_id: "t-shown",
      })
    ).resolves.toBe(true);
    expect(api.recordFeedback).toHaveBeenCalledWith({
      event: "generated",
      step: "template",
      detail: "",
      brand_profile_id: "p1",
      studio_project_id: "s1",
      generation_id: "",
      template_id: "t-shown",
    });
  });

  test("refuses unknown events and a missing component without calling the api", async () => {
    await expect(recordBehavior("thumb_up", "template", {})).resolves.toBe(false);
    await expect(recordBehavior("adopted", "", {})).resolves.toBe(false);
    expect(api.recordFeedback).not.toHaveBeenCalled();
  });

  test("a failed post reads as not recorded, never a throw", async () => {
    api.recordFeedback.mockRejectedValueOnce(new Error("offline"));
    await expect(recordBehavior("adopted", "goal", {})).resolves.toBe(false);
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
