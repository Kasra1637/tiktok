const mockPost = jest.fn();
const mockGet = jest.fn();

jest.mock("axios", () => ({
  __esModule: true,
  default: {
    create: () => ({
      get: (...args) => mockGet(...args),
      post: (...args) => mockPost(...args),
      patch: jest.fn(),
      delete: jest.fn(),
      interceptors: { request: { use: jest.fn() }, response: { use: jest.fn() } },
    }),
  },
}));

import { api, DEMO_CTA_PART_BYTES } from "./api";

beforeEach(() => {
  mockPost.mockReset();
  mockPost.mockResolvedValue({ data: { id: "saved-1" } });
  mockGet.mockReset();
  mockGet.mockResolvedValue({ data: {} });
});

test("the angle list read carries the camera setup when one is given", async () => {
  // ADR 0233: the wizard reads the angles with the project's setup so a
  // fixed camera's list restates outdoor places indoors server-side.
  // No setup (the profile page) sends no param and reads as written.
  await api.getContentAngles("p1", "fixed");
  expect(mockGet.mock.calls[0][0]).toBe("/app-profiles/p1/content-angles");
  expect(mockGet.mock.calls[0][1]).toEqual({ params: { camera_setup: "fixed" } });
  await api.getContentAngles("p1");
  expect(mockGet.mock.calls[1][1]).toEqual({ params: {} });
});

test("angle generation carries the camera setup for the response's display", async () => {
  await api.generateContentAngles("p1", { cameraSetup: "fixed" });
  expect(mockPost.mock.calls[0][0]).toBe("/app-profiles/p1/content-angles");
  expect(mockPost.mock.calls[0][1]).toEqual({ camera_setup: "fixed" });
  await api.regenerateContentAngles("p1", { objective: "educate_viewers", cameraSetup: "fixed" });
  expect(mockPost.mock.calls[1][0]).toBe("/app-profiles/p1/content-angles/regenerate");
  expect(mockPost.mock.calls[1][1]).toEqual({ objective: "educate_viewers", camera_setup: "fixed" });
  await api.generateContentAngles("p1");
  expect(mockPost.mock.calls[2][1]).toEqual({});
});

test("creating a story draft posts to the stories router", async () => {
  // ADR 0235: creation is the one story-shaped call — the stories
  // router owns it because the type is required and validated there.
  // Reads and edits ride the shared studio project endpoints instead.
  await api.createStoryProject({ brand_profile_id: "p1", story_type: "demo_moment" });
  expect(mockPost.mock.calls[0][0]).toBe("/stories/projects");
  expect(mockPost.mock.calls[0][1]).toEqual({ brand_profile_id: "p1", story_type: "demo_moment" });
});

test("the story draft list reads the profile's projects and keeps only stories", async () => {
  // One table, one list endpoint (ADR 0227): the read asks for the
  // profile's projects and the kind marker does the separating, so a
  // hook-video draft for the same app never shows up as a story draft.
  mockGet.mockResolvedValue({
    data: {
      projects: [
        { id: "s1", kind: "story", story_type: "hook_teaser" },
        { id: "v1", kind: "video" },
        { id: "s2", kind: "story", story_type: "question_poll" },
        { id: "v0" },
      ],
    },
  });
  const { projects } = await api.getStoryProjects("p1");
  expect(mockGet.mock.calls[0][0]).toBe("/studio/projects");
  expect(mockGet.mock.calls[0][1]).toEqual({ params: { brand_profile_id: "p1" } });
  expect(projects.map((p) => p.id)).toEqual(["s1", "s2"]);
});

test("the story plan posts to the stories router with the chain timeout", async () => {
  // ADR 0236: the plan is the stories router's one generation call —
  // the page's click makes it, and the answer is the saved project.
  await api.generateStoryPlan("s1", { story_type: "question_poll", frame_seconds: 5 });
  expect(mockPost.mock.calls[0][0]).toBe("/stories/projects/s1/plan");
  expect(mockPost.mock.calls[0][1]).toEqual({ story_type: "question_poll", frame_seconds: 5 });
  expect(mockPost.mock.calls[0][2]).toEqual({ timeout: 600000 });
});

