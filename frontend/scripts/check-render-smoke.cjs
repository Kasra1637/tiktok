/**
 * Mounts every wizard step and the panels in a real DOM, to catch crashes that
 * a type-check and a build cannot.
 *
 * Why this exists: two live defects shipped with the whole gate green.
 * `GenerationPanel` listed `schedulePoll` in a `useEffect` dep array above its
 * `const` declaration, so evaluating the array threw a TDZ ReferenceError on
 * every mount â€” and because an ErrorBoundary wraps the app, that took down
 * every route. `HookContinuityPanel` called `resolveExtendRequest` and read
 * `extendBy`, neither of which exists, on the branch that renders while
 * extending toward a target. Neither is a type error: JSX goes through
 * `createElement`, and an undefined identifier inside a state-dependent branch
 * is still a valid module. `npm run build` lints and type-checks, and
 * `check-frontend-logic.cjs` evaluates pure helpers â€” neither one ever calls a
 * component. So this file does.
 *
 * It uses a real DOM (`jsdom`) and `createRoot` rather than
 * `renderToStaticMarkup`, because the branches that matter are effect-driven:
 * both panels load from the API before their content can render, and server
 * rendering never runs an effect, so a static render would silently skip
 * exactly the code that was broken.
 *
 * `api` is stubbed with fixtures shaped from the server's real responses (see
 * `_public_project`, `_public_library_template` and `video_providers.capability`
 * in server.py), so no network call is made and every branch is reachable. The
 * fixtures were reshaped when a video became one render: a strategy is two
 * sections rather than eight beats, a template declares `middle_structure` and a
 * `default_duration` rather than `continuation_structure` + `cta_pattern`, and a
 * project carries `demo_brief` rather than `cta` + `feature_emphasis`. A fixture
 * that still carried the old shape would make every assertion below pass without
 * touching the product, which is the failure mode this file exists to prevent.
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
global.HTMLInputElement = dom.window.HTMLInputElement;
global.HTMLTextAreaElement = dom.window.HTMLTextAreaElement;
global.HTMLSelectElement = dom.window.HTMLSelectElement;
global.HTMLButtonElement = dom.window.HTMLButtonElement;
global.SVGElement = dom.window.SVGElement;
global.Node = dom.window.Node;
global.NodeFilter = dom.window.NodeFilter;
global.Element = dom.window.Element;
global.Event = dom.window.Event;
global.CustomEvent = dom.window.CustomEvent;
global.MouseEvent = dom.window.MouseEvent;
// Blob and MessageEvent have to come from the same window as the rest. Node
// supplies its own global Blob, so without this a blob built here fails an
// `instanceof Blob` check in component code - a harness artifact that would hide
// a real code path rather than reveal one. In a browser these are one object.
global.Blob = dom.window.Blob;
global.MessageEvent = dom.window.MessageEvent;
// The Demo + CTA engine constructs `new Image()` at module scope to load the
// hand plate and environment photos. Node has no DOM Image, so without this the
// page throws "Image is not defined" on import and every check reports a
// component crash instead of the assertion it meant to make.
global.Image = dom.window.Image;
// The Demo + CTA editor remembers which setting groups are open, and reads that
// on mount via `window.localStorage`. jsdom's own storage throws on this opaque
// origin, and the editor's try/catch then falls back to defaults — so the panel
// would look correct while the persistence path stayed untested. The stub has to
// land on `dom.window` specifically, not on `global`: the component reads
// `window`, and stubbing only `global` left the throw in place.
if (!global.__SMOKE_STORAGE_STUBBED) {
  const store = new Map();
  const stub = {
    getItem: (k) => (store.has(k) ? store.get(k) : null),
    setItem: (k, v) => store.set(k, String(v)),
    removeItem: (k) => store.delete(k),
    clear: () => store.clear(),
  };
  try {
    Object.defineProperty(dom.window, "localStorage", {
      value: stub,
      configurable: true,
      writable: true,
    });
  } catch {
    // Older jsdom refuses; fall back so the check degrades loudly rather than
    // silently testing nothing.
  }
  global.localStorage = stub;
  global.__SMOKE_STORAGE_STUBBED = true;
}
global.getComputedStyle = dom.window.getComputedStyle;
global.MutationObserver = dom.window.MutationObserver;
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
  supports_last_frame: false,
  notes: "One render of up to 15s. A longer request is refused rather than split.",
};

// ai_service.normalize_strategy() guarantees exactly two sections with roles
// "hook" and "middle", assigned by position. `cta_strategy`,
// `continuity_contract`, `max_planned_index` and `planned_segments` are all gone
// and are deliberately absent: a fixture that carried them would let a component
// still reading them render a chain and pass, which is the exact regression the
// strategy-review checks below exist to catch.
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
  scene: { camera_angle: "eye level", lighting: "morning window" },
  performance: { movement: "still", voice_delivery: "unhurried" },
  segments: [
    { index: 0, role: "hook", seconds: 3, goal: "stop the scroll", script: "You do not have a focus problem.", action: "look up" },
    { index: 1, role: "middle", seconds: 7, goal: "develop it, stop at the reach", script: "You have too many lists.", action: "count on fingers" },
  ],
  objective: "address_user_problem",
};

const SEGMENT = {
  id: "gen-1",
  segment_index: 0,
  segment_role: "primary",
  status: "completed",
  duration: 10,
  trim_to_seconds: 0,
  approved: 0,
  video_url: "/media/gen-1.mp4",
    r2_url: null,
  retryable: true,
  performance: null,
};

// The key is `asset_id`, not `id`: the attached-photo row slices
// attachment.asset_id for the label, so a fixture using `id` throws on the
// template step.
//
// No start/end, no audio_role, no audio_gain. Those fields are still accepted
// on the wire for legacy rows, but the studio no longer renders a control for
// any of them: the video is one render with captions composited over it, so an
// asset has no on-screen window and nothing to mix. A fixture carrying them
// would keep rendering as though the controls still existed.
const ASSETS = [
  { asset_id: "a1", kind: "character_reference", label: "face.jpg", status: "ready" },
];

// template_id and content_angle_id are set because canGenerate is
// `profileId && templateId`: without them every step correctly refuses to open
// the render path, which would make the "render controls exist" assertions prove
// nothing.
//
// `cta` and `feature_emphasis` are absent for the same reason the components no
// longer read them: the server stopped writing them, and a fixture that carried
// them would keep a dead input rendering as though it still saved.
const BASE_PROJECT = {
  id: "p1",
  brand_profile_id: "b1",
  content_angle_id: "a1",
  template_id: "t1",
  objective: "address_user_problem",
  status: "draft",
  script_version: 0,
  duration_seconds: 10,
  hook_seconds: 3,
  assets: ASSETS,
  safety_report: { passed: true, blocking: [], unverified: [] },
  strategy: {},
  script: "",
  hook_line: "",
  demo_brief: "",
};

const PROJECT_WITH_STRATEGY = {
  ...BASE_PROJECT,
  status: "ready_for_generation",
  script_version: 1,
  strategy: STRATEGY,
  hook_line: STRATEGY.hook_line,
  script: "You do not have a focus problem. You have too many lists.",
  // The founder's own note about what to record. It is editable on the review
  // step and is never passed to a render, so the panel that must NOT show a CTA
  // has something honest to show instead.
  demo_brief: "Record yourself clearing one list by hand, hands only.",
  visual_direction: "Close, 9:16, desk.",
  beat_timeline: [{ start: 0, end: 10, label: "hook", text: "You do not have a focus problem." }],
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

// middle_structure replaced continuation_structure + cta_pattern, and
// default_duration is now the length of the whole piece rather than a library
// default of 20 or 30. The retired names are deliberately absent for the same
// reason as on the strategy: a component reading them must fail loudly here
// rather than be quietly satisfied.
const TEMPLATE = {
  id: "t1",
  name: "Name the misdiagnosis",
  category: "pain-point-question",
  objective: "address_user_problem",
  opening_structure: "Open by naming what they think is wrong.",
  middle_structure: "Then correct it, and stop at the reach for the phone.",
  visual_style: "Talking head.",
  camera_pacing: "Steady.",
  content_slots: { app_feature: "Task timer" },
  required_assets: ["character_reference"],
  default_duration: 10,
  hook_seconds: 3,
  is_usable: true,
};

const ANGLE = {
  id: "a1",
  kind: "problem",
  label: "Too many lists",
  user_problem: "Nothing gets finished.",
  target_audience: "busy professionals",
};

// template_library.SUPPORTED_DURATIONS. Every one of them is a single render on
// the only studio-eligible model, which is why the length control is gone: there
// is nothing for the founder to choose that would not need a second pass.
const SUPPORTED_DURATIONS = [8, 10, 12, 15];

const apiStub = {
  getStudioVideoModels: async () => ({ default: "minimax-h3", models: [CAPABILITY] }),
  getGenerations: async () => ({ generations: [SEGMENT] }),
  pollGeneration: async () => SEGMENT,
  getTemplates: async () => ({ templates: [TEMPLATE] }),
  getTemplateFacets: async () => ({
    objectives: ["address_user_problem", "demonstrate_feature"],
    supported_durations: SUPPORTED_DURATIONS,
    // Shaped like the real server response, which derives the per-duration
    // render count from the default studio model's single-pass ceiling
    // (CAPABILITY.max_duration above). All four are one render.
    duration_segments: { 8: 1, 10: 1, 12: 1, 15: 1 },
  }),
  getAppProfiles: async () => ({ profiles: [PROFILE] }),
  getContentAngles: async () => ({ angles: [ANGLE] }),
  getTemplateRecommendations: async () => ({
    recommendations: [{
      template: { ...TEMPLATE, brand_profile_id: "b1" },
      score: 9.5,
      // The template's declared length, server-side. It is the length the
      // project will be seeded from, not a suggestion.
      suggested_duration: TEMPLATE.default_duration,
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
  // A create returns a fresh draft with no plan and no strategy, exactly as
  // the server does. The stub used to return a fully-planned project, which
  // the eager create adopts and which hides the "Generate the plan" button
  // behind a plan the founder never wrote.
  createStudioProject: async () => ({ ...BASE_PROJECT }),
  updateStudioProject: async () => PROJECT_WITH_STRATEGY,
  detachAsset: async () => BASE_PROJECT,
  getProjects: async () => ({ projects: [] }),
  getAssets: async () => ({ assets: [] }),
  uploadAsset: async () => ({ asset: null }),
  generatePlan: async () => PROJECT_WITH_STRATEGY,
  generateStrategy: async () => PROJECT_WITH_STRATEGY,
  generateVideo: async () => SEGMENT,
  retryGeneration: async () => SEGMENT,
  composeOverlays: async () => ({ composition: null }),
  markProjectReady: async () => PROJECT_WITH_STRATEGY,
  recordSignal: () => {},
};

/**
 * Every API method the UI called, and every retired one it tried to call.
 *
 * Two separate lists because they defend different things. `apiCalls` is a
 * record: it lets a check assert that a branch fired the request it was supposed
 * to. `retiredCalls` is a trap: the five methods the server deleted are not on
 * the stub at all, so a component that still called one would throw a
 * TypeError â€” and a TypeError inside a `try` with a `catch` that renders
 * `getErrorMessage` would be swallowed and shown as an ordinary failure message.
 * Recording the attempt first means the check sees it either way.
 */
const apiCalls = [];
const retiredCalls = [];
const RETIRED_API_METHODS = [
  "generateHook",
  "approveGeneration",
  "extendGeneration",
  "assembleChain",
  "getGenerationContinuity",
  "setProjectExtendIntent",
  "setProjectHookLength",
];
for (const [name, impl] of Object.entries(apiStub)) {
  apiStub[name] = (...args) => {
    apiCalls.push(name);
    return impl(...args);
  };
}
for (const name of RETIRED_API_METHODS) {
  // Belt and braces: the stub never had these, so a stray call throws anyway.
  // Declaring them as throwing traps is what makes the swallow harmless.
  Object.defineProperty(apiStub, name, {
    get() {
      retiredCalls.push(name);
      return () => Promise.reject(new Error(`retired endpoint: ${name}`));
    },
    configurable: true,
  });
}

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
        useNavigate: () => (...args) => {
          // Rest params, not `arguments`: arrows do not bind their own, so
          // `arguments` here would leak the requireShim spec string instead
          // of the navigated path.
          if (global.__SMOKE_NAVIGATIONS) global.__SMOKE_NAVIGATIONS.push(...args);
        },
        useSearchParams: () => [searchParams(), () => {}],
        // The embedded AssetLibrary on the Assets step reads the route, so a
        // deep link that lands there needs these to exist. Overridable for a
        // page that renders off a route param: AppProfileDetail is driven
        // entirely by :profileId, so with an empty object it would fetch under
        // `undefined` and settle on its error state, and its delete dialog
        // could never be exercised.
        useParams: () => global.__SMOKE_ROUTE_PARAMS || {},
        useLocation: () => ({ pathname: "/create", search: searchParams().toString() }),
      };
    }
    if (spec === "sonner") return { toast: { success: () => {}, error: () => {} } };
    if (spec.endsWith("lib/api")) {
      // Mirror the real getErrorMessage: checks assert on the surfaced text
      // (e.g. a 409's detail), and a constant would swallow it.
      return {
        api: apiStub,
        getErrorMessage: (err) =>
          err?.response?.data?.detail || err?.message || "error",
        mediaUrl: (p) => p,
      };
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
    if (process.env.SMOKE_TRACE && err && Array.isArray(err.errors)) {
      err.errors.forEach((inner, n) => console.log(`         [inner ${n}] ${inner && inner.stack ? inner.stack : String(inner)}`));
    }
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

function expectNone(ctx, needles, why) {
  for (const needle of needles) expectAbsent(ctx, needle, why);
}

/**
 * Asserts two string lists are within `tolerance` characters per row.
 *
 * Used for the landing page's problem/solution bullets. Those two cards sit
 * side by side, so a row that runs long wraps to a second line on one side
 * only and makes that side look busier than the other. Nothing in the build or
 * the type-check can see it, and the copy is exactly the kind that gets edited
 * one line at a time â€” so the balance has to be asserted or it silently rots.
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

/** Every .js/.jsx under src, as [absolutePath, source] pairs. */
function sourceFiles(dir = SRC, out = []) {
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const abs = path.join(dir, entry.name);
    if (entry.isDirectory()) sourceFiles(abs, out);
    else if (/\.(js|jsx)$/.test(entry.name)) out.push(abs);
  }
  return out;
}

