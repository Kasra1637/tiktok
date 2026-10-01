/**
 * Mounts every wizard step and the panels in a real DOM, to catch crashes that
 * a type-check and a build cannot.
 *
 * Why this exists: two live defects shipped with the whole gate green.
 * `GenerationPanel` listed `schedulePoll` in a `useEffect` dep array above its
 * `const` declaration, so evaluating the array threw a TDZ ReferenceError on
 * every mount — and because an ErrorBoundary wraps the app, that took down
 * every route. `HookContinuityPanel` called `resolveExtendRequest` and read
 * `extendBy`, neither of which exists, on the branch that renders while
 * extending toward a target. Neither is a type error: JSX goes through
 * `createElement`, and an undefined identifier inside a state-dependent branch
 * is still a valid module. `npm run build` lints and type-checks, and
 * `check-frontend-logic.cjs` evaluates pure helpers — neither one ever calls a
 * component. So this file does.
 *
 * It uses a real DOM (`jsdom`) and `createRoot` rather than
 * `renderToStaticMarkup`, because two of the branches that matter are
 * effect-driven: the panel loads its segments from the API before the coverage
 * warning can render, and server rendering never runs an effect, so a static
 * render would silently skip exactly the code that was broken.
 *
 * `api` is stubbed with fixtures shaped from the server's real responses (see
 * `_public_project` and `video_providers.capability`), so no network call is
 * made and every branch is reachable.
 *
 * Run: node scripts/check-render-smoke.cjs
 */
const fs = require("fs");
const path = require("path");
const babel = require("@babel/core");
const { JSDOM } = require("jsdom");

const SRC = path.resolve(__dirname, "..", "src");

// ---------------------------------------------------------------------------
// DOM, installed before React is required so it binds to a real document
// ---------------------------------------------------------------------------
const dom = new JSDOM("<!doctype html><html><body></body></html>", {
  url: "https://example.test/create",
  pretendToBeVisual: true,
});
global.window = dom.window;
global.document = dom.window.document;
global.navigator = dom.window.navigator;
global.HTMLElement = dom.window.HTMLElement;
global.SVGElement = dom.window.SVGElement;
global.Node = dom.window.Node;
global.Element = dom.window.Element;
global.Event = dom.window.Event;
global.MouseEvent = dom.window.MouseEvent;
global.getComputedStyle = dom.window.getComputedStyle;
global.requestAnimationFrame = (cb) => setTimeout(() => cb(Date.now()), 0);
global.cancelAnimationFrame = (id) => clearTimeout(id);
global.IS_REACT_ACT_ENVIRONMENT = true;
// Radix and the chart components measure on mount and would throw on undefined.
dom.window.matchMedia = dom.window.matchMedia || (() => ({
  matches: false,
  addEventListener: () => {},
  removeEventListener: () => {},
  addListener: () => {},
  removeListener: () => {},
}));
global.matchMedia = dom.window.matchMedia;
class NoopObserver {
  observe() {}
  unobserve() {}
  disconnect() {}
  takeRecords() { return []; }
}
global.ResizeObserver = global.ResizeObserver || NoopObserver;
global.IntersectionObserver = global.IntersectionObserver || NoopObserver;
dom.window.ResizeObserver = dom.window.ResizeObserver || NoopObserver;
dom.window.IntersectionObserver = dom.window.IntersectionObserver || NoopObserver;

const React = require("react");
const { act } = require("react");
const { createRoot } = require("react-dom/client");

// ---------------------------------------------------------------------------
// Fixtures
// ---------------------------------------------------------------------------
// Shape from list_video_models() (server.py): the row's identity is `key`, and
// `id` is deliberately stripped, so a fixture carrying `id` instead makes every
// <option key={m.key}> undefined and renders a misleading key warning.
const CAPABILITY = {
  key: "minimax-h3",
  name: "MiniMax H3",
  max_duration: 15,
  min_duration: 5,
  resolution: "2K",
  aspect_ratio: "9:16",
  supports_references: true,
  supports_native_audio: true,
};

const STRATEGY = {
  hook_line: "You do not have a focus problem.",
  hook_concept: "Name the thing they already know.",
  hook_promise: "A reason to keep watching.",
  strategy_summary: "Open on the misdiagnosis, then correct it.",
  audience_problem: "Too many things to hold at once.",
  emotional_triggers: ["recognition", "relief"],
  messaging_pillars: ["one thing at a time"],
  primary_feature: "Task timer",
  desired_outcome: "A finished day.",
  differentiation_beat: "Others track time; this finishes tasks.",
  cta_strategy: "Name the free trial.",
  scene: "Desk, morning light, one task visible.",
  performance: "Direct to camera, unhurried.",
  segments: [
    { segment_index: 0, goal: "hook", action: "look up", script: "You do not have a focus problem.", seconds: 5 },
    { segment_index: 1, goal: "problem", action: "count on fingers", script: "You have too many lists.", seconds: 6 },
    { segment_index: 2, goal: "fix", action: "tap the timer", script: "So make it one task.", seconds: 7 },
    { segment_index: 3, goal: "cta", action: "point at screen", script: "Try it free.", seconds: 4 },
  ],
  continuity_contract: {
    established: ["desk", "morning light"],
    must_not_change: ["shirt", "framing"],
    do_not_repeat: ["the opening line"],
  },
  // Stamped on the project by generate_project_strategy, read by
  // plannedCoverage() to say how many more beats the finite plan can produce.
  max_planned_index: 3,
  objective: "address_user_problem",
};