test("a story render posts to the stories router's generate endpoint", async () => {
  // ADR 0236: one frame through the one render path — the payload is
  // the studio generation shape (model, resolution, the frame's own
  // seconds, the render intent key).
  await api.generateStory("s1", { model: "heygen-video-1", duration_seconds: 5, idempotency_key: "k1" });
  expect(mockPost.mock.calls[0][0]).toBe("/stories/projects/s1/generate");
  expect(mockPost.mock.calls[0][1]).toEqual({ model: "heygen-video-1", duration_seconds: 5, idempotency_key: "k1" });
});

test("the screen text suggestion posts the editor's current values", async () => {
  // ADR 0236: advisory like the cover suggestion — the editor's
  // current words ride along so the suggestion answers to them.
  await api.suggestStoryScreenText("s1", { screen_text: "Old text here", hook_line: "Hook.", script: "Script." });
  expect(mockPost.mock.calls[0][0]).toBe("/stories/projects/s1/screen-text-suggestion");
  expect(mockPost.mock.calls[0][1]).toEqual({ screen_text: "Old text here", hook_line: "Hook.", script: "Script." });
  expect(mockPost.mock.calls[0][2]).toEqual({ timeout: 600000 });
});

test("the story kit regenerate posts to the generation's story-kit path", async () => {
  // ADR 0236: the kit's regenerate mirrors the post kit's — a click on
  // the finished render's own kit endpoint, never the post kit's.
  await api.regenerateStoryKit("g1");
  expect(mockPost.mock.calls[0][0]).toBe("/generations/g1/story-kit/regenerate");
  expect(mockPost.mock.calls[0][2]).toEqual({ timeout: 300000 });
});

test("a small export saves in one request to the generation path", async () => {
  const blob = new Blob([new Uint8Array(100)]);
  const row = await api.saveDemoCtaExport("gen-1", blob, "demo-cta.mp4");
  expect(row).toEqual({ id: "saved-1" });
  expect(mockPost).toHaveBeenCalledTimes(1);
  const [url, form] = mockPost.mock.calls[0];
  expect(url).toBe("/generations/gen-1/demo-cta-result");
  expect(form.get("file")).toBeInstanceOf(Blob);
  expect(form.get("file").size).toBe(100);
  expect(form.get("file").name).toBe("demo-cta.mp4");
});

test("a standalone small export posts to the bare path", async () => {
  const blob = new Blob([new Uint8Array(100)]);
  await api.saveDemoCtaExport(null, blob, "demo-cta.mp4");
  expect(mockPost).toHaveBeenCalledTimes(1);
  expect(mockPost.mock.calls[0][0]).toBe("/demo-cta-result");
});

test("an export past 8 MB goes up in parts, then completes under one id", async () => {
  const bytes = new Uint8Array(DEMO_CTA_PART_BYTES + 10);
  bytes.fill(7);
  const blob = new Blob([bytes]);
  mockPost.mockResolvedValue({ data: { id: "saved-9" } });
  const row = await api.saveDemoCtaExport("gen-2", blob, "big.mp4");
  expect(row).toEqual({ id: "saved-9" });
  // Two parts plus the complete call, in order.
  expect(mockPost).toHaveBeenCalledTimes(3);
  const partCalls = mockPost.mock.calls.slice(0, 2);
  const ids = partCalls.map(([url]) => url.match(/^\/demo-cta-uploads\/(.+)\/parts$/)[1]);
  expect(ids[0]).toMatch(/^[0-9a-f-]{36}$/);
  expect(ids[1]).toBe(ids[0]);
  expect(partCalls[0][1].get("index")).toBe("0");
  expect(partCalls[0][1].get("total")).toBe("2");
  expect(partCalls[1][1].get("index")).toBe("1");
  expect(partCalls[1][1].get("total")).toBe("2");
  expect(partCalls[0][1].get("chunk").size).toBe(DEMO_CTA_PART_BYTES);
  expect(partCalls[1][1].get("chunk").size).toBe(10);
  const [completeUrl, completeBody] = mockPost.mock.calls[2];
  expect(completeUrl).toBe(`/demo-cta-uploads/${ids[0]}/complete`);
  expect(completeBody).toEqual({ generation_id: "gen-2", filename: "big.mp4", total: 2 });
});