/**
 * Blank out comments while preserving line numbering, so a scan for a retired
 * field only sees executable code.
 *
 * This matters more than it looks. The files explaining WHY a field was removed
 * have to name it â€” the record of the decision is the point of those comments â€”
 * so a naive text scan fails on the very files that did the work. Newlines are
 * kept so a hit can still be reported at the right line.
 */
function stripComments(src) {
  return src
    .replace(/\/\*[\s\S]*?\*\//g, (block) => block.replace(/[^\n]/g, " "))
    // A `//` preceded by a colon is a protocol separator (https://), not a
    // comment, so the character before it is required to not be one.
    .replace(/(^|[^:])\/\/[^\n]*/g, (line, before) => before);
}

console.log("Mounting every wizard step and panel...");

const { GenerationPanel } = load("components/GenerationPanel.jsx");
const { HookContinuityPanel } = load("components/HookContinuityPanel.jsx");
const CreateVideo = load("pages/CreateVideo.jsx").default;
const DemoCtaStudio = load("pages/DemoCtaStudio.jsx").default;

// The shipped order, in the order the founder walks it. Asserted as a whole
// sequence rather than a set: the point of the reorder is that the free, claim-
// checked plan comes before the step that calls the model, and a set comparison
// would pass just as happily if the render went back to fourth.
//
// The last step is "Hook & middle" rather than "Influencer hook" because that is
// what it produces: one render with two sections. The old label named the first
// beat of a chain, and a step called "Influencer hook" whose output is a hook
// plus a middle is a step that under-describes the thing being rendered.
// Five, not seven. "Assets" was a step whose only content was the photo upload,
// and "Creative plan" was a step whose only content was a button whose result
// you had to go to the next screen to read. Both are now part of the step they
// belonged to, so the founder picks a template and attaches the photo without
// leaving, and presses Generate on the same page that shows the result.
//
// The order still matters and is still asserted as a whole sequence: the
// free, claim-checked plan is read before the step that calls the model, and a// comparison would pass just as happily if the render went back to third.
const STEP_LABELS = [
  "App Profile",
  "Audience & goal",
  "Template & photo",
  "Review",
  "Hook & middle",
];

// The one length every step must be able to state without a control anywhere.
const PIECE_SECONDS = String(TEMPLATE.default_duration);

const stepSource = fs.readFileSync(path.join(SRC, "pages", "CreateVideo.jsx"), "utf8");

async function main() {
  // -------------------------------------------------------------------------
  // The wizard is five steps, and every step that existed only to hold a button
  // has been folded into the step it belonged to. These prove the shape is real
  // rather than a label change: the photo upload is ON the template step, and
  // the plan is generated from the Review step that reads it.
  // -------------------------------------------------------------------------
  await check("the photo upload lives on the template step, not its own", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    await openTemplateStep(ctx);
    const text = ctx.text();
    if (!text.includes("Your photo")) {
      throw new Error("the template step does not offer the photograph upload");
    }
    // The draft is created eagerly now (ensureProject fires on profile +
    // template), so the photo attaches to a project without the founder
    // pressing anything. Either the attachment UI or the pending-draft copy is
    // the proof that this step owns the photo -- a missing project would show
    // neither.
    const ownsPhoto =
      /Create the draft/.test(text) || /attach/i.test(text) || !!ctx.container.querySelector("input[type=file]");
    if (!ownsPhoto) {
      throw new Error("the template step cannot create the draft the photo attaches to");
    }
    // No step of its own: this is the assertion that the old "Assets" pill is
    // gone rather than merely renamed.
    const pills = [...ctx.container.querySelectorAll("[data-testid^='step-pill-']")]
      .map((el) => el.textContent);
    if (pills.length !== STEP_LABELS.length) {
      throw new Error(`expected ${STEP_LABELS.length} steps, saw ${JSON.stringify(pills)}`);
    }
    for (const gone of ["Assets", "Creative plan"]) {
      if (pills.some((p) => p.trim() === gone)) {
        throw new Error(`the ${JSON.stringify(gone)} step still exists as its own step`);
      }
    }
  });

  await check("no step offers time-range or audio controls for an asset", async (ctx) => {
    // The video is one render with captions composited over it, so an asset has
    // no on-screen window and there is nothing to mix. The row used to carry
    // Start, End, Use as and Gain, and "Save timing" wrote them back - controls
    // that implied a placement the composition cannot honour.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      await openTemplateStep(ctx);
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    const text = ctx.text();
    for (const dead of ["Save timing", "Use as", "Gain", "Voiceover", "Background"]) {
      if (text.includes(dead)) {
        throw new Error(`the asset row still offers ${JSON.stringify(dead)}`);
      }
    }
    // ...and it still confirms the photograph is attached and offers a way to
    // remove it, which is the part that did do something.
    if (!text.includes("face.jpg")) {
      throw new Error("the attached photograph is not confirmed anywhere");
    }
    const remove = [...ctx.container.querySelectorAll("button")]
      .find((b) => (b.textContent || "").trim() === "Remove");
    if (!remove) throw new Error("the attached photograph cannot be removed");
    if (!text.includes("used for the whole video")) {
      throw new Error("the photograph does not say how it is used");
    }
  });

  await check("the plan is generated from the step that reviews it", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    // Entering Review with a ready draft and no plan generates it without a
    // click; the button below is the retry path, not the happy path. The
    // default generatePlan stub answers with a planned project, so by the
    // time the acts flush the step reads the fresh plan.
    const plans = [];
    // A create returns a fresh draft (no plan yet) -- matching the server. The
    // default stub returned a fully-planned project, which the eager create now
    // adopts and which would hide the auto-generation this check is about.
    await withApi(
      {
        // A create echoes the angle it was sent (here: none chosen), exactly
        // as the server does. Answering with the canned project's "a1" would
        // disagree with the wizard's empty angle on every pass.
        createStudioProject: async () => ({ ...BASE_PROJECT, content_angle_id: "" }),
        updateStudioProject: async () => ({ ...BASE_PROJECT, content_angle_id: "" }),
        generatePlan: async (id, payload) => {
          plans.push(payload);
          return PROJECT_WITH_STRATEGY;
        },
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
        // Let the eager create land before moving on, so Review sees the
        // fresh draft (script_version 0) rather than a still-null project.
        await act(async () => {});
        await act(async () => {});
        await openStep(ctx, "Review");
        await act(async () => {});
        await act(async () => {});
        // Assert inside the stub scope: the calls above are async and would
        // otherwise land after the stub restores.
        if (plans.length === 0) {
          throw new Error("Review did not generate the plan on entry");
        }
        const text = ctx.text();
        // Either the fresh plan is already showing, or the fallback button is
        // still there mid-flight — both mean the step owns its plan rather
        // than bouncing the founder elsewhere for it.
        const showingPlan = text.includes("Hook line");
        const generate = [...ctx.container.querySelectorAll("button")]
          .find((b) => /Generate the plan/.test((b.textContent || "").trim()));
        if (!showingPlan && !generate) {
          throw new Error("Review neither shows the fresh plan nor offers to generate it");
        }
        if (text.includes("No plan yet")) {
          throw new Error("Review still bounces to a separate plan step for its own plan");
        }
      }
    );
  });

  // -------------------------------------------------------------------------
  // The crash that took the whole app down: a dep array read above its const.
  // -------------------------------------------------------------------------
  await check("GenerationPanel mounts", mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY }));

  await check("GenerationPanel mounts with no project", mount(GenerationPanel, { project: null }));

  await check("GenerationPanel shows the completed generation", async (ctx) => {
    await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    expectText(ctx, "Completed", "the generation status did not render");
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

  await check("GenerationPanel refuses a ready project with no photograph", async (ctx) => {
    // Marking ready is what enables Generate, and until this gate existed a
    // project with no photo sailed through approval and only failed at the
    // click, where a 409 reads as a broken app rather than an unmet rule.
    // The founder is told before they decide to render.
    await withApi({ getGenerations: async () => ({ generations: [] }) }, () =>
      mount(GenerationPanel, {
        project: { ...PROJECT_WITH_STRATEGY, assets: [] },
      })(ctx)
    );
    expectText(ctx, "No photo attached", "the missing-photograph gate did not render");
    expectText(ctx, "invent somebody who looks nothing like you", "the gate did not say why it matters");
    expectText(ctx, "Template & photo", "the gate did not name the step that fixes it");
    // The old ready hint and the new one must not both be talking at once.
    expectAbsent(ctx, "Mark the project ready for generation", "the ready hint competes with the real blocker");
  });

  await check("GenerationPanel is silent about the photo once one is attached", async (ctx) => {
    // The gate must key off the asset KIND, not merely "some asset exists", or a
    // project holding an unrelated row would look ready when it is not.
    await withApi({ getGenerations: async () => ({ generations: [] }) }, () =>
      mount(GenerationPanel, {
        project: {
          ...PROJECT_WITH_STRATEGY,
          assets: [{ asset_id: "a1", kind: "screenshot", label: "ui.png", status: "ready" }],
        },
      })(ctx)
    );
    expectText(ctx, "No photo attached", "a non-character_reference asset was read as a presenter");

    // And with the real thing attached, no gate at all.
    await withApi({ getGenerations: async () => ({ generations: [] }) }, () =>
      mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY } })(ctx)
    );
    expectAbsent(ctx, "No photo attached", "the gate fired on a project that has a photo");
  });

  await check("GenerationPanel explains an un-ready project that already rendered", async (ctx) => {
    // Saving a content edit on an approved project now returns it to draft, so
    // the "already rendered once" case is reachable rather than theoretical. The
    // hint used to be suppressed whenever a generation existed, which left a
    // dead Generate button with no explanation for exactly that founder.
    await mount(GenerationPanel, { project: { ...BASE_PROJECT } })(ctx);
    expectText(
      ctx,
      "Mark the project ready for generation",
      "the ready gate was hidden behind an existing generation"
    );
  });

  await check("a storage failure is loud, offers the retry, and clears on success", async (ctx) => {
    // The durable copy is the only copy that survives the provider URL
    // expiring, so a failed save rendered as muted small text taught the
    // founder nothing until the video would not load. It is now a destructive
    // alert with the recovery action attached -- and the retry endpoint
    // existed with no UI calling it, so the button is the fix, not the alert.
    let saved = { ...SEGMENT, storage_error: "R2 upload failed" };
    try {
      await withApi(
        {
          getGenerations: async () => ({ generations: [saved] }),
          pollGeneration: async () => saved,
          retryGenerationStorage: async () => {
            saved = { ...SEGMENT, storage_error: null };
            return { id: saved.id, r2_url: "/media/gen-1.mp4", storage_error: null };
          },
          getGeneration: async () => saved,
        },
        async () => {
          await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
          expectText(ctx, "Durable copy missing", "the storage failure is not escalated");
          expectText(ctx, "download this video now", "the alert does not say what is at stake");
          const retry = buttonByText(ctx, /Retry durable save/);
          await act(async () => {
            retry.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    if (ctx.text().includes("Durable copy missing")) {
      throw new Error("a successful storage retry left the alert on screen");
    }
    expectText(ctx, "Durable copy saved", "a successful storage retry is not confirmed");
  });

  await check("GenerationPanel blocks generation while a claim is prohibited", async (ctx) => {
    await mount(GenerationPanel, {
      project: {
        ...PROJECT_WITH_STRATEGY,
        safety_report: { passed: false, blocking: [{ claim: "cures anxiety" }], unverified: [] },
      },
    })(ctx);
    expectText(ctx, "Prohibited claim present", "the claim gate did not render");
    // The render panel is where the click is stopped, so the button has to be
    // dead here even though the project is marked ready.
    const generate = [...ctx.container.querySelectorAll("button")]
      .find((b) => /Generate/.test(b.textContent || ""));
    if (!generate) throw new Error("the generate control is missing");
    if (!generate.disabled) {
      throw new Error("a prohibited claim leaves the generate button enabled");
    }
  });

  // -------------------------------------------------------------------------
  // The replacement for the extend-coverage warning.
  //
  // The old check drove the branch that rendered while extending toward a
  // target and asserted "The strategy plans N more segments" â€” the finite-plan
  // warning. There is no chain to run out of, so that branch and its warning are
  // gone. What replaced it is the thing the founder actually has to read before
  // rendering: the two sections, named as the two sections, with the model's own
  // goal for each.
  // -------------------------------------------------------------------------
  await check("the strategy review presents the two sections and what they are", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    expectText(ctx, "The two sections", "the section list did not render");
    expectText(ctx, "hook", "the hook section did not render");
    expectText(ctx, "middle", "the middle section did not render");
    // The goal, straight from the strategy â€” this is the review surface's
    // reason to exist, so it has to reach the screen and not just be fetched.
    expectText(ctx, "stop the scroll", "the hook's goal did not render");
    expectText(ctx, "develop it, stop at the reach", "the middle's goal did not render");
  });

  await check("the strategy review shows the hook boundary from the plan", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    // The strategy plans its opening beat at 3s, so the boundary between the two
    // sections renders as a 3s badge on the hook row.
    expectText(ctx, "3s", "the hook boundary did not render");
  });

  // The property the running-total and coverage checks used to protect: nothing
  // on this panel can start a second job, approve anything, or join
  // anything. It is a review surface, and "no controls" is the whole contract.
  await check("the strategy review renders no render or chain control", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    const labels = [...ctx.container.querySelectorAll("button")]
      .map((b) => (b.textContent || "").trim());
    const forbidden = ["Extend", "Approve", "Join", "Assemble", "Generate", "Render", "Try it free"];
    for (const label of labels) {
      for (const word of forbidden) {
        if (label.toLowerCase().includes(word.toLowerCase())) {
          throw new Error(`the review surface renders a control labelled ${JSON.stringify(label)}`);
        }
      }
    }
    // The retired vocabulary, as rendered text rather than as button labels:
    // a coverage count, a progress bar, a beat list and a close are all things
    // this panel used to describe and none of which has a referent now.
    for (const phrase of [
      "Segments planned",
      "Target reached",
      "of 10s",
      "to go",
      "more segment",
      "the strategy plans",
      "approved segment",
      "Segments planned",
      "One continuous video",
      "end card",
      "CTA",
    ]) {
      expectAbsent(ctx, phrase, "the review surface still describes a chain");
    }
    // A progress bar is a coverage meter whatever its label says.
    if (ctx.container.querySelector('[role="progressbar"]')) {
      throw new Error("the review surface still renders a coverage progress bar");
    }
    // Exactly one button: build the strategy. It is free, and the strategy is
    // what makes the one render about this app.
    const onlyFree = labels.filter((l) => l);
    if (onlyFree.length !== 1 || !/strategy/i.test(onlyFree[0])) {
      throw new Error(`expected only the free strategy button, found: ${JSON.stringify(onlyFree)}`);
    }
  });

  await check("the strategy review mounts with no strategy", async (ctx) => {
    await mount(HookContinuityPanel, { project: BASE_PROJECT })(ctx);
    expectText(ctx, "Build the app-specific strategy", "the free strategy button did not render");
    expectAbsent(ctx, "The two sections", "sections rendered for a project with no strategy");
  });

  await check("the strategy review names a blocking claim", async (ctx) => {
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

  await check("the strategy review warns when no character reference is attached", async (ctx) => {
    await mount(HookContinuityPanel, {
      project: { ...PROJECT_WITH_STRATEGY, assets: [] },
    })(ctx);
    expectText(ctx, "No character reference", "the missing-face warning did not render");
  });

  // -------------------------------------------------------------------------
  // GenerationPanel is the only render UI, and it reflects one render.
  // -------------------------------------------------------------------------
  await check("GenerationPanel offers no second render, approval or join", async (ctx) => {
    await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    // The Extend button went with the endpoint. The remaining controls are the
    // one generate, the download, the caption compose, the retry, a re-render
    // of the SAME single job — and the native Demo + CTA entry, which is a link
    // into this app's own editor, not a second render and not an approval.
    for (const phrase of ["Extend", "Approve", "Join", "end card", "in two passes", "second pass"]) {
      expectAbsent(ctx, phrase, "GenerationPanel still offers a chain affordance");
    }
    // A bare "CTA" used to be banned outright, back when any CTA mention was a
    // promise the render could not keep. The native editor entry is the one
    // legitimate use now, so the check names the entry instead of the acronym.
    expectText(ctx, "Open in Demo + CTA", "the native editor entry is missing");
    const labels = [...ctx.container.querySelectorAll("button")]
      .map((b) => (b.textContent || "").trim())
      .filter(Boolean);
    for (const label of labels) {
      if (/extend|approve|join|assemble/i.test(label)) {
        throw new Error(`GenerationPanel renders a chain control: ${JSON.stringify(label)}`);
      }
    }
  });

  // The replacement for "a length beyond one pass is refused" at the panel
  // level. The old property lived in the extend lock, which returned null past
  // the ceiling so the button was disabled; the refusal itself has moved to the
  // endpoint, which answers 400. The panel's job is now to say so before the
  // click, and to disable the button rather than find out with a failed one.
  await check("GenerationPanel warns that a length past one pass will be refused", async (ctx) => {
    await mount(GenerationPanel, {
      // A project whose declared length is longer than the model's ceiling. A
      // real one cannot be created from the current library, which is exactly
      // why this is a fixture rather than a happy path.
      project: { ...PROJECT_WITH_STRATEGY, duration_seconds: 20 },
    })(ctx);
    expectText(ctx, "cannot render 20s in one pass", "the refusal warning did not render");
    const generate = [...ctx.container.querySelectorAll("button")]
      .find((b) => /Generate/.test(b.textContent || ""));
    if (!generate) throw new Error("the generate control is missing");
    if (!generate.disabled) {
      throw new Error("a length past the model's single pass leaves the generate button enabled");
    }
  });

  await check("GenerationPanel tells the founder the demo and the close are theirs", async (ctx) => {
    await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    // This is the sentence that makes the product honest. Without it the
    // download looks like a finished video, which is precisely what it is not:
    // the middle is built to stop where the presenter reaches for their phone.
    expectText(ctx, "Attach your own demo", "the founder's own demo is not described");
    expectText(ctx, "add your own call to action", "the founder's own close is not described");
  });

  // -------------------------------------------------------------------------
  // No UI path calls a deleted endpoint.
  //
  // Five endpoints went with the chain: /studio/projects/{id}/hook,
  // /generations/{id}/extend, /approve, /assemble and /continuity. Calling one is
  // a 404 that renders as an ordinary error message, so nothing about a founder
  // clicking through would make it obviously wrong â€” the button just does
  // nothing useful. So this is asserted two ways: statically, because a call
  // sitting in an unreachable branch is still a call, and at runtime, through the
  // recorder above.
  // -------------------------------------------------------------------------
  await check("no source file builds a request for a deleted endpoint", async (ctx) => {
    // Matched on the path tail next to the resource prefix, so the live
    // /app-profiles/{id}/approve is not caught by the word "approve".
    const retiredRoutes = [
      { re: /\/generations\/\$\{[^}]*\}\/(extend|approve|assemble|continuity)\b/, what: "a retired /generations/{id} route" },
      { re: /\/studio\/projects\/\$\{[^}]*\}\/hook\b/, what: "the retired /studio/projects/{id}/hook route" },
    ];
    const retiredFields = [
      "cta_pattern",
      "cta_strategy",
      "continuity_contract",
      "max_planned_index",
      "planned_segments",
      "feature_emphasis",
      "extend_intent",
    ];
    const problems = [];
    for (const abs of sourceFiles()) {
      const rel = path.relative(SRC, abs);
      const src = stripComments(fs.readFileSync(abs, "utf8"));
      src.split("\n").forEach((line, i) => {
        for (const { re, what } of retiredRoutes) {
          if (re.test(line)) problems.push(`${rel}:${i + 1} builds ${what}`);
        }
        for (const field of retiredFields) {
          // A property READ counts too: `strategy.cta_strategy` is a field the
          // server deleted, so reading it yields undefined and silently
          // disables whatever it was guarding.
          if (new RegExp(`[.\\[\\s"'\`]${field}\\b`).test(line)) {
            problems.push(`${rel}:${i + 1} still reads the retired field ${field}`);
          }
        }
      });
    }
    if (problems.length) throw new Error(problems.join("\n        "));
  });

  await check("no mounted path calls a deleted endpoint", async (ctx) => {
    retiredCalls.length = 0;
    // Drive every surface that could plausibly have kept a chain call: both
    // panels directly, and every step of the wizard with a drafted project
    // behind it so the render step actually mounts both.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
      await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
      await mount(CreateVideo, {})(ctx);
      for (const label of STEP_LABELS.slice(1)) {
        const pill = stepPill(ctx, label);
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    if (retiredCalls.length) {
      throw new Error(
        `the UI called a deleted endpoint: ${[...new Set(retiredCalls)].join(", ")}`
      );
    }
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

  // Nothing that calls the model may render before the plan has been read. This
  // the reorder's whole point, and it is invisible to a type-check: the render
  // panel is still imported and still reachable, just on a later step.
  await check("no render control appears before the plan step", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    // Every step before the last one. STEP_LABELS minus its final entry, so a
    // step added later is covered here by default rather than silently becoming
    // an unchecked place to run a render.
    for (const label of STEP_LABELS.slice(0, -1)) {
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, label);
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const text = ctx.text();
      for (const control of ["Generate the video", "Build the app-specific strategy"]) {
        if (text.includes(control)) {
          throw new Error(`step ${JSON.stringify(label)} renders a render control: ${JSON.stringify(control)}`);
        }
      }
    }
  });

  await check("the render step holds the render controls once a plan exists", async (ctx) => {
    // A plan reviewed, no strategy yet: the state the reorder puts the founder
    // in when they arrive here. Deep-linked so the wizard has that draft.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy: {},
            strategy_version: 0,
          }),
          // The strategy auto-builds once the project is ready; failing it here
          // keeps the "no strategy yet" state on screen so the button this
          // check is about stays visible.
          generateStrategy: async () => {
            throw new Error("strategy build unavailable in this check");
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          const pill = stepPill(ctx, "Hook & middle");
          await act(async () => {
            pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      );
      if (!ctx.text().includes("Build the app-specific strategy")) {
        throw new Error("the render step no longer offers the strategy button");
      }
      // The button now has an empty state behind it. Previously every panel
      // detail rendered only once a strategy existed, so this was a paragraph
      // and a button with nothing visible to indicate what either produced —
      // which is exactly why it read as a dead control.
      const text = ctx.text();
      if (!text.includes("What you get")) {
        throw new Error("the strategy panel shows no preview of what building it produces");
      }
      if (!text.includes("hook") || !text.includes("middle")) {
        throw new Error("the empty state does not name the two sections it will produce");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("generating is blocked until a strategy is built and read", async (ctx) => {
    // Without a strategy the render falls back to a generic take with a name in
    // it. This used to build the strategy AND render inside one click, which made
    // the panel's "read the strategy" copy cosmetic: the founder never saw it
    // before the money went. The button is now dead until a current strategy
    // exists, and building one is a separate free action on the panel above.
    global.__SMOKE_PARAMS = "?project=p1";
    let renderCalls = 0;
    try {
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy: {},
            strategy_version: 0,
          }),
          // The strategy auto-builds once ready; failing it keeps the
          // "no strategy" state so the dead-button behaviour this check pins
          // stays observable.
          generateStrategy: async () => {
            throw new Error("strategy build unavailable in this check");
          },
          generateVideo: async () => {
            renderCalls += 1;
            return { ...SEGMENT, status: "submitted" };
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
          const btn = renderButton(ctx);
          if (!btn.disabled) {
            throw new Error("the generate button is live with no strategy to render from");
          }
          await act(async () => {
            btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    if (renderCalls !== 0) {
      throw new Error(`a render went out with no strategy, ${renderCalls} call(s)`);
    }
    // A dead button with no explanation strands the founder, so the panel has to
    // say what to do next.
    if (!ctx.text().includes("Build the strategy above")) {
      throw new Error("the blocked generate button does not explain the next step");
    }
  });

  await check("an existing strategy is not rebuilt when generating", async (ctx) => {
    // Rebuilding bumps strategy_version and silently replaces whatever the
    // founder reviewed. A re-render must not do that behind their back.
    global.__SMOKE_PARAMS = "?project=p1";
    let strategyCalls = 0;
    try {
      await withApi(
        {
          generateStrategy: async () => {
            strategyCalls += 1;
            return PROJECT_WITH_STRATEGY;
          },
          generateVideo: async () => ({ ...SEGMENT, status: "submitted" }),
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
          const btn = renderButton(ctx);
          await act(async () => {
            btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    if (strategyCalls !== 0) {
      throw new Error("generating replaced a strategy the founder had already reviewed");
    }
  });

  await check("generating another video asks first, and a no renders nothing", async (ctx) => {
    // Idempotency stops a duplicated click, not a deliberate one the founder
    // did not mean. A re-roll is a second render, so it asks first, and a
    // "no" must leave everything exactly as it was.
    global.__SMOKE_PARAMS = "?project=p1";
    const originalConfirm = dom.window.confirm;
    let renderCalls = 0;
    try {
      await withApi(
        {
          generateVideo: async () => {
            renderCalls += 1;
            return { ...SEGMENT, status: "submitted" };
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
          const btn = renderButton(ctx);
          if (!/Generate another/.test((btn.textContent || "").trim())) {
            throw new Error("expected a re-roll button when a generation already exists");
          }
          dom.window.confirm = () => false;
          await act(async () => {
            btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
          if (renderCalls !== 0) {
            throw new Error("a declined re-roll still spent a render");
          }
          // And a "yes" still renders, so the gate asks rather than blocks.
          dom.window.confirm = () => true;
          await act(async () => {
            btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
          if (renderCalls !== 1) {
            throw new Error(`an accepted re-roll rendered ${renderCalls} time(s), expected 1`);
          }
        }
      );
    } finally {
      dom.window.confirm = originalConfirm;
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("a failed strategy build leaves nothing generated and says so", async (ctx) => {
    // The build is its own action on the panel above, so its failure is reported
    // there. What matters from this panel's side is the guarantee that no render
    // went out: nothing is generated for a video that does not exist, and the
    // founder is told why rather than left with a dead button.
    global.__SMOKE_PARAMS = "?project=p1";
    let renderCalls = 0;
    try {
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy: {},
            strategy_version: 0,
          }),
          generateStrategy: async () => {
            throw new Error("the model returned a truncated response");
          },
          generateVideo: async () => {
            renderCalls += 1;
            return { ...SEGMENT, status: "submitted" };
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
          const build = buttonByText(ctx, /Build the app-specific strategy|Rebuild strategy/);
          await act(async () => {
            build.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
          // Whatever the panel does with the failure, the render button must not
          // become live as a side effect of it.
          const btn = renderButton(ctx);
          if (!btn.disabled) {
            throw new Error("a failed strategy build left the generate button live");
          }
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    if (renderCalls !== 0) {
      throw new Error("a render went out with no strategy to render from");
    }
    // The harness mirrors the real getErrorMessage, so assert the provider's
    // own wording reaches the screen: what is under test is that the failure
    // reaches the founder and no render escaped.
    if (!ctx.text().includes("the model returned a truncated response")) {
      throw new Error("the failure is not surfaced anywhere the founder can see");
    }
  });

  await check("the stale-plan warning matches the server and blocks the click", async (ctx) => {
    // This check used to insist the warning NOT promise a refusal, because the
    // 409 that enforced it "lived only on the two deleted segmented endpoints".
    // It lives on the single-render generate endpoint now: a stale strategy is
    // refused, because a warning that arrives before the render still runs the
    // money on the plan the founder had already moved away from. The warning has
    // to tell the truth about that, and the button has to be dead.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy_version: 2,
            strategy_script_version: 1,
            script_version: 3,
            strategy_is_current: false,
          }),
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    const text = ctx.text();
    if (!text.includes("Plan edited since this strategy was built")) {
      throw new Error("the drift warning is missing entirely");
    }
    // No longer promising a render on the older plan.
    if (/will still work/i.test(text)) {
      throw new Error("the drift warning still says the render will proceed on the older plan");
    }
    if (!/blocked until you rebuild/i.test(text)) {
      throw new Error("the drift warning does not say the render is blocked");
    }
    // It has to name both versions, so "the older plan" is specific rather than
    // a warning with nothing to act on. The copy reads "built from plan v1" and
    // "the plan is now v3".
    if (!/plan v1/.test(text) || !/now v3/.test(text)) {
      throw new Error("the drift warning does not name the plan versions involved");
    }
    // And the click has to match the promise.
    const btn = renderButton(ctx);
    if (!btn.disabled) {
      throw new Error("the generate button is live against a stale strategy");
    }
    if (!text.includes("Rebuild the strategy above")) {
      throw new Error("the drift warning does not say what to do about it");
    }
  });

  await check("rebuilding a stale strategy asks first", async (ctx) => {
    // A rebuild bumps strategy_version and replaces what the founder reviewed.
    // When the plan has moved on, that replacement is the POINT of the click and
    // nothing else on screen says so - so it asks before overwriting.
    const asked = [];
    const originalConfirm = dom.window.confirm;
    let answer = false;
    dom.window.confirm = (message) => {
      asked.push(message);
      return answer;
    };
    apiCalls.length = 0;
    try {
      global.__SMOKE_PARAMS = "?project=p1";
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy_version: 2,
            strategy_script_version: 1,
            script_version: 3,
            strategy_is_current: false,
          }),
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
          const rebuild = [...ctx.container.querySelectorAll("button")]
            .find((b) => (b.textContent || "").includes("Rebuild strategy"));
          if (!rebuild) throw new Error("no rebuild control on the last step");
          await act(async () => {
            rebuild.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      );
      if (asked.length !== 1) {
        throw new Error(`a stale rebuild did not confirm (asked ${asked.length} times)`);
      }
      // The confirmation has to be specific about what is being replaced, or it
      // is a speed bump the founder dismisses without reading.
      if (!/plan v3/.test(asked[0]) || !/plan v1/.test(asked[0])) {
        throw new Error(`the confirmation does not name the plan versions: ${asked[0]}`);
      }
      // Declining must generate nothing. Reads happen on mount and are irrelevant;
      // the thing that would be wrong here is a write.
      const writes = apiCalls.filter((n) => /^(generate|update|create|mark|detach|upload)/.test(n));
      if (writes.length !== 0) {
        throw new Error(`declining the confirmation still wrote: ${JSON.stringify(writes)}`);
      }
    } finally {
      dom.window.confirm = originalConfirm;
      global.__SMOKE_PARAMS = "";
      apiCalls.length = 0;
    }
  });

  await check("rebuilding a current strategy does not interrupt", async (ctx) => {
    // The other half of the same rule. A rebuild of a strategy that already
    // matches the plan is harmless, and prompting every time would only teach
    // the founder to dismiss the dialog without reading it - which is how a
    // confirmation stops working at all.
    const asked = [];
    const originalConfirm = dom.window.confirm;
    dom.window.confirm = (message) => {
      asked.push(message);
      return true;
    };
    apiCalls.length = 0;
    try {
      global.__SMOKE_PARAMS = "?project=p1";
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy_version: 2,
            strategy_script_version: 3,
            script_version: 3,
            strategy_is_current: true,
          }),
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Hook & middle");
          const rebuild = [...ctx.container.querySelectorAll("button")]
            .find((b) => (b.textContent || "").includes("Rebuild strategy"));
          if (!rebuild) throw new Error("no rebuild control on the last step");
          await act(async () => {
            rebuild.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      );
      if (asked.length !== 0) {
        throw new Error("a harmless rebuild was interrupted by a confirmation prompt");
      }
      if (!apiCalls.includes("generateStrategy")) {
        throw new Error("an unprompted rebuild did not go through");
      }
    } finally {
      dom.window.confirm = originalConfirm;
      global.__SMOKE_PARAMS = "";
      apiCalls.length = 0;
    }
  });

  await check("the render step refuses to run without an approved plan", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      // A draft that exists but has no plan: the strategy and the one render
      // must both stay out of reach.
      await withApi(
        { getStudioProject: async () => ({ ...BASE_PROJECT, script_version: 0, script: "" }) },
        async () => {
          await mount(CreateVideo, {})(ctx);
          const pill = stepPill(ctx, "Hook & middle");
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
        `the render step does not explain that a plan comes first; it rendered: ${JSON.stringify(
          text.slice(300, 800)
        )}`
      );
    }
    for (const control of ["Build the app-specific strategy", "Generate the video", "Extend"]) {
      if (text.includes(control)) {
        throw new Error(`the render step offers ${JSON.stringify(control)} with no approved plan`);
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

  // -------------------------------------------------------------------------
  // The length is computed. These three checks replace "Review shows the length
  // but does not offer editing it", "the length selector lives on the step
  // before the plan" and "a length that needs more than one render says so up
  // front" â€” none of whose properties survived, because there is no longer a
  // picker, no step that owns the choice, and no length that takes two renders.
// The properties that did survive are re-asserted below: the length is stated
  // wherever the founder needs it, nothing anywhere can change it, and the UI
  // never implies a length exists that one render cannot produce.
  // -------------------------------------------------------------------------
  await check("the read-only shot timeline says so, and says when it is stale", async (ctx) => {
    // Seven editable fields sit on this step in the same visual style, so a
    // founder will try to type into the timeline. It is also the only block
    // that goes stale the moment the script above changes, so it has to say
    // that too - otherwise it silently describes a video that is no longer
    // the one being rendered.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Review");
      const timeline = ctx.container.querySelector('[data-testid="shot-timeline"]');
      if (!timeline) throw new Error("the shot timeline no longer renders");
      if (!timeline.textContent.includes("read-only")) {
        throw new Error("the shot timeline is not labelled read-only");
      }
      if (timeline.querySelector("input, textarea, select")) {
        throw new Error("the shot timeline renders an editable control");
      }
      // Not yet stale on a freshly loaded plan.
      if (!timeline.textContent.includes("Regenerate the plan to rewrite it")) {
        throw new Error("the timeline does not say how it gets rewritten");
      }

      // Now edit the script and confirm it says it is out of date.
      const script = [...ctx.container.querySelectorAll("textarea")]
        .find((t) => (t.value || "").length > 40);
      const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value").set;
      await act(async () => {
        setter.call(script, `${script.value} Plus a closing line.`);
        script.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      });
      await act(async () => {});
      const after = ctx.container.querySelector('[data-testid="shot-timeline"]');
      if (!after.textContent.includes("still describes the plan as generated")) {
        throw new Error("the timeline does not flag itself as stale after an edit");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("Review states the length and offers no way to change it", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, "Review");
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const text = ctx.text();
      if (!text.includes("Length of the generated piece")) {
        throw new Error("Review no longer states the length of the piece");
      }
      if (!text.includes("written to this length")) {
        throw new Error("Review does not explain that the timeline is tied to this length");
      }
      // The stale-timeline affordance and its two former relatives: an editable
      // length select, and a "regenerating the plan will use Ns" note.
      expectNone(ctx, [
        "Regenerating the plan will use",
        "Total video length",
        "written to this length. To change it, change the length",
      ], "Review still offers an editable total-length control");
      const durationSelect = [...ctx.container.querySelectorAll("select")]
        .find((s) => s.id === "review-duration");
      if (durationSelect) {
        throw new Error("Review still renders an editable total-length control");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  // The whole-wizard version of the above. A length control on one step is
  // enough to re-break the plan's beat timeline, and "which step owns the
  // number" was a question the old suite answered by pinning it to a step id
  // rather than by asserting that no step has one.
  await check("no step in the wizard offers a length control", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      for (const label of STEP_LABELS) {
        const pill = stepPill(ctx, label);
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
        if (ctx.container.querySelector("select#duration")) {
          throw new Error(`step ${JSON.stringify(label)} renders a length select`);
        }
        if (ctx.container.querySelector("input#duration")) {
          throw new Error(`step ${JSON.stringify(label)} renders a length input`);
        }
        // Any <select> whose options are the supported lengths is a length
        // control whatever it is called, and any number input whose label talks
        // about length is one too. The objective select's options are
        // objectives, so this cannot fire on the wrong control.
        for (const select of ctx.container.querySelectorAll("select")) {
          const values = [...select.options].map((o) => o.value);
          if (values.some((v) => SUPPORTED_DURATIONS.includes(Number(v)))) {
            throw new Error(`step ${JSON.stringify(label)} offers a length option: ${values.join()}`);
          }
        }
        const body = ctx.text();
        if (/total video length|video length of|seconds â€”/.test(body)) {
          throw new Error(`step ${JSON.stringify(label)} offers a total-length choice`);
        }
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  // The replacement for "a fresh wizard starts on a single-pass length" and "the
  // length selector lives on the step before the plan". The property was always
  // "the founder is never handed a length the model cannot render". With no
  // picker that is now a statement about what the step SAYS, and the value it
  // says has to be the template's, because that is what the project is seeded
  // from â€” a number that disagreed with the template would be a second, hidden
  // length.
  await check("the Audience step states the template's length, read-only", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = stepPill(ctx, "Audience & goal");
    await act(async () => {
      pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {});
    const text = ctx.text();
    if (!text.includes(`One render of ${PIECE_SECONDS}s`)) {
      throw new Error(
        `the Audience step does not state the piece length; it rendered: ${JSON.stringify(
          text.slice(0, 400)
        )}`
      );
    }
    // The two sections, with the remainder spelled out. A hook boundary that did
    // not add up to the piece would be a plan that does not add up either.
    if (!new RegExp(`a 3s hook,\\s*then a 7s middle`).test(text)) {
      throw new Error("the Audience step does not split the piece into its two sections");
    }
    // Why there is nothing to choose.
    if (!text.includes("not a choice")) {
      throw new Error("the Audience step does not say the length is not the founder's to pick");
    }
  });

  await check("the Audience step says the demo and the close are the founder's own", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = stepPill(ctx, "Audience & goal");
    await act(async () => {
      pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
    });
    await act(async () => {});
    const text = ctx.text();
    if (!text.includes("you record the demo yourself")) {
      throw new Error("the Audience step does not tell the founder the demo is theirs to record");
    }
    if (!text.includes("add your own call to action")) {
      throw new Error("the Audience step does not tell the founder the close is theirs to add");
    }
  });

  // Every offered length is one render, and the UI never implies otherwise.
  // The backend refuses a longer request with a 400 rather than splitting it, so
  // a length that needed two passes would be a length the product cannot make.
  // The old check asserted the multi-pass option LABEL said so; there is no
  // option any more, so the invariant moves up a level and is asserted against
  // the facet contract the code is written against.
  await check("every length the studio offers is a single render", async (ctx) => {
    const facets = await apiStub.getTemplateFacets();
    const counts = facets.duration_segments;
    const missing = facets.supported_durations.filter((d) => !counts[d]);
    if (missing.length) {
      throw new Error(`durations with no render count: ${missing.join()}`);
    }
    const multi = facets.supported_durations.filter((d) => counts[d] > 1);
    if (multi.length) {
      throw new Error(
        `a supported duration needs more than one render, which the endpoint would refuse: ${multi.join()}`
      );
    }
    for (const d of facets.supported_durations) {
      if (d > CAPABILITY.max_duration) {
        throw new Error(`${d}s is offered but past the model's ${CAPABILITY.max_duration}s ceiling`);
      }
    }
  });

  // -------------------------------------------------------------------------
  // The CTA is not offered anywhere, and the demo is not generated either.
  //
  // There is no product demo and no call to action in the generated footage: the
  // middle ends at the moment the presenter would reach for their phone, and the
  // founder attaches their own demo and close. That makes every CTA affordance
  // a lie â€” a field labelled CTA that is no longer writable, an end card the
  // server no longer composes â€” and every promise of a finished file a
  // founder would post without the part that makes it convert.
  // -------------------------------------------------------------------------
  await check("the studio never offers a call to action or a product demo", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      for (const label of STEP_LABELS) {
        const pill = stepPill(ctx, label);
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
        const text = ctx.text();
        // The acronym is the affordance: a field labelled "CTA", a "CTA pattern"
        // row, a "CTA end card" badge. Prose that spells the phrase out to say
        // the close is the founder's own is honest and is allowed to stay. So is
        // the native editor entry: "Demo + CTA" names this app's own editor, not
        // a promise the render keeps, so it is lifted out before the test.
        const withoutEntry = text.replace(/demo \+ cta/gi, "");
        if (/\bCTA\b/.test(withoutEntry)) {
          throw new Error(`step ${JSON.stringify(label)} offers a CTA affordance`);
        }
        if (text.includes("end card")) {
          throw new Error(`step ${JSON.stringify(label)} promises an end card`);
        }
        // The retired field labels, in case one is ever restored as a heading.
        if (text.includes("Feature emphasis")) {
          throw new Error(`step ${JSON.stringify(label)} offers a feature instruction to render`);
        }
      }
      // And the field that replaced the second: the founder's own note about
      // what to record, editable, and clearly not an instruction to the model.
      const reviewPill = stepPill(ctx, "Review");
      await act(async () => {
        reviewPill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const demo = ctx.container.querySelector("textarea#review-demo-brief");
      if (!demo) throw new Error("Review no longer offers the demo brief field");
      if (demo.value !== PROJECT_WITH_STRATEGY.demo_brief) {
        throw new Error(`the demo brief field is empty: ${JSON.stringify(demo.value)}`);
      }
      if (!ctx.text().includes("never reaches the render")) {
        throw new Error("the demo brief field does not say it is a note to the founder, not the model");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
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
        await openTemplateStep(ctx);
      }
    );
    const text = ctx.text();
    if (!text.includes("Top Pick")) {
      throw new Error("the top recommendation is not preselected");
    }
    if (!text.includes("Suggested")) {
      throw new Error("a preselected template is not labelled as a suggestion");
    }
    // The chosen template's declared length and curated middle, on the card.
    // This is where the founder learns the piece is not 20s and not their
    // choice, which used to be a separate picker two steps later.
    if (!text.includes(`${TEMPLATE.default_duration}s piece`)) {
      throw new Error("the template card does not state the length this template produces");
    }
    if (!text.includes(TEMPLATE.middle_structure)) {
      throw new Error("the template card does not show the template's middle structure");
    }
  });

  await check("every fit reason and limitation is on the card, with no toggle to hide them", async (ctx) => {
    // The reasons ARE the evidence for the choice this step asks for, and the
    // count of them is not a quality signal (a 3.0 objective match outranks
    // three 1.0 matches, and a miss becomes a limitation instead of a reason).
    // They used to be collapsed behind "Show all N more", which read as dead UI
    // because opening it only revealed plain text.
    global.__SMOKE_PARAMS = "";
    const FOUR_REASONS = [
      "Built for the 'create curiosity' objective.",
      "Suited to the 'Health & Fitness' category.",
      "Tailored for Vocolens - generated from this app's approved profile.",
      "Matches your audience: anxious, night-owls.",
    ];
    const THREE_LIMITS = [
      "Needs character reference.",
      "Curated for Productivity rather than Health & Fitness.",
      "Rejected or replaced 2 time(s) for this app.",
    ];
    await withApi(
      {
        getTemplates: async () => ({ templates: ORDERED_TEMPLATES }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            {
              template: ORDERED_TEMPLATES[0],
              score: 9.5,
              why_it_fits: FOUR_REASONS,
              limitations: THREE_LIMITS,
              suggested_duration: TEMPLATE.default_duration,
            },
          ],
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
      }
    );
    const text = ctx.text();

    // Every line, with no click required. The old card showed reasons[0] and
    // limits[0] and hid the rest behind the link.
    for (const reason of FOUR_REASONS) {
      if (!text.includes(reason)) {
        throw new Error(`a fit reason is hidden behind the old toggle: ${reason}`);
      }
    }
    for (const limit of THREE_LIMITS) {
      if (!text.includes(limit)) {
        throw new Error(`a limitation is hidden behind the old toggle: ${limit}`);
      }
    }

    // The toggle is gone entirely, in either state.
    if (/Show all \d+ more/i.test(text) || /Show less/i.test(text)) {
      throw new Error("the expand toggle is still present; reasons should always be visible");
    }

    // A reason is the case FOR the template and a limitation is the caveat ON
    // it. Rendering them identically made a warning look like evidence.
    if (!text.includes("Why it fits")) {
      throw new Error("the fit reasons are not labelled");
    }
    if (!text.includes("Before you use it")) {
      throw new Error("the limitations are not labelled as caveats");
    }

    // The score is the sort key and was already computed server-side; showing it
    // is what stops "is four reasons better than two" being a reasonable
    // question for the founder to ask.
    if (!text.includes("Fit 9.5")) {
      throw new Error("the fit score is not shown on the card");
    }
  });

  await check("a card with no reasons or limitations shows neither block", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await withApi(
      {
        getTemplates: async () => ({ templates: ORDERED_TEMPLATES }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            {
              template: ORDERED_TEMPLATES[1],
              score: 5,
              why_it_fits: [],
              limitations: [],
              suggested_duration: TEMPLATE.default_duration,
            },
          ],
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
      }
    );
    const text = ctx.text();
    // An empty heading is worse than no heading.
    if (text.includes("Why it fits") || text.includes("Before you use it")) {
      throw new Error("an empty reasons or limitations block is still rendered");
    }
    if (!text.includes("Fit 5")) {
      throw new Error("the fit score is missing");
    }
  });

  // The objective is the heaviest signal in the template scorer and gates the
  // tailored templates, so leaving it optional meant the strongest
  // recommendation input was silently dropped whenever a founder skipped it -
  // and the step still claimed to be "scored for this app".
  await check("the template step refuses to rank anything without an objective", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await withApi(
      {
        getTemplates: async () => ({ templates: ORDERED_TEMPLATES }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            { template: ORDERED_TEMPLATES[0], score: 9, why_it_fits: ["fits"], limitations: [] },
          ],
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Template & photo");
      }
    );
    const text = ctx.text();
    // It must not show a ranked card list, because nothing behind it was ranked
    // against a goal.
    if (text.includes("Fit 9")) {
      throw new Error("a fit score is shown for a template ranked with no objective");
    }
    // ...and it must say what is missing and how to fix it, rather than
    // rendering an empty step.
    if (!text.includes("Choose what this video is for")) {
      throw new Error("the template step does not explain that the objective is required");
    }
    const back = [...ctx.container.querySelectorAll("button")]
      .find((b) => (b.textContent || "").includes("Set the goal"));
    if (!back) throw new Error("there is no way from the template step to set the goal");
  });

  await check("no objective is silently reported as done on the progress pills", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = ctx.container.querySelector('[data-testid="step-pill-angle"]');
    if (!pill) throw new Error("the progress pills carry no state markers");
    if (pill.getAttribute("data-state") === "done") {
      throw new Error("the Audience step is ticked before an objective is chosen");
    }
    if (pill.getAttribute("aria-label") !== "Audience & goal: needs something from you") {
      throw new Error(
        `the pill does not say it is blocked: ${pill.getAttribute("aria-label")}`
      );
    }
  });

  await check("progress ticks mean done, not merely being to the left", async (ctx) => {
    // The tick used to mean "this step index is below the current one", so
    // jumping straight to the last step showed a tick on all five while nothing
    // had been done - telling the founder they had finished the workflow before
    // starting it. The state is now derived from what actually exists.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    const states = [...ctx.container.querySelectorAll("[data-testid^='step-pill-']")].map(
      (el) => `${el.getAttribute("data-testid")}=${el.getAttribute("data-state")}`
    );
    // This draft has a plan, so Review is genuinely satisfied. The rest are
    // decided by the draft's own profile/template/photo.
    const review = ctx.container.querySelector('[data-testid="step-pill-review"]');
    if (review?.getAttribute("data-state") !== "done") {
      throw new Error(`Review should be done for a project with a plan: ${states.join(", ")}`);
    }
    const render = ctx.container.querySelector('[data-testid="step-pill-hook"]');
    // The render step has no completion state by design: the workflow ends at
    // "attach your own demo", which happens in the founder's editor.
    if (render?.getAttribute("data-state") === "done") {
      throw new Error("the render step is ticked although no clip has been generated");
    }
  });

  await check("a plan with unsaved edits is not reported as reviewed", async (ctx) => {
    // The tick has to mean "read and stored", not "a plan exists". Otherwise
    // the progress indicator tells the founder they finished reading a script
    // they had changed and not saved.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Review");
      const script = [...ctx.container.querySelectorAll("textarea")]
        .find((t) => (t.value || "").length > 40);
      if (!script) throw new Error("no script field on Review to edit");
      const setter = Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value").set;
      await act(async () => {
        setter.call(script, `${script.value} and one more clause`);
        script.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      });
      await act(async () => {});
      const pill = ctx.container.querySelector('[data-testid="step-pill-review"]');
      if (pill?.getAttribute("data-state") === "done") {
        throw new Error("Review is ticked while there are unsaved edits");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
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
        await openTemplateStep(ctx);

        // Click the second card by its rendered name.
        const second = [...ctx.container.querySelectorAll("[role=button]")]
          .find((el) => (el.textContent || "").includes("Second"));
        if (!second) throw new Error("the second recommendation is not clickable");
        await act(async () => {
          second.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});

        // Leave and come back, which re-runs the load with a flipped order.
        // Review is the step that follows the template step; it used to be
        // "Assets", which no longer exists as its own step.
        await openStep(ctx, "Review");
        await openStep(ctx, "Template & photo");
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
        const pill = stepPill(ctx, "Template & photo");
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
        const pill = stepPill(ctx, "Template & photo");
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

  // The project write is where the retired fields would have gone back in. The
  // server still accepts `extend_intent` on the create request and still accepts
  // `duration_seconds` on the patch, so a client that sends them gets a 2xx and
  // a discarded value â€” the silent-write failure mode this whole harness exists
  // to catch, and the one that made the old intent toggle look like it worked.
  //
  // Both write paths are driven, because they are different code and the old bug
  // lived in both: the create sent a length the server would override from the
  // template, and the plan request sent one the server would refuse once a plan
  // existed.
  await check("no project write sends a length or an extend intent", async (ctx) => {
    const creates = [];
    const updates = [];
    const plans = [];
    // Regenerating a plan that exists now asks before discarding it. jsdom's
    // confirm is not implemented and returns undefined, which is falsy — so
    // without this the click silently does nothing and the check would report
    // "no project was updated" for the wrong reason.
    const originalConfirm = dom.window.confirm;
    dom.window.confirm = () => true;
    await withApi(
      {
        createStudioProject: async (payload) => {
          creates.push(payload);
          return PROJECT_WITH_STRATEGY;
        },
        updateStudioProject: async (id, payload) => {
          updates.push(payload);
          return PROJECT_WITH_STRATEGY;
        },
        generatePlan: async (id, payload) => {
          plans.push(payload);
          return PROJECT_WITH_STRATEGY;
        },
      },
      async () => {
        // The create path: the draft is created eagerly from profile + template
        // (ensureProject fires on selection), so the POST happens without a
        // manual button. Opening the template step is enough to trigger it.
        global.__SMOKE_PARAMS = "";
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
        await act(async () => {});

        // The update path: with a project already in hand, generating the plan
        // writes the draft again first. The plan button is on Review, which is
        // where the result is read — it was its own step holding one button.
        global.__SMOKE_PARAMS = "?project=p1";
        await mount(CreateVideo, {})(ctx);
        // Changing the goal first, so the draft genuinely needs rewriting.
        // ensureProject short-circuits when nothing the project carries has
        // moved, and a write that does not happen proves nothing about what it
        // would have sent.
        await openStep(ctx, "Audience & goal");
        const objectiveSelect = ctx.container.querySelector("#objective");
        const options = Array.from(objectiveSelect.options).filter((o) => o.value);
        const other = options.find((o) => o.value !== "address_user_problem");
        if (!other) throw new Error("no second objective to switch to");
        await selectOption(ctx, objectiveSelect, other.value);
        await openStep(ctx, "Review");
        const generate = [...ctx.container.querySelectorAll("button")]
          .find((b) => /^(Generate|Regenerate) (the )?plan/.test((b.textContent || "").trim()));
        if (!generate) throw new Error("Review offers no generate control");
        await act(async () => {
          generate.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
        global.__SMOKE_PARAMS = "";
      }
    );
    dom.window.confirm = originalConfirm;
    if (creates.length === 0) throw new Error("no project was created along the way");
    if (updates.length === 0) throw new Error("no project was updated along the way");
    if (plans.length === 0) throw new Error("no plan was generated along the way");
    const retired = ["duration_seconds", "extend_intent"];
    for (const [what, payloads] of [
      ["createStudioProject", creates],
      ["updateStudioProject", updates],
      ["generatePlan", plans],
    ]) {
      for (const payload of payloads) {
        for (const field of retired) {
          if (field in payload) {
            throw new Error(`${what} still sends ${field}: ${JSON.stringify(payload)}`);
          }
        }
      }
    }
  });

  // -------------------------------------------------------------------------
  // Landing page
  // -------------------------------------------------------------------------
  // The landing page advertises capabilities, so a claim that quietly stops
  // being true is the same class of defect as a panel that stops rendering â€”
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
    // There is no hook-length selector and no total length: the template
    // declares one and the render is that long in a single pass.
    expectAbsent(ctx, "Hooks run 2 to 6", "no hook length is chosen by hand");
    expectAbsent(ctx, "10, 15, 20 or 30 seconds", "no length picker is offered");
    expectAbsent(ctx, "one pass", "no render is described as a pass of a multi-pass plan");
    expectAbsent(ctx, "segment by segment", "a video is no longer built from segments");
    // The template library redirects to /create and has no favourite toggle.
    expectAbsent(ctx, "Favourite", "no favourite UI exists");
    // Rejection is recorded on swap; there is no reject control anywhere.
    expectAbsent(ctx, "Reject a template", "there is no reject button");
    // Trend aggregates now steer the strategy prompt, not only the research tab.
    expectAbsent(ctx, "Trend Research tab only", "trend data reaches generation now");

    // The chain. "One Continuous Clip" claimed a single clip carrying a hook
    // AND an ending, and the continuity block claimed each extension picked up
    // from the last. Both described a workflow with several separately-rendered
    // pieces and a seam between them; there is one render and no seam. One of
    // these strings sits in FLOW_STEPS, a screen above PIPELINE, so correcting
    // only the pipeline block would have left the claim on screen.
    expectAbsent(ctx, "Hook and ending arrive in a single vertical clip", "there is no generated ending");
    expectAbsent(ctx, "A second pass", "there is no second pass to stretch or replace a segment");
    expectAbsent(ctx, "Each Piece Picks Up the Last", "there are no separate pieces to pick up from");
    expectAbsent(ctx, "last frame becomes the next first frame", "the seam frame is not sent");
    expectAbsent(ctx, "picks up from the last frame", "the seam frame is not sent");
    expectAbsent(ctx, "written description of the scene", "there is no seam to describe around");
    expectAbsent(ctx, "may drift", "no clip can drift from another, because there is only one");
    // The honest replacements have to actually be there, or a future edit could
    // satisfy the checks above by deleting the claims outright. The handoff is
    // the disclosure that replaces the continuity claim: the generated video
    // stops on purpose, and what follows it is the founder's own footage.
    expectText(ctx, "The Middle Is Built to Stop", "the handoff is disclosed, not hidden");
    expectText(ctx, "You attach the demo", "the demo is described as the founder's own recording");
  });

  // The call to action and the product demo are the two things the generated
  // video does not contain, and both used to be advertised as features of it.
  await check("Landing does not promise a call to action or a generated demo", async (ctx) => {
    await mount(Landing)(ctx);
    // The acronym was the affordance on screen: an end-card badge, a "CTA
    // pattern" row, a close written into the copy. Spelling the phrase out to
    // say the close is the founder's own is honest and stays.
    expectAbsent(ctx, "CTA", "the acronym still appears as an offered capability");
    expectAbsent(ctx, "end card", "the server no longer composes an end card");
    expectAbsent(ctx, "end-card", "the server no longer composes an end card");
    expectAbsent(ctx, "ready to post", "the render is not a finished, postable video");
    expectAbsent(ctx, "No camera, no editor, no source footage", "the founder records the demo");
    expectAbsent(ctx, "skip the shoot", "the founder records the demo");
    // What the product actually delivers, and the handoff.
    expectText(ctx, "A hook, and a middle", "the two sections are not described as features");
    expectText(ctx, "You finish the video", "the assembly step is not described as the founder's");
    expectText(ctx, "Record your demo", "the demo is described as the founder's own recording");
  });

  // Every live route a tour can fire on, and the page component that route
  // serves. "/app-profiles/abc" stands in for the :id parameter; the assets
  // sub-route is listed separately because it must resolve to the same tour
  // as /assets while serving the same page as the library.
  const TOUR_ROUTE_PAGE = {
    "/": "pages/Landing.jsx",
    "/create": "pages/CreateVideo.jsx",
    "/brand": "pages/BrandSetup.jsx",
    "/assets": "pages/AssetLibrary.jsx",
    "/app-profiles/abc": "pages/AppProfileDetail.jsx",
    "/app-profiles/abc/assets": "pages/AssetLibrary.jsx",
    "/history": "pages/GenerationHistory.jsx",
  };
  const TOUR_LIVE_PATHS = Object.keys(TOUR_ROUTE_PAGE);

  // An onboarding tour is invisible when its targets are missing, because
  // TourOverlay advances silently past a target it cannot find — so a tour
  // pointing at a page that no longer exists passes every other gate, shows a
  // first-timer nothing, and still marks itself seen.
  //
  // So every target is resolved against the real source files, here. A renamed
  // testid or a moved page now fails the gate instead of quietly emptying the
  // tour.
  await check("every onboarding tour step points at a real element", async (ctx) => {
    const { TOURS, getTourIdForPath } = load("lib/onboarding/tours.js");
    const missing = [];

    const ROUTE_PAGE = TOUR_ROUTE_PAGE;
    const firstPath = (tourId) =>
      TOUR_LIVE_PATHS.find((p) => getTourIdForPath(p) === tourId);

    // The page plus everything it imports, so a target owned by a child
    // component still resolves.
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
  // before opening anything while still having marked the tour seen. Deleted
  // routes (/discover, /analysis/*, /bookmarks) must map to null — a stale
  // mapping here would auto-launch a tour for a page that no longer exists.
  await check("every routable path maps to a tour that exists", async (ctx) => {
    const { TOURS, getTourIdForPath } = load("lib/onboarding/tours.js");
    const paths = TOUR_LIVE_PATHS;
    const broken = paths
      .map((p) => [p, getTourIdForPath(p)])
      .filter(([, id]) => id !== null && !TOURS[id])
      .map(([p, id]) => `${p} -> "${id}", which is not a key in TOURS`);
    if (broken.length) throw new Error(broken.join("\n        "));
  });

  await check("deleted routes map to no tour", async (ctx) => {
    const { getTourIdForPath } = load("lib/onboarding/tours.js");
    for (const p of ["/discover", "/analysis/x", "/bookmarks", "/legacy-history"]) {
      if (getTourIdForPath(p) !== null) {
        throw new Error(`${p} still maps to a tour after the page was removed`);
      }
    }
  });

  // Every live work page must open a tour on arrival, and the auth/legal
  // pages must not. Without this, a page added to the router can silently
  // ship with no pop-up at all -- which is exactly how the studio and the
  // Asset Library went tour-less before the tours were rewritten.
  await check("every live work page maps to a tour (and auth/legal pages do not)", async (ctx) => {
    const { getTourIdForPath } = load("lib/onboarding/tours.js");
    // The home page is exempt, and named here rather than quietly filtered out
    // of TOUR_LIVE_PATHS, so the exemption is a visible decision instead of a
    // hole in the list. It had a five-step welcome tour that fired on every
    // arrival over marketing copy the visitor can simply read; see
    // getTourIdForPath in lib/onboarding/tours.js.
    const NO_TOUR = new Set(["/"]);
    const broken = [
      ...TOUR_LIVE_PATHS.filter((p) => !getTourIdForPath(p) && !NO_TOUR.has(p)).map(
        (p) => `${p} maps to no tour`
      ),
      ...[
        "/sign-in",
        "/sign-in/sso-callback",
        "/sign-up",
        "/privacy",
        "/terms",
        // Redirect-only routes: the destination page opens its own tour.
        "/app-profiles",
        "/analytics",
        "/templates",
        "/templates/t-1",
      ]
        .filter((p) => getTourIdForPath(p) !== null)
        .map((p) => `${p} maps to "${getTourIdForPath(p)}" but serves no page of its own`),
    ];
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

  console.log("");
  console.log("Mounting the App Profile detail page...");
  await runDeleteDialogChecks();

  console.log("");
  console.log("Checking the native Product Demo + CTA editor...");
  await runDemoCtaChecks();
}

/**
 * Deleting an App Profile.
 *
 * The endpoint, the cascade and the api client all existed before this control
 * did, and nothing called them — a delete path with no UI, which is worse than
 * no delete path, because the capability looks present in review. So these pin
 * the gate rather than the plumbing: the endpoint already has its own backend
 * tests for the cascade, the 404 and the in-flight 409.
 *
 * Type-to-confirm rather than window.confirm because the blast radius is the
 * profile's finished videos and recorded results, not one regenerable row.
A single * window.confirm on this would be the loosest destructive gate in the app, and
 * the page's own content-angle delete already sets that bar low enough.
 */
function mountProfileDetail() {
  global.__SMOKE_ROUTE_PARAMS = { profileId: "p1" };
  const AppProfileDetail = load("pages/AppProfileDetail.jsx").default;
  return (ctx) => mount(AppProfileDetail, {})(ctx);
}

async function runDeleteDialogChecks() {
  const PROFILE = {
    id: "p1",
    brand_name: "Threadly",
    brand_description: "One list, not eleven.",
    status: "approved",
  };

  const stubProfileApi = (extra = {}) => ({
    getAppProfile: async () => PROFILE,
    getContentAngles: async () => ({ angles: [{ id: "a1", label: "Confession" }] }),
    getStudioProjects: async () => ({ projects: [{ id: "s1", name: "Draft one" }] }),
    getProfileWhatWorks: async () => ({ videos: 3, top: [] }),
    getTemplateRecommendations: async () => ({ recommendations: [] }),
    ...extra,
  });

  async function openDialog(ctx) {
    // Purged before the click, not after: the portal this reads is the one the
    // click is about to create.
    //
    // Radix renders DialogContent through a portal into document.body, not
    // inside the mount container, so the dialog is never found under ctx. The
    // document is taken from the container rather than the global: a bare
    // `document` here resolves against whatever Node exposes, which is not
    // necessarily the one the portalled nodes were written into.
    //
    // The purge also matters because the harness unmounts roots only after the
    // last check. A check that mounts more than once — the copy checks do, one
    // per count — otherwise finds every earlier dialog still in the body and
    // reads the first one's stale contents.
    const doc = ctx.container.ownerDocument;
    doc.querySelectorAll('[data-testid="delete-profile-dialog"]').forEach((n) => n.remove());
    await clickEl(
      ctx,
      ctx.container.querySelector('[data-testid="delete-profile-button"]'),
      "the profile page offers no delete control"
    );
    const dialog = doc.querySelector('[data-testid="delete-profile-dialog"]');
    if (!dialog) throw new Error("the delete control did not open a confirmation");
    return dialog;
  }

  const confirmBtn = (scope) => scope.querySelector('[data-testid="delete-profile-confirm"]');

  await check("a profile cannot be deleted without typing its name", async (ctx) => {
    await withApi(stubProfileApi({ deleteAppProfile: async () => ({ deleted: true }) }), async () => {
      await mountProfileDetail()(ctx);
      const dialog = await openDialog(ctx);

      if (!confirmBtn(dialog).disabled) {
        throw new Error("the destructive button is live before anything is typed");
      }
      const input = dialog.querySelector('[data-testid="delete-confirm-input"]');
      await typeInto(ctx, input, "something else", "no name field in the dialog");
      if (!confirmBtn(dialog).disabled) {
        throw new Error("a wrong name armed the delete");
      }
      await typeInto(ctx, input, PROFILE.brand_name);
      if (confirmBtn(dialog).disabled) {
        throw new Error("the correct name did not arm the delete");
      }
    });
  });

  await check("deleting a profile calls the endpoint and leaves the page", async (ctx) => {
    let called = null;
    await withApi(
      stubProfileApi({
        deleteAppProfile: async (id) => {
          called = id;
          return { deleted: true, id, generations_removed: 3 };
        },
      }),
      async () => {
        global.__SMOKE_NAVIGATIONS = [];
        await mountProfileDetail()(ctx);
        const dialog = await openDialog(ctx);
        await typeInto(ctx, dialog.querySelector('[data-testid="delete-confirm-input"]'), PROFILE.brand_name);
        await clickEl(ctx, confirmBtn(dialog), "no enabled confirm button");
        await act(async () => {});
        if (called !== PROFILE.id) {
          throw new Error(`deleteAppProfile was called with ${JSON.stringify(called)}`);
        }
        // The profile list page is gone, so "Your app" is the only landing.
        const went = global.__SMOKE_NAVIGATIONS || [];
        if (!went.includes("/brand")) {
          throw new Error(`expected to land on /brand, navigated to ${JSON.stringify(went)}`);
        }
      }
    );
  });

  await check("a refused delete keeps the dialog open and shows why", async (ctx) => {
    // The backend refuses while a generation is in flight and the message is
    // already written for a founder. If that message were routed to the page's
    // own error state it would render above a modal the founder cannot see
    // through, and the button would look simply broken.
    await withApi(
      stubProfileApi({
        deleteAppProfile: async () => {
          const err = new Error("refused");
          err.response = { data: { detail: "This profile has a generation still running." } };
          throw err;
        },
      }),
      async () => {
        await mountProfileDetail()(ctx);
        const dialog = await openDialog(ctx);
        await typeInto(ctx, dialog.querySelector('[data-testid="delete-confirm-input"]'), PROFILE.brand_name);
        await clickEl(ctx, confirmBtn(dialog), "no enabled confirm button");
        await act(async () => {});
        // The error renders inside the portalled dialog, so scope to it —
        // ctx.container never contains portal content.
        const shown = dialog.querySelector('[data-testid="delete-profile-error"]');
        if (!shown) throw new Error("the refusal was swallowed and the dialog closed");
        if (!(shown.textContent || "").includes("generation still running")) {
          throw new Error(`the backend's reason never reached the founder: ${shown.textContent}`);
        }
      }
    );
  });

  await check("an unnamed profile still has to be confirmed", async (ctx) => {
    // brand_name is optional on a researched draft. Without the "Untitled app"
    // fallback the required string is "", which the empty input matches, so the
    // destructive button would start live the moment the dialog opened.
    await withApi(
      stubProfileApi({
        getAppProfile: async () => ({ ...PROFILE, brand_name: "" }),
        deleteAppProfile: async () => ({ deleted: true }),
      }),
      async () => {
        await mountProfileDetail()(ctx);
        const dialog = await openDialog(ctx);
        if (!confirmBtn(dialog).disabled) {
          throw new Error("an unnamed profile armed the delete with nothing typed");
        }
        await typeInto(ctx, dialog.querySelector('[data-testid="delete-confirm-input"]'), "Untitled app");
        if (confirmBtn(dialog).disabled) {
          throw new Error("the fallback name did not arm the delete");
        }
      }
    );
  });

  // One check per count rather than a loop inside one check: re-rendering the same
  // root with the same component does not remount it, so a looped check would
  // carry the previous case's state into the next and read a stale dialog.
  const copyCases = [
    { drafts: 0, angles: 0, videos: 0, want: "every uploaded photo" },
    { drafts: 1, angles: 0, videos: 0, want: "1 video draft and every uploaded photo" },
    {
      drafts: 3,
      angles: 2,
      videos: 0,
      want: "3 video drafts, 2 content angles and every uploaded photo",
    },
    {
      drafts: 3,
      angles: 0,
      videos: 3,
      want: "3 video drafts, history from 3 recorded videos and every uploaded photo",
    },
  ];

  for (const c of copyCases) {
    // The counts are the point: a founder cannot tell a profile they forgot
    // about from one that made six videos, and the videos are the finished
    // work they cannot get back. Punctuation has to hold at zero too — an
    // earlier version spread
    // ternaries through the JSX and read "everything built on it: every
    // uploaded photo" for a profile with three drafts on it.
    await check(
      `the delete warning names what is lost (${c.drafts} drafts, ${c.angles} angles, ${c.videos} recorded)`,
      async (ctx) => {
        await withApi(
          stubProfileApi({
            getStudioProjects: async () => ({
              projects: Array.from({ length: c.drafts }, (_, i) => ({ id: `s${i}` })),
            }),
            getContentAngles: async () => ({
              angles: Array.from({ length: c.angles }, (_, i) => ({ id: `a${i}` })),
            }),
            getProfileWhatWorks: async () => ({ videos: c.videos, top: [] }),
          }),
          async () => {
            await mountProfileDetail()(ctx);
            const dialog = await openDialog(ctx);
            const text = (dialog.textContent || "").replace(/\s+/g, " ");
            if (!text.includes(c.want)) {
              throw new Error(`expected ${JSON.stringify(c.want)} in: ${text.slice(0, 240)}`);
            }
          }
        );
      }
    );
  }
}

/**
 * The optional Product Demo + CTA step.
 *
 * It is additive by construction, and these pin that rather than the feature.
 * The studio's own finish line is the download above the new block; if the new
 * block could remove, reorder or replace that, the panel would no longer be
 * "optional" in any sense that matters to a founder who wanted none of it.
 */
async function runDemoCtaChecks() {
  // The native editor, not a handoff. These pin the new contract: the studio
  // links into /demo-cta/:id, the picker lists finished renders, nothing opens
  // a popup and nothing listens for cross-origin messages.

  const COMPLETED = {
    ...SEGMENT,
    id: "gen-1",
    status: "completed",
    video_url: "/api/media/videos/gen-1.mp4",
    r2_url: null,
  };

  async function mountStudio(ctx) {
    // Mounted directly rather than through the wizard, like the other
    // GenerationPanel checks: the block under test only renders for a finished
    // render, and reaching that through the wizard would be testing navigation
    // instead of this.
    await withApi(
      {
        getGenerations: async () => ({ generations: [COMPLETED] }),
      },
      async () => {
        await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
      }
    );
  }

  async function mountPicker(ctx, generations) {
    await withApi(
      {
        getGenerationHistory: async () => ({ generations }),
      },
      async () => {
        await mount(DemoCtaStudio, {})(ctx);
      }
    );
  }

  await check(
    "a finished render offers the native Demo + CTA editor",
    async (ctx) => {
      await mountStudio(ctx);
      const open = [...ctx.container.querySelectorAll("a")].find((a) =>
        (a.textContent || "").includes("Open in Demo + CTA")
      );
      if (!open) {
        throw new Error(
          "no native entry into the Demo + CTA editor on a finished render. " +
            "The render is done and the editor exists, so a missing link means " +
            "the panel regressed to render-only."
        );
      }
    }
  );

  await check(
    "the studio's own download is untouched by the native entry",
    async (ctx) => {
      await mountStudio(ctx);
      const download = [...ctx.container.querySelectorAll("a")].find((a) =>
        (a.textContent || "").includes("Download MP4")
      );
      if (!download) throw new Error("the studio's own download is gone");
      if (!download.getAttribute("href")?.includes("/api/media/videos/")) {
        throw new Error(`the download points somewhere else: ${download.getAttribute("href")}`);
      }
    }
  );

  await check(
    "no popup, opener or cross-origin message contract remains in the studio",
    async (ctx) => {
      await mountStudio(ctx);
      const html = ctx.container.innerHTML;
      for (const needle of [
        "hookforge:demo-cta-finished",
        "Continue to Product Demo + CTA",
        "Bringing your video back",
      ]) {
        if (html.includes(needle)) {
          throw new Error(
            `handoff leftover still rendered: ${needle}. The editor is native ` +
              "now; a popup or message listener here means the old architecture came back."
          );
        }
      }
    }
  );

  await check(
    "the Demo + CTA page lists finished renders and opens each in the editor",
    async (ctx) => {
      await mountPicker(ctx, [COMPLETED]);
      // By text, not testid: the harness shims Link down to a bare anchor and
      // drops every prop but children, so a testid placed on the link cannot
      // survive the mount. Text is what the founder reads anyway.
      const open = [...ctx.container.querySelectorAll("a")].find((a) =>
        (a.textContent || "").includes("Open in editor")
      );
      if (!open) {
        throw new Error(
          "the page does not list the finished render. With no entry point, " +
            "the sidebar link is a dead end."
        );
      }
    }
  );

  await check(
    "Demo + CTA works on its own, without a Hook + Middle",
    async (ctx) => {
      await mountPicker(ctx, []);
      // The whole point of the sidebar entry: no generation, no finished render,
      // and the editor is still there with a file picker as its input.
      const input = ctx.container.querySelector('[data-testid="demo-cta-file-input"]');
      if (!input) {
        throw new Error(
          "no file input on the standalone editor. Requiring a Hook + Middle first " +
            "would make this unreachable for anyone who just wants to wrap their own clip."
        );
      }
      // And it must not nag about a missing render, because none is needed.
      if (ctx.text().includes("No finished render yet")) {
        throw new Error(
          "the standalone editor still claims a render is required, which is no longer true"
        );
      }
      if (ctx.text().includes("Finish recording")) {
        throw new Error("the export is gated on a render that was never made");
      }
    }
  );

  await check(
    "the preview column is pinned, and the settings column is what scrolls",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const html = ctx.container.innerHTML;
          // The regression this exists for: sticky had been on the preview card,
          // which is bounded by its own column and therefore travelled almost
          // nothing, so the video scrolled away with the page.
          if (!/lg:sticky/.test(html)) {
            throw new Error(
              "nothing in the preview column is sticky. Sticky belongs on the column " +
                "itself, not on the preview card inside it — a sticky card is bounded " +
                "by that column and scrolls away with the page."
            );
          }
          if (!/overflow-y-auto/.test(html)) {
            throw new Error(
              "the settings column does not scroll independently. Without its own " +
                "scroll container the whole page scrolls and the two columns cannot " +
                "be peers."
            );
          }
        }
      );
    }
  );

  await check(
    "which settings groups are open is remembered across visits",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      const key = "hookforge.demoCta.openSections.v2";
      dom.window.localStorage.removeItem(key);
      const mountEditor = async () => {
        // A fresh container per mount: `check` owns one, and creating a second
        // root on it warns and leaves the first tree mounted.
        const container = dom.window.document.createElement("div");
        dom.window.document.body.appendChild(container);
        const root = createRoot(container);
        roots.push(root);
        await act(async () => {
          root.render(React.createElement(DemoCtaEditor, { generation: COMPLETED }));
        });
        return { container, root };
      };
      try {
        // First visit: the defaults are Source & Look, Hook Text, End Card CTA open.
        // The duration value renders once, right-aligned in the label row — the
        // label itself carries no value, so "On screen" and "1.8s" are asserted
        // separately rather than as one string.
        const first = await mountEditor();
        const firstText = first.container.textContent;
        if (!firstText.includes("On screen") || !firstText.includes("1.8s")) {
          throw new Error("Hook Text did not start open on a first visit");
        }
        const hooks = [...first.container.querySelectorAll("button")].find(
          (b) => (b.textContent || "").trim() === "Hook Text"
        );
        if (!hooks) throw new Error("no Hook Text group header to click");
        await act(async () => {
          hooks.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        if (first.container.textContent.includes("On screen")) {
          throw new Error("clicking the Hook Text header did not collapse it");
        }
        const saved = JSON.parse(dom.window.localStorage.getItem(key) || "{}");
        if (saved.hook !== false) {
          throw new Error(
            `collapsing Hook Text was not written through (stored: ${JSON.stringify(saved)})`
          );
        }
        // Second visit must honour it.
        const second = await mountEditor();
        if (second.container.textContent.includes("1.8s")) {
          throw new Error(
            "Hook Text reopened on a later visit. The panel is a workspace, not a " +
              "form; re-collapsing the groups someone deliberately opened is the " +
              "friction that makes a tool feel like it forgot you."
          );
        }
        if (!second.container.textContent.includes("Choose a video") && !second.container.textContent.includes("Replace video file")) {
          throw new Error("Source & Look should still be open on the second visit");
        }
      } finally {
        dom.window.localStorage.removeItem(key);
      }
    }
  );

  await check(
    "the export action sits after the preview in the pinned column",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const html = ctx.container.innerHTML;
          const previewAt = html.indexOf("Live preview");
          const exportAt = html.indexOf("demo-cta-export");
          if (previewAt === -1 || exportAt === -1 || exportAt < previewAt) {
            throw new Error(
              "the export action is missing or precedes the preview. It must sit " +
                "below the preview and player in the pinned column so it stays " +
                "reachable without page scroll."
            );
          }
          // Fixed bar on small screens, sticky in-column on desktop. Either
          // class missing means one of the two viewports loses the button.
          // (Below 700px tall, index.css drops the desktop pin so the bar sits
          // in flow and the short column scrolls as one piece — the classes
          // stay so this still asserts the >=700px contract.)
          if (!/fixed inset-x-0 bottom-0/.test(html) || !/lg:sticky lg:bottom-4/.test(html)) {
            throw new Error(
              "the export bar is not fixed on mobile and sticky on desktop. One " +
                "of the two viewports scrolls it out of reach."
            );
          }
          // The frame sizes itself from the column height (70%, floored), not
          // from a fixed rem budget — the old `100vh-30rem` cap is what shrank
          // the video on laptop-height screens.
          if (!/demo-cta-frame/.test(html) || /100vh-30rem/.test(html)) {
            throw new Error(
              "the preview frame is not column-sized. The fixed-rem cap shrank " +
                "the video to fit the player instead of the player fitting " +
                "around the video."
            );
          }
        }
      );
    }
  );

  await check(
    "the player stacks scrubber, one control row, then export",
    async () => {
      // The player only mounts once a real clip supplies metadata, and jsdom
      // has no video pipeline — so no DOM here ever contains it. This asserts
      // the order in source instead: scrubber strip, then the single
      // transport + Zoom Lock row, then export. A row that drifted above the
      // scrubber or a player that drifted below export means the compact
      // layout regressed, and no render test would notice.
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      const order = [
        "demo-cta-player",
        "demo-cta-scrubber",
        "transport-play",
        '<span className="eyebrow">Zoom Lock</span>',
        "demo-cta-export",
      ].map((m) => src.indexOf(m));
      if (order.some((i) => i === -1)) {
        throw new Error("the player card, scrubber, transport, Zoom Lock, or export is missing from source");
      }
      if (!order.every((v, i, a) => i === 0 || a[i - 1] < v)) {
        throw new Error(
          "the player is out of order in source. Scrubber first, then the " +
            "single transport + Zoom Lock row, then export — anything else " +
            "pushes the frame or the button out of reach."
        );
      }
      if (/On screen:|0:00\.0 → \{formatTime\(duration\)\}|justify-between px-0\.5/.test(src)) {
        throw new Error(
          "a removed duplicate readout is back in the player. Time reads once, " +
            "in the control row — the scrubber strip carries no text."
        );
      }
      // Shared-width contract, part 1: the right column is fixed at xl to
      // whatever the single control row needs (~650px), so the player row
      // keeps the width it was measured against.
      if (!/xl:grid-cols-\[minmax\(0,1fr\)_650px\]/.test(src)) {
        throw new Error(
          "the right column is not fixed at xl. A fluid column lets the frame " +
            "budget and the cards drift apart, and the player row loses the " +
            "width it was measured against."
        );
      }
      // No-wrap binds at xl only, where the 650px column holds the row. Below
      // xl the row must still wrap rather than overflow a narrower column.
      if (!/flex flex-wrap items-center gap-x-1\.5 gap-y-2 xl:flex-nowrap/.test(src)) {
        throw new Error(
          "the control row is not wrap-below-xl / nowrap-at-xl. Always-nowrap " +
            "overflows narrow columns; always-wrap reintroduces the two-line " +
            "player the fixed column was measured to avoid."
        );
      }
      // The export button carries no padded desktop container: `lg:p-0` with
      // no `lg:px-4`. Its WIDTH now comes from the shared token (see below),
      // not from the column, so this only guards the padding.
      if (!/demo-cta-export[\s\S]*?lg:p-0/.test(src) || /demo-cta-export[\s\S]{0,400}?lg:px-4/.test(src)) {
        throw new Error(
          "the export button regained a padded desktop container. Its edges no " +
            "longer sit exactly on the preview frame's edges."
        );
      }
    }
  );

  await check(
    "the preview and the export button are chromeless and share one width",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      const css = fs.readFileSync(path.join(__dirname, "..", "src", "index.css"), "utf8");

      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const html = ctx.container.innerHTML;

          // Chromeless: the preview frame may not sit inside a `.surface` card again.
          // The preview card spent ~46px on a border and padding around a video
          // that needed all of it.
          if (/demo-cta-frame[\s\S]{0,400}?class="[^"]*\bsurface\b/.test(html)) {
            throw new Error(
              "the preview frame is inside a surface card again. The card's " +
                "border, background and padding are taken out of the frame's height."
            );
          }
          // One token, two consumers. This is what guarantees identical edges:
          // neither box can measure the other in CSS, so both read the same
          // variable, and the player bar deliberately does not.
          if (!/\.demo-cta-frame,\s*\n\s*\.demo-cta-export\s*\{[^}]*width: var\(--demo-cta-frame-w\)/.test(css)) {
            throw new Error(
              "the frame and the export button no longer resolve the same width " +
                "token. Two separate widths is exactly how they drifted apart."
            );
          }
          // The player is a plain bar, asserted in source: like the order check
          // below, it only mounts with a real clip's metadata, which jsdom
          // cannot supply, so a DOM query here would silently pass forever.
          if (!/<div className="space-y-2" data-testid="demo-cta-player">/.test(src)) {
            throw new Error(
              "the player is a card again. It must be a plain bar matching the " +
                "chromeless preview — a surface box under a chromeless frame."
            );
          }
          if (/data-testid="demo-cta-player"[\s\S]{0,200}?\bsurface\b/.test(src)) {
            throw new Error("the player picked up a surface class");
          }
          if (!/--demo-cta-chrome:\s*84px/.test(css) || !/data-player="on"\][\s\S]{0,120}?--demo-cta-chrome:\s*200px/.test(css)) {
            throw new Error(
              "the chrome budget lost its per-state values. Without a height " +
                "reserve for the player bar the frame is sized as though it were " +
                "never there."
            );
          }
          if (!/data-player=\{videoUrl && videoMeta \? "on" : "off"\}/.test(src)) {
            throw new Error(
              "the column no longer reports whether the player bar is present, so " +
                "the frame gets the wrong height budget."
            );
          }
          // The zoom-keyframe strip keeps its box when empty, so locking a zoom
          // cannot silently resize the video.
          if (/\{zoomKeyframes\.length > 0 && \(\s*\n\s*<div className="relative h-2/.test(src)) {
            throw new Error(
              "the zoom-keyframe strip is conditional again. It must keep its 8px " +
                "box when empty or the frame resizes the first time someone locks."
            );
          }
          // Frame floor: 253px wide is 450px tall at 9:16.
          if (!/max\(253px/.test(css)) {
            throw new Error(
              "the preview frame has no ~450px floor (253px wide at 9:16). Below " +
                "it the column must scroll rather than the frame shrinking further."
            );
          }
        }
      );
    }
  );

  await check(
    "swatches are fixed size and animation uses the app's chip",
    async () => {
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      // Three swatch groups: frame color, background, accent. All 40px and
      // fixed — a grid with `aspect-square` grew them with the settings column.
      const fixed = (src.match(/h-10 w-10 shrink-0/g) || []).length;
      if (fixed < 3) {
        throw new Error(
          `only ${fixed} of 3 swatch groups are fixed 40px. A stretchy grid makes ` +
            "a wider window silently grow every swatch."
        );
      }
      if (/aspect-square overflow-hidden rounded-lg/.test(src)) {
        throw new Error("the background swatches are still a stretchy aspect-square grid");
      }
      if ((src.match(/flex flex-wrap items-center gap-2/g) || []).length < 3) {
        throw new Error("the swatch rows are not flex-wrap with an 8px gap");
      }
      // Selected state has to be visible, and the ring must not use the default
      // white offset Tailwind applies on this dark theme.
      if (!/ring-2 ring-\[color:var\(--indigo-45\)\]/.test(src)) {
        throw new Error("the selected swatch lost its accent ring");
      }
      if (/ring-offset/.test(src)) {
        throw new Error(
          "a ring-offset is back. Tailwind's default offset colour is white, " +
            "which draws a white halo on this theme."
        );
      }
      // Animation is a segmented choice, so it uses the app's own Chip.
      if (!/import \{ Chip \} from "\.\.\/components\/Chip"/.test(src)) {
        throw new Error(
          "animation stopped using the app's Chip. It is a segmented choice, and " +
            "the hand-rolled row of borderless text buttons was the deviation."
        );
      }
      if (!/aria-label="Animation"[\s\S]{0,200}?grid grid-cols-2 gap-1\.5 xl:grid-cols-3/.test(src)) {
        throw new Error(
          "the animation chips are not 2-per-row below xl and 3 above. A bare " +
            "grid-cols-3 truncates labels at narrow widths."
        );
      }
      // The page must stay on the documented control radius. Matched inside a
      // className so the comment that documents the old value does not trip it.
      if (/className=[^>]*rounded-\[10px\]/.test(src)) {
        throw new Error(
          "a rounded-[10px] control is back. design_guidelines.md:124 fixes " +
            "control radii at rounded-xl."
        );
      }
    }
  );

  await check(
    "the settings panel scrolls on a slim bar that never overlaps a card",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      const css = fs.readFileSync(path.join(__dirname, "..", "src", "index.css"), "utf8");
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          if (!/demo-cta-panel-scroll/.test(ctx.container.innerHTML)) {
            throw new Error(
              "the settings panel does not use the slim scrollbar class. The " +
                "global rules give it a 10px bar with arrow buttons."
            );
          }
          if (!/demo-cta-panel-scroll\s*\{[^}]*scrollbar-width: thin[^}]*scrollbar-color: hsl\(228 12% 22%\) transparent/.test(css)) {
            throw new Error("the Firefox scrollbar properties are missing (scrollbar-width/color)");
          }
          if (!/\.demo-cta-panel-scroll::\-webkit-scrollbar\s*\{\s*width: 6px/.test(css)) {
            throw new Error("the webkit scrollbar is not 6px");
          }
          if (!/\.demo-cta-panel-scroll::\-webkit-scrollbar-thumb\s*\{[^}]*border-radius: 9999px/.test(css)) {
            throw new Error("the scrollbar thumb is not rounded");
          }
          if (!/\.demo-cta-panel-scroll::\-webkit-scrollbar-thumb:hover/.test(css)) {
            throw new Error("the scrollbar thumb does not brighten on hover");
          }
          // Chrome/Edge draw arrow buttons at the bar's ends; they have to go.
          if (!/\.demo-cta-panel-scroll::\-webkit-scrollbar-button\s*\{[^}]*display: none/.test(css)) {
            throw new Error(
              "the scrollbar arrow buttons are not suppressed. Chrome and Edge " +
                "draw them regardless of width."
            );
          }
          if (!/lg:pr-2\.5/.test(ctx.container.innerHTML)) {
            throw new Error(
              "the settings panel has no right padding for the bar. A 6px scroll " +
                "bar drawn over a card edge reads as a rendering bug."
            );
          }
        }
      );
    }
  );

  await check(
    "short viewports scroll the column instead of shrinking the frame",
    async () => {
      // jsdom has no viewport to shrink, so this asserts the contract in the
      // stylesheet: a ~400px frame floor and a static export below 700px tall.
      // Without both, a short laptop window either crushes the video or pins
      // the button over a column it no longer fits beside.
      const css = fs.readFileSync(
        path.join(__dirname, "..", "src", "index.css"),
        "utf8"
      );
      if (!/\.demo-cta-frame[\s\S]*?max\(253px/.test(css)) {
        throw new Error(
          "the preview frame has no ~450px floor (253px wide at 9:16). Below it " +
            "the column must scroll rather than the frame shrinking further."
        );
      }
      if (!/max-height:\s*699px[\s\S]*?\.demo-cta-export[\s\S]*?position:\s*static/.test(css)) {
        throw new Error(
          "the export bar has no short-viewport escape. Below 700px tall it " +
            "must sit in flow under the player so the column scrolls as one piece."
        );
      }
    }
  );

  await check(
    "group titles and slider labels read correctly",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const text = ctx.text();
          if (!text.includes("End Card CTA")) {
            throw new Error("the end-card group is mislabeled or missing");
          }
          // The value lives once, right-aligned in the label row. A label that
          // repeats it ("On screen: 1.8s") reads the same number twice.
          if (text.includes("On screen:")) {
            throw new Error("the hook duration value is shown twice: in the label and beside it");
          }
          if (!text.includes("1.8s")) {
            throw new Error("the hook duration value is missing from the label row");
          }
        }
      );
    }
  );

  await check(
    "History offers Demo + CTA on a finished clip",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, brand_name: "Test App", duration: 10 }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
          // A completed row mounts the variations panel's data fetch, which the
          // base stub does not carry.
          getVariationKinds: async () => ({ variations: [] }),
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          const entry = [...ctx.container.querySelectorAll("a")].find(
            (a) => (a.textContent || "").trim() === "Demo + CTA"
          );
          if (!entry) {
            throw new Error(
              "History does not offer Demo + CTA on a finished clip. Without it, a " +
                "clip you liked has no way onward except re-finding it in the studio."
            );
          }
        }
      );
    }
  );

  await check(
    "History does not offer Demo + CTA on a clip that is not finished",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, id: "gen-failed", status: "failed", video_url: null, error: "boom" }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          const entry = [...ctx.container.querySelectorAll("a")].find(
            (a) => (a.textContent || "").trim() === "Demo + CTA"
          );
          if (entry) {
            throw new Error(
              "Demo + CTA is offered on a failed render, which would open an editor " +
                "with no source to wrap"
            );
          }
        }
      );
    }
  );
}

function stepPill(ctx, label) {
  const pill = [...ctx.container.querySelectorAll("button")]
    .find((b) => (b.textContent || "").trim().includes(label));
  if (!pill) throw new Error(`no step nav control labelled ${JSON.stringify(label)}`);
  return pill;
}

/**
 * The one render control on the last step. *
 * Its label depends on whether a previous generation is on file - "Generate the
 * video" the first time, "Generate another" on a re-render, and "Generating..."
 * while one is in flight - so a check that clicks the render must match on the
 * family rather than one string, or it silently fails to find a button that is
 * right there.
 */
/** Find a button by its visible label, with the failure listing what was there. */
function buttonByText(ctx, pattern) {
  const btn = [...ctx.container.querySelectorAll("button")].find((b) =>
    pattern.test((b.textContent || "").trim())
  );
  if (!btn) {
    const seen = [...ctx.container.querySelectorAll("button")]
      .map((b) => (b.textContent || "").trim().slice(0, 45));
    throw new Error(`no button matching ${pattern}; saw ${JSON.stringify(seen)}`);
  }
  return btn;
}

function renderButton(ctx) {
  const btn = [...ctx.container.querySelectorAll("button")].find((b) =>
    /Generate the video|Generate another/.test((b.textContent || "").trim())
  );
  if (!btn) {
    const seen = [...ctx.container.querySelectorAll("button")]
      .map((b) => (b.textContent || "").trim().slice(0, 45));
    throw new Error(`no render control on the last step; saw ${JSON.stringify(seen)}`);
  }
  return btn;
}

/** Click through to a wizard step the way a founder would, then settle. */
async function openStep(ctx, label) {
  const pill = stepPill(ctx, label);
  await act(async () => {
    pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  await act(async () => {});
}

/**
 * Reach the template step the way the workflow now requires.
 *
 * The objective is required, and the template step refuses to show a ranked
 * list without one - which is correct, since the objective is the heaviest
 * signal in the score and the list would otherwise look identical while being
 * ranked on much weaker evidence. So every check about the template cards has to
 * set one first, exactly as a founder must.
 */
async function openTemplateStep(ctx) {
  await openStep(ctx, "Audience & goal");
  const select = ctx.container.querySelector("#objective");
  if (!select) throw new Error("no objective control on the Audience step");
  const first = select.querySelector("option[value]:not([value=''])");
  if (!first) throw new Error("the objective control has no objectives to pick");
  await selectOption(ctx, select, first.value);
  await openStep(ctx, "Template & photo");
}

/** Click an element the way a person would, so React's onClick fires. */
async function clickEl(ctx, el, why) {
  if (!el) throw new Error(why || "nothing to click");
  await act(async () => {
    el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  await act(async () => {});
}

/**
 * Set a text input the way a person would, so React's onChange fires.
 *
 * Assigning `.value` directly does not notify React of a change — React
 * installs its own value setter on the prototype and tracks the last value it
 * wrote, so a plain assignment is swallowed and the state never moves.
 */
async function typeInto(ctx, input, text, why) {
  if (!input) throw new Error(why || "no input to type into");
  const setter = Object.getOwnPropertyDescriptor(
    dom.window.HTMLInputElement.prototype, "value"
  ).set;
  await act(async () => {
    setter.call(input, text);
    input.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
  });
  await act(async () => {});
}

/** Swap api stub methods for the duration of one check, then restore them. */
async function withApi(overrides, fn) {
  const originals = {};
  for (const [name, impl] of Object.entries(overrides)) {
    originals[name] = apiStub[name];
    apiStub[name] = (...args) => {
      apiCalls.push(name);
      return impl(...args);
    };
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
    // a "not wrapped in act" warning â€” noise in a gate is noise people learn to
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
    // A throw outside a check â€” a fixture that no longer matches the API, say.
    // Must fail loudly: a harness that dies quietly is a gate that is green
    // because it never ran.
    console.log("");
    console.log("  [FAIL] the harness itself threw before reporting results");
    console.log(`         ${err && err.stack ? err.stack : String(err)}`);
    process.exit(1);
  });