const SEGMENT = {
  id: "gen-1",
  segment_index: 0,
  status: "completed",
  duration: 5,
  trim_to_seconds: 0,
  approved: true,
  video_url: "/media/gen-1.mp4",
  r2_url: null,
  cost_usd: 0.42,
  retryable: true,
  continuity: {
    guarantee: "frame_exact",
    use_frame: true,
    use_clip_reference: false,
    use_identity_reference: true,
    dropped_anchors: [],
  },
};

// The key is `asset_id`, not `id`: AttachmentRow slices attachment.asset_id for
// the label, so a fixture using `id` throws on the Assets step.
const ASSETS = [
  { asset_id: "a1", kind: "character_reference", label: "face.jpg", status: "ready" },
];

// template_id and content_angle_id are set because canGenerate is
// `profileId && templateId`: without them every step correctly refuses to open
// the paid path, which would make the "paid controls exist" assertions prove
// nothing.
const BASE_PROJECT = {
  id: "p1",
  brand_profile_id: "b1",
  content_angle_id: "a1",
  template_id: "t1",
  objective: "address_user_problem",
  status: "draft",
  script_version: 0,
  duration_seconds: 20,
  extend_intent: true,
  assets: ASSETS,
  safety_report: { passed: true, blocking: [], unverified: [] },
  strategy: null,
  script: "",
  hook_line: "",
};

const PROJECT_WITH_STRATEGY = {
  ...BASE_PROJECT,
  status: "ready_for_generation",
  script_version: 1,
  strategy: STRATEGY,
  hook_line: STRATEGY.hook_line,
  script: "You do not have a focus problem.",
  cta: "Try it free",
  feature_emphasis: "Task timer",
  visual_direction: "Close, 9:16, desk.",
  beat_timeline: [{ start: 0, end: 5, beat: "hook" }],
  overlays: [],
  voice_direction: "Calm.",
  sound_direction: "Room tone.",
  tone: "calm",
};

const PROFILE = {
  id: "b1",
  brand_name: "Taskly",
  app_category: "productivity",
  status: "approved",
  target_audience: "people with too many lists",
};

const TEMPLATE = {
  id: "t1",
  name: "Name the misdiagnosis",
  category: "pain-point-question",
  objective: "address_user_problem",
  opening_structure: "Open by naming what they think is wrong.",
  continuation_structure: "Then correct it.",
  cta_pattern: "Try it free.",
  visual_style: "Talking head.",
  camera_pacing: "Steady.",
  content_slots: { app_feature: "Task timer", cta: "Try it free" },
  required_assets: ["character_reference"],
  default_duration: 20,
  hook_seconds: 5,
  is_usable: true,
};

const ANGLE = {
  id: "a1",
  kind: "problem",
  label: "Too many lists",
  user_problem: "Nothing gets finished.",
  target_audience: "busy professionals",
};

const apiStub = {
  getStudioVideoModels: async () => ({ default: "minimax-h3", models: [CAPABILITY] }),
  getGenerations: async () => ({ generations: [SEGMENT] }),
  pollGeneration: async () => SEGMENT,
  getTemplates: async () => ({ templates: [TEMPLATE] }),
  getTemplateFacets: async () => ({
    objectives: ["address_user_problem", "demonstrate_feature"],
    supported_durations: [10, 15, 20, 30],
    // Shaped like the real server response, which derives the per-duration
    // render count from the default studio model's single-pass ceiling
    // (CAPABILITY.max_duration above). 20s and 30s are two paid renders.
    duration_segments: { 10: 1, 15: 1, 20: 2, 30: 2 },
  }),
  getAppProfiles: async () => ({ profiles: [PROFILE] }),
  getContentAngles: async () => ({ angles: [ANGLE] }),
  getTemplateRecommendations: async () => ({
    recommendations: [{
      template: { ...TEMPLATE, brand_profile_id: "b1" },
      score: 9.5,
      why_it_fits: ["Tailored for Taskly", "Matches this angle"],
      limitations: [],
    }],
  }),
  ensureObjectiveTemplates: async () => ({
    templates: [TEMPLATE],
    generated: false,
    objective: "address_user_problem",
    error: null,
  }),
  getStudioProject: async () => PROJECT_WITH_STRATEGY,
  createStudioProject: async () => PROJECT_WITH_STRATEGY,
  updateStudioProject: async () => PROJECT_WITH_STRATEGY,
  detachAsset: async () => BASE_PROJECT,
  getProjects: async () => ({ projects: [] }),
  getAssets: async () => ({ assets: [] }),
  uploadAsset: async () => ({ asset: null }),
  generatePlan: async () => PROJECT_WITH_STRATEGY,
  generateStrategy: async () => PROJECT_WITH_STRATEGY,
  generateHook: async () => SEGMENT,
  approveGeneration: async () => SEGMENT,
  extendGeneration: async () => SEGMENT,
  assembleChain: async () => ({ generation: SEGMENT, skipped: [] }),
  generateVideo: async () => SEGMENT,
  retryGeneration: async () => SEGMENT,
  composeOverlays: async () => ({ composition: null }),
  markProjectReady: async () => PROJECT_WITH_STRATEGY,
  setProjectExtendIntent: async () => PROJECT_WITH_STRATEGY,
  recordSignal: () => {},
};

// ---------------------------------------------------------------------------
// Transpile + stub loader
// ---------------------------------------------------------------------------
const cache = new Map();