test("a standalone large export completes with a null generation", async () => {
  const bytes = new Uint8Array(DEMO_CTA_PART_BYTES + 1);
  const blob = new Blob([bytes]);
  await api.saveDemoCtaExport(null, blob, "big.mp4");
  const completeBody = mockPost.mock.calls[mockPost.mock.calls.length - 1][1];
  expect(completeBody).toEqual({ generation_id: null, filename: "big.mp4", total: 2 });
});

// The 120s client default is ONE server-side model call's budget
// (ai_service._chat_json: timeout=120, attempts=2+). Every AI generation
// endpoint chains calls or retries inside one request, so on the default
// the browser aborted healthy work mid-flight and the founder met the raw
// "timeout of 120000ms exceeded". The long calls carry their own limit,
// sized to the chain behind them; ordinary calls keep the default.
describe("AI generation calls carry a timeout sized to their server chain", () => {
  const configOf = (callIndex = 0) => mockPost.mock.calls[callIndex][2];

  test("the plan pass and its chained forms get the chain limit", async () => {
    await api.generatePlan("p1");
    expect(configOf()).toEqual({ timeout: 600000 });
    mockPost.mockClear();
    await api.generatePlanAndStrategy("p1");
    expect(configOf()).toEqual({ timeout: 600000 });
    mockPost.mockClear();
    await api.suggestStrategyRefresh("p1");
    expect(configOf()).toEqual({ timeout: 600000 });
  });

  test("the strategy build retries three 120s attempts server-side, so it gets the chain limit", async () => {
    await api.generateStrategy("p1", {});
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 600000 }));
  });

  test("angle generation and its server-chained forms get the chain limit", async () => {
    await api.generateContentAngles("b1");
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 600000 }));
    mockPost.mockClear();
    await api.regenerateContentAngles("b1");
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 600000 }));
    mockPost.mockClear();
    await api.approveAppProfile("b1");
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 600000 }));
    mockPost.mockClear();
    await api.refreshAppProfile("b1");
    expect(configOf()).toEqual({ timeout: 600000 });
    mockPost.mockClear();
    await api.regenerateEverything("b1");
    expect(configOf()).toEqual({ timeout: 600000 });
  });

  test("the clearer-line rewrites get the chain limit", async () => {
    await api.rewriteHook("p1", "A hook.");
    expect(configOf()).toEqual({ timeout: 600000 });
    mockPost.mockClear();
    await api.rewriteLine("p1", { line: "A line." });
    expect(configOf()).toEqual({ timeout: 600000 });
  });

  test("single-call text generations get the single-call limit", async () => {
    await api.researchAppProfile({});
    expect(configOf()).toEqual({ timeout: 300000 });
    mockPost.mockClear();
    await api.generateAngleGoals("b1", "a1");
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 300000 }));
    mockPost.mockClear();
    await api.ensureObjectiveTemplates("b1", {});
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 300000 }));
    mockPost.mockClear();
    await api.generateOpeningMessages("b1");
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 300000 }));
    mockPost.mockClear();
    await api.refreshDirectionOptions("b1", { field: "location" });
    expect(configOf()).toEqual(expect.objectContaining({ timeout: 300000 }));
    mockPost.mockClear();
    await api.regeneratePostKit("g1");
    expect(configOf()).toEqual({ timeout: 300000 });
  });

  test("ordinary calls keep the client default — no override is sent", async () => {
    await api.markProjectReady("p1");
    expect(configOf()).toBeUndefined();
    mockPost.mockClear();
    // The render submit stays on the default too: its wait is the polling
    // progress bar with real position, not this request.
    await api.generateVideo("p1", {});
    expect(configOf()).toBeUndefined();
  });
});
