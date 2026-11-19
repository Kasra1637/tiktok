import { CREATE_ACTION, pickDashboardAction } from "./dashboardNextAction";

const draft = { projectId: "proj-1", appName: "Vocolens", step: "review" };
const draftLink = "/create?project=proj-1&step=review";
const finished = (id) => ({ id, status: "completed" });
const generating = (id) => ({ id, status: "generating" });

describe("pickDashboardAction", () => {
  test("no app profiles sends the founder to App Profile first", () => {
    const action = pickDashboardAction({ profilesCount: 0, generations: [] });
    expect(action.kind).toBe("profile");
    expect(action.to).toBe("/brand");
  });

  test("no profiles outranks a remembered draft and an in-flight render", () => {
    const action = pickDashboardAction({
      profilesCount: 0,
      draft,
      draftLink,
      generations: [generating("g1")],
    });
    expect(action.kind).toBe("profile");
  });

  test("a remembered draft is continued, named for its app", () => {
    const action = pickDashboardAction({
      profilesCount: 2,
      draft,
      draftLink,
      generations: [],
    });
    expect(action.kind).toBe("draft");
    expect(action.title).toBe("Continue your draft for Vocolens");
    expect(action.to).toBe(draftLink);
  });

  test("a draft without a usable link is not an action", () => {
    const action = pickDashboardAction({
      profilesCount: 1,
      draft,
      draftLink: "",
      generations: [finished("g9")],
    });
    expect(action.kind).toBe("finish");
  });

  test("a draft outranks a render in flight", () => {
    const action = pickDashboardAction({
      profilesCount: 1,
      draft,
      draftLink,
      generations: [generating("g1")],
    });
    expect(action.kind).toBe("draft");
  });

  test("a render in flight is watched in History", () => {
    for (const status of ["submitted", "generating"]) {
      const action = pickDashboardAction({
        profilesCount: 1,
        generations: [{ id: "g1", status }],
      });
      expect(action.kind).toBe("rendering");
      expect(action.to).toBe("/history");
    }
  });

  test("an in-flight render outranks a finished one", () => {
    const action = pickDashboardAction({
      profilesCount: 1,
      generations: [generating("new"), finished("old")],
    });
    expect(action.kind).toBe("rendering");
  });

  test("the newest finished render opens its own Demo + CTA", () => {
    const action = pickDashboardAction({
      profilesCount: 1,
      generations: [
        { id: "failed-new", status: "failed" },
        finished("newest-done"),
        finished("older-done"),
      ],
    });
    expect(action.kind).toBe("finish");
    expect(action.to).toBe("/demo-cta/newest-done");
  });

  test("an archived render counts as finished", () => {
    const action = pickDashboardAction({
      profilesCount: 1,
      generations: [{ id: "arch", status: "archived" }],
    });
    expect(action.kind).toBe("finish");
    expect(action.to).toBe("/demo-cta/arch");
  });

  test("a failed render alone is not a next action — Create is", () => {
    const action = pickDashboardAction({
      profilesCount: 1,
      generations: [{ id: "f1", status: "failed" }],
    });
    expect(action).toBe(CREATE_ACTION);
  });

  test("nothing pending anywhere falls back to Create a video", () => {
    expect(pickDashboardAction({ profilesCount: 3, generations: [] })).toBe(CREATE_ACTION);
    expect(CREATE_ACTION.to).toBe("/create");
  });

  test("missing inputs read as no profiles, never a crash", () => {
    expect(pickDashboardAction().kind).toBe("profile");
    expect(pickDashboardAction({ profilesCount: 1, generations: null }).kind).toBe("create");
  });
});
