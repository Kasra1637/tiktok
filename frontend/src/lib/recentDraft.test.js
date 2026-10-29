import {
  rememberDraft,
  readRecentDraft,
  forgetDraft,
  draftHref,
  subscribeRecentDraft,
} from "./recentDraft";

describe("recent draft memory", () => {
  beforeEach(() => {
    localStorage.clear();
  });

  it("round-trips the project, app name and step", () => {
    rememberDraft({ projectId: "proj-1", appName: "Vocolens", step: "review" });
    expect(readRecentDraft()).toEqual({
      projectId: "proj-1",
      appName: "Vocolens",
      step: "review",
    });
  });

  it("refuses to remember without a usable project id", () => {
    for (const projectId of [undefined, null, "", "   ", 42, "x".repeat(200)]) {
      rememberDraft({ projectId, appName: "Vocolens", step: "angle" });
      expect(readRecentDraft()).toBeNull();
    }
  });

  it("drops a step the wizard does not have instead of linking nowhere", () => {
    rememberDraft({ projectId: "proj-2", appName: "", step: "assets" });
    expect(readRecentDraft()).toEqual({ projectId: "proj-2", appName: "", step: "" });
  });

  it("truncates a very long app name rather than growing the nav line", () => {
    rememberDraft({ projectId: "proj-3", appName: "A".repeat(200), step: "profile" });
    expect(readRecentDraft().appName).toHaveLength(80);
  });

  it("reads junk as nothing", () => {
    for (const raw of ["not json", "[]", "null", '{"projectId":""}', '{"projectId":7}']) {
      localStorage.setItem("vocolens.recentDraft", raw);
      expect(readRecentDraft()).toBeNull();
    }
  });

  it("forgets on demand", () => {
    rememberDraft({ projectId: "proj-4", appName: "Vocolens", step: "angle" });
    forgetDraft();
    expect(readRecentDraft()).toBeNull();
  });

  it("builds a deep link that carries the project and step", () => {
    expect(draftHref({ projectId: "proj 5", step: "review" })).toBe(
      "/create?project=proj+5&step=review"
    );
  });

  it("builds no link for an unusable draft", () => {
    expect(draftHref(null)).toBe("");
    expect(draftHref({})).toBe("");
    expect(draftHref({ projectId: "  " })).toBe("");
  });

  it("notifies subscribers on write and forget, and stops after unsubscribe", () => {
    const seen = [];
    const stop = subscribeRecentDraft((draft) => seen.push(draft));
    rememberDraft({ projectId: "proj-6", appName: "Vocolens", step: "angle" });
    forgetDraft();
    stop();
    rememberDraft({ projectId: "proj-7", appName: "Vocolens", step: "angle" });
    expect(seen).toHaveLength(2);
    expect(seen[0].projectId).toBe("proj-6");
    expect(seen[1]).toBeNull();
  });
});