// A cached URLSearchParams per query string, so `useSearchParams()` is stable
// across renders. CreateVideo's mount effect depends on `params`, so handing it
// a new object each call spins the effect in an endless fetch loop.
const searchParamCache = new Map();
function searchParams() {
  const query = global.__SMOKE_PARAMS || "";
  if (!searchParamCache.has(query)) searchParamCache.set(query, new URLSearchParams(query));
  return searchParamCache.get(query);
}

function resolveFile(base) {
  if (fs.existsSync(base) && fs.statSync(base).isFile()) return base;
  for (const ext of [".js", ".jsx", "/index.js", "/index.jsx"]) {
    const candidate = base + ext;
    if (fs.existsSync(candidate) && fs.statSync(candidate).isFile()) return candidate;
  }
  throw new Error(`no module file for ${base}`);
}

function load(relPath) {
  const abs = resolveFile(path.join(SRC, relPath));
  if (cache.has(abs)) {
    const hit = cache.get(abs);
    // A module that threw while loading is remembered as a failure rather than
    // left to hand a half-built exports object to the next caller, which would
    // report a nonsense error ("undefined has no property jsxs") and hide the
    // real cause.
    if (hit.error) throw hit.error;
    return hit.exports;
  }
  const source = fs.readFileSync(abs, "utf8");
  const { code } = babel.transformSync(source, {
    filename: abs,
    babelrc: false,
    configFile: false,
    presets: [
      [require.resolve("@babel/preset-env"), { targets: { node: "current" } }],
      [require.resolve("@babel/preset-react"), { runtime: "automatic" }],
    ],
  });
  const entry = { exports: {}, error: null };
  cache.set(abs, entry);

  const requireShim = (spec) => {
    if (spec === "react" || spec === "react-dom" || spec === "react-dom/client") return require(spec);
    if (spec === "react-router-dom") {
      // useSearchParams must return a STABLE params object per query string.
      // CreateVideo's mount effect depends on `params`, so a fresh object on
      // every call re-runs the effect forever and the page never settles.
      return {
        __esModule: true,
        Link: ({ children }) => React.createElement("a", { href: "#" }, children),
        useNavigate: () => () => {},
        useSearchParams: () => [searchParams(), () => {}],
        // The embedded AssetLibrary on the Assets step reads the route, so a
        // deep link that lands there needs these to exist.
        useParams: () => ({}),
        useLocation: () => ({ pathname: "/create", search: searchParams().toString() }),
      };
    }
    if (spec === "sonner") return { toast: { success: () => {}, error: () => {} } };
    if (spec.endsWith("lib/api")) {
      return { api: apiStub, getErrorMessage: () => "error", mediaUrl: (p) => p };
    }
    if (spec.endsWith("lib/feedback")) {
      return { recordSignal: () => {}, classifyScriptEdit: () => ({ kind: "other" }) };
    }
    // The webpack alias in craco.config.js: "@" is src/.
    if (spec.startsWith("@/")) return load(spec.slice(2));
    if (spec.startsWith(".")) {
      return load(path.relative(SRC, resolveFile(path.resolve(path.dirname(abs), spec))));
    }
    return require(spec);
  };

  try {
    // eslint-disable-next-line no-new-func
    new Function("module", "exports", "require", code)(entry, entry.exports, requireShim);
  } catch (err) {
    entry.error = err;
    throw err;
  }
  return entry.exports;
}

// ---------------------------------------------------------------------------
// Mount helper
// ---------------------------------------------------------------------------
const failures = [];
let checks = 0;
let container = null;
const roots = [];

/**
 * Each check gets a fresh container: state from one mount must not be able to
 * make the next assertion pass.
 *
 * `fn` is awaited, and every check is awaited in turn. This is load-bearing, not
 * tidiness: an un-awaited async check reports PASS synchronously and its
 * rejection escapes as an unhandled promise, so a check whose only assertion is
 * inside an async body would silently pass. That is how a reintroduced TDZ
 * crash in GenerationPanel "passed" this file.
 */
async function check(label, fn) {
  checks += 1;
  const container = dom.window.document.createElement("div");
  dom.window.document.body.appendChild(container);
  const root = createRoot(container);
  roots.push(root);
  const ctx = { root, container, text: () => container.textContent || "" };
  try {
    await fn(ctx);
    console.log(`  [PASS] ${label}`);
  } catch (err) {
    console.log(`  [FAIL] ${label}`);
    console.log(`         ${err && err.message ? err.message : String(err)}`);
    if (process.env.SMOKE_TRACE) console.log(err && err.stack ? err.stack : "");
    failures.push(label);
  }
}

function mount(Component, props) {
  return async (ctx) => {
    await act(async () => {
      ctx.root.render(React.createElement(Component, props));
    });
    // Two passes: the first mount fires the data-loading effects, the second
    // commits the state they set. Branch assertions read the committed DOM.
    await act(async () => {});
  };
}

function expectText(ctx, needle, why) {
  if (!ctx.text().includes(needle)) {
    throw new Error(`${why || "expected text not found"}: ${JSON.stringify(needle)}`);
  }
}

function expectAbsent(ctx, needle, why) {
  if (ctx.text().includes(needle)) {
    throw new Error(`${why || "unexpected text present"}: ${JSON.stringify(needle)}`);
  }
}

/**
 * Asserts two string lists are within `tolerance` characters per row.
 *
 * Used for the landing page's problem/solution bullets. Those two cards sit
 * side by side, so a row that runs long wraps to a second line on one side
 * only and makes that side look busier than the other. Nothing in the build or
 * the type-check can see it, and the copy is exactly the kind that gets edited
 * one line at a time — so the balance has to be asserted or it silently rots.
 */
function expectBalanced(left, right, tolerance, label) {
  if (left.length !== right.length) {
    throw new Error(
      `${label}: expected ${left.length} rows, got ${left.length} and ${right.length}`
    );
  }
  for (let i = 0; i < left.length; i += 1) {
    const delta = Math.abs(left[i].length - right[i].length);
    if (delta > tolerance) {
      throw new Error(
        `${label}: row ${i + 1} is ${delta} chars apart (tolerance ${tolerance})\n` +
          `        without (${left[i].length}): ${JSON.stringify(left[i])}\n` +
          `        with    (${right[i].length}): ${JSON.stringify(right[i])}`
      );
    }
  }
}

console.log("Mounting every wizard step and panel...");

const { GenerationPanel } = load("components/GenerationPanel.jsx");
const { HookContinuityPanel } = load("components/HookContinuityPanel.jsx");
const CreateVideo = load("pages/CreateVideo.jsx").default;

// The shipped order, in the order the founder walks it. Asserted as a whole
// sequence rather than a set: the point of the reorder is that the free, claim-
// checked plan comes before the step that spends money, and a set comparison
// would pass just as happily if the hook went back to fourth.
const STEP_LABELS = [
  "App Profile",
  "Audience & goal",
  "Hook template",
  "Assets",
  "Creative plan",
  "Review",
  "Influencer hook",
];

const stepSource = fs.readFileSync(path.join(SRC, "pages", "CreateVideo.jsx"), "utf8");

async function main() {
  // -------------------------------------------------------------------------
  // The crash that took the whole app down: a dep array read above its const.
  // -------------------------------------------------------------------------
  await check("GenerationPanel mounts", mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY }));

  await check("GenerationPanel mounts with no project", mount(GenerationPanel, { project: null }));

  await check("GenerationPanel shows the completed generation", async (ctx) => {
    await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    expectText(ctx, "Completed", "the segment status did not render");
    expectText(ctx, "Download MP4", "the download control did not render");
  });

  await check("GenerationPanel blocks generation before the project is ready", async (ctx) => {
    // No generations yet: the ready gate only shows when nothing has been
    // produced, so a fixture that still returns a segment proves nothing.
    await withApi({ getGenerations: async () => ({ generations: [] }) }, () =>
      mount(GenerationPanel, { project: { ...BASE_PROJECT } })(ctx)
    );
    expectText(ctx, "Mark the project ready for generation", "the ready gate did not render");
  });

  // -------------------------------------------------------------------------
  // The undefined-symbol crash, on the branch that renders while extending
  // toward a target — the panel's main path, and effect-driven, so a static
  // render would skip the code that was broken.
  // -------------------------------------------------------------------------
  await check("HookContinuityPanel renders the extend-coverage warning", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    // Guarded by extendIntent && completedSegments.length && targetTotal &&
    // plannedCoverage !== null && remainingToTarget > 0. Reaching it proves the
    // panel loaded its segments, read the plan, and resolved the next lock.
    expectText(ctx, "The strategy plans", "the coverage warning did not render");
    expectText(ctx, "s of", "the running total did not render");
  });

  await check("HookContinuityPanel reports the target as reached", async (ctx) => {
    await mount(HookContinuityPanel, {
      project: { ...PROJECT_WITH_STRATEGY, duration_seconds: 5 },
    })(ctx);
    expectText(ctx, "Target reached", "the reached-target state did not render");
  });

  await check("HookContinuityPanel mounts with no strategy", mount(HookContinuityPanel, { project: BASE_PROJECT }));

  await check("HookContinuityPanel surfaces a blocking claim", async (ctx) => {
    await mount(HookContinuityPanel, {
      project: {
        ...PROJECT_WITH_STRATEGY,
        // The panel filters on `b.claim`, so the fixture has to use that key.
        safety_report: { passed: false, blocking: [{ claim: "cures anxiety" }], unverified: [] },
      },
    })(ctx);
    expectText(ctx, "Prohibited claim present", "the claim block did not render");
    expectText(ctx, "cures anxiety", "the blocking claim was not named");
  });

  await check("HookContinuityPanel warns when no character reference is attached", async (ctx) => {
    await mount(HookContinuityPanel, {
      project: { ...PROJECT_WITH_STRATEGY, assets: [] },
    })(ctx);
    expectText(ctx, "No character reference", "the missing-face warning did not render");
  });

  await check("HookContinuityPanel shows the locked hook length from the plan", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    // The strategy plans segment 0 at 5s, the provider floor, so it renders
    // natively with no trim.
    expectText(ctx, "5s", "the locked hook length did not render");
  });

  // -------------------------------------------------------------------------
  // The wizard itself, step by step. Every step is a free jump by design, so
  // the later steps are reached by clicking the nav the founder would click,
  // with no state injected.
  // -------------------------------------------------------------------------
  // Step 0 is the empty state: with an approved profile preselected the wizard
  // advances past it on mount by design, so its own branch needs a profile list
  // with nothing approved in it.
  await check("wizard renders step: App Profile", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await withApi({ getAppProfiles: async () => ({ profiles: [] }) }, () =>
      mount(CreateVideo, {})(ctx)
    );
    expectText(ctx, "Which app are you promoting?", "step 0 did not render its heading");
    expectText(ctx, "No approved App Profile", "step 0 did not render its empty state");
  });

  for (let index = 1; index < STEP_LABELS.length; index += 1) {
    const label = STEP_LABELS[index];
    await check(`wizard renders step: ${label}`, async (ctx) => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, label);
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      // A renamed or dropped step fails here too, so the nav and the rendered
      // step cannot drift apart silently.
      if (!stepSource.includes(`label: "${label}"`)) {
        throw new Error(`step ${JSON.stringify(label)} is no longer in the STEPS list`);
      }
      if (!ctx.text().trim()) throw new Error("the page rendered nothing");
    });
  }

  // Nothing that costs money may render before the plan has been read. This is
  // the reorder's whole point, and it is invisible to a type-check: both panels
  // are still imported and still reachable, just on a later step.
  await check("no paid control renders before the plan step", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    for (const label of ["App Profile", "Audience & goal", "Hook template", "Assets", "Creative plan"]) {
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, label);
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const text = ctx.text();
      for (const paid of ["Generate video", "Generate the 5s hook", "Build the app-specific strategy"]) {
        if (text.includes(paid)) {
          throw new Error(`step ${JSON.stringify(label)} renders a paid control: ${JSON.stringify(paid)}`);
        }
      }
    }
  });

  await check("the hook step holds the paid controls once a plan exists", async (ctx) => {
    // A plan reviewed, no strategy yet: the state the reorder puts the founder
    // in when they arrive here. Deep-linked so the wizard has that draft.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy: null,
            strategy_version: 0,
          }),
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          const pill = stepPill(ctx, "Influencer hook");
          await act(async () => {
            pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      );
      if (!ctx.text().includes("Build the app-specific strategy")) {
        throw new Error("the hook step no longer offers the strategy button");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("the hook step refuses to spend without an approved plan", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      // A draft that exists but has no plan: the strategy, the hook render and
      // the one-pass generation must all stay out of reach.
      await withApi(
        { getStudioProject: async () => ({ ...BASE_PROJECT, script_version: 0, script: "" }) },
        async () => {
          await mount(CreateVideo, {})(ctx);
          const pill = stepPill(ctx, "Influencer hook");
          await act(async () => {
            pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    const text = ctx.text();
    if (!text.includes("no plan yet")) {
      throw new Error(
        `the hook step does not explain that a plan comes first; it rendered: ${JSON.stringify(
          text.slice(300, 800)
        )}`
      );
    }
    for (const paid of ["Build the app-specific strategy", "Generate the 5s hook", "Generate video"]) {
      if (text.includes(paid)) {
        throw new Error(`the hook step offers ${JSON.stringify(paid)} with no approved plan`);
      }
    }
  });

  await check("wizard deep-links to a drafted project and lands on the right step", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      // A draft with a plan goes to Review, so the plan's own field is the proof.
      expectText(ctx, "Hook line", "the deep link did not reach the plan's review fields");
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  // Tailoring only fires once an objective exists, so this drives the real
  // order: pick the goal, then the tailored request runs and its attached error
  // has to appear on the template step.
  // Length is chosen on the Audience & goal step and consumed by the plan
  // step, so it must not be an editable control on Review: the beat timeline is
  // built for the length the plan was generated at and beats are clamped to it,
  // so changing the number there leaves a timeline that no longer adds up.
  await check("Review shows the length but does not offer editing it", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, "Review");
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const text = ctx.text();
      if (!text.includes("Total video length")) {
        throw new Error("Review no longer states the total length");
      }
      if (!text.includes("written to this length")) {
        throw new Error("Review does not explain that the timeline is tied to this length");
      }
      // The stale-timeline affordance: an editable length select with a
      // "regenerating the plan will use Ns" note is what has to be gone.
      if (text.includes("Regenerating the plan will use")) {
        throw new Error("Review still offers an editable length that invalidates the beat timeline");
      }
      const durationSelect = [...ctx.container.querySelectorAll("select")]
        .find((s) => s.id === "review-duration");
      if (durationSelect) {
        throw new Error("Review still renders an editable total-length control");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("the length selector lives on the step before the plan", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = stepPill(ctx, "Audience & goal");
    await act(async () => {
      pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {});
    const select = ctx.container.querySelector("select#duration");
    if (!select) throw new Error("the total length is no longer chosen before the plan");
    if (!ctx.text().includes("Total video length")) {
      throw new Error("the length control has no label");
    }
  });

  // Every segment past the first is a separate paid render, and no
  // studio-eligible model covers 20s in one pass. A 20s default therefore
  // spends two renders before the founder has learned the flow -- and worse,
  // it is the length the plan's beat timeline is written to by default. The
  // option label and the helper both have to say so, because the alternative
  // is the founder discovering the segment count at the extend button.
  await check("a length that costs more than one render says so up front", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = stepPill(ctx, "Audience & goal");
    await act(async () => {
      pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {});
    const select = ctx.container.querySelector("select#duration");
    if (!select) throw new Error("no length control to read");

    const options = [...select.querySelectorAll("option")].map((o) => o.textContent);
    // The seeded facets stub reports 15s as the single-pass ceiling, so 20s
    // and 30s are two segments and 10s/15s are not.
    const multi = options.filter((o) => /segments/.test(o));
    const single = options.filter((o) => /one pass/.test(o));
    if (multi.length === 0) throw new Error("no option states a multi-pass segment count");
    if (single.length === 0) throw new Error("no option distinguishes a single-pass length");
    if (multi.some((o) => !/\d+ segments/.test(o))) {
      throw new Error("a multi-pass option does not state how many: " + JSON.stringify(multi));
    }
    // And the selected one is explained, not just listed.
    await selectOption(ctx, select, "20");
    if (!/segments/.test(ctx.text())) {
      throw new Error("picking a multi-pass length says nothing about the extra renders");
    }
    if (!/paid render/.test(ctx.text())) {
      throw new Error("the multi-pass note never says the extra segments cost money");
    }
  });

  // The seeded default must be a length the default model can actually do in
  // one pass. A default that is impossible to finish in a single render is the
  // single most expensive default the product can ship.
  await check("a fresh wizard starts on a single-pass length", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = stepPill(ctx, "Audience & goal");
    await act(async () => {
      pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {});
    const select = ctx.container.querySelector("select#duration");
    const chosen = String(select.value);
    if (chosen !== "10") {
      throw new Error(
        `a new wizard starts at ${chosen}s; expected 10s, the shortest single-pass length`
      );
    }
  });

  // The recommender reorders on this app's recorded feedback, so its top pick
  // is meaningful. Preselecting it means the founder can accept the suggestion
  // instead of re-deriving it, and means the feedback adjustment is not thrown
  // away by the act of opening the step.
  // Two templates, so the order can flip between loads below.
  const ORDERED_TEMPLATES = [
    { ...TEMPLATE, id: "t-top", name: "Top Pick" },
    { ...TEMPLATE, id: "t-second", name: "Second" },
  ];

  await check("the top recommendation is preselected when the founder has not chosen", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    // getTemplates must list them too: the selected-template card is rendered
    // from the full library, not from the recommendation rows, so a
    // recommendation for a template the library does not contain preselects an
    // id that resolves to nothing.
    await withApi(
      {
        getTemplates: async () => ({ templates: ORDERED_TEMPLATES }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            { template: ORDERED_TEMPLATES[0], score: 9, why_it_fits: ["fits"], limitations: [] },
            { template: ORDERED_TEMPLATES[1], score: 5, why_it_fits: ["ok"], limitations: [] },
          ],
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        const pill = stepPill(ctx, "Hook template");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
      }
    );
    const text = ctx.text();
    if (!text.includes("Top Pick")) {
      throw new Error("the top recommendation is not preselected");
    }
    if (!text.includes("Suggested")) {
      throw new Error("a preselected template is not labelled as a suggestion");
    }
  });

  // The important half: a reload must not move a pick the founder made. The
  // recommender's order depends on recorded feedback, so a re-rank between
  // visits would otherwise silently replace a deliberate choice.
  await check("reloading recommendations never replaces a hand-picked template", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    const order = { call: 0 };
    await withApi(
      {
        getTemplates: async () => ({ templates: ORDERED_TEMPLATES }),
        getTemplateRecommendations: async () => {
          order.call += 1;
          // The founder picks the one ranked second, then the order flips.
          const rows = order.call === 1
            ? [
                { template: ORDERED_TEMPLATES[0], score: 9, why_it_fits: [], limitations: [] },
                { template: ORDERED_TEMPLATES[1], score: 5, why_it_fits: [], limitations: [] },
              ]
            : [
                { template: ORDERED_TEMPLATES[1], score: 9, why_it_fits: [], limitations: [] },
                { template: ORDERED_TEMPLATES[0], score: 5, why_it_fits: [], limitations: [] },
              ];
          return { recommendations: rows };
        },
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        let pill = stepPill(ctx, "Hook template");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});

        // Click the second card by its rendered name.
        const second = [...ctx.container.querySelectorAll("[role=button]")]
          .find((el) => (el.textContent || "").includes("Second"));
        if (!second) throw new Error("the second recommendation is not clickable");
        await act(async () => {
          second.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});

        // Leave and come back, which re-runs the load with a flipped order.
        pill = stepPill(ctx, "Assets");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
        pill = stepPill(ctx, "Hook template");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
      }
    );
    const text = ctx.text();
    // The pick held: the card for the one clicked is the selected one, and it
    // is no longer labelled as a suggestion even though it now ranks second.
    if (text.includes("Suggested")) {
      throw new Error("a hand-picked template is still labelled as a suggestion");
    }
    if (!text.includes("Second")) {
      throw new Error("the hand-picked template is not the one shown after the reload");
    }
  });

  await check("wizard surfaces the tailored-template error instead of failing silently", async (ctx) => {
    global.__SMOKE_PARAMS = "";
      // The override has to span the whole check, not just the mount: the
    // tailored request does not fire until the objective is chosen and the
    // template step opens, which is after mount.
    await withApi(
      {
        ensureObjectiveTemplates: async () => ({
          templates: [],
          generated: false,
          objective: "address_user_problem",
          error: "The model is busy. Your curated picks still work.",
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await selectOption(ctx, selectLabelled(ctx, "objective"), "address_user_problem");
        const pill = stepPill(ctx, "Hook template");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
      }
    );
    expectText(ctx, "still work", "the attached generation error was not surfaced");
  });

  await check("wizard requests tailored templates for the chosen objective", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    const seen = [];
    await withApi(
      {
        ensureObjectiveTemplates: async (profileId, payload) => {
          seen.push({ profileId, payload });
          return { templates: [], generated: false, objective: payload.objective, error: null };
        },
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await selectOption(ctx, selectLabelled(ctx, "objective"), "address_user_problem");
        const pill = stepPill(ctx, "Hook template");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
      }
    );
    if (seen.length === 0) throw new Error("choosing an objective made no tailored-template request");
    if (seen[0].payload.objective !== "address_user_problem") {
      throw new Error(`wrong objective sent: ${JSON.stringify(seen[0].payload.objective)}`);
    }
    if (seen[0].profileId !== "b1") {
      throw new Error(`wrong profile sent: ${JSON.stringify(seen[0].profileId)}`);
    }
  });

  // -------------------------------------------------------------------------
  // Landing page
  // -------------------------------------------------------------------------
  // The landing page advertises capabilities, so a claim that quietly stops
  // being true is the same class of defect as a panel that stops rendering —
  // only slower, and it survives every other gate because nothing about the
  // copy is load-bearing. Each string below was live copy at one point and none
  // of them is true of the product now.
  console.log("");
  console.log("Mounting the landing page...");

  const Landing = load("pages/Landing.jsx").default;

  await check("Landing mounts", mount(Landing));

  await check("Landing claims nothing the product cannot keep", async (ctx) => {
    // Each check gets its own container, so the page has to be mounted here
    // rather than reusing the mount above. Without this the assertions below
    // read an empty document and pass without testing anything.
    await mount(Landing)(ctx);
    // Pricing left the App Profile, and its claim check was deleted outright.
    expectAbsent(ctx, "pricing", "pricing is not in the product any more");
    expectAbsent(ctx, "prices your profile", "the price check was deleted");
    // There is no hook-length selector: the plan computes one and locks it.
    expectAbsent(ctx, "Hooks run 2 to 6", "no hook length is chosen by hand");
    // The template library redirects to /create and has no favourite toggle.
    expectAbsent(ctx, "Favourite", "no favourite UI exists");
    // Rejection is recorded on swap; there is no reject control anywhere.
    expectAbsent(ctx, "Reject a template", "there is no reject button");
    // Trend aggregates now steer the strategy prompt, not only the research tab.
    expectAbsent(ctx, "Trend Research tab only", "trend data reaches generation now");

    // Frame continuity. The only studio-eligible provider reports
    // supports_last_frame: False, so video_providers.continuity_plan forces
    // guarantee "text_only" and server.py nulls the seam frame — every
    // extension really is held to a written scene description. The app says so
    // honestly in GUARANTEE_COPY; these two landing strings used to promise the
    // opposite, and one of them sits in FLOW_STEPS, a screen above PIPELINE, so
    // correcting only the pipeline block would have left the lie on screen.
    expectAbsent(ctx, "last frame becomes the next first frame", "the seam frame is not sent");
    expectAbsent(ctx, "picks up from the last frame", "the seam frame is not sent");
    // The honest replacement has to actually be there, or a future edit could
    // satisfy the two checks above by deleting the claim outright.
    expectText(ctx, "written description of the scene", "continuity is disclosed, not hidden");
  });

  // An onboarding tour is invisible when its targets are missing, because
  // TourOverlay advances silently past a target it cannot find — so a tour
  // pointing at a page that no longer exists passes every other gate, shows a
  // first-timer nothing, and still marks itself seen. Two real tours were in
  // exactly that state: /history served GenerationHistory while the history
  // tour's testids lived in History.jsx at /legacy-history, and /bookmarks
  // mapped to a tour id that is not a key in TOURS at all.
  //
  // So every target is resolved against the real source files, here. A renamed
  // testid or a moved page now fails the gate instead of quietly emptying the
  // tour.
  await check("every onboarding tour step points at a real element", async (ctx) => {
    const { TOURS, getTourIdForPath } = load("lib/onboarding/tours.js");
    const missing = [];

    // The route a tour fires on, and the page component that route serves.
    // Scoping matters: the history tour's testids all still exist in
    // History.jsx, which is why the bug survived so long — they are real, on a
    // page that /history stopped serving. A corpus-wide search would call them
    // fine.
    const ROUTE_PAGE = {
      "/discover": "pages/NicheFeed.jsx",
      "/bookmarks": "pages/HookTemplates.jsx",
      "/brand": "pages/BrandSetup.jsx",
      "/history": "pages/GenerationHistory.jsx",
    };
    const firstPath = (tourId) =>
      ["/discover", "/bookmarks", "/brand", "/history"].find(
        (p) => getTourIdForPath(p) === tourId
      );

    // The page plus everything it imports, so a target owned by a child
    // component (HookBreakdown owns hook-section-*, Filmstrip owns
    // filmstrip-frame-button-*) still resolves.
    const reachableFrom = (rel, seen = new Set()) => {
      if (seen.has(rel)) return "";
      seen.add(rel);
      const abs = resolveFile(path.join(SRC, rel));
      const src = fs.readFileSync(abs, "utf8");
      let out = src;
      for (const m of src.matchAll(/from\s+"(\.[^"]+)"/g)) {
        const target = path.relative(SRC, resolveFile(path.resolve(path.dirname(abs), m[1])));
        out += "\n" + reachableFrom(target, seen);
      }
      return out;
    };

    for (const [tourId, tour] of Object.entries(TOURS)) {
      const p = firstPath(tourId);
      const rel = p && ROUTE_PAGE[p];
      if (!rel) continue; // no known route serves this tour
      const corpus = reachableFrom(rel);

      for (const step of tour.steps) {
        // A null target is the intended "whole page" step, not a failure.
        if (!step.target) continue;
        // A step may list alternates as "a, b". Every one has to resolve:
        // TourOverlay skips an unresolved target, so a step whose only live
        // selector is the second one silently degrades to nothing.
        for (const selector of step.target.split(",")) {
          const trimmed = selector.trim();
          if (!trimmed) continue;
          // Prefix selectors ([data-testid^="x-"]) are legal: resolve the
          // prefix against the interpolated form too, since that is how the
          // component declares it.
          const exact = (trimmed.match(/data-testid="([^"]+)"/) || [])[1];
          const prefix = (trimmed.match(/data-testid\^="([^"]+)"/) || [])[1];
          if (exact) {
            // A testid built with a template literal appears as
            // `hook-section-${key}` in source, not as the final string.
            const asTemplate = exact.replace(/[a-z_]+$/, "");
            const declared =
              corpus.includes(`"${exact}"`) ||
              (asTemplate && corpus.includes("`" + asTemplate + "${"));
            if (!declared) {
              missing.push(`${tourId}: ${rel} (served at ${p}) has no data-testid="${exact}"`);
            }
          } else if (prefix) {
            if (!corpus.includes("`" + prefix + "${") && !corpus.includes(`"${prefix}`)) {
              missing.push(`${tourId}: ${rel} (served at ${p}) declares no testid starting "${prefix}"`);
            }
          } else {
            missing.push(`${tourId}: unreadable target (${trimmed})`);
          }
        }
      }
    }
    if (missing.length) throw new Error(missing.join("\n        "));
  });

  // The path-to-tour map has to name tours that exist, or the provider bails
  // before opening anything while still having marked the tour seen.
  await check("every routable path maps to a tour that exists", async (ctx) => {
    const { TOURS, getTourIdForPath } = load("lib/onboarding/tours.js");
    const paths = ["/discover", "/analysis/x", "/bookmarks", "/brand", "/history"];
    const broken = paths
      .map((p) => [p, getTourIdForPath(p)])
      .filter(([, id]) => id !== null && !TOURS[id])
      .map(([p, id]) => `${p} -> "${id}", which is not a key in TOURS`);
    if (broken.length) throw new Error(broken.join("\n        "));
  });

  // The two cards are one grid row. Bullets that are not length-matched make
  // the longer side wrap and gain a line the other side does not, which is a
  // visible asymmetry inside the section whose whole job is the contrast.
  await check("the problem/solution bullets are length-matched", async (ctx) => {
    await mount(Landing)(ctx);
    const row = /lucide-x[\s\S]*?lucide-check/;
    const html = ctx.container.innerHTML;
    const start = html.search(row);
    if (start === -1) throw new Error("found no X/check rows to compare");
    const scope = html.slice(start);
    const text = (icon) =>
      [...scope.matchAll(new RegExp(`${icon}[\\s\\S]*?<span>([^<]*)</span>`, "g"))].map((m) => m[1]);
    const without = text("lucide-x");
    const with_ = text("lucide-check");
    if (without.length === 0) throw new Error("found no X-marked rows to compare");
    if (with_.length === 0) throw new Error("found no check-marked rows to compare");
    expectBalanced(without, with_, 1, "problem/solution bullets");
  });
}

function stepPill(ctx, label) {
  const pill = [...ctx.container.querySelectorAll("button")]
    .find((b) => (b.textContent || "").trim().includes(label));
  if (!pill) throw new Error(`no step nav control labelled ${JSON.stringify(label)}`);
  return pill;
}

/** Swap api stub methods for the duration of one check, then restore them. */
async function withApi(overrides, fn) {
  const originals = {};
  for (const [name, impl] of Object.entries(overrides)) {
    originals[name] = apiStub[name];
    apiStub[name] = impl;
  }
  try {
    await fn();
  } finally {
    for (const [name, impl] of Object.entries(originals)) apiStub[name] = impl;
  }
}

/** Set a <select> the way a person would, so React's onChange fires. */
async function selectOption(ctx, select, value) {
  const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLSelectElement.prototype, "value").set;
  await act(async () => {
    setter.call(select, value);
    select.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
  });
  await act(async () => {});
}

function selectLabelled(ctx, labelText) {
  // The objective control is the only select whose options are the facet list.
  const withOptions = [...ctx.container.querySelectorAll("select")]
    .find((s) => [...s.options].some((o) => o.value.includes("user_problem")));
  if (!withOptions) throw new Error(`no select carrying ${JSON.stringify(labelText)}`);
  return withOptions;
}

// ---------------------------------------------------------------------------
// Result
// ---------------------------------------------------------------------------
main()
  .then(async () => {
    // Drain anything still in flight before tearing down. The last checks leave
    // a request resolving, and an update that lands after the last act() prints
    // a "not wrapped in act" warning — noise in a gate is noise people learn to
    // ignore, which is how a real warning gets missed too.
    await act(async () => {});
    // Unmount inside act, one root at a time. Unmounting outside it lets the
    // final cleanup effects update state after the last act() and prints a
    // "not wrapped in act" warning; unmounting them all in one act is rejected
    // as overlapping. One per act satisfies both.
    for (const root of roots) {
      try {
        // eslint-disable-next-line no-await-in-loop
        await act(async () => {
          root.unmount();
        });
      } catch {
        /* an unmount failure is not the assertion */
      }
    }
    console.log("");
    if (failures.length > 0) {
      console.log(`${failures.length} of ${checks} render checks FAILED:`);
      failures.forEach((f) => console.log(`  - ${f}`));
      process.exit(1);
    }
    console.log(`All ${checks} render smoke checks pass.`);
    process.exit(0);
  })
  .catch((err) => {
    // A throw outside a check — a fixture that no longer matches the API, say.
    // Must fail loudly: a harness that dies quietly is a gate that is green
    // because it never ran.
    console.log("");
    console.log("  [FAIL] the harness itself threw before reporting results");
    console.log(`         ${err && err.stack ? err.stack : String(err)}`);
    process.exit(1);
  });
