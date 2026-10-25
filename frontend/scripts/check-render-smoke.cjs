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


/**
 * Find JSX text nodes that contain comment syntax, across every source file.
 *
 * This exists because a real defect shipped that this file could not see. An
 * editing pass replaced a SectionCard close tag and its opening comment marker
 * but left the comment's *closing lines* behind as raw text between elements.
 * Raw text between JSX elements is valid, so `npm run build` compiled it, every
 * render check passed, and the page rendered the comment's prose — comment
 * markers and all — as visible copy.
 *
 * Mounting catches this only for components this file happens to mount, and
 * only for the branch each fixture reaches. Parsing every file catches it
 * everywhere: a `JSXText` node with non-whitespace content is by definition
 * something the browser will show, and if that content looks like a comment
 * then a comment lost its braces. Whitespace-only JSXText is normal (JSX drops
 * the newlines and indentation between elements) and is skipped.
 */
function findLeakedJsxText() {
  const leaks = [];
  const walk = (dir) =>
    fs.readdirSync(dir, { withFileTypes: true }).flatMap((entry) => {
      const full = path.join(dir, entry.name);
      return entry.isDirectory() ? walk(full) : [full];
    });

  for (const file of walk(SRC)) {
    if (!/\.(jsx|js)$/.test(file)) continue;
    const code = fs.readFileSync(file, "utf8");
    const ast = babel.parseSync(code, {
      filename: file,
      babelrc: false,
      configFile: false,
      parserOpts: { plugins: ["jsx"] },
    });
    const visit = (node) => {
      if (!node || typeof node !== "object") return;
      if (Array.isArray(node)) {
        node.forEach(visit);
        return;
      }
      if (node.type === "JSXText" && node.value.trim()) {
        const SLASH = String.fromCharCode(47);
        if (node.value.includes(SLASH + "*") || node.value.includes("*" + SLASH)) {
          leaks.push(
            `${path.relative(SRC, file)}:${node.loc.start.line} ` +
              JSON.stringify(node.value.trim().slice(0, 60))
          );
        }
      }
      for (const key of Object.keys(node)) {
        if (key !== "loc") visit(node[key]);
      }
    };
    visit(ast.program);
  }
  return leaks;
}

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
  content_angle_id: "a1",
  strategy_summary: "Open on the misdiagnosis, then correct it.",
  audience_problem: "Too many things to hold at once.",
  emotional_triggers: ["recognition", "relief"],
  messaging_pillars: ["one thing at a time"],
  primary_feature: "Task timer",
  desired_outcome: "A finished day.",
  mechanism_beat: "It counts the time for you instead of you counting it.",
  payoff_beat: "Tomorrow looks like one list, not nine.",
  differentiation_beat: "Others track time; this finishes tasks.",
  scene: { camera_angle: "eye level", lighting: "morning window" },
  performance: { movement: "still", voice_delivery: "unhurried" },
  segments: [
    { index: 0, role: "hook", seconds: 3, goal: "stop the scroll", script: "You do not have a focus problem.", action: "look up" },
    { index: 1, role: "middle", seconds: 7, goal: "develop it, stop at the reach", script: "You have too many lists.", action: "count on fingers" },
  ],
  objective: "address_user_problem",
  content_angle_id: "a1",
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
// merged choosing step.
//
// No start/end, no audio_role, no audio_gain. Those fields are still accepted
// on the wire for legacy rows, but the studio no longer renders a control for
// any of them: the video is one render with no compositing at all, so an
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
  outcome: "Hears what they thought was wrong named out loud, then stays for the correction.",
  opening_structure: "Open by naming what they think is wrong.",
  middle_structure: "Then correct it, and stop at the reach for the phone.",
  visual_style: "Talking head.",
  camera_pacing: "Steady.",
  content_slots: { app_feature: "Task timer" },
  required_assets: ["character_reference"],
  default_duration: 15,
  hook_seconds: 3,
  is_usable: true,
};

const ANGLE = {
  id: "a1",
  kind: "problem_solution",
  label: "Too many lists",
  user_problem: "Nothing gets finished.",
  target_audience: "busy professionals",
};

const ANGLE_B = {
  id: "a2",
  kind: "feature_demonstration",
  label: "One-tap timer",
  user_problem: "Starting takes too many steps.",
  target_audience: "busy professionals",
};

const ANGLE_GOALS = {
  problem_solution: ["address_user_problem", "feel_seen_and_understood", "avoid_common_mistake", "create_curiosity", "ease_daily_moment", "educate_viewers"],
  feature_demonstration: ["demonstrate_feature", "explain_app", "achieve_desired_outcome", "educate_viewers", "create_curiosity", "ease_daily_moment"],
};
const OBJECTIVE_OUTCOMES = {
  address_user_problem: "Gets them naming the problem out loud",
  feel_seen_and_understood: "Makes them feel described, not sold to",
  avoid_common_mistake: "Catches them before the mistake",
  create_curiosity: "Leaves them wanting the answer",
  ease_daily_moment: "Makes the daily moment feel lighter",
  demonstrate_feature: "Keeps them watching long enough to see it work",
  explain_app: "Walks them into what the app is without a feature list",
  achieve_desired_outcome: "Shows the outcome as reachable",
  educate_viewers: "Leaves them with one thing they got wrong",
};

// template_library.SUPPORTED_DURATIONS. Every one of them is a single render on
// the only studio-eligible model, which is why the length control is gone: there
// is nothing for the founder to choose that would not need a second pass.
const SUPPORTED_DURATIONS = [8, 10, 12, 15];

const apiStub = {
  recordFeedback: async () => ({}),
  getStudioVideoModels: async () => ({ default: "minimax-h3", models: [CAPABILITY] }),
  getGenerations: async () => ({ generations: [SEGMENT] }),
  pollGeneration: async () => SEGMENT,
  getTemplates: async () => ({ templates: [TEMPLATE] }),
  getTemplateFacets: async () => ({
    objectives: [
      "address_user_problem", "feel_seen_and_understood", "avoid_common_mistake",
      "create_curiosity", "ease_daily_moment", "demonstrate_feature", "explain_app",
      "achieve_desired_outcome", "educate_viewers",
    ],
    angle_goal_recommendations: ANGLE_GOALS,
    objective_outcomes: OBJECTIVE_OUTCOMES,
    supported_durations: SUPPORTED_DURATIONS,
    // Shaped like the real server response, which derives the per-duration
    // render count from the default studio model's single-pass ceiling
    // (CAPABILITY.max_duration above). All four are one render.
    duration_segments: { 8: 1, 10: 1, 12: 1, 15: 1 },
  }),
  getAppProfiles: async () => ({ profiles: [PROFILE] }),
  // Empty by default: History and Analytics verify draft links against the
  // live list, and an unverified list fails open to the draft link — the
  // behavior every pre-verification check asserts. Checks that exercise the
  // verified paths override this with the drafts their fixtures name.
  getStudioProjects: async () => ({ projects: [] }),
  getContentAngles: async () => ({ angles: [ANGLE, ANGLE_B] }),
  // Empty by default: the base stub has angles, so this only answers checks
  // that override the read to empty and then exercise the generate button.
  generateContentAngles: async () => ({ angles: [] }),
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
  // the eager create adopts and which hides the auto-generation this suite
  // is about behind a plan the founder never wrote.
  createStudioProject: async () => ({ ...BASE_PROJECT }),
  updateStudioProject: async () => PROJECT_WITH_STRATEGY,
  detachAsset: async () => BASE_PROJECT,
  getProjects: async () => ({ projects: [] }),
  getAssets: async () => ({ assets: [] }),
  uploadAsset: async () => ({ asset: null }),
  generatePlan: async () => PROJECT_WITH_STRATEGY,
  generateStrategy: async () => PROJECT_WITH_STRATEGY,
  generateVideo: async () => SEGMENT,
  // The drawer revalidates votes on every expand, so the detail endpoint
  // must answer everywhere the list does. Empty verdicts by default, exactly
  // like a render nobody rated; checks with rated rows override this with
  // their own saved state.
  getGeneration: async (id) => ({ id, verdicts: {} }),
  retryGeneration: async () => SEGMENT,
  markProjectReady: async () => PROJECT_WITH_STRATEGY,
  recordSignal: () => {},
};

/**
 * Every API method the UI called, and every retired one it tried to call.
 *
 * Two separate lists because they defend different things. `apiCalls` is a
 * record: it lets a check assert that a branch fired the request it was supposed
 * to. `retiredCalls` is a trap: the methods the server deleted are not on
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
  "composeOverlays",
  "getOverlayComposition",
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
// Resolver cache + module loader (uses real babel transpilation)
// ---------------------------------------------------------------------------
const importMap = new Map();
const resolveCache = new Map();

// The smoke check mounts real components from this project, so it must call
// the same module loader the app's toolchain resolves. A fresh `require` for
// every mount would be correct in isolation but slow on a checkout this size;
// caching by resolved file path keeps the suite practical without weakening
// what is being asserted.
function resolve(name) {
  if (!resolveCache.has(name)) {
    const resolved = require.resolve(name, { paths: [SRC] });
    resolveCache.set(name, resolved);
  }
  return resolveCache.get(name);
}

function createTranspiledModule(resolvedPath, code) {
  const module = { exports: {} };
  const wrapped =
    `(() => { return {
  id: ${JSON.stringify(resolvedPath)},
  exports: module.exports,
  hot: __hot__,
  filename: ${JSON.stringify(resolvedPath)},
},` +
    babel.transformSync(code, {
      filename: resolvedPath,
      babelrc: false,
      configFile: false,
      parserOpts: { plugins: ["jsx"] },
      sourceType: "module",
      ast: false,
      code: true,
    }).code +
    `})()`;
  return wrapped;
}

function importModule(specifier) {
  if (importMap.has(specifier)) return importMap.get(specifier);
  if (importMap.size > 800) {
    throw new Error(
      "too many distinct imports resolved while loading the smoke graph — " +
        "a dependency is importing far more modules than the file being mounted " +
        "should need, so this check refuses to load silently"
    );
  }
  const resolved = resolve(specifier);
  if (importMap.has(resolved)) return importMap.get(resolved);
  let code;
  try {
    code = fs.readFileSync(resolved, "utf8");
  } catch {
    throw new Error(
      `cannot read ${specifier} as ${resolved} — the smoke harness can only load `
        + "modules that exist on disk"
    );
  }
  let compiled;
  if (resolved.endsWith(".jsx") || resolved.endsWith(".js")) {
    compiled = createTranspiledModule(resolved, code);
  } else {
    // Plain .json/.node/else: fall back to a real require so the harness does
    // not silently fake a dependency it cannot represent.
    compiled = require(resolved);
  }
  importMap.set(resolved, compiled);
  importMap.set(specifier, compiled);
  return compiled;
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

/**
 * The durable-source rule, evaluated from the real src/lib/api.js.
 *
 * The History and Demo + CTA checks mount against a stubbed `lib/api`, so a
 * component would happily render from a copy of this rule that no longer
 * matches what ships — and this is the rule that decides whether a clip plays
 * at all. The function is read out of the source and evaluated, the same
 * approach check-frontend-logic.cjs takes for videoLength.js and for the same
 * reason: the assertion must be about the shipped code. A shape it cannot read
 * is a failure, not a skip, because otherwise the mounts below would pass
 * against a stub that has drifted.
 */
const durableMediaUrl = (() => {
  const source = fs.readFileSync(path.join(SRC, "lib", "api.js"), "utf8");
  // Located by its declaration and its closing brace rather than by a pattern:
  // a regex over source is one escaping mistake away from matching nothing while
  // looking correct, and a silent no-match would leave every mount below
  // asserting against an `undefined` import.
  const start = source.indexOf("export const durableMediaUrl = (row) => {");
  const end = start === -1 ? -1 : source.indexOf("};", start);
  if (start === -1 || end === -1) {
    throw new Error(
      "durableMediaUrl could not be read out of src/lib/api.js, so the durable-copy " +
        "checks would be asserting against a stub instead of the shipped rule"
    );
  }
  const decl = source.slice(start, end + 2).replace("export ", "");
  // eslint-disable-next-line no-new-func
  return new Function("mediaUrl", `${decl} return durableMediaUrl;`)((mediaPath) => mediaPath);
})();

// The saved-vote highlight must also be the shipped implementation: it maps a
// generation's server-attached verdicts onto the pressed thumb, so the
// restore checks below assert the rule that actually ships.
const verdictFor = (() => {
  const source = fs.readFileSync(path.join(SRC, "lib", "feedback.js"), "utf8");
  const start = source.indexOf("export function verdictFor(verdicts, component) {");
  const end = start === -1 ? -1 : source.indexOf("\n}", start);
  if (start === -1 || end === -1) {
    throw new Error(
      "verdictFor could not be read out of src/lib/feedback.js, so the thumb-restore " +
        "checks would be asserting against a stub instead of the shipped rule"
    );
  }
  const decl = source.slice(start, end + 2).replace("export ", "");
  // eslint-disable-next-line no-new-func
  return new Function(`${decl} return verdictFor;`)();
})();

// The History download helper must also be the shipped implementation: it
// chooses the signed same-origin download route rather than reusing a
// cross-origin playback href.
const downloadMediaUrl = (() => {
  const source = fs.readFileSync(path.join(SRC, "lib", "api.js"), "utf8");
  const start = source.indexOf("export const downloadMediaUrl = (row) => {");
  const end = start === -1 ? -1 : source.indexOf("};", start);
  if (start === -1 || end === -1) {
    throw new Error(
      "downloadMediaUrl could not be read out of src/lib/api.js, so the History " +
        "checks would be asserting against a stub instead of the shipped rule"
    );
  }
  const decl = source.slice(start, end + 2).replace("export ", "");
  // eslint-disable-next-line no-new-func
  return new Function(
    "mediaUrl",
    "durableMediaUrl",
    `${decl} return downloadMediaUrl;`
  )((mediaPath) => mediaPath, durableMediaUrl);
})();

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
        Link: ({ children, to, ...props }) => React.createElement("a", { ...props, href: to }, children),
        useNavigate: () => (...args) => {
          // Rest params, not `arguments`: arrows do not bind their own, so
          // `arguments` here would leak the requireShim spec string instead
          // of the navigated path.
          if (global.__SMOKE_NAVIGATIONS) global.__SMOKE_NAVIGATIONS.push(...args);
          global.__SMOKE_ROUTE_CHANGE?.(args[0]);
        },
        useSearchParams: () => [searchParams(), () => {}],
        // The embedded AssetLibrary on the Assets step reads the route, so a
        // deep link that lands there needs these to exist. Overridable for a
        // page that renders off a route param: AppProfileDetail is driven
        // entirely by :profileId, so with an empty object it would fetch under
        // `undefined` and settle on its error state, and its delete dialog
        // could never be exercised.
        useParams: () => global.__SMOKE_ROUTE_PARAMS || {},
        // Hash rides alongside for #generation- deep links: History opens the
        // named render on load, and without this the mount would always read
        // "no hash" no matter what the check asked for.
        useLocation: () => ({ pathname: global.__SMOKE_PATHNAME || "/create", search: searchParams().toString(), hash: global.__SMOKE_HASH || "" }),
      };
    }
    // Exercise the real AuthControls branches without contacting Clerk or
    // changing the shipped configuration. Only landing auth-state checks use this.
    if (global.__SMOKE_LANDING_AUTH && spec.endsWith("lib/clerk")) {
      return { isClerkConfigured: global.__SMOKE_LANDING_AUTH !== "no-auth" };
    }
    if (global.__SMOKE_LANDING_AUTH && spec === "@clerk/clerk-react") {
      const trigger = (kind) => ({ children }) => React.cloneElement(children, {
        onClick: () => global.__SMOKE_AUTH_ACTIONS.push(kind),
      });
      return {
        SignedIn: ({ children }) => global.__SMOKE_LANDING_AUTH === "signed-in" ? children : null,
        SignedOut: ({ children }) => global.__SMOKE_LANDING_AUTH === "signed-out" ? children : null,
        SignInButton: trigger("sign-in"),
        SignUpButton: trigger("sign-up"),
        UserButton: () => React.createElement("button", { "aria-label": "Account" }, "Account"),
      };
    }
    if (spec === "sonner") {
      // Mirror the real toast surface the research flows use: loading toasts
      // resolve in place by id, and dismiss retires one. A mock missing
      // either would turn every loading toast into a crash rather than a
      // tested path.
      const calls = [];
      const toast = (message) => {
        calls.push(message);
        return calls.length;
      };
      toast.success = (message, opts) => { calls.push(message); return opts?.id ?? calls.length; };
      toast.error = (message, opts) => { calls.push(message); return opts?.id ?? calls.length; };
      toast.loading = toast;
      toast.dismiss = () => {};
      return { toast };
    }
    if (spec.endsWith("lib/api") || (abs === path.join(SRC, "lib", "feedback.js") && spec === "./api")) {
      // Mirror the real getErrorMessage: checks assert on the surfaced text
      // (e.g. a 409's detail), and a constant would swallow it. mediaUrl is
      // identity because these mounts are about which URL is chosen, not about
      // the backend prefix. durableMediaUrl is the real function, evaluated
      // from source above, so the History checks cannot pass against a stub
      // that no longer matches the shipped rule.
      return {
        api: apiStub,
        getErrorMessage: (err) =>
          err?.response?.data?.detail || err?.message || "error",
        mediaUrl: (p) => p,
        durableMediaUrl,
        downloadMediaUrl,
      };
    }
    if (spec.endsWith("lib/feedback")) {
      // recordThumb must mirror the real module: CreateVideo's review loop
      // calls it unguarded, so a stub without it turns every thumbs tap into
      // a TypeError and no check could ever exercise the loop. verdictFor is
      // the shipped implementation, evaluated above, because it decides which
      // thumb renders pressed on a revisited render.
      return {
        recordSignal: () => {},
        recordThumb: async (step, verdict, refs) => {
          (global.__SMOKE_THUMBS = global.__SMOKE_THUMBS || []).push({ step, verdict, refs });
          return load("lib/feedback.js").recordThumb(step, verdict, refs);
        },
        verdictFor,
        classifyScriptEdit: () => ({ kind: "other" }),
      };
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
  } finally {
    // End each check's effects while its own stub scope is settled; mounted
    // roots otherwise keep polling and updating during unrelated checks.
    await act(async () => { root.unmount(); });
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
const { OnboardingProvider } = load("components/onboarding/OnboardingProvider.jsx");
const { HistoryFeedback } = load("components/HistoryFeedback.jsx");

// The shipped order, in the order the founder walks it. Asserted as a whole
// sequence rather than a set: the point of the reorder is that the free, claim-
// checked plan comes before the step that calls the model, and a set comparison
// would pass just as happily if the render went back to fourth.
//
// The last step is "Review & submit" rather than "Hook + Story" because that is
// what it holds: the free, claim-checked plan above and the one render it
// approves below. The old label named only the output; a step called
// "Hook + Story" whose first job is reading words understated the read that
// must come before any model call. "Story" replaced "middle" on request: the
// section is the narrative that carries the viewer to the demo, which is what
// the founder recognises it as, and "middle" reads as filler between two more
// interesting things.
// Three, not seven. "Assets" was a step whose only content was the photo upload,
// and "Creative plan" was a step whose only content was a button whose result
// you had to go to the next screen to read. Both are now part of the step they
// belonged to; then angle, goal, template and photo merged into one choosing
// screen and plan and render merged into one reviewing screen. So the founder
// picks a template and attaches the photo without leaving, chooses everything
// the ranking needs before seeing it, and presses Generate on the same page
// that shows the plan it renders.
//
// The order still matters and is still asserted as a whole sequence: the
// free, claim-checked plan is read before the step that calls the model, and a// comparison would pass just as happily if the render went back to third.
const STEP_LABELS = [
  "App Profile",
  "Audience & template",
  "Review & submit",
];


const stepSource = fs.readFileSync(path.join(SRC, "pages", "CreateVideo.jsx"), "utf8");

async function main() {
  await check("no source file leaks JSX comment text into the page", async () => {
    const leaks = findLeakedJsxText();
    if (leaks.length) {
      throw new Error(
        `${leaks.length} JSX text node(s) contain comment syntax and will render ` +
          `as visible copy: ${leaks.join("; ")}`
      );
    }
  });

  // -------------------------------------------------------------------------
  // The wizard is three steps, and every step that existed only to hold a button
  // has been folded into the step it belonged to. These prove the shape is real
  // rather than a label change: the photo upload is ON the merged choosing step,
  // and the plan is generated from the Review & submit step that reads it.
  // -------------------------------------------------------------------------
  await check("the photo upload lives on the merged choosing step, not its own", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    await openTemplateStep(ctx);
    const text = ctx.text();
    if (!text.includes("Presenter photo")) {
      throw new Error("the merged step does not offer the presenter photo upload");
    }
    // The draft is created eagerly now (ensureProject fires on profile +
    // template), so the photo attaches to a project without the founder
    // pressing anything. Either the attachment UI or the pending-draft copy is
    // the proof that this step owns the photo -- a missing project would show
    // neither.
    const ownsPhoto =
      /prepar(?:e|ing).*draft/i.test(text) || /attach/i.test(text) || !!ctx.container.querySelector("input[type=file]");
    if (!ownsPhoto) {
      throw new Error("the merged step cannot create the draft the photo attaches to");
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

  // The photo is the identity input the render needs, so it only makes sense
  // once there is a story to put it in. Landing on the merged step straight
  // from the pill, with no audience angles generated, shows the template ask
  // alone -- not a section asking for a photograph nothing can use yet.
  // The step mirrors into ?step= so a step with its draft is a shareable
  // link. The write half is unobservable here (the harness setter is a noop
  // by design), so this pins the readable half — landing on the named step —
  // in the DOM and the write half in source, including the guard that keeps
  // the mirror from re-firing the deep-link load it shares the URL with.
  await check("the wizard lands on its ?step= and mirrors it back", async (ctx) => {
    global.__SMOKE_PARAMS = "?step=angle";
    try {
      await mount(CreateVideo, {})(ctx);
      const pill = ctx.container.querySelector('[data-testid="step-pill-angle"]');
      if (!pill || pill.getAttribute("aria-current") !== "step") {
        throw new Error("a ?step=angle link does not land on the angle step");
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    const src = fs.readFileSync(
      path.join(SRC, "pages", "CreateVideo.jsx"),
      "utf8"
    );
    for (const part of [
      'next.set("step", STEPS[step].key)',
      "{ replace: true }",
      "}, [projectParam, profileParam]);",
    ]) {
      if (!src.includes(part)) {
        throw new Error(`the step mirror is missing from source: ${part}`);
      }
    }
    // The deep-link load depending on the whole params object would re-fire
    // on every mirror write and drag the founder back to step 1 mid-flow.
    if (src.includes("}, [params]);")) {
      throw new Error("the deep-link load still depends on the params object, so a mirror write reloads it");
    }
  });

  // Retired keys still land somewhere honest: ?step=template means the merged
  // angle step now, ?step=hook the merged review step. One check, two mounts on
  // separate roots — re-mounting in one container would keep the first link's
  // step and prove nothing about the second. Pinned so a future rename cannot
  // strand a shared link on the first step.
  await check("retired ?step= keys land on their merged steps", async (ctx) => {
    const second = dom.window.document.createElement("div");
    dom.window.document.body.appendChild(second);
    const secondRoot = createRoot(second);
    const later = { root: secondRoot, container: second, text: () => second.textContent || "" };
    try {
      for (const [legacy, testid, target] of [
        ["template", "step-pill-angle", ctx],
        ["hook", "step-pill-review", later],
      ]) {
        global.__SMOKE_PARAMS = `?step=${legacy}`;
        await mount(CreateVideo, {})(target);
        const pill = target.container.querySelector(`[data-testid="${testid}"]`);
        if (!pill || pill.getAttribute("aria-current") !== "step") {
          throw new Error(`a ?step=${legacy} link does not land on ${testid}`);
        }
      }
    } finally {
      global.__SMOKE_PARAMS = "";
      await act(async () => { secondRoot.unmount(); });
      second.remove();
    }
  });

  await check("the presenter photo section waits for the audience angles", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    await openStep(ctx, "Audience & template");
    if (ctx.text().includes("Presenter photo")) {
      throw new Error("the presenter photo section shows before the audience angles are generated");
    }
    // Generating and picking an angle is what proceeds the photo: the same
    // step now offers the section.
    await openStep(ctx, "Audience & template");
    await passAngleGate(ctx);
    const angleButton = [...ctx.container.querySelectorAll('[data-testid="audience-goal-step"] button')]
      .find((button) => button.textContent.includes(ANGLE.label));
    if (!angleButton) throw new Error("the audience step has no selectable audience angle");
    await clickEl(ctx, angleButton);
    await openStep(ctx, "Audience & template");
    if (!ctx.text().includes("Presenter photo")) {
      throw new Error("the presenter photo section did not appear after an angle was picked");
    }
  });

  await check("no step offers time-range or audio controls for an asset", async (ctx) => {
    // The video is one render with no compositing, so an asset has
    // no on-screen window and there is nothing to mix. The row used to carry
    // Start, End, Use as and Gain, and "Save timing" wrote them back - controls
    // that implied a placement nothing can honour.
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
    if (!text.includes("Used for the whole video")) {
      throw new Error("the photograph does not say how it is used");
    }
  });

  await check("the plan is written before a character photo is attached", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    // The plan needs a profile, a template and a goal. The photo is required to
    // render, so it must not stop the plan from being written on Review.
    const plans = [];
    await withApi(
      {
        createStudioProject: async () => ({ ...BASE_PROJECT, content_angle_id: "", assets: [] }),
        updateStudioProject: async () => ({ ...BASE_PROJECT, content_angle_id: "", assets: [] }),
        generatePlan: async (id, payload) => {
          plans.push(payload);
          return PROJECT_WITH_STRATEGY;
        },
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
        await act(async () => {});
        await act(async () => {});
        await openStep(ctx, "Review & submit");
        await act(async () => {});
        await act(async () => {});
        if (plans.length === 0) {
          throw new Error("Review did not write the plan while the character photo was missing");
        }
      }
    );
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
        await openStep(ctx, "Review & submit");
        await act(async () => {});
        await act(async () => {});
        // Assert inside the stub scope: the calls above are async and would
        // otherwise land after the stub restores.
        if (plans.length === 0) {
          throw new Error("Review did not generate the plan on entry");
        }
        const text = ctx.text();
        // Either the fresh plan is already showing, or the step is mid-flight
        // with its generating state — both mean the step owns its plan rather
        // than bouncing the founder elsewhere for it.
        const showingPlan = text.includes("Hook line");
        const midFlight = text.includes("Generating your plan");
        if (!showingPlan && !midFlight) {
          throw new Error("Review neither shows the fresh plan nor generates it");
        }
        // Mid-flight, the generating state narrates which section is being
        // written — never a bare spinner while the plan is en route.
        if (midFlight && !ctx.container.querySelector('[data-testid="plan-progress"]')) {
          throw new Error("the generating state narrates nothing live");
        }
        if (text.includes("No plan yet")) {
          throw new Error("Review still bounces to a separate plan step for its own plan");
        }
      }
    );
  });

  await check("Review without a goal asks for it instead of spinning forever", async (ctx) => {
    // Pills allow reaching Review before a goal exists (or opening a draft
    // whose objective is empty). The auto effect cannot fire without one, so
    // the step must say so and offer the picker — never the generating
    // spinner, which previously showed while nothing was en route.
    global.__SMOKE_PARAMS = "?project=p1";
    const plans = [];
    try {
      await withApi(
        {
          getStudioProject: async () => ({ ...BASE_PROJECT, objective: "", assets: [] }),
          createStudioProject: async () => ({ ...BASE_PROJECT, objective: "", assets: [] }),
          updateStudioProject: async (id, patch) => ({ ...BASE_PROJECT, objective: "", assets: [], ...patch }),
          generatePlan: async (id, payload) => {
            plans.push(payload);
            return PROJECT_WITH_STRATEGY;
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          await act(async () => {});
          if (plans.length !== 0) {
            throw new Error("Review fired a plan with no goal to write it from");
          }
          if (ctx.text().includes("Generating your plan")) {
            throw new Error("Review shows the generating spinner while blocked on the missing goal");
          }
          const goalPicker = ctx.container.querySelector('[data-testid="angle-goal-picker"]');
          if (!goalPicker) throw new Error("Review does not offer its missing goal picker");
          const goalButton = goalPicker.querySelector('[data-testid="recommended-goal-address_user_problem"]');
          if (!goalButton) throw new Error("Review does not offer the goal for its selected audience angle");
          await clickEl(ctx, goalButton);
          await act(async () => {});
          await act(async () => {});
          if (plans.length === 0) {
            throw new Error("choosing the goal on Review did not start the plan on its own");
          }
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("a failed plan offers retry instead of spinning forever", async (ctx) => {
    // A rejected generation used to leave the spinner up with no way back:
    // the auto latch rightly refuses to re-fire, and the only button lived
    // behind a state the failure could not reach.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi(
        {
          getStudioProject: async () => ({ ...BASE_PROJECT, assets: [] }),
          createStudioProject: async () => ({ ...BASE_PROJECT, assets: [] }),
          updateStudioProject: async () => ({ ...BASE_PROJECT, assets: [] }),
          generatePlan: async () => {
            throw new Error("provider unavailable in this check");
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          await act(async () => {});
          await act(async () => {});
          if (ctx.text().includes("Generating your plan")) {
            throw new Error("Review still shows the generating spinner after the plan failed");
          }
          const retry = [...ctx.container.querySelectorAll("button")]
            .find((b) => /Try again/.test((b.textContent || "").trim()));
          if (!retry) {
            throw new Error("Review offers no retry after the plan failed");
          }
          if (retry.disabled) {
            throw new Error("the retry is disabled even though profile, template and goal are present");
          }
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
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
    expectText(ctx, "Review and save your script plan first", "the plan-review gate did not render");
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
    expectText(ctx, "presenter reference", "the gate did not explain why the photo matters");
    expectText(ctx, "Audience & template", "the gate did not name the step that fixes it");
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

  await check("render waits for saved edits and model loading has a real retry", async (ctx) => {
    let modelCalls = 0;
    let renders = 0;
    await withApi({
      getGenerations: async () => ({ generations: [] }),
      getStudioVideoModels: async () => {
        if (++modelCalls === 1) throw new Error("Model catalog unavailable");
        return { default: CAPABILITY.key, models: [CAPABILITY] };
      },
      generateVideo: async () => { renders++; return {}; },
    }, async () => {
      await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY, hasUnsavedEdits: true })(ctx);
      if (!buttonByText(ctx, /Generate the video/).disabled) throw new Error("render enabled without models or saved edits");
      expectText(ctx, "Model catalog unavailable");
      expectText(ctx, "not your unsaved text");
      await clickEl(ctx, buttonByText(ctx, /Retry loading models/));
      if (modelCalls !== 2 || ctx.text().includes("Model catalog unavailable")) throw new Error("model retry did not recover");
      if (!buttonByText(ctx, /Generate the video/).disabled || renders !== 0) throw new Error("retry bypassed unsaved edits or started a paid render");
      await act(async () => ctx.root.render(React.createElement(GenerationPanel, { project: PROJECT_WITH_STRATEGY, hasUnsavedEdits: false })));
      if (buttonByText(ctx, /Generate the video/).disabled) throw new Error("saved edits left render blocked");
    });
  });

  await check("GenerationPanel refuses a project with no angle picked", async (ctx) => {
    // The strategy and the render are built around one audience angle: a
    // render without one is the generic framing the angle step exists to
    // prevent. The founder is told before they decide to render.
    await withApi({ getGenerations: async () => ({ generations: [] }) }, () =>
      mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY, content_angle_id: "" } })(ctx)
    );
    expectText(ctx, "No audience angle picked", "the missing-angle gate did not render");
    expectText(ctx, "Audience & template", "the gate did not name the step that fixes it");
    const generate = [...ctx.container.querySelectorAll("button")]
      .find((b) => (b.textContent || "").includes("Generate the video"));
    if (!generate) throw new Error("no Generate button to gate");
    if (!generate.disabled) {
      throw new Error("Generate stays enabled with no audience angle picked");
    }
  });

  await check("GenerationPanel blocks a render after the angle changes", async (ctx) => {
    // The strategy on this project was built for a1 (the fixture stamps it,
    // as the server does). Switching the project to a2 without rebuilding
    // must block the render, not silently film the old angle.
    await withApi({ getGenerations: async () => ({ generations: [] }) }, () =>
      mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY, content_angle_id: "a2" } })(ctx)
    );
    expectText(
      ctx,
      "The audience angle changed after this strategy was built",
      "the angle drift has no warning on the render panel"
    );
    const generate = [...ctx.container.querySelectorAll("button")]
      .find((b) => (b.textContent || "").includes("Generate the video"));
    if (!generate) throw new Error("no Generate button to gate");
    if (!generate.disabled) {
      throw new Error("Generate stays enabled on a strategy built for another angle");
    }
  });

  // -------------------------------------------------------------------------
  // Per-render resolution choice (heygen-video-1 offers 480p beside 768p).
  //
  // The toggle is data-driven off capability.supported_resolutions: models
  // without the list never show it, and the default is always the catalog
  // value. An explicit pick rides the generate payload; omitted stays
  // omitted so a server-side default change needs no client change.
  // -------------------------------------------------------------------------
  const HEYGEN_CAPABILITY = {
    key: "heygen-video-1",
    name: "HeyGen Video",
    max_duration: 15,
    min_duration: 5,
    resolution: "768p",
    supported_resolutions: ["480p", "768p"],
    aspect_ratio: "9:16",
    supports_references: false,
    supports_native_audio: true,
    supports_last_frame: false,
  };

  await check("the resolution toggle appears only for models that offer a choice", async (ctx) => {
    dom.window.localStorage.removeItem("studio-video-model:p1");
    dom.window.localStorage.removeItem("studio-video-resolution:p1");
    await withApi({
      getGenerations: async () => ({ generations: [] }),
      getStudioVideoModels: async () => ({ default: "heygen-video-1", models: [HEYGEN_CAPABILITY] }),
    }, () => mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY } })(ctx));
    const res = ctx.container.querySelector("#gen-resolution");
    if (!res) throw new Error("no resolution toggle for a model that offers 480p and 768p");
    if (res.value !== "") {
      throw new Error(`the toggle does not default to 768p (value ${JSON.stringify(res.value)})`);
    }
    const options = [...res.querySelectorAll("option")].map((o) => o.value);
    if (!options.includes("480p")) {
      throw new Error(`480p is not offered: ${JSON.stringify(options)}`);
    }
  });

  await check("no resolution toggle renders for a model with no choice", async (ctx) => {
    // Minimax H3 renders at its catalog resolution with no per-render option.
    dom.window.localStorage.removeItem("studio-video-model:p1");
    dom.window.localStorage.removeItem("studio-video-resolution:p1");
    await withApi({
      getGenerations: async () => ({ generations: [] }),
    }, () => mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY } })(ctx));
    if (ctx.container.querySelector("#gen-resolution")) {
      throw new Error("a resolution toggle renders for minimax-h3, which offers no choice");
    }
  });

  await check("the chosen resolution reaches the render request", async (ctx) => {
    dom.window.localStorage.removeItem("studio-video-model:p1");
    dom.window.localStorage.removeItem("studio-video-resolution:p1");
    let sent = null;
    await withApi({
      getGenerations: async () => ({ generations: [] }),
      getStudioVideoModels: async () => ({ default: "heygen-video-1", models: [HEYGEN_CAPABILITY] }),
      generateVideo: async (projectId, payload) => {
        sent = payload;
        return { ...SEGMENT, status: "submitted" };
      },
    }, async () => {
      await mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY } })(ctx);
      const res = ctx.container.querySelector("#gen-resolution");
      if (!res) throw new Error("no resolution toggle to choose from");
      await selectOption(ctx, res, "480p");
      const btn = renderButton(ctx);
      if (btn.disabled) throw new Error("Generate is not live on a ready heygen project");
      await act(async () => {
        btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      await act(async () => {});
      if (!sent) throw new Error("Generate never called the endpoint");
      if (sent.resolution !== "480p") {
        throw new Error(`render request carried resolution ${JSON.stringify(sent.resolution)}, expected "480p"`);
      }
    });
  });

  await check("switching models resets the resolution choice", async (ctx) => {
    dom.window.localStorage.removeItem("studio-video-model:p1");
    dom.window.localStorage.removeItem("studio-video-resolution:p1");
    await withApi({
      getGenerations: async () => ({ generations: [] }),
      getStudioVideoModels: async () => ({
        default: "heygen-video-1",
        models: [HEYGEN_CAPABILITY, { ...CAPABILITY, key: "minimax-h3" }],
      }),
    }, async () => {
      await mount(GenerationPanel, { project: { ...PROJECT_WITH_STRATEGY } })(ctx);
      const res = ctx.container.querySelector("#gen-resolution");
      if (!res) throw new Error("no resolution toggle to choose from");
      await selectOption(ctx, res, "480p");
      if (res.value !== "480p") throw new Error("the 480p pick did not stick");
      const model = ctx.container.querySelector("#gen-model");
      if (!model) throw new Error("no model picker to switch with");
      // A 480p pick for heygen must not ride along onto minimax-h3: the server
      // refuses values the new model does not offer.
      await selectOption(ctx, model, "minimax-h3");
      if (ctx.container.querySelector("#gen-resolution")) {
        throw new Error("the resolution toggle survives a switch to a model with no choice");
      }
      await selectOption(ctx, model, "heygen-video-1");
      const resAgain = ctx.container.querySelector("#gen-resolution");
      if (!resAgain) throw new Error("the toggle did not return with heygen");
      if (resAgain.value !== "") {
        throw new Error(`switching back kept the stale 480p pick: ${JSON.stringify(resAgain.value)}`);
      }
    });
  });

  await check("GenerationPanel explains an un-ready project that already rendered", async (ctx) => {
    // Saving a content edit on an approved project now returns it to draft, so
    // the "already rendered once" case is reachable rather than theoretical. The
    // hint used to be suppressed whenever a generation existed, which left a
    // dead Generate button with no explanation for exactly that founder.
    await mount(GenerationPanel, { project: { ...BASE_PROJECT } })(ctx);
    expectText(
      ctx,
      "Review and save your script plan first",
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

  await check("a transient poll failure neither stops the loop nor raises the banner", async (ctx) => {
    // One failed poll used to kill the loop outright: a single 502 during a
    // container restart froze "Generating..." beside a message promising the
    // page checks back on its own. Transient failures now stay silent and
    // keep polling; only a sustained outage escalates. Two intervals (~13s)
    // prove the second poll still fires and no banner appeared.
    const GenerationPanel = load("components/GenerationPanel.jsx").default;
    let polls = 0;
    const generating = { ...SEGMENT, id: "gen-poll", status: "generating" };
    await withApi(
      {
        getGenerations: async () => ({ generations: [generating] }),
        pollGeneration: async () => {
          polls += 1;
          if (polls === 1) throw new Error("edge 502");
          return generating;
        },
      },
      async () => {
        await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
        await act(async () => {
          await new Promise((r) => setTimeout(r, 13500));
        });
        if (polls < 2) {
          throw new Error(
            "one failed poll stopped the loop: the second poll never fired"
          );
        }
        expectAbsent(ctx, "edge 502", "a transient poll failure raised the banner");
      }
    );
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
    expectText(ctx, "Develop it, stop at the reach", "the middle's goal did not render");
  });

  // The three outcome fields already govern the whole render -- the segment
  // prompt is assembled from them -- and this panel printed none of them, so
  // the framing that produced the video was invisible to the founder reading
  // it. Each is asserted separately: one row rendering while the other two are
  // dropped is exactly the silent gap this closes.
  await check("the strategy review shows what the viewer ends up with", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    expectText(ctx, "What the viewer ends up with", "the outcome framing is not on the review");
    for (const [label, value] of [
      ["The change this supports", STRATEGY.desired_outcome],
      ["How it works, as a benefit", STRATEGY.mechanism_beat],
      ["The last thing said", STRATEGY.payoff_beat],
    ]) {
      if (!ctx.text().includes(label)) throw new Error(`missing outcome row label: ${label}`);
      if (!ctx.text().includes(value)) throw new Error(`missing outcome row value: ${label}`);
    }
    // Framed as a change the app supports, never a target it is held to.
    expectText(ctx, "not a result this video can promise", "the outcome block reads as a guarantee");
  });

  // A strategy generated before these fields existed has none of them, and an
  // empty block headed "What the viewer ends up with" is worse than nothing:
  // it implies an outcome exists and was withheld.
  await check("a strategy with no outcome fields renders no outcome block", async (ctx) => {
    await mount(HookContinuityPanel, {
      project: {
        ...PROJECT_WITH_STRATEGY,
        strategy: {
          ...STRATEGY,
          desired_outcome: "",
          mechanism_beat: "",
          payoff_beat: "",
        },
      },
    })(ctx);
    if (ctx.text().includes("What the viewer ends up with")) {
      throw new Error("an empty outcome block is rendered as if an outcome were withheld");
    }
  });

  await check("the strategy panel requires an angle before building", async (ctx) => {
    // The strategy is built around one audience angle: building it with none
    // picked can only produce the generic take the angle step exists to
    // prevent. The button names the missing input, and the free build that
    // fires on mount must not fire either.
    apiCalls.length = 0;
    await mount(HookContinuityPanel, {
      project: { ...BASE_PROJECT, status: "ready_for_generation", content_angle_id: "" },
    })(ctx);
    await act(async () => {});
    const build = [...ctx.container.querySelectorAll("button")]
      .find((b) => (b.textContent || "").includes("Build the app-specific strategy"));
    if (!build) throw new Error("no strategy build button to gate");
    if (!build.disabled) {
      throw new Error("the strategy builds with no audience angle picked");
    }
    if (!ctx.container.querySelector('[data-testid="strategy-needs-angle"]')) {
      throw new Error("the gate does not name the Audience & template step");
    }
    if (apiCalls.includes("generateStrategy")) {
      throw new Error("the mount fired a strategy build with no angle picked");
    }
  });

  await check("an angle change after the build marks the strategy stale", async (ctx) => {
    // strategy_is_current only tracks plan versions, so without this an angle
    // picked after the build would silently keep a strategy describing the
    // wrong video.
    await mount(HookContinuityPanel, {
      project: { ...PROJECT_WITH_STRATEGY, content_angle_id: "a2" },
    })(ctx);
    expectText(
      ctx,
      "Audience angle changed since this strategy was built",
      "the angle drift has no warning"
    );
  });

  await check("the strategy review shows the hook boundary from the plan", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    // The strategy plans its opening beat at 3s, so the boundary between the two
    // sections renders as a 3s badge on the hook row.
    expectText(ctx, "3s", "the hook boundary did not render");
  });

  // The words the viewer hears, per section. The panel showed the goal ("stop
  // the scroll") and the action but never the spoken line itself, so a founder
  // could review a strategy whose middle read as a feature list and never see
  // it. Each section's script is asserted separately: one line rendering while
  // the other is dropped is the silent gap this closes.
  await check("the strategy review shows what is said in each section", async (ctx) => {
    await mount(HookContinuityPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    expectText(ctx, "What is said here", "the spoken words are not on the review");
    for (const [role, words] of [
      ["hook", STRATEGY.segments[0].script],
      ["middle", STRATEGY.segments[1].script],
    ]) {
      if (!ctx.container.querySelector(`[data-testid="section-spoken-${role}"]`)) {
        throw new Error(`the ${role} section renders no spoken line`);
      }
      if (!ctx.text().includes(words)) {
        throw new Error(`the ${role} section's spoken words did not render`);
      }
    }
  });

  // A middle longer than its seconds is cut before it is spoken, and the tail
  // is usually the payoff. The record is recomputed from the live plan on
  // every read, so the panel asserts both the number and the fix.
  await check("the strategy review warns when approved words do not fit the middle", async (ctx) => {
    await mount(HookContinuityPanel, {
      project: {
        ...PROJECT_WITH_STRATEGY,
        spoken_overflow: { dropped_chars: 42, budget: 105, middle_seconds: 7 },
      },
    })(ctx);
    expectText(ctx, "does not all fit in the middle", "the overflow warning did not render");
    expectText(ctx, "42 characters", "the overflow warning does not state how much is lost");
    expectText(ctx, "Regenerate plan", "the overflow warning does not name the fix");
    // A trim is a plan edit: the strategy built before it stops describing the
    // plan, and the render refuses it. The copy has to say the rebuild is the
    // next step, or the founder trims, generates, and meets a second refusal.
    expectText(ctx, "rebuild the strategy", "the overflow warning does not say a rebuild follows the trim");
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
      "Show closing call-to-action card",
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
    // one generate, the download, the retry, a re-render
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

  // The panel no longer shows a warning when the length exceeds the model's
  // single-pass ceiling. The button is still disabled via the `tooLong` flag
  // so the founder cannot click into a 400, but there is no inline alert.
  await check("GenerationPanel disables Generate when length exceeds single pass", async (ctx) => {
    await mount(GenerationPanel, {
      // A project whose declared length is longer than the model's ceiling. A
      // real one cannot be created from the current library, which is exactly
      // why this is a fixture rather than a happy path.
      project: { ...PROJECT_WITH_STRATEGY, duration_seconds: 20 },
    })(ctx);
    // No warning text should appear
    expectAbsent(ctx, "cannot render 20s in one pass", "a refusal warning should not render");
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
    // the file is the hook and the middle, and the demo plus close are the
    // founder's next step in Demo + CTA.
    expectText(ctx, "This is the hook and the middle", "the file's scope is not described");
    expectText(ctx, "add your demo and call to action", "the founder's own close is not described");
  });

  // Burned-in captions are gone: no text appears on the finished video, so
  // the panel must not promise on-screen text from Review anymore.
  await check("GenerationPanel promises no on-screen text", async (ctx) => {
    await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
    expectAbsent(ctx, "Captions use your approved script", "the caption source is still misattributed");
    expectAbsent(ctx, "the on-screen text you wrote on Review", "the caption source is still stated");
    expectAbsent(ctx, "Add captions", "the compose control is still offered");
    expectAbsent(ctx, "Download captioned", "the captioned download is still offered");
    expectText(ctx, "add your demo and call to action", "the founder's own close is not described");
  });

  // Words that do not fit are not spoken, and the gate refuses the render — so
  // the button has to be disabled with the fix named, not enabled into a 409.
  // An enabled Generate under a blocking overflow warning is the gate working
  // and the UI lying about it.
  await check("GenerationPanel disables Generate while words do not fit", async (ctx) => {
    await mount(GenerationPanel, {
      project: {
        ...PROJECT_WITH_STRATEGY,
        spoken_overflow: { dropped_chars: 42, budget: 105, middle_seconds: 7 },
      },
    })(ctx);
    const generate = [...ctx.container.querySelectorAll("button")]
      .find((b) => /Generate/.test(b.textContent || ""));
    if (!generate) throw new Error("the generate control is missing");
    if (!generate.disabled) {
      throw new Error("Generate stays enabled while approved words do not fit");
    }
    expectText(ctx, "Script too long for this piece", "the overflow block does not name the stop");
    expectText(ctx, "Regenerate plan", "the overflow block does not name the fix");
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
      { re: /\/generations\/\$\{[^}]*\}\/overlay\b/, what: "the retired /generations/{id}/overlay route" },
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
    // panels directly, and every step of the wizard with a drafted project      // behind it so the last step actually mounts both.
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
    // The shell carries the step title; the empty state stays the primary content
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

  // Sequential arrows beside free-jump pills: Continue walks one phase
  // forward and Back walks one back, and neither is offered where it cannot
  // go. Skipping phases stays the pills' job alone.
  await check("wizard arrows walk the steps in order", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await withApi({ getAppProfiles: async () => ({ profiles: [] }) }, () =>
      mount(CreateVideo, {})(ctx)
    );
    const back = () => ctx.container.querySelector('[data-testid="wizard-back-button"]');
    const next = () => ctx.container.querySelector('[data-testid="wizard-continue-button"]');
    if (!back() || back().disabled !== true) throw new Error("Back is not disabled on the first step");
    if (!next()) throw new Error("Continue is missing on the first step");
    if (next().getAttribute("aria-label") !== "Continue to Audience & template") {
      throw new Error(`Continue does not name its destination: ${next().getAttribute("aria-label")}`);
    }
    await clickEl(ctx, next(), "Continue to the angle step");
    if (!ctx.container.querySelector('[data-testid="audience-goal-step"]')) {
      throw new Error("Continue did not move to the Audience & template step");
    }
    if (back().disabled !== false) throw new Error("Back is still disabled after moving forward");
    await clickEl(ctx, back(), "Back to the profile step");
    if (ctx.container.querySelector('[data-testid="audience-goal-step"]')) {
      throw new Error("Back did not return to the profile step");
    }
    // Last step: there is nowhere to continue to.
    await openStep(ctx, "Review & submit");
    if (ctx.container.querySelector('[data-testid="wizard-continue-button"]')) {
      throw new Error("Continue is offered on the last step");
    }
  });

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

  await check("Review & submit holds the render controls once a plan exists", async (ctx) => {
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
          const pill = stepPill(ctx, "Review & submit");
          await act(async () => {
            pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      );
      if (!ctx.text().includes("Build the app-specific strategy")) {
        throw new Error("Review & submit no longer offers the strategy button");
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
          await openStep(ctx, "Review & submit");
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
    if (!ctx.text().includes("Read the app-specific strategy above")) {
      throw new Error("the blocked generate button does not explain the next step");
    }
  });

  await check("an existing strategy is not rebuilt when generating", async (ctx) => {
    // Rebuilding bumps strategy_version and silently replaces whatever the
    // founder reviewed. A re-render must not do that behind their back.
    global.__SMOKE_PARAMS = "?project=p1";
    let strategyCalls = 0;
    let renderCalls = 0;
    const originalConfirm = dom.window.confirm;
    dom.window.confirm = () => true;
    try {
      await withApi(
        {
          generateStrategy: async () => {
            strategyCalls += 1;
            return PROJECT_WITH_STRATEGY;
          },
          generateVideo: async () => {
            renderCalls += 1;
            return { ...SEGMENT, status: "submitted" };
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
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
      dom.window.confirm = originalConfirm;
    }
    if (renderCalls !== 1) throw new Error(`expected one confirmed render, saw ${renderCalls}`);
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
          await openStep(ctx, "Review & submit");
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

  // The build narrates liveness while running — dots cycling on a line that
  // claims motion only, never stages the backend cannot show. It unmounts
  // with the busy state, so a failure can never strand it beside its error.
  await check("a strategy build narrates liveness, then clears it", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    let releaseBuild;
    const buildGate = new Promise((resolve) => { releaseBuild = resolve; });
    try {
      await withApi(
        {
          getStudioProject: async () => ({
            ...PROJECT_WITH_STRATEGY,
            strategy: {},
            strategy_version: 0,
          }),
          generateStrategy: () => buildGate,
          generateVideo: async () => {
            throw new Error("no render should escape a strategy that never built");
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          const build = buttonByText(ctx, /Build the app-specific strategy|Rebuild strategy/);
          await act(async () => {
            build.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          const live = ctx.container.querySelector('[data-testid="strategy-progress"]');
          if (!live) throw new Error("no liveness line while the strategy builds");
          if (!/Building your strategy/.test(live.textContent || "")) {
            throw new Error(`the liveness line claims stages it cannot see: ${JSON.stringify(live.textContent)}`);
          }
          await act(async () => {
            releaseBuild({ ...PROJECT_WITH_STRATEGY });
          });
          await act(async () => {});
          await act(async () => {});
          if (ctx.container.querySelector('[data-testid="strategy-progress"]')) {
            throw new Error("the liveness line survived its own build");
          }
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("a failed strategy build leaves nothing generated and says so", async (ctx) => {    // The build is its own action on the panel above, so its failure is reported
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
          await openStep(ctx, "Review & submit");
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
          await openStep(ctx, "Review & submit");
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
    if (!text.includes("Rebuild it so it matches your saved plan")) {
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
          await openStep(ctx, "Review & submit");
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
          await openStep(ctx, "Review & submit");
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

  await check("Review & submit refuses to run without an approved plan", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      // A draft that exists but has no plan: the strategy and the one render
      // must both stay out of reach. Entering this step writes the plan on its
      // own, so the fixture fails the write: a plan the step cannot produce is
      // the only plan-less state reachable here.
      await withApi(
        {
          getStudioProject: async () => ({ ...BASE_PROJECT, script_version: 0, script: "" }),
          createStudioProject: async () => ({ ...BASE_PROJECT, script_version: 0, script: "" }),
          updateStudioProject: async (id, payload) => ({ ...BASE_PROJECT, script_version: 0, script: "", ...payload, script_version: 0, script: "" }),
          generatePlan: async () => {
            throw new Error("plan unavailable in this check");
          },
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          const pill = stepPill(ctx, "Review & submit");
          await act(async () => {
            pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          await act(async () => {});
          // Assert inside the stub scope: the plan write is async and would
          // otherwise land after the throwing stub restores, planning the
          // draft with the default fixture and hiding the gate this check
          // is about.
          const text = ctx.text();
          if (!text.includes("The plan didn't generate")) {
            throw new Error(
              `Review & submit does not explain that a plan comes first; it rendered: ${JSON.stringify(
                text.slice(300, 800)
              )}`
            );
          }
          for (const control of ["Build the app-specific strategy", "Generate the video", "Extend"]) {
            if (text.includes(control)) {
              throw new Error(`Review & submit offers ${JSON.stringify(control)} with no approved plan`);
            }
          }
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
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
      await openStep(ctx, "Review & submit");
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
      const pill = stepPill(ctx, "Review & submit");
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
      // The outcome the picked template was chosen for, above the words. The
      // plan step showed the hook and the script with no statement of what
      // they were meant to leave the viewer with, so there was nothing on
      // screen to tell a founder whether the words still served the pick.
      if (!text.includes("What this is aiming to leave them with")) {
        throw new Error("Review does not state the outcome the template is aiming at");
      }
      if (!text.includes(TEMPLATE.outcome)) {
        throw new Error("Review does not show the template's outcome line");
      }
      // Same honesty rule as the card: a framing, not a promise about results.
      expectText(ctx, "not a result this video can promise", "the Review outcome reads as a guarantee");
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

  // Burned-in captions are gone, so Review offers no on-screen-text control:
  // a legacy overlays array on an old row renders nothing and saves nothing.
  // The caption editor went with burned-in captions: Review offers no
  // on-screen-text control, and a legacy overlays array on an old row renders
  // nothing and saves nothing.
  await check("Review offers no caption editor", async (ctx) => {
    await withApi(
      {
        getStudioProject: async () => ({
          ...PROJECT_WITH_STRATEGY,
          overlays: [{ start: 0, end: 2, text: "one list" }],
        }),
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          await act(async () => {});
          if (ctx.container.querySelector('[data-testid="caption-editor"]')) {
            throw new Error("Review still offers the caption editor");
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Both spoken lines, counted against the length each aims at. The hook line
  // used to be the one count nothing showed: the middle had a budget and the
  // opening line had none. The numbers come from the server's own measurement
  // of the saved plan, which is the plan a render validates.
  await check("Review shows both spoken counts against their targets", async (ctx) => {
    await withApi(
      {
        getStudioProject: async () => ({
          ...PROJECT_WITH_STRATEGY,
          spoken_check: {
            hook: { chars: 40, target: 60, ceiling: 60, verdict: "on_target" },
            script: { chars: 71, target: 140, ceiling: 140, verdict: "under_target" },
            story: {
              problem_in_hook: true,
              resolution_in_script: true,
              restates_hook: false,
              coherent: true,
            },
            over_ceiling: false,
          },
        }),
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          expectText(
            ctx,
            "Hook line: 40 characters, aiming for about 60",
            "the hook count and its target are not shown"
          );
          expectText(
            ctx,
            "Script: 71 characters, aiming for about 140",
            "the script count and its target are not shown"
          );
          expectText(
            ctx,
            "The hook names the problem and the script closes it.",
            "the story verdict is not shown"
          );
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // The partition the render actually speaks: what it says, and how much of the
  // script is not spoken. There is deliberately no trim control. A generated
  // script is measured and cut to fit before it is stored, so the founder is
  // never handed a broken plan to repair by hand — and the overflow this block
  // reports can now only come from their own edit, which the copy names as such.
  await check("Review shows the spoken partition without offering a manual trim", async (ctx) => {
    const kept = "Most evenings blur together.";
    await withApi(
      {
        getStudioProject: async () => ({
          ...PROJECT_WITH_STRATEGY,
          script: `${kept} ${"x".repeat(200)}`,
          spoken_middle: kept,
          spoken_overflow: { dropped_chars: 200, budget: 105, middle_seconds: 7 },
        }),
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          expectText(ctx, "What the middle will say", "the spoken partition is not shown");
          expectText(ctx, kept, "the kept spoken line is not shown");
          // The dropped words are no longer a tail sliced out of the script:
          // an over-long middle gives up the sentences in the middle of itself
          // and keeps the one that resolves the hook. So the block reports the
          // COUNT the server dropped, which is the only honest number left.
          expectText(
            ctx,
            "200 characters of the script are past",
            "the dropped count is not shown"
          );
          expectText(
            ctx,
            "Regenerate the plan",
            "the overflow does not name the automatic fix",
          );
          if (ctx.container.querySelector('[data-testid="spoken-trim"]')) {
            throw new Error("Review still offers a manual trim control");
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // The arrival clamp, reported. The founder's script is shorter than the model
  // wrote it, and silence about that reads as the studio losing words — so the
  // size of the cut is stated, and the note says what was removed is not
  // dropped at render.
  await check("Review reports a script that was trimmed on arrival", async (ctx) => {
    await withApi(
      {
        getStudioProject: async () => ({
          ...PROJECT_WITH_STRATEGY,
          plan_trim: { dropped_chars: 111, middle_seconds: 12, budget: 180 },
        }),
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          const note = ctx.container.querySelector('[data-testid="plan-trimmed-note"]');
          if (!note) throw new Error("a trimmed plan is not reported to the founder");
          const text = note.textContent || "";
          if (!text.includes("111")) {
            throw new Error(`the trim note does not size the cut: ${JSON.stringify(text)}`);
          }
          if (!text.includes("12-second middle")) {
            throw new Error(`the trim note does not name the middle it fits: ${JSON.stringify(text)}`);
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Review must read the words from the server, not from whatever the wizard
  // last held: an eager draft update issued while the plan was still being
  // written can resolve after it, leaving the editors on a pre-plan copy of
  // the row — an empty script above a plan the render section can count in.
  await check("Review shows the server's words, not a stale local copy", async (ctx) => {
    await withApi(
      {
        // The server's row carries the plan. An eager draft update issued while
        // the plan was being written can resolve after it, which left the
        // editors on a pre-plan copy of the row: an empty Hook line and Script
        // above a plan the render section can count characters in.
        getStudioProject: async () => ({
          ...PROJECT_WITH_STRATEGY,
          hook_line: "Hook line from the server",
          script: "Script text from the server",
        }),
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          expectText(
            ctx,
            "Script text from the server",
            "the script editor did not adopt the server's copy",
          );
          // The hook line is an <input>, so its value is an attribute rather than page
// text and has to be read off the element.
          const hookInput = [...ctx.container.querySelectorAll("input")].find(
            (i) => (i.value || "") === "Hook line from the server"
          );
          if (!hookInput) {
            throw new Error("the hook line editor did not adopt the server's copy");
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // And it must not fight the founder: a refetch that lands while they have
  // unsaved edits must not overwrite the words they are writing.
  // Approval is not a decision the founder makes by hand. A plan marks its own
// project ready, so a second "Mark ready" button could only ever confirm what
// the studio already knew -- and its absence read as the render button being
// broken. If one reappears, the founder is being asked to do the app's job.
await check("Review offers no manual mark-ready control", async (ctx) => {
  await withApi({}, async () => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Review & submit");
      const buttons = [...ctx.container.querySelectorAll("button")].map(
        (b) => (b.textContent || "").trim()
      );
      for (const gone of ["Mark ready for generation"]) {
        if (buttons.some((label) => label === gone)) {
          throw new Error(`Review still offers the manual control ${JSON.stringify(gone)}`);
        }
      }
      // The state is still reported, so the founder can see the plan is
      // approved rather than wondering where the control went.
      expectText(ctx, "Ready for generation", "the ready state is not reported");
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });
});

// A re-read must never move a project backwards. The plan marks the project
// ready right after generating; a refetch resolving with the row from just
// before that quietly downgraded an approved project to a draft and left the
// render button disabled on the next step with nothing on screen to explain it.
await check("the Review re-read never downgrades a ready project", async (ctx) => {
    // The wizard adopts the deep-link row as current, so the re-read is skipped
    // and this read is never issued. That skip is the first half of the
    // behaviour: a row already held from the server must not be re-fetched.
    // The second half -- a stale row never downgrading readiness -- is proven
    // by "Review never overwrites unsaved edits with a refetch", which forces
    // the re-read and holds a draft response behind the founder's words.
    let reads = 0;
    await withApi(
      {
        getStudioProject: async () => {
          reads += 1;
          return PROJECT_WITH_STRATEGY;
        },
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          await act(async () => {});
          // One read is the deep link. A second would mean the wizard is
          // re-reading a row it already holds, which is the wasted request (and
          // the late state update) this records.
          if (reads !== 1) {
            throw new Error(
              `Review re-read a project it already held current: ${reads} reads`
            );
          }
          expectText(ctx, "Ready for generation", "the deep-linked ready project lost its state");
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

await check("Review never overwrites unsaved edits with a refetch", async (ctx) => {
    let resolveProject;
    let reads = 0;
    await withApi(
      {
        // No deep link, so the draft comes from the eager create and was never
        // adopted from the server. That is exactly the case the re-read exists
        // for, and it means this stub is reached by the re-read alone.
        getStudioProject: async () => {
          reads += 1;
          // Held, so it can be released AFTER the founder has typed — the only
          // ordering where the guard is testable at all.
          return new Promise((resolve) => {
            resolveProject = () =>
              resolve({ ...PROJECT_WITH_STRATEGY, script: "Text from the server" });
          });
        },
      },
      async () => {
        global.__SMOKE_PARAMS = "";
        try {
          await mount(CreateVideo, {})(ctx);
          await openTemplateStep(ctx);
          await act(async () => {});
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          if (!resolveProject || reads === 0) {
            throw new Error("Review never issued the re-read it should have");
          }
          // Type into the script box, then let the in-flight read resolve.
          const box = [...ctx.container.querySelectorAll("textarea")].find((t) =>
            (t.value || "").includes("You do not have a focus problem"),
          );
          if (!box) throw new Error("Review has no script editor to type into");
          const setter = Object.getOwnPropertyDescriptor(
            dom.window.HTMLTextAreaElement.prototype,
            "value"
          ).set;
          await act(async () => {
            setter.call(box, "My own unsaved words");
            box.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
          });
          await act(async () => {
            resolveProject();
          });
          await act(async () => {});
          expectText(ctx, "My own unsaved words", "the refetch discarded an unsaved edit");
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Plan generation is single-flight: a double-tapped Regenerate (both taps
  // read the still-false `busy` in the same tick) must not stack two
  // minute-long model calls, each holding `busy` while every control sits
  // disabled — stacked flights read as a frozen page.
  await check("a double-tapped Regenerate starts one plan generation, not two", async (ctx) => {
    let releasePlan;
    let planCalls = 0;
    await withApi(
      {
        generatePlan: async () => {
          planCalls += 1;
          await new Promise((resolve) => { releasePlan = resolve; });
          return PROJECT_WITH_STRATEGY;
        },
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        // jsdom's confirm exists but answers undefined, which the
        // Regenerate guard reads as "founder said no". Answer yes, the way
        // a founder accepting the replace-plan prompt would.
        const originalConfirm = dom.window.confirm;
        dom.window.confirm = () => true;
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          const btn = buttonByText(ctx, /Regenerate plan/);
          await act(async () => {
            btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
            btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          if (planCalls !== 1) {
            throw new Error(`double tap started ${planCalls} plan generations`);
          }
          await act(async () => { releasePlan(); });
          await act(async () => {});
          await act(async () => {});
          if (planCalls !== 1) {
            throw new Error(`settling started a second generation: ${planCalls}`);
          }
          // Busy cleared: the step is interactive again rather than latched.
          if (buttonByText(ctx, /Regenerate plan/).disabled) {
            throw new Error("busy never cleared after the generation settled");
          }
        } finally {
          dom.window.confirm = originalConfirm;
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // The refinement cap is a terminus, not a pause: the fourth thumbs-down
  // states the cap instead of generating, and the thumb must not stay
  // pressed as if a plan were coming.
  await check("the fourth thumbs-down states the cap instead of generating", async (ctx) => {
    let planCalls = 0;
    await withApi(
      {
        generatePlan: async () => {
          planCalls += 1;
          return PROJECT_WITH_STRATEGY;
        },
      },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          const down = () => ctx.container.querySelector('[data-testid="review-thumb-down"]');
          if (!down()) throw new Error("Review has no thumbs-down control");
          for (let i = 0; i < 3; i++) {
            await clickEl(ctx, down(), `thumbs-down tap ${i + 1} missing`);
          }
          if (planCalls !== 3) {
            throw new Error(`expected 3 refinements, saw ${planCalls}`);
          }
          await clickEl(ctx, down(), "fourth thumbs-down missing");
          expectText(ctx, "Three fresh plans", "the refinement cap is not stated");
          if (down().getAttribute("aria-pressed") === "true") {
            throw new Error("the capped thumbs-down stays pressed as if a plan were coming");
          }
          if (planCalls !== 3) {
            throw new Error("the capped tap generated a fourth plan");
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Each component's rating is filed under its own component, so it can only
  // teach the AI step that produces it.
  await check("plan and template thumbs are recorded under their own component", async (ctx) => {
    await withApi(
      { generatePlan: async () => PROJECT_WITH_STRATEGY },
      async () => {
        global.__SMOKE_PARAMS = "?project=p1";
        global.__SMOKE_THUMBS = [];
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Review & submit");
          const up = ctx.container.querySelector('[data-testid="review-thumb-up"]');
          await clickEl(ctx, up, "Review has no thumbs-up control");
          await openStep(ctx, "Audience & template");
          const tUp = ctx.container.querySelector('[data-testid="template-feedback-thumb-down"]');
          await clickEl(ctx, tUp, "Template step has no template rating");
          await act(async () => {});
          const steps = global.__SMOKE_THUMBS.map((t) => `${t.step}:${t.verdict}`);
          if (!steps.includes("plan:1")) {
            throw new Error(`plan thumbs-up not filed under plan: ${steps.join(", ")}`);
          }
          if (!steps.includes("template:-1")) {
            throw new Error(`template thumbs-down not filed under template: ${steps.join(", ")}`);
          }
          const tpl = global.__SMOKE_THUMBS.find((t) => t.step === "template");
          if (!tpl.refs.template_id) throw new Error("template rating does not name the template");
          expectText(ctx, "Rating saved", "template rating gives no confirmation");
        } finally {
          global.__SMOKE_PARAMS = "";
          global.__SMOKE_THUMBS = [];
        }
      }
    );
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
  // The statement moved rather than went. The Audience step used to carry an
  // uneditable "What you get" card repeating the piece length and the demo/close
  // caveat, which was a block of prose between that step's two real choices.
  // Review is where the length is read now — beside the shot timeline written to
  // it — and the studio's own footer note carries the demo/close caveat at every
  // step. So this asserts each property on the surface that kept it, plus the
  // Audience step not growing a second copy of the length back.
  await check("the Review step states the piece's length, read-only", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Review & submit");
      const text = ctx.text();
      if (!text.includes("Length of the generated piece")) {
        throw new Error(
          `the Review step does not state the piece length; it rendered: ${JSON.stringify(
            text.slice(0, 400)
          )}`
        );
      }
      // The number it states is the draft's own: the length its beat timeline
      // was written to and the length the render is asked for. A number that
      // disagreed with the draft would be a second, hidden length.
      if (!text.includes(`${PROJECT_WITH_STRATEGY.duration_seconds} seconds`)) {
        const at = text.indexOf("Length of the generated piece");
        throw new Error(
          `the Review step does not name the draft's own length ` +
            `(${PROJECT_WITH_STRATEGY.duration_seconds}s); it rendered: ` +
            JSON.stringify(text.slice(at, at + 120))
        );
      }
    } finally {
      global.__SMOKE_PARAMS = "";
    }

    // The template fallback for a draft that declares no length of its own is
    // asserted directly against readPieceSeconds in check-frontend-logic.cjs.
    await mount(CreateVideo, {})(ctx);
    await openStep(ctx, "Audience & template");
    if (ctx.container.querySelector('[data-testid="create-what-you-get"]')) {
      throw new Error("the Audience step's length card is back, stating the length a second time");
    }
  });

  // -------------------------------------------------------------------------
  // The optional angle is usable from in here.
  //
  // The angle used to be a dead end in the wizard: a founder with no angles was
  // told to add them on the App Profile page, which meant leaving the flow,
  // generating, and coming back. The empty state now offers the generation
  // itself — and it must stay honest about failure, or a silent zero reads as
  // "this app has no angles" rather than "the call failed".
  // -------------------------------------------------------------------------
  await check("the Audience step offers to generate missing angles", async (ctx) => {
    await withApi({
      getContentAngles: async () => ({ angles: [] }),
      generateContentAngles: async () => ({ angles: [ANGLE] }),
    }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, "Audience & template");
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      if (!step?.textContent.includes("Get your six audience angles, then pick one to move forward.")) {
        throw new Error("the empty angle state does not carry the single CTA copy");
      }
      const button = step.querySelector('[data-testid="generate-angles-button"]');
      if (!button) throw new Error("the empty angle state offers no generate button");

      apiCalls.length = 0;
      await act(async () => {
        button.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      if (!apiCalls.includes("generateContentAngles")) {
        throw new Error("clicking generate angles never called the endpoint");
      }
      // The generated angles render, and one can be picked — the whole point of
      // generating them in the wizard.
      const cards = Array.from(step.querySelectorAll("button")).filter((b) =>
        b.textContent.includes(ANGLE.label));
      if (!cards.length) {
        throw new Error("generated angles were not offered in the list");
      }
      await act(async () => {
        cards[0].dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
    });
  });

  // The server generates the six on approval, so without a gate the founder
  // lands on a finished list plus Regenerate they never asked for. Landing
  // shows one Generate CTA instead; the click reveals the pre-generated set
  // for free (no endpoint call, no spend). Regenerate appears only beside
  // the visible list. A fresh profile id keeps this free of whatever other
  // checks persisted, so the gate is asserted, not the order they ran in.
  await check("landing on angles shows Generate, not the list or Regenerate", async (ctx) => {
    const FRESH = { ...PROFILE, id: "b9", brand_name: "Freshly" };
    await withApi({
      getAppProfiles: async () => ({ profiles: [FRESH] }),
      getContentAngles: async () => ({ angles: [ANGLE, ANGLE_B] }),
    }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Audience & template");
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      if (step.querySelector('[data-testid^="angle-option-"]')) {
        throw new Error("the pre-generated six show before the founder clicks anything");
      }
      if (step.querySelector('[data-testid="regenerate-angles-button"]')) {
        throw new Error("Regenerate shows before there is a visible generation");
      }
      const cta = step.querySelector('[data-testid="generate-angles-button"]');
      if (!cta) throw new Error("first view offers no Generate CTA for the six");
      if (!/Generate angles/.test(cta.textContent || "")) {
        throw new Error(`the CTA does not read as Generate angles: ${JSON.stringify(cta.textContent)}`);
      }
      apiCalls.length = 0;
      await clickEl(ctx, cta);
      if (apiCalls.includes("generateContentAngles")) {
        throw new Error("revealing pre-generated angles called the generate endpoint");
      }
      if (!step.querySelector('[data-testid="angle-option-a1"]')) {
        throw new Error("the Generate click did not show the six angles");
      }
      if (!step.querySelector('[data-testid="regenerate-angles-button"]')) {
        throw new Error("Regenerate is missing beside the visible generation");
      }
    });
  });

  // A pick that names nothing must not open the gate either. A stale ?angle=
  // param or a draft pointing at a deleted angle used to read as "viewed"
  // through the raw id, so first view landed on a list of strangers with no
  // row picked — the exact failure this rule fixes.
  await check("a stale angle pick still lands gated", async (ctx) => {
    const FRESH = { ...PROFILE, id: "b9", brand_name: "Freshly" };
    await withApi({
      getAppProfiles: async () => ({ profiles: [FRESH] }),
      getContentAngles: async () => ({ angles: [ANGLE, ANGLE_B] }),
    }, async () => {
      global.__SMOKE_PARAMS = "?angle=ghost-id";
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Audience & template");
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      if (step.querySelector('[data-testid^="angle-option-"]')) {
        throw new Error("a dangling pick opened the list on first view");
      }
      if (!step.querySelector('[data-testid="generate-angles-button"]')) {
        throw new Error("a dangling pick left no Generate CTA to recover through");
      }
    });
  });

  // Generation narrates fresh work while in flight, then the rows arrive as
  // a staggered cascade — never a spinner-to-list blink, and never a frozen
  // count beside an error.
  await check("angle generation counts up in flight, then cascades rows in", async (ctx) => {
    const FRESH = { ...PROFILE, id: "b9", brand_name: "Freshly" };
    let release;
    const flight = new Promise((r) => { release = r; });
    await withApi({
      getAppProfiles: async () => ({ profiles: [FRESH] }),
      getContentAngles: async () => ({ angles: [] }),
      generateContentAngles: () => flight,
    }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Audience & template");
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      await clickEl(ctx, step.querySelector('[data-testid="generate-angles-button"]'), "no Generate CTA on empty angles");
      const progress = step.querySelector('[data-testid="angles-progress"]');
      if (!progress) throw new Error("no live count while the generation is in flight");
      if (!/Reading angle \d+ of 6/.test(progress.textContent || "")) {
        throw new Error(`the count does not read as fresh work: ${JSON.stringify(progress.textContent)}`);
      }
      await act(async () => {
        release({ angles: [ANGLE, ANGLE_B] });
      });
      await act(async () => {});
      if (step.querySelector('[data-testid="angles-progress"]')) {
        throw new Error("the count survived its own generation");
      }
      const rows = [...step.querySelectorAll('[data-testid^="angle-option-"]')];
      if (rows.length !== 2) throw new Error(`expected two fresh rows, saw ${rows.length}`);
      const delays = rows.map((row) => {
        const host = row.closest("div.animate-fade-up");
        if (!host) throw new Error("a fresh row carries no arrival animation");
        return host.style.animationDelay;
      });
      if (new Set(delays).size !== delays.length) {
        throw new Error(`rows do not arrive staggered: ${JSON.stringify(delays)}`);
      }
    });
  });

  // Review & submit never generates angles: its red button names Audience & template
  // and jumps there, so no call goes out from a screen whose job is the render.
  // The render section's own angle CTA is covered by the same-control check below.
  await check("Review & submit redirects angle-less founders instead of generating", async (ctx) => {
    const FRESH = { ...PROFILE, id: "b9", brand_name: "Freshly" };
    await withApi({
      getAppProfiles: async () => ({ profiles: [FRESH] }),
      getContentAngles: async () => ({ angles: [ANGLE, ANGLE_B] }),
    }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Review & submit");
      if (ctx.container.querySelector('[data-testid="create-draft-button"]')) throw new Error("a draft action that cannot run competes with the missing-input action");
      const btn = ctx.container.querySelector('[data-testid="goto-first-gap-button"]');
      if (!btn) throw new Error("no angle CTA on Review & submit with no angle picked");
      if (!/Pick an audience angle/.test(btn.textContent || "")) {
        throw new Error(`the CTA does not name its destination: ${JSON.stringify(btn.textContent)}`);
      }
      apiCalls.length = 0;
      await clickEl(ctx, btn);
      if (apiCalls.includes("generateContentAngles") || apiCalls.includes("regenerateContentAngles")) {
        throw new Error("Review & submit spent an angle call instead of redirecting");
      }
      const pill = ctx.container.querySelector('[data-testid="step-pill-angle"]');
      if (!pill || pill.getAttribute("aria-current") !== "step") {
        throw new Error("the red button did not land on the Audience & template step");
      }
      if (ctx.container.querySelector('[data-testid^="angle-option-"]')) {
        throw new Error("an angle list rendered outside its home step");
      }
      expectText(ctx, "Generate and pick an audience angle first");
      expectAbsent(ctx, "Pick a goal above", "goal guidance points at a hidden control");
    });
  });

  // The draft button only renders when every input exists and no draft does,
  // so by construction it must always act: clicking it starts the create
  // call, never a silent early return. Pinned here because the gates that
  // guarantee this live in three different places (outer gate, firstGap, the
  // ensureProject guard), and a future edit could render the button where
  // the guarantees no longer hold.
  await check("the draft button acts instead of dying silently", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    // A template with no photo requirement: with character_reference required
    // the render step rightly shows the photo gate instead, and the draft
    // button is the wrong assertion there.
    const NOPHOTO = { ...TEMPLATE, id: "t-nophoto", name: "No Photo Pick", required_assets: [] };
    try {
      await withApi(
        {
          // No draft anywhere: the list, the fetch and the eager create all
          // answer empty, so the wizard holds complete inputs and no draft —
          // exactly the state the draft button exists for.
          getStudioProject: async () => null,
          createStudioProject: async () => null,
          updateStudioProject: async () => null,
          getTemplates: async () => ({ templates: [NOPHOTO] }),
          getTemplateRecommendations: async () => ({
            recommendations: [
              { template: NOPHOTO, score: 9, why_it_fits: ["needs no photo"], limitations: [] },
            ],
          }),
          ensureObjectiveTemplates: async () => ({
            templates: [NOPHOTO],
            generated: true,
            objective: "address_user_problem",
            error: null,
          }),
        },
        async () => {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "App Profile");
          const picker = ctx.container.querySelector('[data-testid="app-profile-picker"]');
          if (!picker) throw new Error("no app profile picker on the first step");
          await clickEl(ctx, picker.querySelector("button"), "no approved profile to pick");
          await openTemplateStep(ctx);
          const card = [...ctx.container.querySelectorAll('[role="button"]')].find((el) =>
            (el.textContent || "").includes("No Photo Pick")
          );
          if (!card) throw new Error("no template card to pick after goal");
          await clickEl(ctx, card);
          await openStep(ctx, "Review & submit");
          await act(async () => {});
          await act(async () => {});
          const draft = ctx.container.querySelector('[data-testid="create-draft-button"]');
          if (!draft) throw new Error("complete inputs with no draft show no draft button");
          if (draft.disabled) throw new Error("the draft button renders disabled with nothing missing");
          apiCalls.length = 0;
          await clickEl(ctx, draft);
          if (!apiCalls.includes("createStudioProject")) {
            throw new Error("the draft button died silently instead of creating the draft");
          }
        }
      );
    } finally {
      global.__SMOKE_PARAMS = "";
    }
  });

  await check("a failed angle generation is named and stays retryable", async (ctx) => {
    await withApi({
      getContentAngles: async () => ({ angles: [] }),
      generateContentAngles: async () => {
        throw new Error("AI content angle generation failed. Please try again.");
      },
    }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      const pill = stepPill(ctx, "Audience & template");
      await act(async () => {
        pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      const button = step.querySelector('[data-testid="generate-angles-button"]');
      await act(async () => {
        button.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      if (!ctx.text().includes("AI content angle generation failed")) {
        throw new Error("the failure is not surfaced where the button was");
      }
      if (button.disabled) {
        throw new Error("the button stays disabled after a failure, so there is no retry");
      }
    });
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
        const stepContent = ctx.container.querySelector(".surface.rounded-2xl");
        const stepText = stepContent?.textContent || "";
        // Only test text inside the active step. Shared page guidance outside the
        // step truthfully names the separate editor without offering a control.
        const withoutEntry = stepText.replace(/demo \+ cta/gi, "");
        if (/CTA/.test(withoutEntry)) {
          throw new Error(`step ${JSON.stringify(label)} offers a CTA affordance`);
        }
        if (stepText.includes("CTA card")) {
          throw new Error(`step ${JSON.stringify(label)} promises an end card`);
        }
        // The retired field labels, in case one is ever restored as a heading.
        if (stepText.includes("Feature emphasis")) {
          throw new Error(`step ${JSON.stringify(label)} offers a feature instruction to render`);
        }
      }
      // And the field that replaced the second: the founder's own note about
      // what to record, editable, and clearly not an instruction to the model.
      const reviewPill = stepPill(ctx, "Review & submit");
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
        ensureObjectiveTemplates: async () => ({
          templates: ORDERED_TEMPLATES,
          generated: false,
          objective: "address_user_problem",
          error: null,
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
    // choice, which once lived on its own step before the merge.
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
      "Built for 'create curiosity'. Leaves them wanting the answer.",
      "Lands with Health & Fitness viewers before the app is even named — framed for how they talk about the problem.",
      "Tailored for Vocolens - generated from this app's approved profile.",
      "Aimed at anxious, night-owls — they're already in the situation this opens on.",
    ];
    const THREE_LIMITS = [
      "Needs character reference.",
      "Framed for Productivity rather than Health & Fitness — the opening will need rewording.",
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
        ensureObjectiveTemplates: async () => ({
          templates: [ORDERED_TEMPLATES[0]],
          generated: false,
          objective: "address_user_problem",
          error: null,
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

    // The outcome is the card's lead line: what the viewer ends up with,
    // above the evidence for the pick. A card without it is a template
    // described only by its mechanics again.
    if (!text.includes(TEMPLATE.outcome)) {
      throw new Error("the template outcome headline is not rendered on the card");
    }

    // A reason is the case FOR the template and a limitation is the caveat ON
    // it. Rendering them identically made a warning look like evidence.
    if (!text.includes("Why it fits")) {
      throw new Error("the fit reasons are not labelled");
    }

    // The score is the sort key and was already computed server-side; showing it
    // is what stops "is four reasons better than two" being a reasonable
    // question for the founder to ask.
    if (!text.includes("Fit 9.5")) {
      throw new Error("the fit score is not shown on the card");
    }

    // The first reason is the verdict and the rest is detail: the server sorts
    // strongest-first, so reasons[0] is the decision and the others are its
    // evidence. Rendering all four identically left the founder unable to tell
    // which was which.
    const verdict = ctx.container.querySelector('[data-testid="template-fit-verdict"]');
    if (!verdict) {
      throw new Error("the top fit reason is not styled as the card's verdict");
    }
    if (!verdict.textContent.includes(FOUR_REASONS[0])) {
      throw new Error("the verdict is not the strongest (first) reason");
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
        ensureObjectiveTemplates: async () => ({
          templates: [ORDERED_TEMPLATES[1]],
          generated: false,
          objective: "address_user_problem",
          error: null,
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
      }
    );
    const text = ctx.text();
    // An empty heading is worse than no heading.
    if (text.includes("Why it fits")) {
      throw new Error("an empty reasons block is still rendered");
    }
    if (!text.includes("Fit 5")) {
      throw new Error("the fit score is missing");
    }
  });

  await check("a one-reason card shows the verdict with no detail list", async (ctx) => {
    // One reason means the detail list has nothing to hold; rendering an empty
    // <ul> would leave a stray marker row and confuse the verdict/detail split.
    global.__SMOKE_PARAMS = "";
    await withApi(
      {
        getTemplates: async () => ({ templates: ORDERED_TEMPLATES }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            {
              template: ORDERED_TEMPLATES[0],
              score: 9,
              why_it_fits: ["Built for 'create curiosity'. Leaves them wanting the answer."],
              limitations: [],
              suggested_duration: TEMPLATE.default_duration,
            },
          ],
        }),
        ensureObjectiveTemplates: async () => ({
          templates: [ORDERED_TEMPLATES[0]],
          generated: false,
          objective: "address_user_problem",
          error: null,
        }),
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
      }
    );
    const verdict = ctx.container.querySelector('[data-testid="template-fit-verdict"]');
    if (!verdict) {
      throw new Error("the single reason is not styled as the verdict");
    }
    if (verdict.closest("ul")) {
      throw new Error("the verdict is nested inside the detail list");
    }
    if (ctx.container.querySelector('[data-testid="template-fit-verdict"] ~ ul')) {
      throw new Error("a one-reason card renders an empty detail list");
    }
  });

  // The objective is the heaviest signal in the template scorer and gates the
  // tailored templates, so leaving it optional meant the strongest
  // recommendation input was silently dropped whenever a founder skipped it -
  // and the step still claimed to be "scored for this app".
  await check("the merged step refuses to rank anything without an objective", async (ctx) => {
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
        await openStep(ctx, "Audience & template");
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
    if (!text.includes("Generate and pick an audience angle first; then choose its goal and template.")) {
      throw new Error("the merged step does not explain the missing angle before its goal");
    }
    // The fix lives on this same screen: the angle gate above is what ranks
    // the goal that ranks the templates, so no jump elsewhere is needed.
    if (!ctx.container.querySelector('[data-testid="generate-angles-button"]')) {
      throw new Error("there is no way on this step to fix the missing choice");
    }
  });

  await check("no objective is silently reported as done on the progress pills", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    const pill = ctx.container.querySelector('[data-testid="step-pill-angle"]');
    if (!pill) throw new Error("the progress pills carry no state markers");
    if (pill.getAttribute("data-state") === "done") {
      throw new Error("the Audience step is ticked before an objective is chosen");
    }
    if (pill.getAttribute("aria-label") !== "Audience & template: needs something from you") {
      throw new Error(
        `the pill does not say it is blocked: ${pill.getAttribute("aria-label")}`
      );
    }
  });

  await check("no angle is silently reported as done on the progress pills", async (ctx) => {
    // The objective alone used to satisfy this step, so the angle was cosmetic
    // to completion. Now an objective with no picked angle is still blocked.
    await withApi({
      getStudioProject: async () => ({ ...PROJECT_WITH_STRATEGY, content_angle_id: "" }),
    }, async () => {
  await check("an unknown angle kind provides six fallback goals without all-goals controls", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
        await mount(CreateVideo, {})(ctx);
        await act(async () => {});
      } finally {
        global.__SMOKE_PARAMS = "";
      }
      const pill = ctx.container.querySelector('[data-testid="step-pill-angle"]');
      if (!pill) throw new Error("the progress pills carry no state markers");
      if (pill.getAttribute("data-state") === "done") {
        throw new Error("the Audience step is ticked with an objective but no angle picked");
      }
      if (pill.getAttribute("aria-label") !== "Audience & template: needs something from you") {
        throw new Error(
          `the pill does not say it is blocked: ${pill.getAttribute("aria-label")}`
        );
      }
    });
  });

  // The profile pill names the step, not the app. Echoing the chosen app's
  // name beside "App Profile" repeated what the step's own picker card already
  // says and read as a second label on the same thing.
  await check("the progress pill for the app does not echo the app name", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
    } finally {
      global.__SMOKE_PARAMS = "";
    }
    const pill = ctx.container.querySelector('[data-testid="step-pill-profile"]');
    if (!pill) throw new Error("the progress pills carry no profile step");
    if ((pill.textContent || "").trim() !== "App Profile") {
      throw new Error(`the profile pill still names the app: ${JSON.stringify(pill.textContent)}`);
    }
    if (pill.getAttribute("aria-label") !== "App Profile: done") {
      throw new Error(`the profile pill announces the app: ${pill.getAttribute("aria-label")}`);
    }
  });



  await check("goal options wait until the founder picks an audience angle", async (ctx) => {
    await withApi({ getContentAngles: async () => ({ angles: [] }) }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Audience & template");
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      if (!step?.querySelector('[data-testid="angles-cta-copy"]')
          || !step.textContent.includes("(required)")) {
        throw new Error("the step does not explain that an audience angle is required");
      }
      const marker = step.querySelector('[data-testid="goal-waits-for-angle"]');
      if (!marker) {
        throw new Error("goal suggestions appear before an angle is selected");
      }
      // The marker is a contract, not copy. The angle ask is already on screen
      // above it — "(required)" plus the CTA sentence — so a line restating it
      // in the marker would be the third copy of the same instruction.
      if ((marker.textContent || "").trim() !== "") {
        throw new Error(
          `the goal waits marker carries copy again: ${JSON.stringify(marker.textContent)}`
        );
      }
      if (step.querySelector('[data-testid^="recommended-goal-"]')) {
        throw new Error("featured goal buttons appear without an angle");
      }
    });
  });

  await check("six goals are tailored when an angle is selected without an all-goals control", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    await openStep(ctx, "Audience & template");
    await passAngleGate(ctx);
    const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
    const angleButtons = [...step.querySelectorAll("button")]
      .filter((button) => button.textContent.includes(ANGLE.label));
    if (angleButtons.length !== 1) throw new Error(`expected one angle control, saw ${angleButtons.length}`);
    const angleButton = angleButtons[0];
    await clickEl(ctx, angleButton);
    const featured = [...step.querySelectorAll('[data-testid^="recommended-goal-"]')];
    if (featured.length !== 6) throw new Error(`expected six featured goals, saw ${featured.length}`);
    const expected = ANGLE_GOALS.problem_solution;
    const shown = featured.map((button) => button.getAttribute("data-testid").slice("recommended-goal-".length));
    if (JSON.stringify(shown) !== JSON.stringify(expected)) {
      throw new Error(`the wrong goals were recommended: ${JSON.stringify(shown)}`);
    }
    if (!step.textContent.includes(OBJECTIVE_OUTCOMES[expected[0]])) {
      throw new Error("recommended goal choices do not explain their intended outcome");
    }
    if (step.querySelector("select, details") || step.textContent.includes("See all goals")) {
      throw new Error("the removed all-goals control is still present");
    }
    if (!step.textContent.includes("Six suggestions")) throw new Error("the copy does not describe six suggestions");
  });

  await check("changing an angle reranks goals without changing a chosen goal", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    await openStep(ctx, "Audience & template");
    await passAngleGate(ctx);
    const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
    const buttons = [...step.querySelectorAll("button")];
    await clickEl(ctx, buttons.find((button) => button.textContent.includes(ANGLE.label)));
    await clickEl(ctx, step.querySelector('[data-testid="recommended-goal-address_user_problem"]'));
    await act(async () => {});
    await act(async () => {});
    if (step.querySelector('[data-testid="recommended-goal-address_user_problem"]')?.getAttribute("aria-pressed") !== "true") {
      throw new Error("selecting the first goal did not update its selected state");
    }
    await clickEl(ctx, [...step.querySelectorAll("button")].find((button) => button.textContent.includes(ANGLE_B.label)));
    await act(async () => {});
    await act(async () => {});
    if (!step.querySelector('[data-testid="recommended-goal-demonstrate_feature"]')) {
      throw new Error("changing angle did not rerank the six goal suggestions");
    }
    if (!step.querySelector('[data-testid="goal-outside-recommendations"]')
        || !step.textContent.includes("Address User Problem")) {
      throw new Error(`the existing goal was replaced instead of being preserved with a nudge; goal text was: ${step.textContent}`);
    }
  });

  // -------------------------------------------------------------------------
  // The picked angle shows the fields the strategy is written from.
  //
  // Closed, an angle is one line — the field its KIND is best summarized by —
  // which is what makes the list comparable. That line is a summary: the
  // promise, the feature it demonstrates and the claims bounding it were never
  // visible in the flow that renders them, so the founder chose from a model's
  // one-line abstraction and the first sight of the rest was the strategy. The
  // picked row now opens onto its own fields; the others stay closed, because
  // two open panels side by side are two half-read angles.
  // -------------------------------------------------------------------------
  await check("the picked audience angle shows the fields the strategy uses", async (ctx) => {
    const FULL_ANGLE = {
      id: "a3",
      kind: "problem_solution",
      label: "The nightly reset",
      target_audience: "shift workers who plan at midnight",
      user_problem: "Plans get made after the day is over",
      hook_promise: "Tomorrow is decided in one tap",
      app_feature: "One-tap shift logging",
      desired_emotion: "Relief",
      claims_to_respect: ["works offline", "no iOS support"],
    };
    await withApi({ getContentAngles: async () => ({ angles: [FULL_ANGLE, ANGLE] }) }, async () => {
      global.__SMOKE_PARAMS = "";
      await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Audience & template");
        await passAngleGate(ctx);
      const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
      if (step.querySelector('[data-testid^="angle-details-"]')) {
        throw new Error("an angle shows its fields before it is picked");
      }
      // A closed row is its title only. The subtitle came off the bar, so the
      // field that used to summarize it must not be on screen before the pick
      // — the open panel is what shows it now.
      if (step.textContent.includes("Plans get made after the day is over")) {
        throw new Error("a closed angle row still prints its subtitle");
      }

      await clickEl(ctx, step.querySelector('[data-testid="angle-option-a3"]'), "no angle row to pick");
      const detail = step.querySelector('[data-testid="angle-details-a3"]');
      if (!detail) throw new Error("picking an angle did not show its fields");
      const shown = detail.textContent;
      for (const field of [
        "Audience", "Shift workers who plan at midnight",
        "Problem", "Plans get made after the day is over",
        "First 3 seconds promise", "Tomorrow is decided in one tap",
        "Feature shown", "One-tap shift logging",
        "Emotion by the end", "Relief",
        "Bounded by", "Works offline; No iOS support",
      ]) {
        if (!shown.includes(field)) {
          throw new Error(`the picked angle does not show ${JSON.stringify(field)}: ${shown}`);
        }
      }
      if (step.querySelectorAll('[data-testid^="angle-details-"]').length !== 1) {
        throw new Error("more than one angle is open at once");
      }

      await clickEl(ctx, step.querySelector('[data-testid="angle-option-a1"]'), "no second angle row to pick");
      if (step.querySelector('[data-testid="angle-details-a3"]')) {
        throw new Error("the previously picked angle stayed open after another was picked");
      }
      const secondDetail = step.querySelector('[data-testid="angle-details-a1"]');
      if (!secondDetail?.textContent.includes("Busy professionals")) {
        throw new Error("the newly picked angle does not show its own audience");
      }
      if (step.querySelector('[data-testid="angle-option-a1"]').getAttribute("aria-expanded") !== "true"
          || step.querySelector('[data-testid="angle-option-a3"]').getAttribute("aria-expanded") !== "false") {
        throw new Error("the angle bars do not report which one is open");
      }
    });
  });

  // A row is its kind's glyph and its uppercase title, and nothing else. The
  // subtitle, the kind badge and the founder verdict tally all came off the
  // bar: three pieces of meta around a 14px title made a list you scan into a
  // paragraph you read, and the picked row still opens onto every field. Pinned
  // on the rendered row, so any of the three drifting back is caught here.
  await check("angle rows show only their kind icon and caps title", async (ctx) => {
    const PROVEN = { ...ANGLE, id: "a9", label: "Proven opener", evidence: { wins: 3, flops: 1 } };
    // Every row, not the first: the rule is the list's, and a row that kept
    // its old chrome would be the one a single-row fixture never looked at.
    const ROWS = [
      ["a9", "Proven opener", ["Nothing gets finished", "wins", "flop"]],
      ["a2", "One-tap timer", ["Starting takes too many steps", "Feature demonstration"]],
    ];
    await withApi({ getContentAngles: async () => ({ angles: [PROVEN, ANGLE_B] }) }, async () => {
      global.__SMOKE_PARAMS = "";
      try {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Audience & template");
        await passAngleGate(ctx);
        const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
        const rendered = [...step.querySelectorAll('[data-testid^="angle-option-"]')];
        if (rendered.length !== ROWS.length) {
          throw new Error(`expected ${ROWS.length} angle rows, saw ${rendered.length}`);
        }
        for (const [id, label, extras] of ROWS) {
          const row = step.querySelector(`[data-testid="angle-option-${id}"]`);
          if (!row) throw new Error(`no row for angle ${id}`);
          const spans = [...row.querySelectorAll("span")];
          if (spans.length !== 1) {
            throw new Error(`angle ${id} renders ${spans.length} text spans, expected its title alone`);
          }
          const title = spans[0];
          if (!/uppercase/.test(title.className) || !/tracking-/.test(title.className)) {
            throw new Error(`angle ${id}'s title is off the uppercase tracked token: ${title.className}`);
          }
          if (title.textContent.trim() !== label) {
            throw new Error(`angle ${id} shows more than its label: ${JSON.stringify(title.textContent)}`);
          }
          const text = row.textContent;
          for (const extra of extras) {
            if (text.includes(extra)) {
              throw new Error(`angle ${id} still shows ${JSON.stringify(extra)}: ${text}`);
            }
          }
          if (row.querySelector('[data-testid^="angle-evidence-"]')) {
            throw new Error(`the verdict chip came back onto angle ${id}`);
          }
          if (!row.querySelector('[data-testid="angle-row-check"]')) {
            throw new Error(`angle ${id} lost its check mark`);
          }
        }
      } finally {
        global.__SMOKE_PARAMS = "";
      }
    });
  });

  // Every angle row opens with the same check mark at the bar's 16px icon
  // size — muted until picked, indigo once open. One glyph for every row:
  // twelve kind icons made the list something you decode rather than scan.
  await check("angle rows carry the check mark", async (ctx) => {
    await withApi({ getContentAngles: async () => ({ angles: [ANGLE, ANGLE_B] }) }, async () => {
      global.__SMOKE_PARAMS = "";
      try {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Audience & template");
        await passAngleGate(ctx);
        const rows = [...ctx.container.querySelectorAll('[data-testid^="angle-option-"]')];
        if (rows.length !== 2) throw new Error(`expected two angle rows, saw ${rows.length}`);
        for (const row of rows) {
          const icon = row.querySelector('[data-testid="angle-row-check"]');
          if (!icon) throw new Error("an angle row shows no check mark");
          if (icon.tagName !== "svg") throw new Error("the check mark is not an svg glyph");
          const cls = icon.getAttribute("class") || "";
          if (!/\bh-4\b/.test(cls) || !/\bw-4\b/.test(cls)) {
            throw new Error(`the check mark is off the 16px token: ${cls}`);
          }
          if (/brand-indigo/.test(cls)) throw new Error("an unpicked row shows the picked check");
        }
        await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'), "no angle row to pick");
        const picked = ctx.container.querySelector('[data-testid="angle-option-a1"] [data-testid="angle-row-check"]');
        const other = ctx.container.querySelector('[data-testid="angle-option-a2"] [data-testid="angle-row-check"]');
        if (!picked || !/brand-indigo/.test(picked.getAttribute("class") || "")) {
          throw new Error("the picked row's check did not turn indigo");
        }
        if (!other || /brand-indigo/.test(other.getAttribute("class") || "")) {
          throw new Error("the unpicked row's check is not muted");
        }
      } finally {
        global.__SMOKE_PARAMS = "";
      }
    });
  });

  // The goal cards annotate with the picked angle kind's counts; the six stay
  // in fetched order. Evidence must never become a second ranking.
  await check("goal cards carry the angle kind's counts without reordering", async (ctx) => {
    const PROVEN = { ...ANGLE, evidence: { wins: 2, flops: 1 } };
    await withApi({ getContentAngles: async () => ({ angles: [PROVEN, ANGLE_B] }) }, async () => {
      global.__SMOKE_PARAMS = "";
      try {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Audience & template");
        await passAngleGate(ctx);
        await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'), "no angle row to pick");
        const line = ctx.container.querySelector('[data-testid="goal-angle-evidence-address_user_problem"]');
        if (!line) throw new Error("the goal card shows no angle-kind count");
        if (!line.textContent.includes("2 wins") || !line.textContent.includes("1 flop")) {
          throw new Error(`the goal line does not read as counts: ${line.textContent}`);
        }
        const order = [...ctx.container.querySelectorAll('[data-testid^="recommended-goal-"]')]
          .map((el) => el.getAttribute("data-testid").replace("recommended-goal-", ""));
        const expected = ANGLE_GOALS.problem_solution;
        if (order.join("|") !== expected.join("|")) {
          throw new Error(`goal order moved: ${order.join(", ")}`);
        }
      } finally {
        global.__SMOKE_PARAMS = "";
      }
    });
  });

  await check("formatVerdicts prints counts and stays silent on empty evidence", async () => {
    const { formatVerdicts } = load("lib/angleSubtitle.js");
    const cases = [
      [{ wins: 3, flops: 1 }, "3 wins · 1 flop"],
      [{ wins: 1, flops: 0 }, "1 win"],
      [{ wins: 0, flops: 1 }, "1 flop"],
      [{ wins: 0, flops: 0 }, ""],
      [undefined, ""],
      [null, ""],
    ];
    for (const [input, want] of cases) {
      const got = formatVerdicts(input);
      if (got !== want) {
        throw new Error(`formatVerdicts(${JSON.stringify(input)}) is ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
      }
    }
  });

  // Generated angle copy arrives as sentences (trailing full stop included)
  // but renders as standalone lines, where the period is clutter. Stripped at
  // render, with an ellipsis and an abbreviation tail left alone.
  await check("angle copy carries no trailing period", async () => {
    const { angleSubtitle, angleDetails, stripTrailingPeriod } = load("lib/angleSubtitle.js");
    const cases = [
      ["Nothing gets finished.", "Nothing gets finished"],
      ["No dot here", "No dot here"],
      ["Wait...", "Wait..."],
      ["Such as e.g.", "Such as e.g."],
      ["", ""],
    ];
    for (const [input, want] of cases) {
      const got = stripTrailingPeriod(input);
      if (got !== want) {
        throw new Error(`stripTrailingPeriod(${JSON.stringify(input)}) is ${JSON.stringify(got)}, want ${JSON.stringify(want)}`);
      }
    }
    const sub = angleSubtitle({ kind: "problem_solution", user_problem: "Nothing gets finished." });
    if (sub !== "Nothing gets finished") {
      throw new Error(`angle subtitle kept its period: ${JSON.stringify(sub)}`);
    }
    const rows = angleDetails({ target_audience: "busy professionals.", user_problem: "Nothing gets finished." });
    for (const row of rows) {
      if (/\.$/.test(row.value)) {
        throw new Error(`angle detail kept its period: ${JSON.stringify(row)}`);
      }
    }
  });

  // The objective axis on goal cards: same counts, different key. The goal
  // picker is the surface where "what wins at this goal" should guide choice,
  // not the angle-kind axis. The evidence map is keyed by objective name
  // and is shared across kinds; the picker just reads it.
  await check("goal cards show objective-level counts alongside angle-kind counts", async (ctx) => {
    const PROVEN_OBJ = {
      ...ANGLE,
      objective: "address_user_problem",
      evidence: { wins: 2, flops: 1 },
      objective_evidence: { address_user_problem: { wins: 3, flops: 1 } },
    };
    await withApi(
      { getContentAngles: async () => ({ angles: [PROVEN_OBJ, ANGLE_B], objective_evidence: { address_user_problem: { wins: 3, flops: 1 } } }) },
      async () => {
        global.__SMOKE_PARAMS = "";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Audience & template");
          await passAngleGate(ctx);
          await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'), "no angle row to pick");
          const objLine = ctx.container.querySelector('[data-testid="goal-objective-evidence-address_user_problem"]');
          if (!objLine) throw new Error("the goal card shows no objective-level count");
          if (!objLine.textContent.includes("3 wins") || !objLine.textContent.includes("1 flop")) {
            throw new Error(`objective line does not read as counts: ${objLine.textContent}`);
          }
          if (objLine.textContent.includes("%")) {
            throw new Error("objective line presents a rate instead of counts");
          }
          const kindLine = ctx.container.querySelector('[data-testid="goal-angle-evidence-address_user_problem"]');
          if (!kindLine) throw new Error("the goal card lost its angle-kind count");
          if (!kindLine.textContent.includes("2 wins") || !kindLine.textContent.includes("1 flop")) {
            throw new Error(`kind line does not read as counts: ${kindLine.textContent}`);
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

// The objective axis must not reorder the six-goal list — it annotates.
  await check("objective evidence does not reorder the goal list", async (ctx) => {
    const PROVEN_OBJ = {
      ...ANGLE,
      objective: "address_user_problem",
      evidence: { wins: 2, flops: 1 },
      objective_evidence: { address_user_problem: { wins: 3, flops: 1 } },
    };
    await withApi(
      { getContentAngles: async () => ({ angles: [PROVEN_OBJ, ANGLE_B], objective_evidence: { address_user_problem: { wins: 3, flops: 1 } } }) },
      async () => {
        global.__SMOKE_PARAMS = "";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Audience & template");
          await passAngleGate(ctx);
          // Wait for facet recommendations to load - need to flush effects and wait for async
          await act(async () => {});
          await act(async () => {});
          await new Promise((r) => setTimeout(r, 200));
          // Debug: check if angle state is set
          const angleEl = ctx.container.querySelector('[data-testid="angle-option-a1"]');
          if (!angleEl) throw new Error("angle option a1 not found");
          await clickEl(ctx, angleEl, "no angle row to pick");
          await act(async () => {});
          await new Promise((r) => setTimeout(r, 200));
          const goals = [...ctx.container.querySelectorAll('[data-testid^="recommended-goal-"]')]
            .map((el) => el.getAttribute("data-testid").replace("recommended-goal-", ""));
          if (goals.length === 0) {
            const html = ctx.container.innerHTML;
            throw new Error(`no goal cards found. HTML: ${html.slice(0, 3000)}`);
          }
          const expected = ANGLE_GOALS.problem_solution;
          if (goals.join("|") !== expected.join("|")) {
            throw new Error(`goal order moved: ${goals.join(", ")}`);
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Shuffle advances the six goal suggestions on every press and always
  // shows six. The stub mirrors the server contract: the variant persists
  // server-side and the list re-read drives the display (the POST return is
  // ignored by the client, so a stub that only answers the POST proves
  // nothing — the GET must reflect the new order).
  await check("shuffle advances the six goal suggestions on every press", async (ctx) => {
    const SIX = ANGLE_GOALS.problem_solution;
    const rotate = (list, step) => [...list.slice(step), ...list.slice(0, step)];
    let variant = 0;
    const SHUFFLED = {
      ...ANGLE,
      goal_variant: 0,
      goal_suggestions: [...SIX],
      evidence: { wins: 0, flops: 0 },
    };
    const orderOf = () => [...ctx.container.querySelectorAll('[data-testid^="recommended-goal-"]')]
      .map((el) => el.getAttribute("data-testid").replace("recommended-goal-", ""));
    apiCalls.length = 0;
    await withApi(
      {
        getContentAngles: async () => ({
          angles: [{ ...SHUFFLED, goal_variant: variant, goal_suggestions: rotate(SIX, variant) }],
          objective_evidence: {},
        }),
        regenerateContentAngleGoals: async () => {
          variant = variant >= 3 ? 1 : variant + 1;
          return { goal_variant: variant, suggestions: rotate(SIX, variant) };
        },
      },
      async () => {
        global.__SMOKE_PARAMS = "";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Audience & template");
          await passAngleGate(ctx);
          await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'), "no angle row to pick");
          const first = orderOf();
          if (first.length !== 6) throw new Error(`expected six goal cards, saw ${first.length}`);
          if (first.join("|") !== SIX.join("|")) throw new Error(`initial goal order moved: ${first.join(", ")}`);
          // The picker heading is a GroupLabel now; its id must still land
          // on the h3 or aria-labelledby points nowhere.
          const goalLabel = ctx.container.querySelector("#video-goal-label");
          if (!goalLabel || goalLabel.tagName !== "H3") {
            throw new Error("the video goal heading lost its labelledby id");
          }
          const seen = [first.join("|")];
          for (let press = 0; press < 3; press += 1) {
            await clickEl(ctx, ctx.container.querySelector('[data-testid="regenerate-goals-button"]'), "no shuffle button");
            await new Promise((r) => setTimeout(r, 150));
            const order = orderOf();
            if (order.length !== 6) throw new Error(`press ${press + 1}: expected six goal cards, saw ${order.length}`);
            if (seen.includes(order.join("|"))) throw new Error(`press ${press + 1}: goal order repeats an earlier one`);
            seen.push(order.join("|"));
          }
          if (!apiCalls.includes("regenerateContentAngleGoals")) {
            throw new Error("shuffle never called the server variant endpoint");
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Shuffle narrates fresh work while cycling, then the six arrive staggered —
  // never a spinner-to-grid blink, and never a frozen count beside an error.
  await check("goal shuffle counts up in flight, then cascades cards in", async (ctx) => {
    const SIX = ANGLE_GOALS.problem_solution;
    let releaseShuffle;
    const shuffleGate = new Promise((resolve) => { releaseShuffle = resolve; });
    await withApi(
      {
        getContentAngles: async () => ({
          angles: [{ ...ANGLE, goal_variant: 0, goal_suggestions: [...SIX] }],
          objective_evidence: {},
        }),
        regenerateContentAngleGoals: () => shuffleGate,
      },
      async () => {
        global.__SMOKE_PARAMS = "";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Audience & template");
          await passAngleGate(ctx);
          await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'), "no angle row to pick");
          await clickEl(ctx, ctx.container.querySelector('[data-testid="regenerate-goals-button"]'), "no shuffle button");
          const progress = ctx.container.querySelector('[data-testid="goals-progress"]');
          if (!progress) throw new Error("no live count while goals reshuffle");
          if (!/Shuffling goal \d+ of 6/.test(progress.textContent || "")) {
            throw new Error(`the count does not read as fresh work: ${JSON.stringify(progress.textContent)}`);
          }
          await act(async () => {
            releaseShuffle({ goal_variant: 1, suggestions: [...SIX].reverse() });
          });
          await act(async () => {});
          if (ctx.container.querySelector('[data-testid="goals-progress"]')) {
            throw new Error("the count survived its own reshuffle");
          }
          const cards = [...ctx.container.querySelectorAll('[data-testid^="recommended-goal-"]')];
          if (cards.length !== 6) throw new Error(`expected six goal cards, saw ${cards.length}`);
          const delays = cards.map((card) => {
            const host = card.closest(".animate-fade-up");
            if (!host) throw new Error("a fresh goal card carries no arrival animation");
            return host.style.animationDelay;
          });
          if (new Set(delays).size !== delays.length) {
            throw new Error(`goal cards do not arrive staggered: ${JSON.stringify(delays)}`);
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // Regenerate angles replaces the list with six fresh serialized rows and
  // keeps the goal step populated: the old pick's id is gone, so the wizard
  // parks on the strongest new angle instead of collapsing to the wait
  // state, and every fresh row still opens with its kind's glyph.
  await check("regenerate angles shows six fresh options and keeps goals", async (ctx) => {
    const FRESH = [0, 1, 2, 3, 4, 5].map((i) => ({
      id: `n${i}`,
      kind: "problem_solution",
      label: `Fresh angle ${i}`,
      target_audience: "busy professionals",
      user_problem: "Nothing gets finished.",
      goal_variant: 0,
      origin: "generated",
      goal_suggestions: [...ANGLE_GOALS.problem_solution],
      evidence: { wins: 2, flops: 1 },
    }));
    await withApi(
      {
        getContentAngles: async () => ({ angles: [ANGLE, ANGLE_B], objective_evidence: {} }),
        regenerateContentAngles: async () => ({ angles: FRESH, objective_evidence: {} }),
      },
      async () => {
        global.__SMOKE_PARAMS = "";
        try {
          await mount(CreateVideo, {})(ctx);
          await openStep(ctx, "Audience & template");
          await passAngleGate(ctx);
          await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'), "no angle row to pick");
          await clickEl(ctx, ctx.container.querySelector('[data-testid="regenerate-angles-button"]'), "no regenerate button");
          await new Promise((r) => setTimeout(r, 150));
          const rows = [...ctx.container.querySelectorAll('[data-testid^="angle-option-"]')];
          if (rows.length !== 6) throw new Error(`expected six fresh angles, saw ${rows.length}`);
          if (ctx.container.querySelector('[data-testid="angle-option-a1"]')) {
            throw new Error("the replaced angle row is still rendered");
          }
          if (!rows[0].textContent.includes("Fresh angle")) {
            throw new Error("the angle list did not refresh with new options");
          }
          const goals = [...ctx.container.querySelectorAll('[data-testid^="recommended-goal-"]')];
          if (goals.length !== 6) throw new Error(`expected six goal cards after regen, saw ${goals.length}`);
          const glyphs = [...ctx.container.querySelectorAll('[data-testid="angle-row-check"]')];
          if (glyphs.length !== 6) {
            throw new Error(`the six fresh rows lost their check marks: saw ${glyphs.length}`);
          }
        } finally {
          global.__SMOKE_PARAMS = "";
        }
      }
    );
  });

  // The vertical scrollbar's gutter stays reserved, so switching between
  // steps of different heights never shifts the centred frame sideways.
  // jsdom does no layout, so this guards the rule in source: deleting the
  // declaration is exactly how the shift comes back.
  await check("the page reserves the scrollbar gutter across steps", async () => {
    const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
    if (!/html\s*\{[^}]*scrollbar-gutter\s*:\s*stable/.test(css)) {
      throw new Error("index.css does not reserve the scrollbar gutter on html");
    }
  });

  // formatVerdicts prints counts and stays silent on empty evidence
  await check("formatVerdicts prints counts and stays silent on empty evidence", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    const rankings = [];
    const writes = [];
    await withApi({
      getTemplateRecommendations: async (profile, query) => {
        rankings.push(query);
        return { recommendations: [{ template: TEMPLATE, why_it_fits: [], limitations: [] }] };
      },
      createStudioProject: async (payload) => {
        writes.push(payload);
        return { ...BASE_PROJECT, ...payload };
      },
      updateStudioProject: async (id, payload) => {
        writes.push(payload);
        return { ...BASE_PROJECT, ...payload };
      },
    }, async () => {
      await mount(CreateVideo, {})(ctx);
      await openTemplateStep(ctx);
      await openStep(ctx, "Audience & template");
      const goal = ctx.container.querySelector('[data-testid="recommended-goal-educate_viewers"]');
      await clickEl(ctx, goal);
      if (goal.getAttribute("aria-pressed") !== "true") throw new Error("the sixth goal was not selected");
      await openStep(ctx, "Audience & template");
      if (!rankings.some((query) => query.objective === "educate_viewers" && query.angle_id === "a1")) {
        throw new Error("ranking did not receive the sixth suggested goal and selected angle");
      }
      if (!writes.some((payload) => payload.objective === "educate_viewers" && payload.content_angle_id === "a1")) {
        throw new Error("project persistence did not receive the sixth suggested goal and selected angle");
      }
    });
  });

  await check("Review with a goal but no angle waits for a real angle before planning", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    let plans = 0;
    try {
      await withApi({
        getStudioProject: async () => ({ ...BASE_PROJECT, content_angle_id: "" }),
        updateStudioProject: async (id, payload) => ({ ...BASE_PROJECT, ...payload }),
        generatePlan: async () => { plans += 1; return PROJECT_WITH_STRATEGY; },
      }, async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Review & submit");
        if (plans !== 0) throw new Error("a plan was generated before an angle was selected");
        if (ctx.text().includes("Generating your plan")) throw new Error("Review spins while missing an angle");
        // No angle control lives here anymore: one red jump back to step 1,
        // where selection happens, then back to Review for the plan.
        await clickEl(ctx, ctx.container.querySelector('[data-testid="goto-first-gap-button"]'), "no first-gap button on Review");
        const pill = ctx.container.querySelector('[data-testid="step-pill-angle"]');
        if (!pill || pill.getAttribute("aria-current") !== "step") {
          throw new Error("the red button did not land on the Audience & template step");
        }
        await passAngleGate(ctx);
        await clickEl(ctx, ctx.container.querySelector('[data-testid="angle-option-a1"]'));
        await openStep(ctx, "Review & submit");
        await act(async () => {});
        if (plans !== 1) throw new Error(`selecting an angle started ${plans} plans instead of one`);
      });
    } finally { global.__SMOKE_PARAMS = ""; }
  });

  // The still-missing panel offers one red button to the first missing choice
  // in flow order — never a generate action while anything is missing, and
  // never two black buttons naming their destinations beside two subtitles.
  await check("Review sends a missing profile back to its step on one red button", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    try {
      await withApi({
        getAppProfiles: async () => ({ profiles: [] }),
        getStudioProject: async () => ({ ...BASE_PROJECT, brand_profile_id: "", content_angle_id: "", objective: "" }),
        updateStudioProject: async (id, payload) => ({ ...BASE_PROJECT, ...payload }),
        getContentAngles: async () => ({ angles: [] }),
      }, async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Review & submit");
        const btn = ctx.container.querySelector('[data-testid="goto-first-gap-button"]');
        if (!btn) throw new Error("no single red button on the still-missing panel");
        if (!/Choose an App Profile/.test(btn.textContent || "")) {
          throw new Error(`the button does not name the first gap: ${JSON.stringify(btn.textContent)}`);
        }
        await clickEl(ctx, btn);
        const pill = ctx.container.querySelector('[data-testid="step-pill-profile"]');
        if (!pill || pill.getAttribute("aria-current") !== "step") {
          throw new Error("the red button did not land on the App Profile step");
        }
      });
    } finally { global.__SMOKE_PARAMS = ""; }
  });

  // One gap, one button — never two competing "first" asks. With a profile and
  // template present but no angle or goal, the panel shows the angle action
  // only; the goal waits for the angle that would rank it.
  await check("Review shows only the gap actually missing, never two firsts", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi({
        getStudioProject: async () => ({
          ...BASE_PROJECT,
          brand_profile_id: "b1",
          template_id: "t1",
          content_angle_id: "",
          objective: "",
        }),
        updateStudioProject: async (id, payload) => ({ ...BASE_PROJECT, ...payload }),
        getContentAngles: async () => ({ angles: [] }),
      }, async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Review & submit");
      const firsts = [...ctx.container.querySelectorAll("button")]
        .filter((b) => /first/.test((b.textContent || "")));
      if (firsts.length !== 1) {
        throw new Error(`expected exactly one 'first' action, saw ${firsts.length}: ${JSON.stringify(firsts.map((b) => b.textContent))}`);
      }
        if (!/Pick an audience angle first/.test(firsts[0].textContent || "")) {
          throw new Error(`the lone action does not name the missing angle: ${JSON.stringify(firsts[0].textContent)}`);
        }
      });
    } finally { global.__SMOKE_PARAMS = ""; }
  });

  // The red "Pick an audience angle first" above the plan is the same ask as the
  // render section's own angle CTA below it, so it must be the same control:
  // the small size read as a lesser action than the button it duplicates.
  // One check, two drafts on separate roots: no plan (the missing panel names
  // the gap) and a plan but no angle (the render section asks instead of
  // generating). Re-mounting in one container would keep the first draft's
  // state and prove nothing about the second.
  await check("Review & submit's angle gap asks once, with one shared control", async (ctx) => {
    global.__SMOKE_PARAMS = "?project=p1";
    const second = dom.window.document.createElement("div");
    dom.window.document.body.appendChild(second);
    const secondRoot = createRoot(second);
    const later = { root: secondRoot, container: second, text: () => second.textContent || "" };
    let reviewBtn = null;
    try {
      await withApi({
        getStudioProject: async () => ({ ...BASE_PROJECT, content_angle_id: "" }),
      }, async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Review & submit");
        reviewBtn = ctx.container.querySelector('[data-testid="goto-first-gap-button"]');
        if (!reviewBtn) throw new Error("Review & submit has no first-gap button");
        if (!/Pick an audience angle first/.test(reviewBtn.textContent || "")) {
          throw new Error(`Review & submit's first-gap button names something else: ${JSON.stringify(reviewBtn.textContent)}`);
        }
        await withApi({
          getStudioProject: async () => ({ ...PROJECT_WITH_STRATEGY, content_angle_id: "" }),
        }, async () => {
          await mount(CreateVideo, {})(later);
          await openStep(later, "Review & submit");
          const hookBtn = later.container.querySelector('[data-testid="generate-angles-button"]');
          if (!hookBtn) throw new Error("the render section has no angle CTA to compare against");
          if (hookBtn.className !== reviewBtn.className) {
            throw new Error(
              "Review & submit's first-gap button is not the render gate control:\n" +
                `  review: ${reviewBtn.className}\n  hook:   ${hookBtn.className}`
            );
          }
        });
      });
    } finally {
      global.__SMOKE_PARAMS = "";
      await act(async () => { secondRoot.unmount(); });
      second.remove();
    }
  });

  // The "what's missing" gate is one section wherever it appears: a helper line
  // with the red action under it, spaced the same everywhere. Review's stack is
  // the reference, so a gate cannot drift tighter and make the same ask read as
  // a different kind of control.
  await check("every step spaces its gate hint from the red button the same", async (ctx) => {
    const gates = [];
    const record = (label, hint) => {
      if (!hint) throw new Error(`no gate hint on ${label}`);
      const token = (/space-y-\d/.exec(hint.parentElement.className) || [""])[0];
      if (!token) throw new Error(`the gate hint on ${label} shares no spacing token with its button`);
      const button = hint.nextElementSibling;
      if (!button || button.tagName !== "BUTTON") {
        throw new Error(`no button directly under the gate hint on ${label}`);
      }
      if (!button.className.includes("bg-[color:var(--brand-indigo)]")) {
        throw new Error(`the gate action on ${label} is not the indigo button`);
      }
      gates.push({ label, token });
    };
    const hintStartingWith = (prefix) =>
      [...ctx.container.querySelectorAll("p")].find((p) => (p.textContent || "").trim().startsWith(prefix));

    // The choosing screen from a blank draft (no angle, no goal, no template)
    // and the still-missing panel: the goal hint below the angle gate names the
    // next pick but carries no red button of its own — the angle CTA above is
    // the fix — so only the angle gate records a spacing here.
    global.__SMOKE_PARAMS = "";
    await mount(CreateVideo, {})(ctx);
    await openStep(ctx, "Audience & template");
    record("Audience & template", ctx.container.querySelector('[data-testid="angles-cta-copy"]'));
    await openStep(ctx, "Review & submit");
    record("Review & submit", hintStartingWith("Your free plan starts"));

    // The render gate with an angle but no template: the gate that used to state
    // the problem with no way out. A planned project, because the gate below
    // the plan only renders once a plan exists to approve. Recommendations are
    // empty so nothing is preselected into the template slot.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi({
        getStudioProject: async () => ({ ...PROJECT_WITH_STRATEGY, content_angle_id: "a1", template_id: "" }),
        getTemplateRecommendations: async () => ({ recommendations: [] }),
      }, async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Review & submit");
        const button = ctx.container.querySelector('[data-testid="hook-first-gap-button"]');
        if (!button) throw new Error("the render gate has no red button");
        record("render gate", button.previousElementSibling);
      });
    } finally {
      global.__SMOKE_PARAMS = "";
    }

    const tokens = [...new Set(gates.map((g) => g.token))];
    if (tokens.length !== 1) {
      throw new Error(
        `the gate sections do not share one spacing: ${gates
          .map((g) => `${g.label}=${g.token}`)
          .join(", ")}`
      );
    }
  });
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await withApi({ getContentAngles: async () => ({ angles: [{ ...ANGLE, kind: "legacy" }] }) }, async () => {
        await mount(CreateVideo, {})(ctx);
        await openStep(ctx, "Audience & template");
        const goals = ctx.container.querySelectorAll('[data-testid^="recommended-goal-"]');
        if (goals.length !== 6) throw new Error("legacy angle does not provide six fallback goals");
        if (ctx.container.querySelector("#all-video-goals")) throw new Error("legacy angle shows the removed selector");
        const goal = ctx.container.querySelector('[data-testid="recommended-goal-demonstrate_feature"]');
        await clickEl(ctx, goal);
        if (goal.getAttribute("aria-pressed") !== "true") throw new Error("legacy angle blocks fallback selection");
      });
    } finally { global.__SMOKE_PARAMS = ""; }
  });

  await check("progress ticks mean done, not merely being to the left", async (ctx) => {
    // The tick used to mean "this step index is below the current one", so
    // jumping straight to the last step showed a tick on all three while nothing
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
    // No render-only pill exists anymore: the render lives at the bottom of
    // Review & submit, so there is no separate step that could tick. The merge
    // is pinned by asserting the retired pills are gone rather than unticked.
    for (const retired of ["step-pill-template", "step-pill-hook"]) {
      if (ctx.container.querySelector(`[data-testid="${retired}"]`)) {
        throw new Error(`the retired ${retired} pill still exists as its own step`);
      }
    }
  });

  await check("a plan with unsaved edits is not reported as reviewed", async (ctx) => {
    // The tick has to mean "read and stored", not "a plan exists". Otherwise
    // the progress indicator tells the founder they finished reading a script
    // they had changed and not saved.
    global.__SMOKE_PARAMS = "?project=p1";
    try {
      await mount(CreateVideo, {})(ctx);
      await openStep(ctx, "Review & submit");
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
        ensureObjectiveTemplates: async () => ({
          templates: ORDERED_TEMPLATES,
          generated: false,
          objective: "address_user_problem",
          error: null,
        }),
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
        // Review & submit follows the merged choosing screen on the same step;
        // "Assets" used to be its own step, which no longer exists.
        await openStep(ctx, "Review & submit");
        await openStep(ctx, "Audience & template");
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
    // merged step opens, which is after mount.
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
        await openStep(ctx, "Audience & template");
        await passAngleGate(ctx);
        await clickEl(ctx, [...ctx.container.querySelectorAll("button")].find((button) => button.textContent.includes(ANGLE.label)));
        await clickEl(ctx, ctx.container.querySelector('[data-testid="recommended-goal-address_user_problem"]'));
        const pill = stepPill(ctx, "Audience & template");
        await act(async () => {
          pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});
      }
    );
    expectText(ctx, "still work", "the attached generation error was not surfaced");
    expectText(ctx, "Name the misdiagnosis", "the curated fallback is hidden on a tailoring failure");
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
          await openStep(ctx, "Audience & template");
          await passAngleGate(ctx);
          await clickEl(ctx, [...ctx.container.querySelectorAll("button")].find((button) => button.textContent.includes(ANGLE.label)));
        await clickEl(ctx, ctx.container.querySelector('[data-testid="recommended-goal-address_user_problem"]'));
        const pill = stepPill(ctx, "Audience & template");
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

  await check("pre-made templates stay hidden until the tailored set is ready", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    const PREMADE = { ...TEMPLATE, id: "t-premade", name: "Premade Pick" };
    const CUSTOM = {
      ...TEMPLATE,
      id: "t-custom",
      name: "Custom Pick",
      brand_profile_id: "b1",
      objective: "address_user_problem",
      origin: "custom",
    };
    let releaseTailoring;
    const tailoringGate = new Promise((resolve) => {
      releaseTailoring = resolve;
    });
    await withApi(
      {
        getTemplates: async () => ({ templates: [PREMADE, CUSTOM] }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            { template: PREMADE, score: 9, why_it_fits: ["popular"], limitations: [] },
            { template: CUSTOM, score: 8, why_it_fits: ["Tailored for Taskly"], limitations: [] },
          ],
        }),
        ensureObjectiveTemplates: async () => tailoringGate,
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
        const waiting = ctx.text();
        if (!waiting.includes("Tailoring templates")) {
          throw new Error("the step does not say it is tailoring before showing templates");
        }
        if (waiting.includes("Premade Pick") || waiting.includes("Custom Pick")) {
          throw new Error("template cards are shown before the tailored set is ready");
        }
        await act(async () => {
          releaseTailoring({
            templates: [CUSTOM],
            generated: true,
            objective: "address_user_problem",
            error: null,
          });
        });
        await act(async () => {});
      }
    );
    const ready = ctx.text();
    if (!ready.includes("Custom Pick")) {
      throw new Error("the tailored custom template is not shown once ready");
    }
    if (!ready.includes("Tailored for this app")) {
      throw new Error("the ready list is not labelled as the tailored set");
    }
    if (ready.includes("Premade Pick")) {
      throw new Error("a pre-made template is shown alongside the tailored set");
    }
  });

  // Tailoring narrates fresh work while reading, then the cards arrive
  // staggered. The count caps at the outgoing list — the only honest total
  // mid-flight — and unmounts on settle so it never outlives the call.
  await check("template tailoring counts up in flight, then cascades cards in", async (ctx) => {
    global.__SMOKE_PARAMS = "";
    const PREMADE = { ...TEMPLATE, id: "t-premade", name: "Premade Pick" };
    const CUSTOM = {
      ...TEMPLATE,
      id: "t-custom",
      name: "Custom Pick",
      brand_profile_id: "b1",
      objective: "address_user_problem",
      origin: "custom",
    };
    let releaseTailoring;
    const tailoringGate = new Promise((resolve) => {
      releaseTailoring = resolve;
    });
    await withApi(
      {
        getTemplates: async () => ({ templates: [PREMADE, CUSTOM] }),
        getTemplateRecommendations: async () => ({
          recommendations: [
            { template: PREMADE, score: 9, why_it_fits: ["popular"], limitations: [] },
            { template: CUSTOM, score: 8, why_it_fits: ["Tailored for Taskly"], limitations: [] },
          ],
        }),
        ensureObjectiveTemplates: async () => tailoringGate,
      },
      async () => {
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
        const waiting = ctx.text();
        if (!waiting.includes("Tailoring templates")) {
          throw new Error("the step does not say it is tailoring before showing templates");
        }
        const progress = ctx.container.querySelector('[data-testid="templates-progress"]');
        if (!progress) throw new Error("no live count while templates tailor");
        if (!/Reading template \d+ of \d+/.test(progress.textContent || "")) {
          throw new Error(`the count does not read as fresh work: ${JSON.stringify(progress.textContent)}`);
        }
        await act(async () => {
          releaseTailoring({
            templates: [CUSTOM],
            generated: true,
            objective: "address_user_problem",
            error: null,
          });
        });
        await act(async () => {});
        if (ctx.container.querySelector('[data-testid="templates-progress"]')) {
          throw new Error("the count survived its own tailoring");
        }
        if (!ctx.text().includes("Custom Pick")) {
          throw new Error("the tailored custom template is not shown once ready");
        }
        const scores = [...ctx.container.querySelectorAll('[data-testid="template-fit-score"]')];
        if (!scores.length) throw new Error("no scored template cards after tailoring");
        const delays = scores.map((s) => {
          const host = s.closest(".animate-fade-up");
          if (!host) throw new Error("a fresh template card carries no arrival animation");
          return host.style.animationDelay;
        });
        if (new Set(delays).size !== delays.length) {
          throw new Error(`template cards do not arrive staggered: ${JSON.stringify(delays)}`);
        }
      }
    );
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
        // manual button. Opening the merged step is enough to trigger it.
        global.__SMOKE_PARAMS = "";
        await mount(CreateVideo, {})(ctx);
        await openTemplateStep(ctx);
        await act(async () => {});

        // The update path: with a project already in hand, generating the plan
        // writes the draft again first. The plan button sits on Review & submit
        // above the result it writes — generating and reading share one screen.
        global.__SMOKE_PARAMS = "?project=p1";
        await mount(CreateVideo, {})(ctx);
        // Changing the goal first, so the draft genuinely needs rewriting.
        // ensureProject short-circuits when nothing the project carries has
        // moved, and a write that does not happen proves nothing about what it
        // would have sent.
        await openStep(ctx, "Audience & template");
        const otherGoal = ctx.container.querySelector('[data-testid="recommended-goal-educate_viewers"]');
        await clickEl(ctx, otherGoal);
        if (otherGoal.getAttribute("aria-pressed") !== "true") throw new Error("the goal picker did not retain the sixth goal");
        await openStep(ctx, "Review & submit");
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
    const copy = ctx.text().replace(/\s+/g, " ").toLowerCase();
    for (const unsupported of [
      /free until the render|cost nothing|free trial|unlimited renders/,
      /cost me a (saturday|coffee)|400 views/,
      /(?:ten|six|18) (?:curated )?(?:openers|openings|structures|templates)/,
      /see what each video earned|success rate, failures and rework/,
      /guaranteed (?:views|downloads|sales|likeness)|guarantees? virality/,
      /nothing (?:is )?generated until you render/,
      /the presenter is you|your real face|the only face in your video/,
    ]) {
      if (unsupported.test(copy)) throw new Error(`unsupported landing promise: ${unsupported}`);
    }
    expectText(ctx, "limitations", "template fit is not presented as proven performance");
    expectText(ctx, "Matches to your banned claims block generation", "the claim gate is disclosed");
  });

  // Demo + CTA now supports user-authored end cards. A blanket ban on those
  // words hid a real capability; scope the guarantees to each output instead.
  await check("Landing separates generated stories from real footage and editor overlays", async (ctx) => {
    await mount(Landing)(ctx);
    const text = (id) => {
      const block = ctx.container.querySelector(`[data-testid="${id}"]`);
      if (!block) throw new Error(`missing capability disclosure: ${id}`);
      return block.textContent.replace(/\s+/g, " ");
    };
    const generation = text("landing-capability-generation");
    const editor = text("landing-capability-editor");
    const review = text("landing-capability-review");
    for (const phrase of ["one AI-generated clip", "demo and closing message are not generated footage", "Record the demo yourself"]) {
      if (!generation.includes(phrase)) throw new Error(`missing generation boundary: ${phrase}`);
    }
    for (const phrase of ["a base clip", "an end card you write", "Second clip", "Real Video", "one TikTok MP4"]) {
      if (!editor.includes(phrase)) throw new Error(`missing editor boundary: ${phrase}`);
    }
    if (!review.includes("not a guarantee that every claim is correct")) throw new Error("claim checks presented as factual certification");
    const answers = [...ctx.container.querySelectorAll('[data-testid="landing-questions"] details')].map((e) => e.textContent.replace(/\s+/g, " "));
    for (const pattern of [
      /own video.*don’t need to generate a Hook \+ Story first/,
      /not a recording of you or a clone of your voice/,
      /Audio depends.*some models produce silent clips/,
      /1080×1920 MP4 at 30 fps.*Chrome or Edge/,
      /publish them yourself.*posted TikTok link.*manually logged, not synced from TikTok.*do not prove conversions/,
    ]) {
      if (!answers.some((a) => pattern.test(a))) throw new Error(`missing buyer disclosure: ${pattern}`);
    }
    expectNone(ctx, ["ready to post", "No camera, no editor, no source footage", "skip the shoot"], "a real product demo remains the user's own footage");
  });

  await check("Landing headings, workflow, and navigation have real destinations", async (ctx) => {
    await mount(Landing)(ctx);
    const h1 = ctx.container.querySelectorAll("h1");
    if (h1.length !== 1 || h1[0].textContent.trim().length < 20) throw new Error("expected one meaningful H1");
    const steps = [...ctx.container.querySelectorAll('[data-testid="landing-how-it-works"] h3')];
    if (steps.length !== 5) throw new Error("expected five workflow steps");
    const workflow = ctx.container.querySelector('[data-testid="landing-how-it-works"]').textContent;
    for (const phrase of ["approve the facts", "set a goal", "both are required", "Tone is optional", "presenter photo", "save it", "Second clip", "publish them yourself"]) {
      if (!workflow.includes(phrase)) throw new Error(`missing workflow action: ${phrase}`);
    }
    for (const link of ctx.container.querySelectorAll('a[href^="#"]')) {
      const target = link.getAttribute("href").slice(1);
      if (!target || !ctx.container.querySelector(`[id="${target}"]`)) throw new Error(`broken landing anchor: ${target}`);
    }
    for (const route of ["/create", "/demo-cta", "/brand", "/history", "/privacy", "/terms"]) {
      if (!ctx.container.querySelector(`a[href="${route}"]`)) throw new Error(`missing product/legal link: ${route}`);
    }
    if (ctx.container.querySelector("a button, button a")) throw new Error("landing actions must not nest interactive elements");
    const questions = ctx.container.querySelectorAll('[data-testid="landing-questions"] details');
    if (questions.length !== 5 || [...questions].some((q) => !q.querySelector("summary") || !q.querySelector("p")?.textContent)) throw new Error("buyer questions are incomplete");
  });

  for (const authState of ["signed-out", "signed-in", "no-auth"]) {
    await check(`Landing actions work in ${authState} mode`, async (ctx) => {
      // Marketing.jsx is cleared too: it re-exports the header/CTA that read
      // AuthControls, and a cached copy would hold the previous phase's
      // isClerkConfigured binding instead of the mock for this mode.
      const modules = ["pages/Landing.jsx", "components/Marketing.jsx", "components/auth/AuthControls.jsx", "lib/clerk.js"];
      const saved = modules.map((p) => [resolveFile(path.join(SRC, p)), cache.get(resolveFile(path.join(SRC, p)))]);
      global.__SMOKE_LANDING_AUTH = authState;
      global.__SMOKE_AUTH_ACTIONS = [];
      modules.forEach((p) => cache.delete(resolveFile(path.join(SRC, p))));
      try {
        await mount(load("pages/Landing.jsx").default)(ctx);
        const header = ctx.container.querySelector("header");
        if (!header) throw new Error("landing header did not render");
        if (header.querySelector('[data-testid="landing-enter-app-button"]')) {
          throw new Error("landing header should not contain a Create Video/Get Started CTA");
        }
        if (authState === "signed-out") {
          for (const section of ['[data-testid="landing-hero"]', '[data-testid="landing-final-cta"]']) {
            const button = ctx.container.querySelector(`${section} button`);
            if (!button) throw new Error(`missing sign-up action: ${section}`);
            await act(async () => button.click());
          }
          const signIn = [...header.querySelectorAll("button")].find((b) => b.textContent.trim() === "Sign In");
          if (!signIn) throw new Error("missing sign-in action");
          await act(async () => signIn.click());
          const heroSignIn = [...ctx.container.querySelectorAll('[data-testid="landing-hero"] button')].find((b) => b.textContent.trim() === "Sign in");
          if (!heroSignIn) throw new Error("missing mobile-friendly sign-in action");
          await act(async () => heroSignIn.click());
          if (global.__SMOKE_AUTH_ACTIONS.join(",") !== "sign-up,sign-up,sign-in,sign-in") throw new Error("auth actions did not reach the correct triggers");
        } else {
          for (const section of ["landing-hero", "landing-final-cta"]) {
            const link = ctx.container.querySelector(`[data-testid="${section}"] a[href="/create"]`);
            if (!link || !link.textContent.includes("Create Video")) throw new Error(`missing creation action: ${section}`);
          }
          if (ctx.text().includes("Create your first video")) throw new Error("signed-out actions leaked into an authenticated view");
        }
        if (!ctx.container.querySelector('[data-testid="landing-final-cta"] a[href="/demo-cta"]')) throw new Error("missing standalone editor action");
      } finally {
        await act(async () => ctx.root.render(null));
        delete global.__SMOKE_LANDING_AUTH;
        delete global.__SMOKE_AUTH_ACTIONS;
        for (const [abs, entry] of saved) {
          if (entry) cache.set(abs, entry); else cache.delete(abs);
        }
      }
    });
  }

  // Features page: six alternating rows, code-built mockups, nav both ways.
  // Copy reuses the landing descriptions, so the claim pins above apply to
  // Landing only — here the shape is pinned: one H1, five rows each with a
  // heading and a mockup, in-page anchors that all resolve, a Home link back
  // to landing, and a single closing CTA with no nested interactives.
  await check("Features showcases six highlights with working nav", async (ctx) => {
    const Features = load("pages/Features.jsx").default;
    await mount(Features)(ctx);
    const h1 = ctx.container.querySelectorAll("h1");
    if (h1.length !== 1 || h1[0].textContent.trim().length < 20) throw new Error("expected one meaningful H1");
    const rows = [...ctx.container.querySelectorAll('[data-testid^="features-row-"]')];
    if (rows.length !== 6) throw new Error(`expected six feature rows, found ${rows.length}`);
    for (const row of rows) {
      if (!row.querySelector("h2")?.textContent.trim()) throw new Error("a feature row has no heading");
    }
    const header = ctx.container.querySelector("header");
    if (!header?.querySelector('a[href="/"]')) throw new Error("missing Home link back to landing");
    for (const link of header.querySelectorAll('a[href^="#"]')) {
      const target = link.getAttribute("href").slice(1);
      if (!target || !ctx.container.querySelector(`[id="${target}"]`)) throw new Error(`broken features anchor: ${target}`);
    }
    if (!ctx.container.querySelector('[data-testid="features-final-cta"]')) throw new Error("missing closing CTA");
    if (ctx.container.querySelector("a button, button a")) throw new Error("features actions must not nest interactive elements");
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
    "/analytics": "pages/Analytics.jsx",
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
  console.log("Checking the App Profile research actions...");
  await runProfileResearchActionsChecks();

  console.log("");
  console.log("Checking the sidebar navigation model...");
  await runSidebarNavChecks();

  console.log("");
  console.log("Checking the icon system...");
  await runIconChecks();

  console.log("");
  console.log("Mounting the Analytics results ledger...");
  await runAnalyticsChecks();

  console.log("");
  console.log("Checking the App Profile review actions...");
  await runBrandSetupChecks();

  console.log("");
  console.log("Checking the native Product Demo + CTA editor...");
  await runDemoCtaChecks();
}

/**
 * The Analytics page: the results ledger and the loop it closes.
 *
 * The page exists to answer one question the retired Analytics page never
 * asked - what did my own videos do, and what has the app learned from it. Every
 * number is one the founder typed in by hand, so the page has no instrumentation
 * of its own and these checks are about the three things that could quietly
 * break that promise:
 *
 * - a verdict that is not the founder's (an inferred or defaulted one)
 * - a deep link that does not land on the row it names
 * - a completed video that disappears instead of showing up as a nudge
 *
 * The nudge row matters most. Silently dropping unrecorded completions is the
 * failure mode that makes the page look better than the founder's actual
 * practice: a ledger of only logged videos implies they logged everything.
 */
async function runAnalyticsChecks() {
  const PROFILE = { id: "p1", brand_name: "Threadly", status: "approved" };

  const SIGNALS = {
    feedback: [],
    summary: {
      total: 4,
      top_signals: [{ signal: "template_changed", count: 3 }],
      top_reasons: [],
    },
  };

  const stub = (extra = {}) => ({
    getAppProfiles: async () => ({ profiles: [PROFILE] }),
    getFeedback: async () => SIGNALS,
    getGenerationHistory: async () => ({ generations: [] }),
    getStudioProjects: async () => ({ projects: [] }),
    ...extra,
  });

  async function mountAnalytics(ctx, extra) {
    const Analytics = load("pages/Analytics.jsx").default;
    await withApi(stub(extra), async () => {
      await mount(Analytics, {})(ctx);
    });
  }

  await check("Analytics mounts and shows the header for the selected app", async (ctx) => {
    await mountAnalytics(ctx);
    expectText(ctx, "Analytics", "the page has no title");
    const header = ctx.container.querySelector('[data-testid="analytics-header"]');
    if (!header) {
      throw new Error("the analytics header is not on the page");
    }
    // The subtitle as rendered, not just as written: the budget is asserted
    // against the painted line (see "every topic page subtitle fits the
    // masthead budget" for the other five pages) so a description that never
    // reaches the DOM cannot pass on the source alone.
    const lede = (header.querySelector("p") || {}).textContent;
    const copy = (lede || "").trim();
    if (!copy) {
      throw new Error("the analytics subtitle is missing from the rendered header");
    }
    if (copy.length < 54 || copy.length > 60) {
      throw new Error(
        `the analytics subtitle is ${copy.length} chars, outside the 54-60 budget`
      );
    }
  });

  await check("Analytics recommends the highest-reach Good-rated posted clip", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        // Higher reach, but unrated: comparison only, never the recommendation.
        { id: "viral", status: "completed", hook_line: "Unrated viral", tiktok_views: 20000, tiktok_url: "https://www.tiktok.com/@founder/video/9", verdicts: {} },
        { id: "top", status: "completed", hook_line: "A good opening", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/123", verdicts: { video: 1 }, studio_project_id: "draft1" },
        // Rated Good but never posted: not eligible either.
        { id: "shelf", status: "completed", hook_line: "Shelf Good", tiktok_views: 500, verdicts: { video: 1 } },
        { id: "failed", status: "failed", tiktok_views: 30000 },
      ] }),
      getStudioProjects: async () => ({ projects: [{ id: "draft1" }] }),
    });
    const pick = ctx.container.querySelector('[data-testid="analytics-next-take"]');
    if (!pick) throw new Error("no next-take recommendation rendered");
    if (!/A good opening/.test(pick.textContent || "")) {
      throw new Error("the recommendation names the wrong clip");
    }
    const action = pick.querySelector("a");
    if (!action) throw new Error("the recommendation has no next action");
    if (!/\/create\?project=draft1$/.test(action.getAttribute("href") || "")) {
      throw new Error(`the recommendation reuses the wrong draft: ${action.getAttribute("href")}`);
    }
  });

  await check("Analytics stays silent with no qualifying clip", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        { id: "unrated", status: "completed", hook_line: "Unrated", tiktok_views: 20000, tiktok_url: "https://www.tiktok.com/@founder/video/9", verdicts: {} },
        { id: "shelf", status: "completed", hook_line: "Shelf Good", tiktok_views: 500, verdicts: { video: 1 } },
      ] }),
    });
    if (ctx.container.querySelector('[data-testid="analytics-next-take"]')) {
      throw new Error("a recommendation rendered with no qualifying clip");
    }
  });

  await check("Analytics skips archived clips when recommending the next take", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        // Highest reach on the shelf: shelved means set aside, so it stays
        // comparison and never becomes advice.
        { id: "vault", status: "archived", hook_line: "Shelved winner", tiktok_views: 50000, tiktok_url: "https://www.tiktok.com/@founder/video/7", verdicts: { video: 1 }, studio_project_id: "draft0" },
        { id: "live", status: "completed", hook_line: "Live Good", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/8", verdicts: { video: 1 }, studio_project_id: "draft2" },
      ] }),
      getStudioProjects: async () => ({ projects: [{ id: "draft0" }, { id: "draft2" }] }),
    });
    await act(async () => {});
    const pick = ctx.container.querySelector('[data-testid="analytics-next-take"]');
    if (!pick) throw new Error("no next-take recommendation rendered");
    if (!/Live Good/.test(pick.textContent || "")) {
      throw new Error("the recommendation picked a shelved clip");
    }
    const action = pick.querySelector("a");
    if (!/\/create\?project=draft2$/.test(action?.getAttribute("href") || "")) {
      throw new Error(`the recommendation reuses the wrong draft: ${action?.getAttribute("href")}`);
    }
  });

  await check("Analytics recommends from the selected app only", async (ctx) => {
    global.localStorage.setItem("vocolens.currentAppProfileId", "p1");
    try {
      await mountAnalytics(ctx, {
        getAppProfiles: async () => ({ profiles: [PROFILE, { id: "p2", brand_name: "Second", status: "approved" }] }),
        getGenerationHistory: async (params = {}) => ({ generations: params.brand_profile_id === "p2" ? [
          { id: "p2top", status: "completed", hook_line: "Other app hit", tiktok_views: 50000, tiktok_url: "https://www.tiktok.com/@founder/video/2", verdicts: { video: 1 }, studio_project_id: "draftP2" },
        ] : [
          { id: "p1top", status: "completed", hook_line: "This app Good", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/1", verdicts: { video: 1 }, studio_project_id: "draftP1" },
        ] }),
        getStudioProjects: async () => ({ projects: [{ id: "draftP1" }, { id: "draftP2" }] }),
      });
      await act(async () => {});
      const pick = ctx.container.querySelector('[data-testid="analytics-next-take"]');
      if (!pick) throw new Error("no next-take recommendation rendered");
      if (!/This app Good/.test(pick.textContent || "")) {
        throw new Error("the recommendation crossed into another app");
      }
    } finally {
      global.localStorage.removeItem("vocolens.currentAppProfileId");
    }
  });

  await check("Analytics never links a deleted draft from the recommendation", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        { id: "top", status: "completed", hook_line: "A good opening", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/123", verdicts: { video: 1 }, studio_project_id: "ghost" },
      ] }),
      getStudioProjects: async () => ({ projects: [{ id: "something-else" }] }),
    });
    await act(async () => {});
    const pick = ctx.container.querySelector('[data-testid="analytics-next-take"]');
    if (!pick) throw new Error("no next-take recommendation rendered");
    const href = pick.querySelector("a")?.getAttribute("href") || "";
    if (/project=ghost/.test(href)) {
      throw new Error(`the recommendation links a deleted draft: ${href}`);
    }
    if (!/\/demo-cta\/top$/.test(href)) {
      throw new Error(`the deleted draft falls back to the wrong action: ${href}`);
    }
  });

  await check("Analytics keeps Reuse draft when draft verification fails", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        { id: "top", status: "completed", hook_line: "A good opening", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/123", verdicts: { video: 1 }, studio_project_id: "draft1" },
      ] }),
      getStudioProjects: async () => { throw new Error("offline"); },
    });
    await act(async () => {});
    const pick = ctx.container.querySelector('[data-testid="analytics-next-take"]');
    if (!pick) throw new Error("no next-take recommendation rendered");
    const href = pick.querySelector("a")?.getAttribute("href") || "";
    if (!/\/create\?project=draft1$/.test(href)) {
      throw new Error(`an unverifiable draft should fail open to Reuse draft: ${href}`);
    }
  });

  await check("Analytics names the winner CTA Another take like this", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        { id: "win", status: "completed", hook_line: "Winner clip", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/1", verdicts: { video: 1 }, studio_project_id: "wd1" },
        { id: "plain", status: "completed", hook_line: "Plain clip", tiktok_views: 100, tiktok_url: "https://www.tiktok.com/@founder/video/2", verdicts: {}, studio_project_id: "wd2" },
      ] }),
      getStudioProjects: async () => ({ projects: [{ id: "wd1" }, { id: "wd2" }] }),
    });
    await act(async () => {});
    const card = ctx.container.querySelector('[data-testid="analytics-results"]');
    if (!card) throw new Error("no clip comparison");
    const winLink = card.querySelector('a[href="/create?project=wd1"]');
    if (!winLink || winLink.textContent.trim() !== "Another take like this") {
      throw new Error("the winner row does not offer another take like this");
    }
    const plainLink = card.querySelector('a[href="/create?project=wd2"]');
    if (!plainLink || plainLink.textContent.trim() !== "Reuse draft") {
      throw new Error("a non-winner row lost its Reuse draft entry");
    }
    const pickAction = ctx.container.querySelector('[data-testid="analytics-next-take"] a');
    if (!pickAction || pickAction.textContent.trim() !== "Another take like this") {
      throw new Error("the recommendation does not offer another take like this");
    }
  });

  await check("clip results compare reach, posted links and votes without inferring conversions", async (ctx) => {
    await mountAnalytics(ctx, {
      getGenerationHistory: async () => ({ generations: [
        { id: "missing", status: "completed", segment_role: "demo_cta" },
        { id: "zero", status: "completed", hook_line: "Zero is recorded", tiktok_views: 0, verdicts: { video: -1 } },
        { id: "top", status: "completed", hook_line: "A good opening", tiktok_views: 9000, tiktok_url: "https://www.tiktok.com/@founder/video/123", verdicts: { video: 1 }, studio_project_id: "draft1" },
        { id: "failed", status: "failed", tiktok_views: 10000 },
      ] }),
      getStudioProjects: async () => ({ projects: [{ id: "draft1" }] }),
    });
    const card = ctx.container.querySelector('[data-testid="analytics-results"]');
    if (!card) throw new Error("no clip comparison");
    const rows = [...card.querySelectorAll('tbody tr')];
    if (rows.map(r => r.dataset.testid).join() !== "result-top,result-zero,result-missing") throw new Error("comparison order lost zero, missing or status distinction");
    for (const copy of ["1 posted", "2 with recorded views", "2 rated", "not installs, revenue, or conversions", "different posting dates", "never a view threshold"]) {
      if (!card.textContent.includes(copy)) throw new Error(`missing factual result/caveat: ${copy}`);
    }
    if (!rows[0].textContent.includes("9,000") || !rows[0].textContent.includes("Good")) throw new Error("reach/vote missing");
    if (!rows[1].textContent.includes("Not posted") || !rows[1].textContent.includes("Not good")) throw new Error("negative vote hidden");
    if (!rows[2].textContent.includes("Not recorded") || !rows[2].textContent.includes("Unassigned app")) throw new Error("missing data invented");
    if (!card.querySelector('a[href="/create?project=draft1"]') || !card.querySelector('a[href$="#generation-top"]')) throw new Error("reuse/review link lost provenance");
  });

  await check("Analytics scopes result requests and shows failures rather than empty success", async (ctx) => {
    const calls = [];
    const Analytics = load("pages/Analytics.jsx").default;
    await withApi(stub({
      getGenerationHistory: async (params) => {
        calls.push(params);
        if (params.brand_profile_id) throw new Error("Results could not load");
        return { generations: [{ id: "unassigned", status: "completed" }] };
      },
    }), async () => {
      await mount(Analytics)(ctx);
      const picker = ctx.container.querySelector('[data-testid="analytics-profile-picker"]');
      await selectOption(ctx, picker, "");
      if (!ctx.container.querySelector('[data-testid="result-unassigned"]')) throw new Error("All apps dropped standalone results");
      await selectOption(ctx, picker, "p1");
      expectText(ctx, "Results could not load");
      if (ctx.text().includes("Nothing captured yet") || ctx.container.querySelector('[data-testid="result-unassigned"]')) throw new Error("failed scope displayed empty or stale results");
      if (!calls.some(p => p.brand_profile_id === "p1" && p.limit === 200)) throw new Error("app scope not sent");
    });
  });

  await check("Analytics fetch failure shows an honest error with retry, not empty data", async (ctx) => {
    let fail = true;
    const failingHistory = async () => {
      if (fail) throw new Error("Results could not load");
      return { generations: [{ id: "recovered", status: "completed", hook_line: "Recovered clip" }] };
    };
    await mountAnalytics(ctx, { getGenerationHistory: failingHistory });
    expectText(ctx, "Results could not load", "failed fetch shows no honest error");
    if (ctx.text().includes("Nothing captured yet") || ctx.container.querySelector('[data-testid="analytics-results"]')) {
      throw new Error("failed fetch rendered as empty or stale success");
    }
    const retry = ctx.container.querySelector('[data-testid="analytics-retry"]');
    if (!retry) throw new Error("failed fetch offers no retry");
    fail = false;
    await withApi(stub({ getGenerationHistory: failingHistory }), async () => {
      await clickEl(ctx, retry, "retry the failed Analytics fetch");
    });
    if (!ctx.container.querySelector('[data-testid="result-recovered"]')) {
      throw new Error("retry did not recover the results");
    }
    if (ctx.container.querySelector('[data-testid="analytics-retry"]')) {
      throw new Error("retry control lingers after success");
    }
  });

  await check("Analytics acknowledges saved votes even without renders or automatic signals", async (ctx) => {
    await mountAnalytics(ctx, {
      getFeedback: async () => ({ feedback: [{ event: "thumb_up", step: "goal" }], summary: { total: 1, by_event: { thumb_up: 1 }, top_signals: [], top_reasons: [] } }),
    });
    expectAbsent(ctx, "Nothing captured yet", "saved feedback was called missing");
    expectText(ctx, "Feedback is saved", "feedback-only Analytics is blank");
    expectText(ctx, "not conversions", "feedback-only Analytics overstates evidence");
  });

  await check("automatic signals render as counts, never as judgments", async (ctx) => {
    await mountAnalytics(ctx);
    const card = ctx.container.querySelector('[data-testid="analytics-signals"]');
    if (!card) throw new Error("the signals card is not on the page");
    expectText(ctx, "Template Changed", "a captured signal is not shown");
    expectText(ctx, "3", "the signal count is not shown");
  });

  await check("no signals yet says so instead of showing an empty card", async (ctx) => {
    await mountAnalytics(ctx, {
      getFeedback: async () => ({ feedback: [], summary: { total: 0, top_signals: [] } }),
    });
    if (ctx.container.querySelector('[data-testid="analytics-signals"]')) {
      throw new Error("an empty signals card renders with nothing to count");
    }
    expectText(ctx, "Nothing captured yet", "an empty Analytics page is not explained");
    if (!ctx.container.querySelector('a[href^="/create"]')) throw new Error("empty Analytics has no next action");
  });

  await check("no app at all points at the profile editor", async (ctx) => {
    const Analytics = load("pages/Analytics.jsx").default;
    await withApi(
      {
        getAppProfiles: async () => ({ profiles: [] }),
        getFeedback: async () => null,
        getGenerationHistory: async () => ({ generations: [] }),
      },
      async () => {
        await mount(Analytics, {})(ctx);
      }
    );
    expectText(ctx, "Create an App Profile", "a founder with no app is told nothing");
    if (!ctx.container.querySelector('a[href="/brand"]')) {
      throw new Error("there is no way forward from an empty Analytics page");
    }
  });

  // The funnel, activity and reasons cards below are the Analytics depth:
  // renders counted by status off the same rows History shows, renders per
  // week, and the founder's own reason codes. Each hides when its data is
  // missing rather than rendering an empty card, the same rule the signals
  // card follows above.
  const dayAgo = new Date(Date.now() - 86400000).toISOString();

  await check("the render funnel counts every clip by status", async (ctx) => {
    await mountAnalytics(ctx, {
      getFeedback: async () => ({
        feedback: [],
        summary: { total: 0, top_signals: [], top_reasons: [] },
      }),
      getGenerationHistory: async () => ({
        generations: [
          { id: "g1", status: "completed", created_at: dayAgo },
          { id: "g2", status: "completed", created_at: dayAgo },
          { id: "g3", status: "failed", created_at: dayAgo },
        ],
      }),
    });
    const card = ctx.container.querySelector('[data-testid="analytics-funnel"]');
    if (!card) throw new Error("the render funnel is not on the page");
    for (const row of ["Completed", "Failed", "In progress", "Archived", "3 total"]) {
      if (!card.textContent.includes(row)) {
        throw new Error(`the funnel does not count "${row}"`);
      }
    }
    if (!card.querySelector('[data-testid="analytics-funnel-history"]')) {
      throw new Error("the funnel has no way back to the History rows it counts");
    }
    if (ctx.text().includes("Nothing captured yet")) {
      throw new Error("renders exist but the page still claims nothing was captured");
    }
  });

  await check("renders per week buckets clips into Monday-start weeks", async (ctx) => {
    // dayAgo is not guaranteed to share this Monday-start week with today: on
    // a Monday it falls on the previous Sunday, so it buckets to last week.
    // Everything below is one mount: re-rendering the same root keeps the
    // first mount's state (the effect does not refetch), so a second mount
    // would still show the first mount's buckets.
    // justBefore/justAfter are computed in local wall time so timezones
    // cannot collapse them: 30 min before this Monday midnight (Sunday) and
    // 30 min after it (Monday) share a Sunday-start week but fall on either
    // side of a Monday boundary, so two buckets proves Monday-start. Fixed
    // UTC strings cannot do this — a UTC midnight pair lands on the same
    // local Sunday either side of the Atlantic.
    const thisMondayMidnight = new Date();
    thisMondayMidnight.setDate(
      thisMondayMidnight.getDate() - ((thisMondayMidnight.getDay() + 6) % 7)
    );
    thisMondayMidnight.setHours(0, 0, 0, 0);
    const justBefore = new Date(thisMondayMidnight.getTime() - 30 * 60000).toISOString();
    const justAfter = new Date(thisMondayMidnight.getTime() + 30 * 60000).toISOString();
    await mountAnalytics(ctx, {
      getFeedback: async () => ({
        feedback: [],
        summary: { total: 0, top_signals: [], top_reasons: [] },
      }),
      getGenerationHistory: async () => ({
        generations: [
          { id: "g1", status: "completed", created_at: justAfter },
          { id: "g2", status: "completed", created_at: justBefore },
        ],
      }),
    });
    const card = ctx.container.querySelector('[data-testid="analytics-activity"]');
    if (!card) throw new Error("the weekly activity card is not on the page");
    expectText(ctx, "This week", "a recent render is not bucketed into this week");
    const buckets = [...ctx.container.querySelectorAll('[data-testid="analytics-activity"] li')];
    if (buckets.length !== 2) {
      throw new Error(
        `a Sunday/Monday pair straddling a Monday boundary buckets into ${buckets.length} week(s), expected 2`
      );
    }
  });

  await check("reasons list the founder's own codes with an explained count", async (ctx) => {
    await mountAnalytics(ctx, {
      getFeedback: async () => ({
        feedback: [],
        summary: {
          total: 5,
          top_signals: [],
          top_reasons: [{ reason: "hook_weak", count: 2 }],
          explained: 2,
        },
      }),
    });
    const card = ctx.container.querySelector('[data-testid="analytics-reasons"]');
    if (!card) throw new Error("the reasons card is not on the page");
    expectText(ctx, "Hook Weak", "a recorded reason is not shown");
    expectText(
      ctx,
      "2 of 5 signals explained.",
      "a thin reasons list is not readable as unexplained"
    );
  });
}

/**
 * The sidebar's link list: its order and its one label.
 *
 * Source-level rather than mounted, and deliberately. Mounting Sidebar means
 * shimming Clerk and the onboarding provider (useOnboarding throws outside its
 * provider, and AccountButton pulls in @clerk/clerk-react), which is a lot of
 * harness to assert a literal array. The list is a plain module-level constant
 * with no logic in it, so reading it is not a weaker check here — it is the same
 * check.
 *
 * Order is pinned as a whole sequence, the way STEP_LABELS is: the point is that
 * App Profile comes FIRST, because everything else is generated from it and
 * Create Video refuses to run without an approved one. A set comparison would
 * pass just as happily with the profile back in the middle.
 */
async function runSidebarNavChecks() {
  await check(
    "App Profile leads the sidebar, and nothing still calls it \"Your app\"",
    async () => {
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "components", "Sidebar.jsx"),
        "utf8"
      );
      const block = src.slice(src.indexOf("const NAV_ITEMS = ["));
      const items = [...block.matchAll(/to:\s*"([^"]+)",\s*label:\s*"([^"]+)"/g)].map(
        (m) => ({ to: m[1], label: m[2] })
      );
      if (items.length < 5) {
        throw new Error(
          `parsed ${items.length} nav items from Sidebar.jsx, expected 5. The ` +
            "pattern no longer matches the model, so this check would pass on nothing."
        );
      }
      if (items[0].to !== "/brand" || items[0].label !== "App Profile") {
        throw new Error(
          `the first sidebar link is ${items[0].label} (${items[0].to}), expected ` +
            "App Profile (/brand). Everything else in the app is generated from " +
            "the profile, so leading with a screen whose inputs do not exist yet " +
            "opens on a dead end."
        );
      }
      // Analytics is last on purpose: it reads results the pages above it produced,
      // so leading with it would open on an empty ledger during setup.
      const expected = [
        "/brand",
        "/demo-cta",
        "/create",
        "/assets",
        "/history",
        "/analytics",
      ];
      const actual = items.map((i) => i.to);
      if (actual.join("|") !== expected.join("|")) {
        throw new Error(
          `sidebar order is ${actual.join(" -> ")}, expected ${expected.join(" -> ")}`
        );
      }
      // The label, everywhere it is user-visible. A nav item reading "App
      // Profile" above a page titled "Your app" is the exact inconsistency this
      // rename exists to remove, and it would come straight back.
      const stale = [];
      for (const rel of [
        "src/components/Sidebar.jsx",
        "src/pages/BrandSetup.jsx",
        "src/pages/AppProfileDetail.jsx",
        "src/pages/Landing.jsx",
        "src/lib/onboarding/tours.js",
      ]) {
        const text = fs.readFileSync(path.join(__dirname, "..", rel), "utf8");
        // Matched only where a label actually lives: a nav label, a page title,
        // a tour label, or a JSX text node. A bare quoted mention is not enough,
        // because the comment explaining WHY this was renamed has to be able to
        // name the old thing — punishing documentation for existing would make
        // the rename unreversible.
        const labelSite =
          /label:\s*"Your app"|title\s*[:=]\s*"Your app"|"Your app tour"|\/>\s*Your app\b/;
        if (labelSite.test(text)) stale.push(rel);
      }
      if (stale.length) {
        throw new Error(
          `the old "Your app" label is back in: ${stale.join(", ")}. The page is ` +
            "called App Profile everywhere else in the product."
        );
      }
      // The route and testid must not move with the label: the onboarding tour
      // and every existing deep link depend on them.
      if (!/to: "\/brand", label: "App Profile", icon: Briefcase, testId: "brand-nav-link"/.test(src)) {
        throw new Error(
          "the App Profile link changed its route or testId. brand-nav-link is " +
            "referenced by convention and /brand by every existing deep link."
        );
      }
    }
  );
}

/**
 * The icon system: three sizes, and nothing that lies about its role.
 *
 * Icons carried the whole app's meaning at a glance, which is exactly why
 * they drift: each page grew its own glyph and its own size for the same
 * role, and nothing complained. Three concrete failures this pins:
 *
 * - A card wearing the glyph of an error. "Known limitations" is content the
 *   founder is told to respect; drawing it with AlertTriangle -- the same
 *   glyph as every destructive Alert -- made a content card read as broken.
 * - A small button wearing a large icon. A 16px glyph in a size="sm" button
 *   is a different optical weight from the same glyph at 14px, and the eye
 *   reads it as a different control.
 * - A dead import. A lucide icon that is imported and never rendered costs
 *   nothing at runtime, but it is evidence: something that used to be there
 *   was removed without taking its import, and the next reader assumes the
 *   glyph is still in use.
 *
 * Sizes are read from the shipped source rather than asserted per page,
 * because the point is that there are three sizes and no fourth.
 */
async function runIconChecks() {
  const iconFiles = [];
  const walk = (dir) => {
    for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
      const full = path.join(dir, entry.name);
      if (entry.isDirectory()) {
        // components/ui is the vendored shadcn layer; its glyph sizing is the
        // primitives' own contract, not this app's.
        if (entry.name === "ui") continue;
        walk(full);
      } else if (entry.name.endsWith(".jsx") || entry.name.endsWith(".js")) {
        iconFiles.push(full);
      }
    }
  };
  walk(SRC);

  await check("no page imports a lucide icon it never renders", async () => {
    const dead = [];
    for (const abs of iconFiles) {
      const text = fs.readFileSync(abs, "utf8");
      const m = text.match(/import\s*\{([^}]*)\}\s*from\s*"lucide-react"/);
      if (!m) continue;
      const body = text.replace(m[0], "");
      for (const raw of m[1].split(",")) {
        const name = raw.trim().split(/\s+as\s+/).filter(Boolean).pop();
        if (!name) continue;
        const used = new RegExp(`\\b${name}\\b`).test(body);
        if (!used) dead.push(`${path.relative(SRC, abs)}: ${name}`);
      }
    }
    if (dead.length) {
      throw new Error(
        `lucide icons imported but never rendered:\n        ${dead.join("\n        ")}`
      );
    }
  });

  await check("a size=sm button never carries a 16px icon", async () => {
    const bad = [];
    for (const abs of iconFiles) {
      const lines = fs.readFileSync(abs, "utf8").split("\n");
      for (let i = 0; i < lines.length; i++) {
        if (!/size="sm"/.test(lines[i])) continue;
        // The opening tag ends at the first line that closes it; only the
        // children between there and </Button> are inside the button. A plain
        // N-line window ran past </Button> into the next Alert and reported its
        // glyph as a button's, so the span is measured rather than guessed.
        let open = i;
        while (open < lines.length && !/>\s*$/.test(lines[open])) open++;
        let close = open;
        while (close < lines.length && !/<\/Button>/.test(lines[close])) close++;
        if (open >= lines.length || close >= lines.length) continue;
        const children = lines.slice(open, close).join(" ");
        const glyph = children.match(/<([A-Z][A-Za-z0-9]*)\s+className="[^"]*\bh-4\b/);
        if (glyph) bad.push(`${path.relative(SRC, abs)}:${i + 1} ${glyph[1]}`);
      }
    }
    if (bad.length) {
      throw new Error(
        `16px icons in size="sm" buttons (should be 14px / h-3.5):\n        ${bad.join("\n        ")}`
      );
    }
  });

  await check("every profile card and group bar opens with its own icon", async () => {
    // Profile Detail headings are read the way Demo + CTA's panel headers are:
    // an uppercase title with a glyph on its left. The page has exactly five
    // groups, each one's icon names a different subject, and a heading left
    // bare is the row that breaks the skim.
    //
    // Source-level on purpose: which glyph belongs to which section is a
    // judgement call, but *that* every heading carries one is the invariant.
    const abs = path.join(SRC, "pages", "AppProfileDetail.jsx");
    const src = fs.readFileSync(abs, "utf8");
    const bare = [];
    const seen = [];
    for (const m of src.matchAll(/<(ProfileCard|SectionGroup)\b[^>]*>/g)) {
      seen.push(m[1]);
      if (!/icon=\{/.test(m[0])) bare.push(m[0].replace(/\s+/g, " ").slice(0, 70));
    }
    if (bare.length) {
      throw new Error(`profile headings without an icon:\n        ${bare.join("\n        ")}`);
    }
    const groups = seen.filter((name) => name === "SectionGroup").length;
    if (groups !== 5) {
      throw new Error(`expected the page's five section groups, saw ${groups}`);
    }
    if (seen.filter((name) => name === "ProfileCard").length < 10) {
      throw new Error("too few profile cards to be the whole page");
    }
  });

  await check("section cards share the profile's unboxed muted heading", async (ctx) => {
    const { SectionCard } = load("components/SectionCard.jsx");
    const { Layers } = require("lucide-react");
    await mount(SectionCard, { title: "What the app does", icon: Layers, description: "Verified facts." })(ctx);
    const heading = ctx.container.querySelector("h2.section-heading");
    if (!heading || !heading.querySelector("svg.h-4")) throw new Error("section lacks the shared heading and 16px outline icon");
    if (heading.querySelector(".border") || ctx.container.querySelector('[class*="bg-[color:var(--indigo-8)]"]')) {
      throw new Error("a colored icon tile returned to a section heading");
    }
    if (!ctx.text().includes("Verified facts.")) throw new Error("section description disappeared");
  });

  await check("app chrome never takes a text caret", async () => {
    // Clicking a sidebar label dropped a blinking caret as if the label were
    // editable: nothing on this page opts chrome out of selection, so Chrome
    // renders a caret for the collapsed click selection. jsdom never paints a
    // caret, so this pins the mechanism the way the heading-token check does:
    // the stylesheet rule and the pill components that carry it.
    const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
    const rule = css.match(/\/\*[\s\S]*?never editable[\s\S]*?\*\/\s*([^{]+)\{([^}]+)\}/);
    if (!rule) throw new Error("the non-editable-chrome rule is gone from index.css");
    for (const selector of ["nav", "button", "h1", ".section-heading", ".eyebrow"]) {
      if (!rule[1].includes(selector)) {
        throw new Error(`chrome rule no longer covers ${selector}: clicks there caret again`);
      }
    }
    for (const token of ["user-select: none", "-webkit-user-select: none"]) {
      if (!rule[2].includes(token)) throw new Error(`chrome rule lost ${token}`);
    }
    for (const [file, name] of [
      ["components/ui/badge.jsx", "Badge"],
      ["components/FactChip.jsx", "FactChip"],
    ]) {
      const src = fs.readFileSync(path.join(SRC, file), "utf8");
      if (!src.includes("select-none")) {
        throw new Error(`${name} lost select-none: clicking a pill carets again`);
      }
    }
  });

  await check("an eyebrow icon is always 12px", async () => {
    // The one size for a glyph beside a label. A 16px glyph next to an 11px
    // uppercase label is heavier than the label it introduces.
    //
    // Only the hand-written eyebrow rows are matched, not ProfileCard and
    // SectionCard: those apply the size inside the component, and a wrapper
    // may forward the glyph as a prop (`icon={icon}`) rather than naming one.
    const bad = [];
    for (const abs of iconFiles) {
      const src = fs.readFileSync(abs, "utf8");
      for (const m of src.matchAll(
        /className="eyebrow flex items-center gap-1\.5">\s*<(\w+)\s+className="([^"]*)"/g
      )) {
        if (!/\bh-3\b/.test(m[2])) bad.push(`${path.relative(SRC, abs)} ${m[1]}: ${m[2]}`);
      }
    }
    if (bad.length) {
      throw new Error(`eyebrow icons off the 12px token:\n        ${bad.join("\n        ")}`);
    }
  });

  await check("icon-bearing group labels use GroupLabel", async () => {
    // A label with a glyph beside it is GroupLabel (eyebrow + 12px icon),
    // not a hand-built flex row: the hand pattern drifts in gap and icon
    // size, and the drift is what made identical labels disagree. Plain
    // icon-less `.eyebrow` spans are fine — the token is already shared —
    // and SectionCard.jsx defines the primitive itself.
    const hand = [];
    for (const abs of iconFiles) {
      if (abs.endsWith("SectionCard.jsx")) continue;
      const src = fs.readFileSync(abs, "utf8");
      for (const m of src.matchAll(/className="eyebrow flex[^"]*"/g)) {
        hand.push(`${path.relative(SRC, abs)}: ${m[0]}`);
      }
    }
    if (hand.length) {
      throw new Error(`hand-built icon labels (use GroupLabel):\n        ${hand.join("\n        ")}`);
    }
  });

  await check("no small section headings", async () => {
    // Card and section titles are the display token (font-display 14
    // semibold) or the uppercase GroupLabel; a 14px medium h2/h3 is a
    // fourth title dialect. ProfileCard's old sentence-case h3 was the
    // last one and is now a GroupLabel, so there is no exception left.
    const small = [];
    for (const abs of iconFiles) {
      const src = fs.readFileSync(abs, "utf8");
      for (const m of src.matchAll(/<h[23]\b[^>]*text-sm font-medium/g)) {
        small.push(`${path.relative(SRC, abs)}: ${m[0].slice(0, 60)}`);
      }
    }
    if (small.length) {
      throw new Error(`small h2/h3 section headings:\n        ${small.join("\n        ")}`);
    }
  });

  await check("workspace enforces 3 sizes x 2 weights", async () => {
    // Workspace pages and shared components use only text-xs / text-sm / text-2xl
    // and font-normal / font-semibold (Landing, Features, the Marketing chrome
    // they share, and LegalPage retain their own marketing and document scales).
    const bad = [];
    function collectSrc(dir, out = []) {
      for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
        const p = path.join(dir, entry.name);
        if (entry.isDirectory()) collectSrc(p, out);
        else if (/\.(js|jsx|css)$/.test(entry.name)) out.push(p);
      }
      return out;
    }
    for (const abs of collectSrc(SRC)) {
      if (abs.endsWith("Landing.jsx") || abs.endsWith("Features.jsx") || abs.endsWith("Marketing.jsx") || abs.endsWith("LegalPage.jsx")) continue;
      const src = fs.readFileSync(abs, "utf8");
      for (const m of src.matchAll(
        /\b(?:md:|sm:|lg:)?text-(?:base|lg|xl|3xl|4xl|5xl|\[[^\]]+\])\b|\bfont-(?:light|medium|bold|extrabold)\b/g
      )) {
        bad.push(`${path.relative(SRC, abs)}: ${m[0]}`);
      }
    }
    if (bad.length) {
      throw new Error(
        `off-scale font size or weight in workspace:\n        ${bad.join("\n        ")}`
      );
    }
  });

  await check("buttons share the studio specular bevel and soft sweep with static text and icons", async () => {
    const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
    for (const token of [
      ".btn-studio",
      ".btn-bevel-brand",
      ".btn-bevel-accent",
      ".btn-bevel-neutral",
    ]) {
      if (!css.includes(token)) {
        throw new Error(`index.css is missing studio button rule: ${token}`);
      }
    }
    for (const forbidden of [
      ".btn-studio:hover:not(:disabled) svg",
      ".pill-studio:hover:not(:disabled) svg",
    ]) {
      if (css.includes(forbidden)) {
        throw new Error(`index.css still animates button icons or text: ${forbidden}`);
      }
    }
    const buttonSrc = fs.readFileSync(path.join(SRC, "components", "ui", "button.jsx"), "utf8");
    for (const cls of ["btn-studio", "btn-bevel-brand", "btn-bevel-accent", "btn-bevel-neutral"]) {
      if (!buttonSrc.includes(cls)) {
        throw new Error(`button.jsx is missing studio button class: ${cls}`);
      }
    }
    if (buttonSrc.includes("hover:-translate-y-[1.5px]") || buttonSrc.includes("active:scale-")) {
      throw new Error("button.jsx still uses the sharp hover lift or press scale instead of the softer hover");
    }
    const landingSrc = fs.readFileSync(path.join(SRC, "pages", "Landing.jsx"), "utf8");
    if (landingSrc.includes("bg-[color:var(--brand-coral)]")) {
      throw new Error("Landing.jsx still hand-rolls coral CTA styles instead of variant=\"brand\"");
    }
    const tourSrc = fs.readFileSync(path.join(SRC, "components", "onboarding", "TourOverlay.jsx"), "utf8");
    if (tourSrc.includes('bg-[color:var(--brand-indigo)] hover:bg-[color:var(--brand-indigo-dark)] text-white')) {
      throw new Error("TourOverlay still hand-rolls an indigo button instead of variant=\"accent\"");
    }
  });

  await check("no button paints coral or red, and the destructive fill stays dark", async (ctx) => {
    // Every CTA in the app used to be the loudest surface on its screen,
    // because the palette reserved coral for "this performs the action". The
    // button system is indigo for actions and the dark material for everything
    // else now; this pins that so a warm fill cannot come back through a
    // variant, the shared bevel, or the chip's pressed state.
    const { buttonVariants } = load("components/ui/button.jsx");
    for (const variant of ["default", "brand", "accent", "secondary", "outline", "destructive", "ghost", "link"]) {
      const cls = buttonVariants({ variant });
      if (/(^|\s)bg-destructive(\s|$)/.test(cls) || cls.includes("bg-[color:var(--brand-coral)]")) {
        throw new Error(`button variant "${variant}" still paints a warm fill: ${cls}`);
      }
    }
    // The intent behind the dark destructive fill, asserted rather than
    // described: the surface is dark, the label is what says "destructive".
    const destructive = buttonVariants({ variant: "destructive" });
    if (!destructive.includes("bg-secondary/70") || !destructive.includes("text-destructive")) {
      throw new Error("the destructive variant lost its dark fill or its red label");
    }
    const cls = buttonVariants({ variant: "brand" });
    if (!cls.includes("bg-secondary") || !cls.includes("btn-bevel-brand")) {
      throw new Error(`the brand variant does not wear the dark studio material: ${cls}`);
    }
    const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
    const start = css.indexOf(".btn-bevel-brand {");
    const end = css.indexOf(".btn-bevel-accent {");
    if (start === -1 || end === -1 || end < start) {
      throw new Error("the brand bevel block could not be read out of index.css");
    }
    const bevel = css.slice(start, end);
    for (const forbidden of ["brand-coral", "glow-coral", "#ff3b63", "#ff4d72", "254, 44, 85", "#e0264c"]) {
      if (bevel.includes(forbidden)) {
        throw new Error(`the brand button bevel still paints coral: ${forbidden}`);
      }
    }
    const chipSrc = fs.readFileSync(path.join(SRC, "components", "Chip.jsx"), "utf8");
    if (chipSrc.includes("brand-coral")) {
      throw new Error("the chip's pressed state still paints coral instead of the indigo accent");
    }
  });

  await check("pills, pickable cards, inputs, icon tiles, and alerts share the studio material system", async () => {
    const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
    for (const token of [".pill-studio", ".card-pickable", ".input-well"]) {
      if (!css.includes(token)) {
        throw new Error(`index.css is missing studio material rule: ${token}`);
      }
    }
    const expectations = [
      ["components/Chip.jsx", "pill-studio"],
      ["components/AppPicker.jsx", "pill-studio"],
      ["components/ui/input.jsx", "input-well"],
      ["components/ui/textarea.jsx", "input-well"],
      ["components/formControls.js", "input-well"],
      ["components/IconTile.jsx", "from-[color:var(--indigo-15)]"],
      ["components/Sidebar.jsx", "shadow-[0_0_10px_var(--brand-indigo)]"],
      ["pages/CreateVideo.jsx", "card-pickable"],
    ];
    for (const [rel, token] of expectations) {
      const src = fs.readFileSync(path.join(SRC, rel), "utf8");
      if (!src.includes(token)) {
        throw new Error(`${rel} is missing expected studio material token: ${token}`);
      }
    }
  });

  await check("no block doubles its parent's spacing with mt-*", async () => {
    // A block that opens with `border-t` gets its gutter from `pt-4` — the
    // padding below its own rule. An `mt-*` next to that rule is a second gap
    // on top of whatever the parent already contributes, and because a
    // `space-y-*` parent reserves its gap by DOM position, the doubling only
    // shows up when a sibling is closed — the state nobody screenshots.
    // Generation History's variations block shipped `mt-4 space-y-4 border-t`
    // inside a `space-y-4` parent: 32px where 16px was designed.
    //
    // `mt-*` + `border-t` on one element is the whole signature, which is what
    // makes this checkable without parsing parents. A bare `mt-2` on a label is
    // the documented optical case and stays allowed.
    //
    // Landing and Legal keep their own systems by decision — marketing scale
    // and document type respectively — so the sweep skips them.
    const bad = [];
    const skip = new Set(["Landing.jsx"]);
    for (const entry of fs.readdirSync(path.join(SRC, "pages"))) {
      if (!entry.endsWith(".jsx") || skip.has(entry)) continue;
      const abs = path.join(SRC, "pages", entry);
      const src = fs.readFileSync(abs, "utf8");
      for (const m of src.matchAll(/className="([^"]*\bborder-t\b[^"]*)"/g)) {
        const cls = m[1];
        if (!/\bmt-\d/.test(cls)) continue;
        bad.push(`${path.relative(SRC, abs)}: ${cls.replace(/\s+/g, " ").slice(0, 80)}`);
      }
    }
    if (bad.length) {
      throw new Error(
        `border-t blocks spaced with mt-* instead of pt-*:\n        ${bad.join("\n        ")}`
      );
    }
  });
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
 * profile's finished videos, not one regenerable row.
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
    generateContentAngles: async () => ({ angles: [{ id: "a1", label: "Confession" }] }),
    getStudioProjects: async () => ({ projects: [{ id: "s1", name: "Draft one" }] }),
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
        // The profile list page is gone, so the App Profile page is the only landing.
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
    { drafts: 0, angles: 0, want: "every uploaded photo" },
    { drafts: 1, angles: 0, want: "1 video draft and every uploaded photo" },
    {
      drafts: 3,
      angles: 2,
      want: "3 video drafts, 2 content angles and every uploaded photo",
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
      `the delete warning names what is lost (${c.drafts} drafts, ${c.angles} angles)`,
      async (ctx) => {
        await withApi(
          stubProfileApi({
            getStudioProjects: async () => ({
              projects: Array.from({ length: c.drafts }, (_, i) => ({ id: `s${i}` })),
            }),
            getContentAngles: async () => ({
              angles: Array.from({ length: c.angles }, (_, i) => ({ id: `a${i}` })),
            }),
            // No recorded-videos count anymore: manual result logging is gone,
            // so the warning names drafts, angles and photos only.
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

  // Angles moved out of the profile page into the Create Video wizard: the
  // profile is facts, results, audiences and guardrails, and the Audience &
  // goal step already offers to generate missing angles (pinned above). The
  // profile must therefore carry no angles or drafts section at all.
  await check("the profile page carries no angles or drafts section", async (ctx) => {
    await withApi(
      stubProfileApi({
        getContentAngles: async () => ({ angles: [] }),
      }),
      async () => {
        await mountProfileDetail()(ctx);
        await act(async () => {});
        if (ctx.container.querySelector('[data-testid="app-profile-angles"]')) {
          throw new Error("the angles section is still on the profile page");
        }
        if (ctx.container.querySelector('[data-testid="app-profile-videos"]')) {
          throw new Error("the drafts section is still on the profile page");
        }
        if (ctx.container.querySelector('[data-testid="generate-angles-button"]')) {
          throw new Error("angle generation is still offered on the profile page");
        }
      }
    );
  });

  // The restyle onto the Content Angles tokens, pinned on the rendered
  // output rather than the source: uppercase tracked headings that open with
  // their own glyph on the left (16px on a bar, 12px on a card eyebrow),
  // chips at the 12px Badge shape, and the angle panel's hairline content
  // chrome under an open group bar.
  await check("Profile Detail headings use the Content Angles tokens", async (ctx) => {
    const RICH = {
      ...PROFILE,
      app_category: "Productivity",
      tone_voice: "direct and plain",
      core_features: ["One shared list"],
      use_cases: ["Weekly planning"],
    };
    await withApi(
      stubProfileApi({ getAppProfile: async () => RICH }),
      async () => {
        await mountProfileDetail()(ctx);
        await act(async () => {});
        const group = ctx.container.querySelector('[data-testid="group-essentials"]');
        if (!group) throw new Error("the essentials group did not render");
        const bar = group.querySelector("button");
        const barTitle = bar.querySelector(".section-heading");
        if (!barTitle) throw new Error("the group bar has no shared section heading");
        const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
        const headingRule = css.match(/\.section-heading\s*\{([^}]+)\}/)?.[1] || "";
        for (const token of ["text-transform: uppercase", "letter-spacing: 0.08em", "color: hsl(var(--muted-foreground))", "font-size: 0.875rem"]) {
          if (!headingRule.includes(token)) throw new Error(`section heading lost ${token}`);
        }
        const barIcon = barTitle.querySelector("svg");
        if (!barIcon || barIcon.tagName !== "svg") {
          throw new Error("the group bar does not open with its section icon");
        }
        if (!/\bh-4\b/.test(barIcon.getAttribute("class") || "")) {
          throw new Error(`the group bar icon is off the 16px token: ${barIcon.getAttribute("class")}`);
        }
        const cardTitle = group.querySelector('[data-testid="profile-facts"] h3');
        if (!cardTitle) throw new Error("the product-facts card has no heading");
        if (!/\beyebrow\b/.test(cardTitle.className)) {
          throw new Error(`the card heading is not the shared GroupLabel: ${cardTitle.className}`);
        }
        const cardIcon = cardTitle.querySelector("svg");
        if (!cardIcon) throw new Error("the product-facts card heading carries no icon");
        if (!/\bh-3\b/.test(cardIcon.getAttribute("class") || "")) {
          throw new Error(`the card heading icon is off the 12px token: ${cardIcon.getAttribute("class")}`);
        }
        const chip = group.querySelector("li");
        if (!chip) throw new Error("the core-features chips did not render");
        if (!/text-xs/.test(chip.className) || /text-\[13px\]/.test(chip.className)) {
          throw new Error(`chips are off the 12px Badge token: ${chip.className}`);
        }
        const content = group.querySelector("div.min-h-0 > div");
        if (!content || !/border-t/.test(content.className)) {
          throw new Error("the open group lost the angle panel's hairline content chrome");
        }
      }
    );
  });
}

/**
 * App Profile detail: the two research actions beside the delete control.
 *
 * Both sit behind one Research menu: three sentences of button text made the
 * header read as a paragraph, and each re-run carries a consequence ("needs
 * re-approval", "creates separate draft") that belongs beside the item rather
 * than inside a label. The header keeps a single control for all of them, so
 * these checks open the menu before touching an item.
 *
 * Refresh-from-sources stages a proposal and owes re-approval (unlike
 * Refresh research & angles, which applies immediately), so the pending
 * proposal must surface a review path on this page — otherwise the item
 * silently does nothing visible. Research-into-a-new-draft forks from the
 * stored store listing and lands in the editor, which owns drafts; without
 * a listing on file that item must not render at all.
 */
async function runProfileResearchActionsChecks() {
  const RESEARCHED = {
    id: "p1",
    brand_name: "Threadly",
    brand_description: "One list, not eleven.",
    status: "approved",
    last_research_at: "2026-09-01T10:00:00Z",
    appstore_url: "https://apps.apple.com/threadly",
  };

  const stubDetailApi = (extra = {}) => ({
    getAppProfile: async () => RESEARCHED,
    getContentAngles: async () => ({ angles: [] }),
    getStudioProjects: async () => ({ projects: [] }),
    getTemplateRecommendations: async () => ({ recommendations: [] }),
    ...extra,
  });

  await check("refresh from sources stages a pending proposal", async (ctx) => {
    let called = null;
    const pending = { ...RESEARCHED, pending_research: { brand_description: "New words" } };
    await withApi(
      stubDetailApi({
        refreshAppProfile: async (id) => {
          called = id;
          return pending;
        },
      }),
      async () => {
        await mountProfileDetail()(ctx);
        // Opened through the trigger, not force-mounted: the item has to be
        // reachable the way a founder reaches it for this to prove anything.
        const btn = await openMenu(ctx, "research-menu-button", "refresh-sources-button");
        await clickEl(ctx, btn, "the research menu offers no refresh-from-sources item");
        await act(async () => {});
        if (called !== "p1") {
          throw new Error(`refreshAppProfile was called with ${JSON.stringify(called)}`);
        }
        if (!ctx.container.querySelector('[data-testid="pending-proposal-alert"]')) {
          throw new Error("no pending-proposal alert after refresh");
        }
        if (!ctx.container.querySelector('[data-testid="approve-pending-button"]')) {
          throw new Error("the pending proposal offers no review path");
        }
      }
    );
  });

  await check("approving the pending proposal applies it", async (ctx) => {
    let called = null;
    await withApi(
      stubDetailApi({
        getAppProfile: async () => ({ ...RESEARCHED, pending_research: { brand_description: "New words" } }),
        approveAppProfile: async (id, applyPending) => {
          called = [id, applyPending];
          return RESEARCHED;
        },
      }),
      async () => {
        await mountProfileDetail()(ctx);
        await clickEl(
          ctx,
          ctx.container.querySelector('[data-testid="approve-pending-button"]'),
          "no review path on the pending proposal"
        );
        await act(async () => {});
        if (!called || called[0] !== "p1" || called[1] !== true) {
          throw new Error(`approveAppProfile was called with ${JSON.stringify(called)}`);
        }
        if (ctx.container.querySelector('[data-testid="pending-proposal-alert"]')) {
          throw new Error("the pending alert survives its own approval");
        }
      }
    );
  });

  await check("research into a new draft forks from the store listing", async (ctx) => {
    let payload = null;
    global.__SMOKE_NAVIGATIONS = [];
    await withApi(
      stubDetailApi({
        researchAppProfile: async (p) => {
          payload = p;
          return { id: "p9", brand_name: "Threadly", status: "draft" };
        },
      }),
      async () => {
        await mountProfileDetail()(ctx);
        await clickEl(
          ctx,
          await openMenu(ctx, "research-menu-button", "research-new-draft-button"),
          "the research menu offers no research-into-new-draft item"
        );
        await act(async () => {});
        if (!payload || payload.appstore_url !== "https://apps.apple.com/threadly") {
          throw new Error(`researchAppProfile was called with ${JSON.stringify(payload)}`);
        }
        const went = global.__SMOKE_NAVIGATIONS || [];
        if (!went.includes("/brand")) {
          throw new Error(`expected to land on /brand, navigated to ${JSON.stringify(went)}`);
        }
      }
    );
  });

  await check("research into a new draft stays hidden without a store listing", async (ctx) => {
    const { appstore_url, ...bare } = RESEARCHED;
    void appstore_url;
    await withApi(stubDetailApi({ getAppProfile: async () => bare }), async () => {
      await mountProfileDetail()(ctx);
      // The menu has to open for its silence to mean anything: an unopened
      // menu has no items either, which is not the claim under test.
      const refresh = await openMenu(ctx, "research-menu-button", "refresh-sources-button");
      if (!refresh) throw new Error("the research menu has no refresh item, so it never opened");
      if (dom.window.document.querySelector('[data-testid="research-new-draft-button"]')) {
        throw new Error("the fork item shows with no store listing to research");
      }
    });
  });
}

/**
 * "Save profile" and "Approve profile" are review affordances over a
 * machine-written draft, sitting in the research row beside the Research menu.
 * Before research runs there is nothing to review, so the row buttons are
 * withheld. But the row save was also the only save on the page, so gating it
 * alone would quietly remove the ability to store a hand-typed profile -- the
 * one failure mode here is a form you can fill and never save, which no other
 * gate would catch.
 *
 * The row is deliberately short, so that is asserted and not assumed: one
 * Signal Coral commit per state, and the re-runs that carry a consequence
 * ("needs re-approval", "creates separate draft") behind a single Research
 * menu instead of two more wide labels. A button per action read as a
 * paragraph and put two coral primaries on one screen.
 *
 * The signal under test is `last_research_at`, which the server writes on exactly
 * the research and refresh paths and on neither analyze-url nor a manual create.
 * Both halves are asserted: the row actions appear for a researched profile,
 * and a hand-typed one keeps a save. Nothing on this page sticks to the
 * viewport: the old sticky bottom bar was removed, so these also pin that no
 * `.sticky` element remains here.
 *
 * Profiles are created from store listings only: the details card renders
 * once research returns a profile, never before. So these also pin the two
 * halves of that gate — nothing to correct before research, and the draft
 * revealed the moment it exists.
 */
async function runBrandSetupChecks() {
  const BrandSetup = load("pages/BrandSetup.jsx").default;

  const researched = {
    id: "p1",
    brand_name: "Threadly",
    brand_description: "One list, not eleven.",
    status: "draft",
    appstore_url: "https://apps.apple.com/threadly",
    last_research_at: "2026-09-01T10:00:00Z",
    research_sources: [{ label: "app_store", ok: true }],
  };

  const handTyped = {
    id: "p2",
    brand_name: "Handmade",
    brand_description: "",
    status: "draft",
    // No last_research_at: the founder typed this one.
  };

  // An approved profile: the state the re-runs belong to. Refresh owes a
  // re-approval, so it is offered only here, and the fork is the other entry
  // point into the same research run.
  const approved = {
    ...researched,
    status: "approved",
    approved_at: "2026-09-02T10:00:00Z",
  };

  async function mountWith(ctx, active) {
    await withApi(
      {
        getActiveBrand: async () => active,
        getAppProfiles: async () => ({ profiles: [active] }),
      },
      async () => {
        await mount(BrandSetup, {})(ctx);
      }
    );
    await act(async () => {});
  }

  await check("profile next action approves a manual draft before opening its scoped studio", async (ctx) => {
    let approval = null;
    const previousNavigations = global.__SMOKE_NAVIGATIONS;
    global.__SMOKE_NAVIGATIONS = [];
    try {
      await withApi({
        getActiveBrand: async () => handTyped,
        getAppProfiles: async () => ({ profiles: [handTyped] }),
        approveAppProfile: async (id, applyPending) => { approval = { id, applyPending }; return { ...handTyped, status: "approved" }; },
      }, async () => {
        await mount(BrandSetup)(ctx);
        const next = () => ctx.container.querySelector('[data-testid="find-video-to-remix-button"]');
        if (!next().textContent.includes("Approve saved profile")) throw new Error("draft points at a studio it cannot use");
        await clickEl(ctx, next());
        if (approval?.id !== "p2" || approval.applyPending !== false || global.__SMOKE_NAVIGATIONS.length) throw new Error("approval skipped review or navigated prematurely");
        if (!next().textContent.includes("Create Video")) throw new Error("approved profile has no next action");
        await clickEl(ctx, next());
        if (!global.__SMOKE_NAVIGATIONS.includes("/create?profile=p2")) throw new Error("studio navigation lost approved profile");
      });
    } finally {
      global.__SMOKE_NAVIGATIONS = previousNavigations;
    }
  });

  await check(
    "save and approve sit in the research row once research has generated the profile",
    async (ctx) => {
      await mountWith(ctx, researched);
      const save = ctx.container.querySelector('[data-testid="save-brand-button"]');
      if (!save) {
        throw new Error(
          "the research row has no Save for a researched profile. The founder has a " +
            "generated draft to review and no way to save or approve it."
        );
      }
      if (!ctx.container.querySelector('[data-testid="approve-profile-button"]')) {
        throw new Error("a researched draft cannot be approved from the research row");
      }
      // Same row as the research controls, not pinned to the viewport: the row
      // div holds them, and nothing here sticks.
      const row = save.closest("div");
      if (!row || !row.querySelector('[data-testid="research-menu-button"]')) {
        throw new Error("Save is not in the same row as the Research menu");
      }
      // The card's own submit is gone once a draft exists: re-running research
      // is the menu's job, and a submit left beside it would fork a profile on
      // Enter with no control on screen to explain it.
      if (row.querySelector('[data-testid="research-app-button"]')) {
        throw new Error(
          "a researched draft still carries the card's research submit beside the Research menu"
        );
      }
      // One Signal Coral primary — the state's commit action. Two would leave
      // the founder choosing between two "main" buttons, which is the palette
      // rule this row broke when every action had a button of its own.
      const primaries = row.querySelectorAll(".btn-bevel-accent");
      if (primaries.length !== 2) {
        throw new Error(
          `the research row shows ${primaries.length} Signal Indigo primaries; expected Save and Approve`
        );
      }
      if (ctx.container.querySelector(".sticky")) {
        throw new Error(
          "a sticky element remains on the profile editor: review actions live " +
            "in the research row now, nothing should pin to the viewport"
        );
      }
      // Exactly one Save on the page. Two would leave the founder choosing
      // between them for no reason, which is the ambiguity the gate removed.
      const saves = ctx.container.querySelectorAll(
        '[data-testid="save-brand-button"], [data-testid="save-manual-profile-button"]'
      );
      if (saves.length !== 1) {
        throw new Error(
          `expected exactly one Save on a researched profile, found ${saves.length}`
        );
      }
    }
  );

  await check(
    "an approved profile's row is two short controls, and the menu carries the re-runs",
    async (ctx) => {
      let refreshed = null;
      // Everything inside withApi: the override only lives for the callback,
      // and the click at the end of this check has to reach it.
      await withApi(
        {
          getActiveBrand: async () => approved,
          getAppProfiles: async () => ({ profiles: [approved] }),
          refreshAppProfile: async (id) => {
            refreshed = id;
            return { ...approved, pending_research: { brand_description: "New words" } };
          },
        },
        async () => {
          await mount(BrandSetup, {})(ctx);
          await act(async () => {});
          const save = ctx.container.querySelector('[data-testid="save-brand-button"]');
          if (!save) throw new Error("an approved profile offers no way to store an edit");
          const row = save.closest("div");
          const labels = [...row.querySelectorAll("button")].map((b) => (b.textContent || "").trim());
          if (labels.join(" | ") !== "Save profile | Research") {
            throw new Error(
              `the approved row reads ${JSON.stringify(labels)}, not two short controls`
            );
          }
          // The sentences this row used to carry are gone from the page, not
          // just from the row: a label that long is what made it unreadable,
          // and the fork a label promised is now promised by the item it opens.
          expectAbsent(ctx, "Refresh from sources (needs re-approval)", "the long refresh label is still on the page");
          expectAbsent(ctx, "Review complete", "the reviewed-to-approve label is still on the page");
          expectAbsent(ctx, "Research into a new draft", "a button label still promises the fork");
          // Each re-run states its consequence beside the item, where it is read
          // at the moment of choosing rather than a screen earlier.
          const refreshItem = await openMenu(ctx, "research-menu-button", "refresh-profile-button");
          if (!refreshItem) throw new Error("the Research menu offers no refresh item on an approved profile");
          if (!/Needs re-approval/.test(refreshItem.textContent || "")) {
            throw new Error("the refresh item does not say it owes a re-approval");
          }
          const forkItem = dom.window.document.querySelector('[data-testid="research-new-draft-button"]');
          if (!forkItem) throw new Error("the Research menu offers no research-into-new-draft item");
          if (!/Creates separate draft/.test(forkItem.textContent || "")) {
            throw new Error("the fork item does not say it creates a separate draft");
          }
          // Wired to the page's own handler, not merely present: the refresh
          // item has to stage the proposal the alert on this page reviews.
          await clickEl(ctx, refreshItem, "no refresh item to click");
          if (refreshed !== "p1") {
            throw new Error(`refreshAppProfile was called with ${JSON.stringify(refreshed)}`);
          }
          if (!ctx.container.querySelector('[data-testid="pending-refresh-alert"]')) {
            throw new Error("the refreshed proposal has no review path on this page");
          }
        }
      );
    }
  );

  await check(
    "a hand-typed profile keeps a Save even though it gets no research-row actions",
    async (ctx) => {
      await mountWith(ctx, handTyped);
      if (ctx.container.querySelector('[data-testid="save-brand-button"]')) {
        throw new Error(
          "research-row review actions are showing for a profile research never ran. " +
            "There is no generated draft to review."
        );
      }
      if (ctx.container.querySelector('[data-testid="research-menu-button"]')) {
        throw new Error(
          "a hand-typed profile is offered the re-run menu. Nothing was researched, " +
            "so neither the proposal refresh nor the fork applies."
        );
      }
      const manualSave = ctx.container.querySelector(
        '[data-testid="save-manual-profile-button"]'
      );
      if (!manualSave) {
        throw new Error(
          "a hand-typed profile has no Save at all. The research row was the only " +
            "other save on this page, so the form can now be filled and never stored."
        );
      }
    }
  );

  await check(
    "with no profile the details stay hidden and only research is offered",
    async (ctx) => {
      // Before research there is no draft to correct, so the manual card must
      // not render — and neither may the removed website autofill.
      await withApi(
        {
          getActiveBrand: async () => {
            throw new Error("no brand yet");
          },
          getAppProfiles: async () => ({ profiles: [] }),
        },
        async () => {
          await mount(BrandSetup, {})(ctx);
        }
      );
      await act(async () => {});
      if (!ctx.container.querySelector('[data-testid="app-research-card"]')) {
        throw new Error("the research card is missing: there is no way to create a profile");
      }
      for (const gone of [
        "brand-manual-card",
        "brand-url-card",
        "save-brand-button",
        "save-manual-profile-button",
        "research-menu-button",
      ]) {
        if (ctx.container.querySelector(`[data-testid="${gone}"]`)) {
          throw new Error(
            `a profile-less page still renders ${gone}: review controls with nothing to review`
          );
        }
      }
    }
  );

  await check(
    "research reveals the details card for the draft it just created",
    async (ctx) => {
      // Everything inside withApi: the override only lives for the callback,
      // and the submit below must still see it.
      await withApi(
        {
          getActiveBrand: async () => {
            throw new Error("no brand yet");
          },
          getAppProfiles: async () => ({ profiles: [researched] }),
          researchAppProfile: async () => researched,
        },
        async () => {
          await mount(BrandSetup, {})(ctx);
          await act(async () => {});
          if (ctx.container.querySelector('[data-testid="brand-manual-card"]')) {
            throw new Error("the details card renders before any profile exists");
          }
          await typeInto(
            ctx,
            ctx.container.querySelector('[data-testid="appstore-url-input"]'),
            "https://apps.apple.com/threadly",
            "no App Store input to research from"
          );
          // Submitted the way the form submits it, so this pins the wiring
          // and not just the handler existing.
          await act(async () => {
            ctx.container
              .querySelector('[data-testid="app-research-card"]')
              .dispatchEvent(new dom.window.Event("submit", { bubbles: true, cancelable: true }));
          });
          await act(async () => {});
          if (!ctx.container.querySelector('[data-testid="brand-manual-card"]')) {
            throw new Error(
              "research succeeded but the details card never appeared: the draft " +
                "exists and the founder cannot see it"
            );
          }
          if (!ctx.container.querySelector('[data-testid="save-brand-button"]')) {
            throw new Error("the revealed draft has no research-row save to store corrections with");
          }
        }
      );
    }
  );
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
    // The server mints this fresh on every read, so the panel can always
    // splice the same-origin /download route off it.
    playback_url: "/api/media/videos/gen-1.mp4?exp=1&sig=abc",
  };

  async function mountStudio(ctx, generations) {
    // Mounted directly rather than through the wizard, like the other
    // GenerationPanel checks: the block under test only renders for a finished
    // render, and reaching that through the wizard would be testing navigation
    // instead of this.
    await withApi(
      {
        getGenerations: async () => ({ generations: generations || [COMPLETED] }),
      },
      async () => {
        await mount(GenerationPanel, { project: PROJECT_WITH_STRATEGY })(ctx);
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
      const href = download.getAttribute("href") || "";
      if (!href.includes("/api/media/videos/")) {
        throw new Error(`the download points somewhere else: ${href}`);
      }
      // Same-origin is not enough: only the /download route forces a save.
      // A same-origin playback href still opens in a tab.
      if (!href.includes("/download")) {
        throw new Error(`the download does not force a save: ${href}`);
      }
    }
  );

  // The vote already saves; this is the visual restore after a reload. The
  // panel reads the verdicts riding on the generation it already fetched, so
  // no extra request is needed and none may be recorded by the mount itself.
  await check(
    "a finished render restores its saved video thumb without a new vote",
    async (ctx) => {
      global.__SMOKE_THUMBS = [];
      try {
        await mountStudio(ctx, [{ ...COMPLETED, verdicts: { video: -1 } }]);
        const down = ctx.container.querySelector(
          '[data-testid="video-feedback-thumb-down"]'
        );
        if (!down) throw new Error("the post-render video thumb is missing");
        if (down.getAttribute("aria-pressed") !== "true") {
          throw new Error("a saved thumbs-down on the video is not highlighted");
        }
        if ((global.__SMOKE_THUMBS || []).length !== 0) {
          throw new Error("restoring the highlight recorded a vote that was never cast");
        }
      } finally {
        global.__SMOKE_THUMBS = [];
      }
    }
  );

  await check(
    "the studio download never points at raw cloud storage",
    async (ctx) => {
      // The reported bug: r2_url is a cross-origin private-bucket locator, so
      // handing it to the anchor opened an R2 error page instead of saving.
      // The preview has the same latent flaw, masked by preload="none".
      const hostile = {
        ...COMPLETED,
        r2_url: "https://bucket.r2.dev/owner/gen-1.mp4",
        playback_url: "/api/media/videos/gen-1.mp4?exp=1&sig=abc",
      };
      await mountStudio(ctx, [hostile]);
      const download = [...ctx.container.querySelectorAll("a")].find((a) =>
        (a.textContent || "").includes("Download MP4")
      );
      if (!download) throw new Error("the studio's own download is gone");
      const href = download.getAttribute("href") || "";
      if (!href.includes("/download") || href.includes("r2.dev")) {
        throw new Error(`the download still points at raw storage: ${href}`);
      }
      const video = ctx.container.querySelector("video");
      if (!video) throw new Error("the preview is gone");
      const src = video.getAttribute("src") || "";
      if (!src.includes("/api/media/videos/") || src.includes("r2.dev")) {
        throw new Error(`the preview still points at raw storage: ${src}`);
      }
    }
  );

  // The frozen post kit is written at completion and the output moment reads
  // the same frozen object History keeps — never re-derived, never invented.
  const POST_KIT = {
    caption:
      "Stop writing empty pages with one timed start — a focus timer that starts in one tap. What stalls your first sentence?",
    hashtags: ["#FocusTimer", "#productivity", "#studytok", "#focus"],
    cover_text: "Stop writing empty pages",
  };
  const LEGACY_KIT = {
    captions: [
      "Stop writing empty pages with one timed start.",
      "A focus timer that starts in one tap.",
      "What stalls your first sentence?",
    ],
    hashtags: ["#FocusTimer", "#productivity"],
    cover_text: "Stop writing empty pages",
  };

  // One owner for the frozen-kit assertions the output moment, the History
  // drawer, and the details modal all repeat: the same captions, hashtags,
  // cover text, and copy buttons, with only the site label differing.
  function assertFrozenKit(section, site) {
    if (!section) throw new Error(`no frozen post kit at ${site}`);
    if (!section.textContent.includes(POST_KIT.caption)) {
      throw new Error(`post caption missing at ${site}`);
    }
    if (section.textContent.includes("Caption 1")) {
      throw new Error(`three-caption layout leaked at ${site}: one caption only`);
    }
    if (!section.textContent.includes("#FocusTimer")) {
      throw new Error(`post hashtags missing at ${site}`);
    }
    if (!section.textContent.includes("Stop writing empty pages")) {
      throw new Error(`post cover text missing at ${site}`);
    }
    for (const id of ["postkit-copy-all", "postkit-copy-caption-0", "postkit-copy-hashtags", "postkit-copy-cover"]) {
      if (!section.querySelector(`[data-testid="${id}"]`)) {
        throw new Error(`post copy button missing at ${site}: ${id}`);
      }
    }
  }

  await check(
    "a finished render shows its frozen post kit at the output moment",
    async (ctx) => {
      await mountStudio(ctx, [{ ...COMPLETED, post_kit: POST_KIT }]);
      assertFrozenKit(ctx.container.querySelector('[data-testid="post-kit"]'), "output moment");
    }
  );

  await check(
    "a render without a kit shows no post copy at the output moment",
    async (ctx) => {
      await mountStudio(ctx);
      if (ctx.container.querySelector('[data-testid="post-kit"]')) {
        throw new Error("a pre-kit render invents post copy at the output moment");
      }
    }
  );

  await check(
    "an old three-caption kit still shows its first caption",
    async (ctx) => {
      await mountStudio(ctx, [{ ...COMPLETED, post_kit: LEGACY_KIT }]);
      const section = ctx.container.querySelector('[data-testid="post-kit"]');
      if (!section) throw new Error("a legacy kit renders nothing at the output moment");
      if (!section.textContent.includes(LEGACY_KIT.captions[0])) {
        throw new Error("a legacy kit lost its first caption");
      }
      for (const extra of LEGACY_KIT.captions.slice(1)) {
        if (section.textContent.includes(extra)) {
          throw new Error("a legacy kit shows more than its first caption");
        }
      }
    }
  );

  await check(
    "regenerate replaces the saved copy only when clicked",
    async (ctx) => {
      const FRESH = {
        caption: "Fresh caption written on demand, never before the click.",
        hashtags: ["#FocusTimer", "#fresh", "#deepwork", "#habits"],
        cover_text: "Fresh cover",
      };
      let calls = 0;
      await withApi(
        {
          regeneratePostKit: async () => {
            calls += 1;
            return { post_kit: FRESH };
          },
        },
        async () => {
          await mountStudio(ctx, [{ ...COMPLETED, post_kit: POST_KIT }]);
        }
      );
      if (calls !== 0) throw new Error("the kit regenerated without a click");
      const button = ctx.container.querySelector('[data-testid="postkit-regenerate"]');
      if (!button) throw new Error("no Regenerate button on the post copy");
      await withApi(
        {
          regeneratePostKit: async () => {
            calls += 1;
            return { post_kit: FRESH };
          },
        },
        async () => clickEl(ctx, button, "regenerate the post copy")
      );
      if (calls !== 1) throw new Error("regenerate did not run exactly once on click");
      const section = ctx.container.querySelector('[data-testid="post-kit"]');
      if (!section || !section.textContent.includes(FRESH.caption)) {
        throw new Error("regenerate did not replace the saved copy");
      }
      if (section.textContent.includes(POST_KIT.caption)) {
        throw new Error("the old caption survived its replacement");
      }
    }
  );

  await check(
    "a failed regenerate keeps the current copy and says so",
    async (ctx) => {
      await withApi({ regeneratePostKit: async () => { throw new Error("text model is down"); } }, async () => {
        await mountStudio(ctx, [{ ...COMPLETED, post_kit: POST_KIT }]);
        await clickEl(
          ctx,
          ctx.container.querySelector('[data-testid="postkit-regenerate"]'),
          "regenerate the post copy"
        );
      });
      const section = ctx.container.querySelector('[data-testid="post-kit"]');
      if (!section || !section.textContent.includes(POST_KIT.caption)) {
        throw new Error("a failed regenerate lost the current copy");
      }
      if (!ctx.container.querySelector('[data-testid="postkit-regenerate-error"]')) {
        throw new Error("a failed regenerate shows no error");
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
    "Demo + CTA works on its own, without a Hook + Story",
    async (ctx) => {
      await mount(DemoCtaStudio, {})(ctx);
      // The whole point of the sidebar entry: no generation, no finished render,
      // and the editor is still there with a file picker as its input.
      const input = ctx.container.querySelector('[data-testid="demo-cta-file-input"]');
      if (!input) {
        throw new Error(
          "no file input on the standalone editor. Requiring a Hook + Story first " +
            "would make this unreachable for anyone who just wants to wrap their own clip."
        );
      }
      // The finished-render list lived here and its "Open in editor" links were
      // the only anchors on this page. Gone on purpose: History chooses the clip.
      const pickerLink = [...ctx.container.querySelectorAll("a")].find((a) =>
        (a.textContent || "").includes("Open in editor")
      );
      if (pickerLink) throw new Error("the finished-render list is back on the standalone page");
      // The section carries no picker button of its own: the frame's upload
      // button drives the input above by ref in both routes, so a second
      // button here was two doors to the same input. The input stays.
      const labels = [...ctx.container.querySelectorAll("button")].map((b) =>
        (b.textContent || "").trim()
      );
      if (labels.some((t) => t === "Choose a video" || t === "Replace")) {
        throw new Error(
          "the Source & Look picker button is back. The frame's upload button " +
            "is the one picker control; this one only duplicated it."
        );
      }
      // The standalone header describes the page in one sentence, on the same
      // 54-60 char budget as every other topic page masthead (that budget is
      // asserted for all six pages by "every topic page subtitle fits the
      // masthead budget" below; this one is repeated here because the rendered
      // string is what a founder actually reads).
      const STANDALONE_COPY =
        "Style any clip: phone mockup or full-frame for History.";
      if (STANDALONE_COPY.length < 54 || STANDALONE_COPY.length > 60) {
        throw new Error(
          `the standalone copy is ${STANDALONE_COPY.length} chars, outside the 54-60 budget`
        );
      }
      if (!ctx.text().includes(STANDALONE_COPY)) {
        throw new Error(
          "the standalone page does not carry its one-sentence description"
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

  // The subtitle under a topic name is the first line a founder reads, and it
  // had drifted: six pages carried a 56-104 char sentence under the same 24px
  // title, so "a subtitle" meant a different amount of reading per page and the
  // longest ones pushed the page's own content further down than the title had
  // promised. One budget for all six makes the line scan at a glance and stops
  // the length being re-decided, differently, every time a page is touched.
  //
  // Read from the source rather than from a mount, because two of these
  // subtitles are route-dependent variants and the rest would need six sets of
  // API mocks to render a copy rule. The guard against a silent pass is a
  // missing-page report: a page that stops declaring a description fails here
  // instead of quietly leaving the budget.
  await check("every topic page subtitle fits the masthead budget", async () => {
    const MIN = 54;
    const MAX = 60;
    // Page file -> the nav label it serves, so a failure names the page a founder
    // would be looking at rather than a path.
    const PAGES = {
      "src/pages/BrandSetup.jsx": "App Profile",
      "src/pages/DemoCtaStudio.jsx": "Demo + CTA",
      "src/pages/CreateVideo.jsx": "Create Video",
      "src/pages/AssetLibrary.jsx": "Asset Library",
      "src/pages/GenerationHistory.jsx": "Generation History",
      "src/pages/Analytics.jsx": "Analytics",
    };
    const problems = [];
    const missing = [];
    for (const [rel, label] of Object.entries(PAGES)) {
      const text = fs.readFileSync(path.join(__dirname, "..", rel), "utf8");
      const subtitles = [];
      for (const block of text.match(/<PageHeader[\s\S]*?\n\s*\/>/g) || []) {
        // Only a page-level masthead: one that carries a literal title.
        if (!/title="[^"]+"/.test(block)) continue;
        for (const m of block.matchAll(/description="([^"]*)"/g)) subtitles.push(m[1]);
        // A braced description is a state or route variant ("on this route, this
        // sentence"). Its string literals are the copy; a computed one is not on
        // the budget and contributes nothing here.
        const braced = block.match(/description=\{([\s\S]*?)\n\s*\}/);
        if (braced) {
          for (const m of braced[1].matchAll(/"([^"]+)"/g)) subtitles.push(m[1]);
        }
      }
      if (!subtitles.length) {
        missing.push(label);
        continue;
      }
      for (const copy of subtitles) {
        if (copy.length < MIN || copy.length > MAX) {
          problems.push(`${label}: ${copy.length} chars — "${copy}"`);
        }
      }
    }
    if (missing.length) {
      throw new Error(
        `no masthead subtitle found for: ${missing.join(", ")}. Each topic page ` +
          "must still pass a description to PageHeader; a page that drops it would " +
          "otherwise leave this budget without being noticed."
      );
    }
    if (problems.length) {
      throw new Error(
        `masthead subtitles outside the ${MIN}-${MAX} char budget:\n        ` +
          problems.join("\n        ")
      );
    }
  });

  // The same budget, one level down: the helper sentence under a group label
  // or a field label inside a wizard step. It had drifted the way the masthead
  // did, and worse — the Template card and the Presenter photo card sit side by
  // side in the same step, and their subtitles rendered at 12px and 14px while
  // running 53 and 197 characters. A different size read as a different kind of
  // control, and a two-sentence subtitle pushed its own card's content down.
  //
  // Read from source with `data-subtitle` as the selector, not from a mount:
  // these sit behind four different API states and a render would only cover
  // whichever one a fixture happened to set up. The marker is the point — a
  // subtitle added later without it fails the marker-count below rather than
  // quietly joining the set with no budget.
  //
  // Scope is deliberate. This covers label-attached helper copy ONLY. Spinner
  // text, error strings and whole state panels ("The plan didn't generate…")
  // are body copy with a job of their own, and padding them to 55 would cost
  // the founder the instruction. They are not tagged, so they stay out.
  await check("every wizard subtitle fits the shared size and length budget", async () => {
    const MIN = 55;
    const MAX = 60;
    const FILE = path.join(__dirname, "..", "src/pages/CreateVideo.jsx");
    const text = fs.readFileSync(FILE, "utf8");
    const found = [];
    for (const m of text.matchAll(/<p className="([^"]*)"[^>]*data-subtitle=""[^>]*>([\s\S]*?)<\/p>/g)) {
      const copy = m[2]
        .replace(/<[^>]+>/g, " ")
        .replace(/&apos;/g, "'")
        .replace(/&amp;/g, "&")
        .replace(/\s+/g, " ")
        .trim();
      // This element renders a shared constant, so its own text is the
      // identifier, not the sentence. Counted once, resolved, below.
      if (/^\{[A-Z_]+\}$/.test(copy)) continue;
      found.push({ cls: m[1], copy });
    }
    // The angles CTA copy renders from a shared constant, so its own <p> holds
    // only the identifier. Count it separately rather than pretending it is
    // empty: a constant that drifts out of budget must still be caught.
    const cta = /const ANGLES_CTA_COPY = "([^"]*)"/.exec(text);
    if (cta) found.push({ cls: "text-xs", copy: cta[1] });

    if (!found.length) {
      throw new Error(
        "no data-subtitle elements found in CreateVideo.jsx. The marker is what this " +
          "check selects on; if the subtitles moved, re-mark them rather than " +
          "deleting the check."
      );
    }

    const problems = [];
    for (const { cls, copy } of found) {
      const line = text.split("\n").findIndex((l) => l.includes(`data-subtitle=""`) && l.includes(cls.split(" ").pop()));
      if (/\btext-sm\b|\btext-base\b|\btext-lg\b/.test(cls)) {
        problems.push(`not text-xs (class "${cls.trim()}") — "${copy}"`);
      }
      if (copy.length < MIN || copy.length > MAX) {
        problems.push(`${copy.length} chars — "${copy}"`);
      }
    }
    if (problems.length) {
      throw new Error(
        `wizard subtitles outside text-xs + ${MIN}-${MAX} chars:\n        ` +
          problems.join("\n        ")
      );
    }
  });

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
      const key = "hookforge.demoCta.openSections.v4";
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
      // Which groups are expanded, read from the rendered aria-expanded state
      // rather than from text: two groups can each contain "1.8s"-like content,
      // but only one header can claim to be open.
      const openGroups = (container) =>
        [...container.querySelectorAll('button[aria-expanded]')]
          .filter((b) => b.getAttribute("aria-expanded") === "true")
          .map((b) => (b.textContent || "").trim());
      const clickGroup = async (container, label) => {
        const btn = [...container.querySelectorAll("button[aria-expanded]")].find(
          (b) => (b.textContent || "").trim() === label
        );
        if (!btn) throw new Error(`no ${label} group header to click`);
        await act(async () => {
          btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
      };
      try {
        // First visit: exactly one group, Source & Look — it is the input, and
        // eleven open groups made the panel taller than the video it describes.
        const first = await mountEditor();
        const firstOpen = openGroups(first.container);
        if (firstOpen.length !== 1 || firstOpen[0] !== "Source & Look") {
          throw new Error(
            `a first visit should open only Source & Look (open: ${JSON.stringify(firstOpen)})`
          );
        }
        // Opening another closes the first. This is the whole point of the
        // change: two expanded groups is the layout that pushed the video small.
        await clickGroup(first.container, "Hook Text");
        const afterSwitch = openGroups(first.container);
        if (afterSwitch.length !== 1 || afterSwitch[0] !== "Hook Text") {
          throw new Error(
            `opening Hook Text must leave exactly it open (open: ${JSON.stringify(afterSwitch)})`
          );
        }
        // And the content assertion: the duration reads once, right-aligned.
        const firstText = first.container.textContent;
        if (!firstText.includes("On screen") || !firstText.includes("1.8s")) {
          throw new Error("Hook Text did not open on click");
        }
        const saved = JSON.parse(dom.window.localStorage.getItem(key) || "{}");
        const savedOpen = Object.keys(saved).filter((k) => saved[k]);
        if (savedOpen.length !== 1 || savedOpen[0] !== "hook") {
          throw new Error(
            `switching groups was not written through (stored: ${JSON.stringify(saved)})`
          );
        }
        // Second visit must honour it, not reset to the default.
        const second = await mountEditor();
        const secondOpen = openGroups(second.container);
        if (secondOpen.length !== 1 || secondOpen[0] !== "Hook Text") {
          throw new Error(
            "the open group was not remembered. The panel is a workspace, not a " +
              "form; re-opening a different group than the one someone left on " +
              `is the friction that makes a tool feel like it forgot you (open: ${JSON.stringify(secondOpen)})`
          );
        }
        // Clicking the open group closes it; none open is valid.
        await clickGroup(second.container, "Hook Text");
        const closed = openGroups(second.container);
        if (closed.length !== 0) {
          throw new Error(
            `clicking the open group should close it (still open: ${JSON.stringify(closed)})`
          );
        }
      } finally {
        dom.window.localStorage.removeItem(key);
      }
    }
  );

  // Disclosure triggers must not name a panel that is not in the DOM: a
  // collapsed trigger pointing at a missing id sends a screen reader
  // nowhere, and an expanded trigger whose controls resolve nowhere is a
  // lie. Exercised through the real editor in both states, not just the
  // default render — the History panel starts collapsed and only exists
  // once opened.
  await check(
    "collapsed disclosures name no panel; expanded ones resolve",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
      await withApi(
        {
          getGenerations: async () => ({ generations: [COMPLETED] }),
          getGenerationHistory: async () => ({ generations: [] }),
        },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const dangling = () => {
            const bad = [];
            for (const btn of ctx.container.querySelectorAll("button[aria-expanded]")) {
              const controls = btn.getAttribute("aria-controls");
              if (controls && !ctx.container.ownerDocument.getElementById(controls)) {
                bad.push((btn.textContent || "").trim().slice(0, 40) || controls);
              }
            }
            return bad;
          };
          const collapsedNaming = () =>
            [...ctx.container.querySelectorAll('button[aria-expanded="false"]')].filter((b) =>
              b.hasAttribute("aria-controls")
            );
          let bad = dangling();
          if (bad.length) {
            throw new Error(`triggers point at missing panels: ${bad.join("; ")}`);
          }
          // The History toggle starts collapsed and must not name its panel
          // until the panel exists.
          const toggle = ctx.container.querySelector('[data-testid="history-source-toggle"]');
          if (!toggle) throw new Error("no history-source-toggle to expand");
          if (toggle.hasAttribute("aria-controls")) {
            throw new Error("collapsed History toggle names a panel that is not rendered");
          }
          await act(async () => {
            toggle.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          const controls = toggle.getAttribute("aria-controls");
          if (!controls || !ctx.container.ownerDocument.getElementById(controls)) {
            throw new Error("expanded History toggle does not resolve to its panel");
          }
          bad = dangling();
          if (bad.length) {
            throw new Error(`after expanding History: ${bad.join("; ")}`);
          }
          if (collapsedNaming().length) {
            throw new Error("a collapsed disclosure still names a panel");
          }
        }
      );
    }
  );

  // The mobile drawer stays mounted for its slide transition, so the closed
  // state must be inert — otherwise keyboard users tab into an off-screen
  // panel. And focus must travel: into the drawer on open (it opens over
  // whatever had focus), back to the trigger on close (or focus is dropped
  // on the page behind it).
  await check(
    "the closed mobile drawer is inert; focus enters on open and returns on close",
    async (ctx) => {
      const { MobileSidebar } = load("components/Sidebar.jsx");
      const renderDrawer = (open) =>
        React.createElement(
          OnboardingProvider,
          null,
          React.createElement(MobileSidebar, { open, onClose: () => {} })
        );
      const trigger = dom.window.document.createElement("button");
      trigger.textContent = "Menu";
      dom.window.document.body.appendChild(trigger);
      trigger.focus();
      try {
        await act(async () => {
          ctx.root.render(renderDrawer(false));
        });
        await act(async () => {});
        const drawer = ctx.container.querySelector('[data-testid="mobile-sidebar"]');
        if (!drawer) throw new Error("no mobile drawer rendered");
        if (!drawer.hasAttribute("inert")) {
          throw new Error("closed drawer is not inert and stays tabbable off-screen");
        }
        await act(async () => {
          ctx.root.render(renderDrawer(true));
        });
        await act(async () => {});
        const close = ctx.container.querySelector('[data-testid="mobile-sidebar-close-button"]');
        if (drawer.hasAttribute("inert")) {
          throw new Error("open drawer is still inert");
        }
        if (dom.window.document.activeElement !== close) {
          throw new Error("opening the drawer did not move focus to Close");
        }
        await act(async () => {
          ctx.root.render(renderDrawer(false));
        });
        await act(async () => {});
        if (dom.window.document.activeElement !== trigger) {
          throw new Error("closing the drawer did not return focus to the trigger");
        }
      } finally {
        trigger.remove();
      }
    }
  );

  // The tour tooltip is a programmatic focus target: it needs dialog
  // semantics, a real step position, and a visible focus indicator. Pinned
  // here because each half fails silently — a missing role just never
  // announces, and outline-none just never shows.
  await check("the tour tooltip is an announced dialog with a visible focus target", async () => {
    const src = fs.readFileSync(
      path.join(SRC, "components", "onboarding", "TourOverlay.jsx"),
      "utf8"
    );
    for (const [needle, why] of [
      ['role="dialog"', "the tooltip names no dialog role"],
      ["Step {stepIndex + 1} of {totalSteps}", "the tooltip announces no step position"],
      ["focus-ring", "the tooltip card carries no visible focus indicator"],
    ]) {
      if (!src.includes(needle)) throw new Error(why);
    }
    if (/p-4 outline-none/.test(src)) {
      throw new Error("the tooltip card still suppresses its focus outline");
    }
  });

  // The frame's Upload a clip button drives the file input by ref from OUTSIDE
  // the collapsible Source & Look group, so the input must survive that group
  // closing. The regression: the input lived inside the collapsible content,
  // so opening any other group unmounted it and the button clicked into a
  // null ref — silently doing nothing, with no dialog and no error.
  await check(
    "the frame upload still reaches its file input with Source & Look closed",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const header = [...ctx.container.querySelectorAll("button[aria-expanded]")].find(
            (b) => (b.textContent || "").trim() === "Hook Text"
          );
          if (!header) throw new Error("no Hook Text group header");
          await act(async () => {
            header.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          if (!ctx.container.querySelector('[data-testid="demo-cta-file-input"]')) {
            throw new Error(
              "closing Source & Look unmounted the file input, so the frame's " +
                "Upload a clip button clicks into a null ref and silently does nothing."
            );
          }
        }
      );
    }
  );

  // Public Sans and Sora are off the overlay font catalog. Public Sans shipped
  // in both lists (Hook Text and End Card CTA) and was the least distinct of
  // the text faces, so a founder could pick it and get something that read as
  // the browser default; Sora followed as a second trim of the same list.
  await check("Public Sans and Sora are gone from both overlay font lists", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
    // One group is open at a time, so each list is opened in turn.
    const openGroup = async (container, label) => {
      const btn = [...container.querySelectorAll("button[aria-expanded]")]
        .find((b) => (b.textContent || "").trim() === label);
      if (!btn) throw new Error(`no ${label} group header`);
      if (btn.getAttribute("aria-expanded") === "true") return;
      await act(async () => {
        btn.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
    };
    await withApi(
      { getGenerations: async () => ({ generations: [COMPLETED] }) },
      async () => {
        await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
        for (const [group, prefix] of [["Hook Text", "caption-font"], ["End Card CTA", "cta-font"]]) {
          await openGroup(ctx.container, group);
          const tiles = [...ctx.container.querySelectorAll(`[data-testid^="${prefix}-"]`)];
          if (tiles.length !== 9) {
            throw new Error(`expected 9 faces in the ${group} list, saw ${tiles.length}`);
          }
          for (const retired of ["public-sans", "sora"]) {
            if (tiles.some((t) => t.getAttribute("data-testid") === `${prefix}-${retired}`)) {
              throw new Error(`${retired} is still offered in the ${group} font list`);
            }
          }
        }
      }
    );
  });

  // With no loaded clip there is no window to replay, so option changes hold
  // the playhead. The canvas redraws either way — the six values are in the
  // preview loop's deps — so the choice is visible on the next frame. (This
  // mounts with a generation but no decoded clip, so videoMeta is empty and
  // the scoped replay below is a deliberate no-op. jsdom cannot observe
  // play(), so this pins currentTime.)
  await check("an overlay entrance, size or face change keeps the playhead", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
    // Overlay prefs persist across checks: a fade picked anywhere earlier
    // would make the fade click below a same-value no-op that still holds
    // the playhead — a pass that proves nothing.
    dom.window.localStorage.removeItem("hookforge.demoCta.overlayPrefs.v1");
    // The canvas redraw is what makes a choice visible at all, and jsdom has no
    // 2d context to assert it against — so the preview loop's dependency
    // contract is read from source. These seven were missing, which is why a new
    // entrance, size, face or text style never reached the canvas until the clip reloaded.
    const src = fs.readFileSync(
      path.join(__dirname, "..", "src", "demoCta", "usePreviewLoop.js"),
      "utf8"
    );
    const loopDeps = /}, \[device,[^\]]*\]\);/.exec(src);
    if (!loopDeps) throw new Error("the preview loop's dependency array moved");
    for (const name of ["captionFont", "ctaFont", "captionAnim", "ctaAnim", "captionScale", "ctaScale", "textStyle"]) {
      if (!loopDeps[0].includes(name)) {
        throw new Error(`the preview loop does not depend on ${name}, so the canvas keeps the old choice`);
      }
    }
    await withApi(
      { getGenerations: async () => ({ generations: [COMPLETED] }) },
      async () => {
        await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
        const video = ctx.container.querySelector("video");
        if (!video) throw new Error("the preview media element is missing");
        const group = [...ctx.container.querySelectorAll("button[aria-expanded]")]
          .find((b) => (b.textContent || "").trim() === "Hook Text");
        if (!group) throw new Error("no Hook Text group header");
        await act(async () => {
          group.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
        });
        await act(async () => {});

        const change = async (label, el) => {
          if (!el) throw new Error(`no control for ${label}`);
          video.currentTime = 4;
          if (video.currentTime !== 4) throw new Error(`could not seek the preview for ${label}`);
          await act(async () => {
            el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
          if (el.getAttribute("aria-pressed") !== "true") {
            throw new Error(`${label} did not take the click, so holding the playhead proves nothing`);
          }
          if (video.currentTime !== 4) {
            throw new Error(`${label} moved the playhead (now at ${video.currentTime}s)`);
          }
        };

        await change("an entrance", ctx.container.querySelector('[data-testid="caption-anim-fade"]'));
        await change("a face", ctx.container.querySelector('[data-testid="caption-font-nunito"]'));
        await change("a text style", ctx.container.querySelector('[data-testid="text-style-glow"]'));

        // Text size is a Radix slider, so it takes a key press on the thumb.
        const thumb = ctx.container.querySelector('[data-testid="caption-size-slider"] [role="slider"]');
        if (!thumb) throw new Error("no caption size slider thumb");
        video.currentTime = 4;
        await act(async () => {
          thumb.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true }));
        });
        await act(async () => {});
        if (video.currentTime !== 4) {
          throw new Error(`a text size change moved the playhead (now at ${video.currentTime}s)`);
        }
      }
    );
  });

  /**
   * A loaded clip with zero decoded bytes. jsdom has no canvas 2d and never
   * fires media metadata, so a no-op context (counting through onClear when
   * given) and a probe reporting the given fake dimensions stand in for a
   * real decode the suite must never depend on. clearRect runs once per
   * paintFrame in the default floating view, which makes it the paint
   * counter for the paint-on-demand check.
   *
   * Component code resolves URL from the global scope (Node's), not the
   * jsdom window, so the createObjectURL stub lands globally — exactly like
   * Blob. Node's real createObjectURL rejects a jsdom File and the upload
   * dies inside handleFile before videoUrl is ever set. drawPhone branches
   * on `video instanceof HTMLCanvasElement`, which the harness never mapped
   * to global, so without that mapping the first paint throws instead of
   * proving anything. Call restore() in a finally.
   */
  function installLoadedClipStubs({ width, height, onClear = () => {}, onDraw = () => {} }) {
    const gradientStub = { addColorStop() {} };
    const fakeCtx = new Proxy({}, {
      get(t, p) {
        if (p === "clearRect") return () => onClear();
        if (p === "drawImage") return (...args) => onDraw(...args);
        if (p === "measureText") return () => ({ width: 10 });
        if (typeof p === "string" && p.startsWith("create")) return () => gradientStub;
        return () => undefined;
      },
      set() { return true; },
    });
    const origGetContext = dom.window.HTMLCanvasElement.prototype.getContext;
    const origCreateObjectURL = URL.createObjectURL;
    const origRevokeObjectURL = URL.revokeObjectURL;
    const origCreateElement = dom.window.document.createElement.bind(dom.window.document);
    const createdVideos = [];
    dom.window.HTMLCanvasElement.prototype.getContext = function () { return fakeCtx; };
    URL.createObjectURL = () => "blob:fake-clip";
    URL.revokeObjectURL = () => {};
    const hadCanvasGlobal = "HTMLCanvasElement" in global;
    const origCanvasGlobal = global.HTMLCanvasElement;
    global.HTMLCanvasElement = dom.window.HTMLCanvasElement;
    const origPlay = dom.window.HTMLMediaElement.prototype.play;
    const origLoad = dom.window.HTMLMediaElement.prototype.load;
    const origPause = dom.window.HTMLMediaElement.prototype.pause;
    dom.window.HTMLMediaElement.prototype.play = () => Promise.resolve();
    dom.window.HTMLMediaElement.prototype.load = () => {};
    dom.window.HTMLMediaElement.prototype.pause = function () {
      if (Object.getOwnPropertyDescriptor(this, "paused")?.writable) this.paused = true;
      this.dispatchEvent(new dom.window.Event("pause"));
    };
    dom.window.document.createElement = (tag, opts) => {
      const el = origCreateElement(tag, opts);
      if (tag === "video") {
        Object.defineProperties(el, {
          videoWidth: { value: width, configurable: true },
          videoHeight: { value: height, configurable: true },
          duration: { value: 8, configurable: true },
        });
        createdVideos.push(el);
      }
      return el;
    };
    const flush = async () => {
      await act(async () => {});
      await new Promise((r) => setTimeout(r, 30));
      await act(async () => {});
    };
    // Overlay prefs and open sections persist across checks through the
    // stubbed storage: an earlier check that picked fade would make a later
    // fade click a no-op (same value, no repaint), and a group left open
    // would make the open click close it instead. Start clean, end clean.
    const resetUiState = () => {
      dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
      dom.window.localStorage.removeItem("hookforge.demoCta.overlayPrefs.v1");
    };
    const restore = () => {
      dom.window.HTMLCanvasElement.prototype.getContext = origGetContext;
      URL.createObjectURL = origCreateObjectURL;
      URL.revokeObjectURL = origRevokeObjectURL;
      dom.window.HTMLMediaElement.prototype.play = origPlay;
      dom.window.HTMLMediaElement.prototype.load = origLoad;
      dom.window.HTMLMediaElement.prototype.pause = origPause;
      dom.window.document.createElement = origCreateElement;
      if (hadCanvasGlobal) global.HTMLCanvasElement = origCanvasGlobal;
      else delete global.HTMLCanvasElement;
      resetUiState();
    };
    // Drives the upload path with a fake file: no bytes are decoded.
    const loadClip = async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          resetUiState();
          await mount(DemoCtaEditor, {})(ctx);
          const input = ctx.container.querySelector('[data-testid="demo-cta-file-input"]');
          if (!input) throw new Error("no file input");
          const file = new dom.window.File([new Uint8Array(16)], "clip.mp4", { type: "video/mp4" });
          Object.defineProperty(input, "files", { value: [file], configurable: true });
          await act(async () => {
            input.dispatchEvent(new dom.window.Event("change", { bubbles: true }));
          });
          await flush();
          const probe = createdVideos.find((v) => v.onloadedmetadata);
          if (!probe) throw new Error("the uploaded clip was never probed");
          await act(async () => {
            probe.onloadedmetadata();
          });
          await flush();
          await flush();
        }
      );
    };
    return { flush, restore, loadClip, createdVideos };
  }

  for (const mode of ["hand", "floating"]) {
    await check(`multiple ${mode} zoom locks preview new edits and replay zoom-in/out`, async (ctx) => {
      const clip = installLoadedClipStubs({ width: 1280, height: 720 });
      const zoom = load("demoCta/zoom.js");
      const originalResolve = zoom.getEffectiveZoom;
      let paintedZoom;
      zoom.getEffectiveZoom = (args) => {
        paintedZoom = originalResolve(args);
        return paintedZoom;
      };
      try {
        await clip.loadClip(ctx);
        const video = ctx.container.querySelector("video");
        const canvas = ctx.container.querySelector("canvas");
        Object.defineProperty(video, "paused", { configurable: true, value: true, writable: true });
        const click = async (el) => {
          if (!el) throw new Error("required zoom control missing");
          await act(async () => el.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true })));
          await clip.flush();
        };
        const seek = async (time) => {
          const slider = ctx.container.querySelector('[data-testid="demo-cta-scrubber"] [role="slider"]');
          await act(async () => slider.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Home", bubbles: true })));
          for (let t = 0; t < time; t++) {
            await act(async () => slider.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowRight", bubbles: true })));
          }
          await act(async () => video.dispatchEvent(new dom.window.Event("seeked")));
          await clip.flush();
        };
        const wheel = async (deltaY) => {
          await act(async () => canvas.dispatchEvent(new dom.window.WheelEvent("wheel", { deltaY, bubbles: true, cancelable: true })));
          await clip.flush();
        };
        const lock = async () => click([...ctx.container.querySelectorAll("button")].find((b) => b.textContent.trim() === "+ Lock"));
        const value = () => mode === "hand" ? paintedZoom.hZoom : paintedZoom.phoneScale;
        if (mode === "hand") await click(ctx.container.querySelector('[data-testid="view-mode-hand"]'));
        await seek(0);
        await lock();
        const baseline = value();
        await seek(2);
        if (mode === "hand") {
          await wheel(-200);
        } else {
          const thumb = ctx.container.querySelector('[data-testid="phone-size-slider"] [role="slider"]');
          await act(async () => thumb.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "End", bubbles: true })));
          await clip.flush();
        }
        const zoomedIn = value();
        if (!(zoomedIn > baseline)) throw new Error(`new ${mode} zoom is hidden behind the first lock: ${zoomedIn} <= ${baseline}`);
        if (video.currentTime !== 2 || !video.paused) throw new Error("framing edits must hold their timestamp");
        await lock();
        await seek(5);
        if (mode === "hand") {
          await wheel(400);
        } else {
          const thumb = ctx.container.querySelector('[data-testid="phone-size-slider"] [role="slider"]');
          await act(async () => thumb.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Home", bubbles: true })));
          await clip.flush();
        }
        const zoomedOut = value();
        if (!(zoomedOut < baseline)) throw new Error(`new ${mode} zoom-out is hidden: ${zoomedOut} >= ${baseline}`);
        await lock();
        if (!ctx.container.textContent.includes("3 locked segments")) throw new Error("three distinct locks were not saved");
        for (const [time, expected] of [[0, baseline], [1, baseline], [2, zoomedIn], [4, zoomedIn], [5, zoomedOut], [7, zoomedOut]]) {
          await seek(time);
          // Exercise actual playing paint, not just a paused seek.
          await act(async () => {
            video.paused = false;
            video.dispatchEvent(new dom.window.Event("play"));
          });
          await clip.flush();
          if (Math.abs(value() - expected) > 1e-9) throw new Error(`${mode} playback at ${time}s painted ${value()}, expected ${expected}`);
          await act(async () => {
            video.paused = true;
            video.dispatchEvent(new dom.window.Event("pause"));
          });
        }
        await seek(2);
        if (mode === "hand") {
          const thumb = ctx.container.querySelector('[data-testid="hand-zoom-slider"] [role="slider"]');
          if (Number(thumb.getAttribute("aria-valuenow")) !== zoomedIn) throw new Error("hand controls do not reflect the active lock");
        }
        // The actual export callback must resolve saved locks too, even if a
        // paused draft is still being auditioned. No codec/network is needed.
        await wheel(-10);
        const encoder = load("demoCta/exportTikTok.js");
        const originalEncode = encoder.exportTikTok;
        const originalFetch = global.fetch;
        const handAssets = load("demoCta/handView.js");
        const originalPrepare = handAssets.prepareHandViewImages;
        handAssets.prepareHandViewImages = async () => {};
        const rendered = [];
        encoder.exportTikTok = async ({ canvas: target, drawFrame }) => {
          for (const time of [0, 2, 5, 7]) {
            drawFrame(time, document.createElement("canvas"));
            rendered.push(mode === "hand" ? paintedZoom.hZoom : paintedZoom.phoneScale);
          }
          throw new Error("Zoom export callback verified");
        };
        global.fetch = async () => ({ ok: true, blob: async () => new Blob() });
        try {
          await click(ctx.container.querySelector('[data-testid="demo-cta-export"]'));
          if (JSON.stringify(rendered) !== JSON.stringify([baseline, zoomedIn, zoomedOut, zoomedOut])) {
            throw new Error(`export did not render the saved ${mode} locks: ${JSON.stringify(rendered)}`);
          }
          if (!ctx.container.textContent.includes("Zoom export callback verified")) throw new Error("the export callback was not exercised");
        } finally {
          encoder.exportTikTok = originalEncode;
          global.fetch = originalFetch;
          handAssets.prepareHandViewImages = originalPrepare;
        }
        // Updating the same timestamp replaces one lock; removing it reveals
        // the preceding lock again instead of leaving a stale live draft.
        await seek(2);
        await wheel(-20);
        const replacement = value();
        await lock();
        if (!ctx.container.textContent.includes("3 locked segments")) throw new Error("updating a lock duplicated its timestamp");
        await seek(3);
        if (Math.abs(value() - replacement) > 1e-9) throw new Error("updated lock did not play back");
        const remove = ctx.container.querySelectorAll('[title="Remove this keyframe"]')[1];
        await click(remove);
        if (Math.abs(value() - baseline) > 1e-9) throw new Error("removing a lock did not restore its predecessor");
        await click([...ctx.container.querySelectorAll("button")].find((b) => b.textContent.trim() === "Clear"));
        if (ctx.container.querySelector('[data-testid="demo-cta-keyframes"]')) throw new Error("Clear did not remove locks");
      } finally {
        zoom.getEffectiveZoom = originalResolve;
        clip.restore();
      }
    });
  }

  // Paused idle schedules zero frames; one settings change or seek paints
  // exactly one frame.
  await check("paused preview paints on demand: zero frames idle, one per change and seek", async (ctx) => {
    let paints = 0;
    const clip = installLoadedClipStubs({ width: 1280, height: 720, onClear: () => { paints += 1; } });
    const { flush } = clip;
    try {
      await clip.loadClip(ctx);
      const video = ctx.container.querySelector("video");
      if (!video) throw new Error("the preview media element is missing");
      if (!video.paused) throw new Error("the stubbed video is playing, so idle is unmeasurable");
      const idle = paints;
      if (idle === 0) throw new Error("no initial paint landed, so parking proves nothing");
      await flush();
      await flush();
      if (paints !== idle) {
        throw new Error(`paused idle painted ${paints - idle} extra frame(s); the loop is not parked`);
      }
      // One settings change paints exactly one frame and replays its window.
      video.currentTime = 4;
      const hookGroup = [...ctx.container.querySelectorAll("button[aria-expanded]")]
        .find((b) => (b.textContent || "").trim() === "Hook Text");
      if (!hookGroup) throw new Error("no Hook Text group header");
      await act(async () => {
        hookGroup.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await flush();
      const paintsAfterOpen = paints;
      const fade = ctx.container.querySelector('[data-testid="caption-anim-fade"]');
      if (!fade) throw new Error("no caption fade chip");
      await act(async () => {
        fade.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await flush();
      if (fade.getAttribute("aria-pressed") !== "true") {
        throw new Error("the fade chip did not take the click, so a repaint proves nothing");
      }
      // Opening the group may itself dirty one frame; the entrance change
      // must add exactly one more.
      if (paints !== paintsAfterOpen + 1) {
        throw new Error(`an entrance change painted ${paints - paintsAfterOpen} frame(s), expected exactly 1`);
      }
      // A hook style pick replays the hook window from frame 0 and parks at
      // the hook end instead of holding mid-clip: loop switches off for the
      // window so a CTA replay ending at the clip end cannot wrap either.
      if (video.currentTime !== 0) {
        throw new Error(`a hook entrance change did not replay the hook window (at ${video.currentTime}s, expected 0)`);
      }
      if (video.loop !== false) {
        throw new Error("a hook entrance change did not hold the scoped window (loop still on)");
      }
      // One paused seek paints exactly one frame.
      const paintsBeforeSeek = paints;
      await act(async () => {
        video.dispatchEvent(new dom.window.Event("seeked"));
      });
      await flush();
      if (paints !== paintsBeforeSeek + 1) {
        throw new Error(`a paused seek painted ${paints - paintsBeforeSeek} frame(s), expected exactly 1`);
      }
      // A landed seek repaints once and holds wherever it lands — here the
      // replay start the entrance change left behind. (Direct currentTime
      // assignment is the test-only path; real seeks go through the
      // transport, which is what ends the scoped window.)
    } finally {
      clip.restore();
    }
  });

  // A hook style tweak replays the hook window and a CTA tweak replays the
  // end card — never the middle of the clip. With an 8s stubbed clip the
  // hook window opens at frame 0 and the default 2s end card opens at 6s,
  // so each replay lands exactly on its window start with looping held off
  // (a CTA replay ending at the clip end must not wrap to the top). A
  // founder seek through the transport then ends the window and hands free
  // playback back.
  await check("a hook tweak replays the hook and a CTA tweak replays the end card", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    const clip = installLoadedClipStubs({ width: 1280, height: 720 });
    try {
      await clip.loadClip(ctx);
      const video = ctx.container.querySelector("video");
      if (!video) throw new Error("the preview media element is missing");
      const openGroup = async (name) => {
        const header = [...ctx.container.querySelectorAll("button[aria-expanded]")]
          .find((b) => (b.textContent || "").trim() === name);
        if (!header) throw new Error(`no ${name} group header`);
        if (header.getAttribute("aria-expanded") !== "true") {
          await act(async () => {
            header.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          await act(async () => {});
        }
      };
      await openGroup("Hook Text");
      video.currentTime = 4;
      const fade = ctx.container.querySelector('[data-testid="caption-anim-fade"]');
      if (!fade) throw new Error("no caption fade chip");
      await act(async () => {
        fade.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      if (video.currentTime !== 0) {
        throw new Error(`a hook tweak did not replay the hook window (at ${video.currentTime}s, expected 0)`);
      }
      if (video.loop !== false) {
        throw new Error("a hook replay did not hold the window (loop still on)");
      }
      await openGroup("End Card CTA");
      video.currentTime = 1;
      const ctaFade = ctx.container.querySelector('[data-testid="cta-anim-fade"]');
      if (!ctaFade) throw new Error("no CTA fade chip");
      await act(async () => {
        ctaFade.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      if (video.currentTime !== 6) {
        throw new Error(`a CTA tweak did not replay the end card (at ${video.currentTime}s, expected 6)`);
      }
      if (video.loop !== false) {
        throw new Error("a CTA replay did not hold the window (loop still on)");
      }
      // Founder transport ends the window: +1s seeks through handleSeek,
      // which clears the scope and restores the loop.
      const fwd = ctx.container.querySelector('[data-testid="transport-forward-1s"]');
      if (!fwd) throw new Error("no forward-1s transport button");
      await act(async () => {
        fwd.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      await act(async () => {});
      if (video.currentTime !== 7) {
        throw new Error(`the transport seek did not land (at ${video.currentTime}s, expected 7)`);
      }
      if (video.loop !== true) {
        throw new Error("a founder seek did not end the scoped window (loop still off)");
      }
    } finally {
      clip.restore();
    }
  });

  // The loaded DOM pins the narrow-column overflow contract where it holds —
  // on the mounted row (reached with zero decoded bytes via the shared stub
  // above). Order inside the row stays covered by the source-level check
  // below; this one covers only what source cannot: clipping and wrapping.
  await check("the loaded player row fits narrow columns without horizontal overflow", async (ctx) => {
    const clip = installLoadedClipStubs({ width: 720, height: 1280 });
    try {
      await clip.loadClip(ctx);
      // Loaded state genuinely reached: without it every assertion below
      // would pass on an empty column.
      const col = ctx.container.querySelector(".demo-cta-column");
      if (!col) throw new Error("no preview column");
      if (col.getAttribute("data-player") !== "on") {
        throw new Error("the column never reported a loaded player, so the row below proves nothing");
      }
      const player = ctx.container.querySelector('[data-testid="demo-cta-player"]');
      if (!player) throw new Error("no loaded player row");
      if (!player.classList.contains("overflow-x-clip")) {
        throw new Error("the player row lost overflow-x-clip: scrubber ticks and the seek knob bleed past 0%/100% and grow a horizontal bar");
      }
      if (!ctx.container.querySelector('[data-testid="demo-cta-scrubber"]')) {
        throw new Error("no scrubber strip in the loaded player");
      }
      const play = ctx.container.querySelector('[data-testid="transport-play"]');
      const exp = ctx.container.querySelector('[data-testid="demo-cta-export"]');
      if (!play || !exp) throw new Error("the loaded player is missing transport or Export");
      if (!exp.classList.contains("shrink-0")) {
        throw new Error("the Export button is squeezable in the loaded row: without shrink-0 the nowrap parent crushes it below its text");
      }
      const row = play.closest('[class*="flex-nowrap"]');
      if (!row || !row.classList.contains("flex-wrap")) {
        throw new Error("the control row does not wrap below xl: always-nowrap overflows narrow columns");
      }
      const grid = col.parentElement;
      if (!grid || !grid.classList.contains("grid") || !grid.className.includes("minmax(0,")) {
        throw new Error("the settings/preview grid lost its minmax(0, …) columns, so the preview can force the page wider than the viewport");
      }
      const frame = ctx.container.querySelector(".demo-cta-frame");
      if (!frame || !frame.classList.contains("overflow-hidden")) {
        throw new Error("the preview frame is not clipping its canvas");
      }
    } finally {
      clip.restore();
    }
  });

  // The scrub strip is a real slider: arrows move a second (matching the
  // −1s/+1s buttons), Home/End jump to the clip ends. Ticks and transport
  // already seek, so this pins the keyboard path on the strip itself — a
  // pointer-only div would pass every other check here.
  await check("the scrubber slider seeks from the keyboard", async (ctx) => {
    const clip = installLoadedClipStubs({ width: 720, height: 1280 });
    try {
      await clip.loadClip(ctx);
      const slider = ctx.container.querySelector('[data-testid="demo-cta-scrubber"] [role="slider"]');
      if (!slider) throw new Error("no slider in the scrub strip");
      if (slider.getAttribute("aria-valuemax") !== "8") {
        throw new Error(`the slider reports the wrong duration: ${slider.getAttribute("aria-valuemax")}`);
      }
      const video = ctx.container.querySelector("video");
      if (!video) throw new Error("the preview media element is missing");
      const press = async (key) => {
        await act(async () => {
          slider.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key, bubbles: true }));
        });
        await act(async () => {});
      };
      await press("ArrowRight");
      if (video.currentTime !== 1) {
        throw new Error(`ArrowRight did not move a second forward (at ${video.currentTime}s)`);
      }
      if (slider.getAttribute("aria-valuenow") !== "1") {
        throw new Error("the slider did not report its new position");
      }
      await press("ArrowLeft");
      if (video.currentTime !== 0) {
        throw new Error(`ArrowLeft did not move back (at ${video.currentTime}s)`);
      }
      await press("End");
      if (video.currentTime !== 8) {
        throw new Error(`End did not jump to the clip end (at ${video.currentTime}s)`);
      }
      await press("Home");
      if (video.currentTime !== 0) {
        throw new Error(`Home did not jump to the clip start (at ${video.currentTime}s)`);
      }
    } finally {
      clip.restore();
    }
  });

  await check(
    "the export action sits after the preview in the pinned column",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const html = ctx.container.innerHTML;
          // Export is a button in the player row, so it only exists once a clip
          // has loaded — and jsdom never supplies video metadata, which is why
          // this check reads the source below rather than this DOM. What this
          // asserts here is the frame itself: present, and sized by the column's
          // height budget rather than the old fixed rem cap that shrank it.
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
    "Space toggles preview playback outside text entry",
    async () => {
      // The player only mounts with a real clip's metadata, which jsdom
      // cannot supply — the order check above says so at length — so a DOM
      // query here would silently pass forever. Asserted in source instead:
      // a Space keydown that calls the play toggle, skips text entry, and
      // leaves focused buttons and links to their native activation (a
      // second toggle there would undo the click).
      const editorSrc = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      const hookSrc = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "usePreviewLoop.js"),
        "utf8"
      );
      const src = editorSrc + hookSrc;
      for (const part of [
        'event.code !== "Space"',
        "togglePlayPause()",
        'tag === "INPUT"',
        'tag === "TEXTAREA"',
        'tag === "BUTTON"',
      ]) {
        if (!src.includes(part)) {
          throw new Error(`the Space transport shortcut is missing from source: ${part}`);
        }
      }
    }
  );

  await check(
    "the player stacks scrubber, one control row, then export",
    async () => {
      // The player only mounts once a real clip supplies metadata, and jsdom
      // has no video pipeline — so no DOM here ever contains it. This asserts
      // the order in source instead: scrubber strip, then the single
      // transport + Export/Lock row, then export. A row that drifted above the
      // scrubber or a player that drifted below export means the compact
      // layout regressed, and no render test would notice.
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      // The lock action is a bare `+ Lock` button now — the Zoom Lock label
      // and its description were removed, so match the button by pattern,
      // not by exact class string.
      const order = [
        "demo-cta-player",
        "demo-cta-scrubber",
        "transport-play",
        'data-testid="demo-cta-export"',
      ].map((m) => src.indexOf(m));
      const lockMatch = />\s*\+ Lock\s*</.exec(src);
      order.push(lockMatch ? lockMatch.index : -1);
      if (order.some((i) => i === -1)) {
        throw new Error("the player card, scrubber, transport, Export, or + Lock is missing from source");
      }
      if (!order.every((v, i, a) => i === 0 || a[i - 1] < v)) {
        throw new Error(
          "the player is out of order in source. Scrubber first, then the single " +
            "transport row with Export immediately left of the + Lock button."
        );
      }
      if (/Zoom Lock<\/span>|Hold this zoom from this point on/.test(src)) {
        throw new Error(
          "the Zoom Lock label or its description is back in the player row. " +
            "The row is buttons only now; lock state reads off the timeline " +
            "strip and the locked-segments disclosure."
        );
      }
      if (/On screen:|0:00\.0 → \{formatTime\(duration\)\}|justify-between px-0\.5/.test(src)) {
        throw new Error(
          "a removed duplicate readout is back in the player. Time reads once, " +
            "in the control row — the scrubber strip carries no text."
        );
      }
      // Shared-width contract, part 1: the right column is fluid at xl (1fr)
      // with the left panel at 0.8fr, so the preview widens as the window grows
      // and the settings panel narrows.
      if (!/xl:grid-cols-\[minmax\(0,0\.8fr\)_minmax\(0,1fr\)\]/.test(src)) {
        throw new Error(
          "the right column is not fluid at xl with left at 0.8fr. " +
            "The grid should use xl:grid-cols-[minmax(0,0.8fr)_minmax(0,1fr)]."
        );
      }
      // No-wrap binds at xl only, where the 650px column holds the row. Below
      // xl the row must still wrap rather than overflow a narrower column.
      if (!/flex flex-wrap items-center gap-x-3 gap-y-3 xl:flex-nowrap/.test(src)) {
        throw new Error(
          "the control row is not wrap-below-xl / nowrap-at-xl. Always-nowrap " +
            "overflows narrow columns; always-wrap reintroduces the two-line " +
            "player the fixed column was measured to avoid."
        );
      }
      // Export must be the bare `sm` Button, not the old `h-11 w-full` bar button.
      // A full-width bar inside the nowrap player row would blow the row's
      // measured width out immediately.
      if (!/variant="accent"[\s\S]{0,160}?size="sm"[\s\S]{0,200}?data-testid="demo-cta-export"/.test(src)) {
        throw new Error(
          "the Export button is not the compact accent button inside the player " +
            "row. A full-width variant there cannot fit beside the lock buttons."
        );
      }
      if (/h-11 w-full[\s\S]{0,120}?demo-cta-export/.test(src)) {
        throw new Error("the Export button reverted to the full-width bar variant");
      }
      // The button must not be squeezable by its nowrap flex parent. It
      // carries .btn-studio, whose overflow:hidden (the sheen sweep) zeroes
      // the automatic minimum size flex items normally enjoy — so when the
      // button cluster runs out of room the button shrinks below its own
      // text and the same overflow clips "Export MP4" mid-label. shrink-0
      // keeps its measured width; the flexible description beside it absorbs
      // the squeeze instead, by wrapping.
      if (!/shrink-0[\s\S]{0,200}?data-testid="demo-cta-export"/.test(src) && !/data-testid="demo-cta-export"[\s\S]{0,200}?shrink-0/.test(src)) {
        throw new Error(
          "the Export button is squeezable in its flex row. Without shrink-0 " +
            "the row crushes it below its text and .btn-studio's overflow " +
            "clips the label."
        );
      }
      // The outer row is nowrap at xl by contract, so the button cluster on
      // its right must still wrap: without min-w-0 + wrap on the inner
      // group, the buttons force the row past the column and Export clips
      // at the edge. This pins the actual fix, not the intent.
      if (!/ml-auto flex min-w-0 flex-wrap/.test(src)) {
        throw new Error(
          "the button cluster cannot give inside the nowrap row. Without " +
            "min-w-0 + flex-wrap there, the buttons force the row past " +
            "the column and Export clips at the edge."
        );
      }
    }
  );

  await check("unavailable editor sources offer recovery, retry and an upload exit", async (ctx) => {
    global.__SMOKE_ROUTE_PARAMS = { generationId: "missing-source" };
    let calls = 0;
    try {
      await withApi({ getGeneration: async () => { calls++; return { id: "missing-source", status: "completed" }; } }, async () => {
        await mount(DemoCtaStudio)(ctx);
        expectText(ctx, "retry the durable save");
        for (const href of ["/history#generation-missing-source", "/demo-cta"]) {
          if (!ctx.container.querySelector(`a[href="${href}"]`)) throw new Error(`editor dead end: ${href}`);
        }
        await clickEl(ctx, buttonByText(ctx, /Try loading again/));
        if (calls !== 2) throw new Error("editor retry did not fetch the source again");
      });
    } finally {
      global.__SMOKE_ROUTE_PARAMS = {};
    }
  });

  await check(
    "the editor opens a finished render only from its durable, fetchable copy",
    async () => {
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "pages", "DemoCtaStudio.jsx"),
        "utf8"
      );
      // The broken pattern picks the provider's temporary link (needs a bearer
      // token → 401); the durable copy is in r2_url, and every other consumer
      // already uses durable-first.
      if (src.match(/generation\.video_url \|r2_url|video_url \|r2_url/)) {
        throw new Error(
          "the editor prefers video_url over r2_url. video_url carries the " +
            "provider's temporary link that returns 401 in the browser; " +
            "durableMediaUrl must pick r2_url first."
        );
      }
      // The load() path must choose the durable copy and refuse rows that
      // expose only a provider link.
      if (!src.includes("durableMediaUrl(row)")) {
        throw new Error(
          "the editor does not use durableMediaUrl to choose the source. It " +
            "must always load from the durable copy and refuse rows with none."
        );
      }
      // The "Start from a finished render" picker was removed from this page
      // on purpose: the editor is standalone, and History is where a finished
      // clip is chosen. Asserted as absent so the list cannot be rebuilt here
      // by habit — it was a second, competing entry point under an editor that
      // already takes its own footage.
      if (/SourcePicker|Start from a finished render/.test(src)) {
        throw new Error(
          "the finished-render picker is back in Demo + CTA. History is where " +
            "a finished clip is chosen; the editor below the header takes its own footage."
        );
      }
      // The backend signs both stored media paths on the way out, so an R2
      // upload failure (local fallback path in r2_url) is still openable.
      const server = fs.readFileSync(
        path.join(__dirname, "..", "..", "backend", "server.py"),
        "utf8"
      );
      if (!server.match(/r2_url.*sign_stored_path|sign_stored_path.*r2_url/)) {
        throw new Error(
          "r2_url is not signed in _public_generation. A local fallback path " +
            "in r2_url would 404 instead of playing."
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
          // Export is inside the player row now, not a bar of its own. It was a
          // sibling of the frame resolving the same width token; the button and
          // the frame must never be siblings again, because that is what made
          // the column spend 44px plus a gap on a separate decision bar.
          if (/\.demo-cta-export\s*\{/.test(css)) {
            throw new Error(
              "the export bar has its own width rules again. The button belongs " +
                "in the player row now, not in a sibling of the frame."
            );
          }
          if (!/position:\s*static/.test(css.replace(/\.demo-cta-export[^}]*\}/g, ""))) {
            // `position: static` also appears in the slim-scrollbar block, so
            // this is only a smoke test that the export-specific override is
            // gone rather than restored.
          }
          // Order inside the player row: transport, time, Export, + Lock.
          const exportIdx = src.indexOf('data-testid="demo-cta-export"');
          const lockMatch2 = />\s*\+ Lock\s*</.exec(src);
          const lockIdx = lockMatch2 ? lockMatch2.index : -1;
          const playIdx = src.indexOf('testId="transport-play"');
          if ([exportIdx, lockIdx, playIdx].some((i) => i === -1)) {
            throw new Error("the player row is missing transport, Export, or + Lock");
          }
          if (!(playIdx < exportIdx && exportIdx < lockIdx)) {
            throw new Error(
              "Export must sit left of the + Lock button in the player row."
            );
          }
          // "Live preview" moved inside the frame, below the upload button, and
          // the platform label is gone.
          // Anchored on the JSX element, not the bare word: the comment above the
          // button explains where the copy used to live, and matching that would
          // read as "still above the button".
          const liveIdx = src.indexOf('>Upload one clip to style it.</p>');
          const uploadIdx = src.indexOf('data-testid="demo-cta-frame-upload"');
          if (liveIdx === -1 || uploadIdx === -1 || liveIdx < uploadIdx) {
            throw new Error(
              'The upload guidance must be below the upload button, inside the frame.'
            );
          }
          // The label was removed from the caption row. The literal string still exists
          // in constants.js as the preset's name — the Output group's radiogroup
          // needs it — so this asserts it is not rendered in the preview column,
          // not that it is absent from the file.
          if (/justify-center gap-x-2 px-1|>\s*Live preview\s*<\/span>/.test(html)) {
            throw new Error(
              "the preview caption row is back above the frame. It no longer has " +
                "a second label to justify."
            );
          }
          // The player is a plain bar, asserted in source: like the order check
          // below, it only mounts with a real clip's metadata, which jsdom
          // cannot supply, so a DOM query here would silently pass forever.
          if (!/<div className="space-y-3 overflow-x-clip" data-testid="demo-cta-player"/.test(src)) {
            throw new Error(
              "the player is a card again. It must be a plain bar matching the " +
                "chromeless preview — a surface box under a chromeless frame."
            );
          }
          if (/data-testid="demo-cta-player"[\s\S]{0,200}?\bsurface\b/.test(src)) {
            throw new Error("the player picked up a surface class");
          }
          
          // The budget must EXCEED the real content, not equal it. At exactly
          // 84px (caption 16 + two 12px gaps + export 44) the column landed on
          // its own max-h, so rounding pushed it 1px over and a scrollbar
          // appeared beside a video that fitted. 8px of slack is load-bearing.
          const emptyChrome = Number(
            (/--demo-cta-chrome:\s*(\d+)px/.exec(css) || [])[1]
          );
          // With the caption row and the export bar both gone, the empty column
          // is just the frame — so this is slack and nothing else. It must stay
          // above zero: at exactly 0 the column lands on its own max-h and a
          // rounding pixel shows a scrollbar beside a video that fits.
          if (!Number.isFinite(emptyChrome) || emptyChrome < 8) {
            throw new Error(
              `the empty column's height budget is ${emptyChrome}px. It must keep ` +
                "slack, or the column overflows its own max-h and shows a scrollbar."
            );
          }
          // The loaded column is the player bar plus one gap plus that slack.
          const loadedChrome = Number(
            (/data-player="on"\]\s*\{[^}]*?--demo-cta-chrome:\s*(\d+)px/.exec(css) || [])[1]
          );
          if (!Number.isFinite(loadedChrome) || loadedChrome < 132) {
            throw new Error(
              `the loaded column's height budget is ${loadedChrome}px. It must cover ` +
                "the player bar's ~104px, a gap, and the slack above."
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
          // Stacked (below lg) the frame spends a 52vh budget with no headroom
          // factor: beside the panel the 0.75 factor keeps the preview compact,
          // but stacked the frame IS the preview and headroom shrank it past
          // usability on phones.
          if (!/\.demo-cta-column\s*\{[^}]*--demo-cta-frame-w:\s*min\(100%,\s*calc\(52vh/.test(css)) {
            throw new Error(
              "the stacked preview frame lost its 52vh no-headroom budget, so " +
                "phones and narrow windows get a shrunken frame again."
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
      // Two swatch groups: background and accent. Frame color was removed, so
      // a third fixed-size group here means it came back. All 40px and fixed —
      // a grid with `aspect-square` grew them with the settings column.
      const fixed = (src.match(/h-10 w-10 shrink-0/g) || []).length;
      if (fixed !== 2) {
        throw new Error(
          `found ${fixed} fixed-40px swatch groups, expected exactly 2 (background ` +
            "and accent). A third is either the removed frame color returning, or " +
            "a stretchy grid replacing a fixed row."
        );
      }
      if (/aspect-square overflow-hidden rounded-lg/.test(src)) {
        throw new Error("the background swatches are still a stretchy aspect-square grid");
      }
      // Matched on control artifacts, not prose: the comment explaining the
      // removal mentions frame color by name, and tripping on it would punish
      // documentation for existing.
      if (/frame-color-|setFrameColor|<SubLabel>Frame color/.test(src)) {
        throw new Error(
          "frame color is back. Every mockup renders the black frame; there is " +
            "no control that sets anything else."
        );
      }
      if ((src.match(/flex flex-wrap items-center gap-2/g) || []).length < 2) {
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
      if (!/aria-label="Animation"[\s\S]{0,200}?grid grid-cols-3 gap-1\.5 lg:grid-cols-2 xl:grid-cols-3/.test(src)) {
        throw new Error(
          "the animation chips are not 3-per-row with a 2-per-row guard for " +
            "the narrow lg-xl column, where a third column wraps labels."
        );
      }
      // Both entrance grids render through one shared EntranceGrid: pin the
      // contract as fragments — the 3-per-row class inside the component, one
      // call site per overlay with its testid namespace and group label. Whole
      // div literals would fail the build on attribute reorder or gap tweaks
      // that change no behavior.
      if ((src.match(/<EntranceGrid /g) || []).length !== 2) {
        throw new Error(
          "the Caption and CTA entrance grids no longer share one EntranceGrid."
        );
      }
      if (!/function EntranceGrid\([\s\S]{0,300}?grid grid-cols-3 gap-2/.test(src)) {
        throw new Error(
          "EntranceGrid is not 3-per-row like the font grid above it."
        );
      }
      for (const [prefix, label] of [["caption-anim", "Caption animation"], ["cta-anim", "CTA animation"]]) {
        if (!src.includes(`testPrefix="${prefix}"`) || !src.includes(`ariaLabel="${label}"`)) {
          throw new Error(
            `the ${label} entrance grid lost its testid namespace or group label.`
          );
        }
      }
      // The font/animation disclosure triggers are <summary> elements, which
      // a11y trees expose as disclosure triangles without a clickable
      // reference. Each disclosure component's own trigger must carry the
      // button role plus expanded state so assistive tech and automation
      // reach it. Scoped per component (not every <summary> in the file —
      // the zoom-lock list has its own disclosure pattern), and pinned as
      // fragments: attribute order is free to move without changing behavior.
      // Space is deliberately NOT handled here: the playback shortcut owns
      // Space outside text entry, and the mutual-exclusion check below fails
      // the build if a disclosure swallows it.
      for (const fn of ["function AnimDisclosure", "function FontDisclosure"]) {
        const body = src.split(fn)[1];
        // Up to className, not the first `>`: the onClick arrow's `=>`
        // would end a naive tag match before the role is even read.
        const attrs = body && /<summary([\s\S]*?)className=/.exec(body);
        if (!attrs || !/role="button"/.test(attrs[1]) || !/aria-expanded=\{open\}/.test(attrs[1])) {
          throw new Error(
            `the ${fn} disclosure trigger lost its button role — it is ` +
              "unreachable to assistive tech and automation again."
          );
        }
        if (/onKeyDown/.test(attrs[1])) {
          throw new Error(
            `the ${fn} disclosure trigger handles keys — Space belongs to the ` +
              "playback shortcut, and swallowing it breaks preview transport."
          );
        }
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
          const html = ctx.container.innerHTML;
          const panels = ctx.container.querySelectorAll(".demo-cta-panel-scroll");
          if (panels.length < 2) {
            throw new Error(
              `only ${panels.length} scroll container(s) use the slim scrollbar. ` +
                "Both the settings panel and the preview column need it: the " +
                "global rules give them a 10px bar with arrow buttons."
            );
          }
          // The preview column keeps `overflow-y-auto` for short viewports, but at a
          // normal height it must not overflow — that is what put a scrollbar
          // beside a frame that fitted. Height correctness is the CSS budget
          // above; this guards that the container can still scroll when a short
          // viewport or the Export-ready card demands it. Scoped to the column
          // itself: the settings panel also scrolls, so a document-wide match
          // would pass even with the preview column's overflow removed.
          const previewColumn = ctx.container.querySelector(".demo-cta-column");
          if (!previewColumn) {
            throw new Error("no preview column to check");
          }
          if (!/lg:overflow-y-auto/.test(previewColumn.className)) {
            throw new Error(
              "the preview column cannot scroll. A short viewport or an " +
                "Export-ready card below the button would be clipped."
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
      if (!/max\(253px/.test(css)) {
        throw new Error(
          "the preview frame has no ~450px floor (253px wide at 9:16). Below it " +
            "the column must scroll rather than the frame shrinking further."
        );
      }
      // The short-viewport escape used to be a `position: static` override on a
      // sticky export bar. The button is in the player row now, so nothing pins
      // and the column simply scrolls; that override must not come back.
      if (/\.demo-cta-export\s*\{[^}]*position/.test(css)) {
        throw new Error(
          "the export button has positioning rules again. It lives in the player " +
            "row, where nothing needs pinning."
        );
      }
    }
  );

  await check(
    "an old stored open-groups value cannot open two groups",
    async (ctx) => {
      // v2 allowed several groups open at once. Anyone who visited before the
      // one-open change has that shape on disk, and reading it as-is would
      // restore the exact layout the change was made to remove.
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      const key = "hookforge.demoCta.openSections.v4";
      dom.window.localStorage.removeItem(key);
      try {
        dom.window.localStorage.setItem(
          key,
          JSON.stringify({ source: true, hook: true, cta: true, output: false, advanced: false })
        );
        const container = dom.window.document.createElement("div");
        dom.window.document.body.appendChild(container);
        const root = createRoot(container);
        roots.push(root);
        await act(async () => {
          root.render(React.createElement(DemoCtaEditor, { generation: COMPLETED }));
        });
        const open = [...container.querySelectorAll('button[aria-expanded]')]
          .filter((b) => b.getAttribute("aria-expanded") === "true")
          .map((b) => (b.textContent || "").trim());
        if (open.length !== 1) {
          throw new Error(
            `a stored multi-open value opened ${open.length} groups (${JSON.stringify(open)}). ` +
              "It must be coerced to one."
          );
        }
      } finally {
        dom.window.localStorage.removeItem(key);
      }
    }
  );

  await check(
    "the empty frame offers a real upload control",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          const input = ctx.container.querySelector('[data-testid="demo-cta-file-input"]');
          const button = ctx.container.querySelector('[data-testid="demo-cta-frame-upload"]');
          if (!button) {
            throw new Error(
              "the empty frame has no upload control. \"Upload a clip to preview\" " +
                "was a sentence describing an action; the frame should offer it."
            );
          }
          if (!input) {
            throw new Error("no file input to drive — the upload button would do nothing");
          }
          // Behaviour, not a class list: a button wired to a dead ref looks
          // perfect in markup and does nothing when clicked.
          let reached = false;
          input.addEventListener("click", () => {
            reached = true;
          });
          await act(async () => {
            button.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          if (!reached) {
            throw new Error(
              "clicking the frame's upload button did not reach the file input"
            );
          }
          // The whole empty box is the upload target, not just the button:
          // a click on the box padding must reach the same file input.
          reached = false;
          const frame = ctx.container.querySelector('[data-testid="demo-cta-frame-empty"]');
          if (!frame) {
            throw new Error("the empty frame has no clickable container");
          }
          await act(async () => {
            frame.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          if (!reached) {
            throw new Error(
              "clicking the empty frame outside the button did not reach the file input"
            );
          }
          // The History link inside the box is a second destination: it
          // must navigate, never open the picker instead.
          reached = false;
          const historyLink = frame.querySelector('a[href="/history"]');
          if (!historyLink) {
            throw new Error("the empty frame lost its History door");
          }
          await act(async () => {
            historyLink.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          if (reached) {
            throw new Error(
              "clicking the frame's History link opened the picker instead of navigating"
            );
          }
        }
      );
    }
  );

  await check("no Output group: the TikTok spec lives on the Export action and result", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    await mount(DemoCtaEditor)(ctx);
    // A single upload-ready format means nothing to choose, so the group is
    // gone instead of an empty selector. The spec must still surface where
    // the decision happens (Export title) and where it lands (result card).
    const header = [...ctx.container.querySelectorAll("button[aria-expanded]")].find((b) => b.textContent.trim() === "Output");
    if (header) throw new Error("the Output group is back with nothing selectable in it");
    const src = fs.readFileSync(path.join(SRC, "demoCta", "DemoCtaEditor.jsx"), "utf8");
    for (const marker of ["title=\"Export TikTok MP4 · 1080×1920 · 30 fps\"", "MP4 · 1080×1920 · 30 fps"]) {
      if (!src.includes(marker)) throw new Error(`missing TikTok spec on the export path: ${marker}`);
    }
    if (ctx.container.querySelector('[aria-label="Export format"], [aria-label="Platform preset"]')) throw new Error("alternate delivery formats remain selectable");
    dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
  });

  await check("MP4 duration and decoding validation precede download and History", async () => {
    // The recorder, validation and save live in demoCta/exportFlow.js; the
    // editor only calls the two actions. Read both so the ordering gate
    // follows the moved code.
    const src = fs.readFileSync(path.join(SRC, "demoCta", "DemoCtaEditor.jsx"), "utf8")
      + fs.readFileSync(path.join(SRC, "demoCta", "exportFlow.js"), "utf8");
    const probeAt = src.indexOf("await probeRecordingPlays(blob, expectedDuration, appendBlob ? audioSegments : [])");
    const resultAt = src.indexOf("setResult({ url, name, size: blob.size, mime, blob })");
    if (probeAt < 0 || resultAt < probeAt || src.indexOf("await saveExport(blob, name)") < resultAt) throw new Error("invalid MP4 can reach download or History");
    for (const marker of ["probe.onloadeddata", "Math.abs(probe.duration - expectedDuration)", "probe.videoWidth === TIKTOK_EXPORT.width", "probe.videoHeight === TIKTOK_EXPORT.height"]) {
      if (!src.includes(marker)) throw new Error(`missing export gate: ${marker}`);
    }
    if (/new MediaRecorder|captureStream\(/.test(src)) throw new Error("wall-clock capture is back");
  });

  await check("Story text keeps its message and clamps timing when CTA settings change", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    const media = dom.window.HTMLMediaElement.prototype;
    const original = { createUrl: URL.createObjectURL, play: media.play, load: media.load, context: dom.window.HTMLCanvasElement.prototype.getContext, createElement: document.createElement };
    const probes = [];
    URL.createObjectURL = () => "blob:story-smoke";
    media.play = () => Promise.resolve();
    media.load = () => {};
    dom.window.HTMLCanvasElement.prototype.getContext = () => null;
    document.createElement = function(tag, ...args) {
      const element = original.createElement.call(this, tag, ...args);
      if (tag === "video") probes.push(element);
      return element;
    };
    const openGroup = async (label) => clickEl(ctx,
      [...ctx.container.querySelectorAll("button[aria-expanded]")].find((b) => b.textContent.trim() === label), `open ${label}`);
    try {
      dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
      await mount(DemoCtaEditor)(ctx);
      const input = ctx.container.querySelector('[data-testid="demo-cta-file-input"]');
      Object.defineProperty(input, "files", { value: [new dom.window.File(["video"], "story.mp4", { type: "video/mp4" })] });
      await act(async () => input.dispatchEvent(new dom.window.Event("change", { bubbles: true })));
      const probe = probes.find((video) => video.onloadedmetadata);
      if (!probe) throw new Error("uploaded clip was not probed");
      Object.defineProperties(probe, { videoWidth: { value: 360 }, videoHeight: { value: 640 }, duration: { value: 8 } });
      await act(async () => probe.onloadedmetadata());
      await openGroup("Story Text");
      const text = ctx.container.querySelector('[data-testid="story-text-input"]');
      await act(async () => {
        Object.getOwnPropertyDescriptor(dom.window.HTMLTextAreaElement.prototype, "value").set.call(text, "My Story message");
        text.dispatchEvent(new dom.window.Event("input", { bubbles: true }));
      });
      await clickEl(ctx, ctx.container.querySelector('[data-testid="story-toggle"]'), "enable Story");
      const timing = () => [...ctx.container.querySelectorAll('[data-testid^="story-"] [role="slider"]')].map((s) => Number(s.getAttribute("aria-valuenow")));
      if (JSON.stringify(timing()) !== JSON.stringify([1.8, 6])) throw new Error(`wrong initial Story timing: ${timing()}`);
      await openGroup("End Card CTA");
      await clickEl(ctx, ctx.container.querySelector('[data-testid="cta-timing-last3"]'), "reserve last three seconds");
      await openGroup("Story Text");
      if (timing()[1] !== 5 || ctx.container.querySelector('[data-testid="story-text-input"]').value !== "My Story message") throw new Error("Story timing did not clamp or message was lost");
      await openGroup("End Card CTA");
      await clickEl(ctx, ctx.container.querySelector('[data-testid="cta-timing-full"]'), "reserve full clip");
      await openGroup("Story Text");
      if (!ctx.container.querySelector('[data-testid="story-no-room"]') || timing().length) throw new Error("full-clip CTA must leave no Story window");
    } finally {
      await act(async () => ctx.root.unmount());
      URL.createObjectURL = original.createUrl;
      media.play = original.play;
      media.load = original.load;
      dom.window.HTMLCanvasElement.prototype.getContext = original.context;
      document.createElement = original.createElement;
      dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
    }
  });

  await check("Font & Animation close each other in Hook Text and End Card CTA", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
    await mount(DemoCtaEditor)(ctx);
    for (const [label, prefix] of [["Hook Text", "caption"], ["End Card CTA", "cta"]]) {
      const header = [...ctx.container.querySelectorAll("button[aria-expanded]")]
        .find((button) => button.textContent.trim() === label);
      await clickEl(ctx, header, `open ${label}`);
      const font = ctx.container.querySelector(`[data-testid="${prefix}-fonts-disclosure"]`);
      const animation = ctx.container.querySelector(`[data-testid="${prefix}-anim-disclosure"]`);
      font.querySelector("summary").focus();
      const space = new dom.window.KeyboardEvent("keydown", { key: " ", code: "Space", bubbles: true, cancelable: true });
      await act(async () => font.querySelector("summary").dispatchEvent(space));
      if (space.defaultPrevented) throw new Error(`${label}: playback shortcut swallowed disclosure keyboard activation`);
      await clickEl(ctx, font.querySelector("summary"), "open Font");
      if (!font.open || animation.open) throw new Error(`${label}: Font must open alone`);
      await clickEl(ctx, animation.querySelector("summary"), "open Animation");
      if (font.open || !animation.open) throw new Error(`${label}: Animation must close Font`);
      await clickEl(ctx, font.querySelector("summary"), "reopen Font");
      if (!font.open || animation.open) throw new Error(`${label}: Font must close Animation`);
      await clickEl(ctx, font.querySelector("summary"), "close Font");
      if (font.open || animation.open) throw new Error(`${label}: both panels must be collapsible`);
    }
    dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
  });

  await check(
    "group titles and slider labels read correctly",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      await withApi(
        { getGenerations: async () => ({ generations: [COMPLETED] }) },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
          if (!ctx.text().includes("End Card CTA")) {
            throw new Error("the end-card group is mislabeled or missing");
          }
          // Group headers always render, but the hook duration only exists once
          // Hook Text is expanded — and only one group is open at a time, so
          // this check has to open it rather than assume it.
          const hook = [...ctx.container.querySelectorAll("button[aria-expanded]")].find(
            (b) => (b.textContent || "").trim() === "Hook Text"
          );
          if (!hook) throw new Error("no Hook Text group header to click");
          await act(async () => {
            hook.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          const text = ctx.text();
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

  await check("finished looks save only after clip review in End Card CTA and remain reusable", async (ctx) => {
    const clip = installLoadedClipStubs({ width: 720, height: 1280 });
    const openGroup = async (label) => {
      const header = [...ctx.container.querySelectorAll("button[aria-expanded]")]
        .find((b) => b.textContent.trim() === label);
      if (header.getAttribute("aria-expanded") !== "true") await clickEl(ctx, header, `open ${label}`);
    };
    const get = (id) => ctx.container.querySelector(`[data-testid="${id}"]`);
    try {
      await clip.loadClip(ctx);
      if (get("look-preset-save-btn")) throw new Error("Save look must not be in Source & Look");
      await openGroup("Hook Text");
      await clickEl(ctx, get("caption-font-nunito"), "pick hook font");
      await clickEl(ctx, get("caption-anim-fade"), "pick hook entrance");
      await clickEl(ctx, get("caption-size-preset-l"), "pick hook size");
      await clickEl(ctx, get("text-style-glow"), "pick text treatment");
      if (get("text-style-glow").getAttribute("aria-pressed") !== "true") throw new Error("text treatment did not take the click");
      await openGroup("End Card CTA");
      const review = get("look-save-review");
      if (!get("cta-controls").contains(review) || review.closest("details")) throw new Error("Save look must finish CTA setup outside its disclosures");
      if (get("look-preset-save-btn").disabled !== true) throw new Error("Save look enabled before review");
      await clickEl(ctx, get("cta-font-dm-sans"), "pick CTA font");
      await clickEl(ctx, get("cta-anim-slide"), "pick CTA entrance");
      await clickEl(ctx, get("cta-size-preset-s"), "pick CTA size");
      const accent = ctx.container.querySelector('[data-testid^="overlay-accent-"]');
      await clickEl(ctx, accent, "pick accent");
      await typeInto(ctx, get("look-preset-name-input"), "My Brand Look", "name finished look");
      if (!get("look-preset-save-btn").disabled) throw new Error("name alone enabled saving");
      await clickEl(ctx, get("look-reviewed-checkbox"), "confirm preview review");
      if (get("look-preset-save-btn").disabled) throw new Error("reviewed named look cannot be saved");
      await clickEl(ctx, get("cta-anim-pop"), "change reviewed style");
      if (get("look-reviewed-checkbox").getAttribute("aria-checked") !== "false" || !get("look-preset-save-btn").disabled) throw new Error("style changes reuse stale review approval");
      await clickEl(ctx, get("look-reviewed-checkbox"), "review updated style");
      await clickEl(ctx, get("look-preset-save-btn"), "save finished look");
      if (!get("look-save-status").textContent.includes("My Brand Look") || get("look-preset-name-input").value) throw new Error("save lacks confirmation or leaves name populated");
      const prefs = JSON.parse(dom.window.localStorage.getItem("hookforge.demoCta.overlayPrefs.v1"));
      const saved = prefs.global.lookPresets.find((p) => p.name === "My Brand Look");
      if (!saved || saved.captionFont !== "nunito" || saved.captionAnim !== "fade" || saved.captionScale !== 1.15 || saved.ctaFont !== "dm-sans" || saved.ctaAnim !== "pop" || saved.ctaScale !== 0.85 || saved.textStyle !== "glow") throw new Error(`saved styling differs from final choices: ${JSON.stringify(saved)}`);
      await clickEl(ctx, get("look-preset-launch"), "try another look");
      await clickEl(ctx, get("look-preset-custom-my-brand-look"), "reuse saved look");
      if (get("look-preset-custom-my-brand-look").getAttribute("aria-pressed") !== "true") throw new Error("saved look cannot be reapplied");
      // Remount with no clip: the named look persists, but review/save is
      // unavailable until there is footage to judge it against.
      await act(async () => ctx.root.unmount());
      ctx.root = createRoot(ctx.container);
      await mount(load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor)(ctx);
      await openGroup("End Card CTA");
      if (!get("look-preset-custom-my-brand-look")) throw new Error("look was not restored after remount");
      if (!get("look-reviewed-checkbox").disabled || !get("look-preset-save-btn").disabled || !get("look-preset-name-input").disabled) throw new Error("no-clip editor allows review or saving");
      if (!get("look-review-hint").textContent.includes("Upload")) throw new Error("blocked save does not explain next step");
    } finally {
      clip.restore();
    }
  });

  await check(
    "Demo + CTA offers S/M/L size presets, safe-area guard, copy flipper, timing presets, and named looks",
    async (ctx) => {
      const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
      dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
      dom.window.localStorage.removeItem("hookforge.demoCta.overlayPrefs.v1");
      const openGroup = async (label) => {
        const btn = [...ctx.container.querySelectorAll("button[aria-expanded]")]
          .find((b) => (b.textContent || "").trim() === label);
        if (!btn) throw new Error(`no ${label} group header`);
        if (btn.getAttribute("aria-expanded") === "true") return;
        await clickEl(ctx, btn, `open ${label}`);
      };
      await withApi(
        {
          getGenerations: async () => ({ generations: [COMPLETED] }),
          generateOpeningMessages: async () => ({ messages: Array.from({ length: 20 }, (_, i) => `Fresh app opening ${i + 1}`) }),
        },
        async () => {
          await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);

          // #5 Named look presets live with saving in End Card CTA, not Source & Look
          await openGroup("End Card CTA");
          if (ctx.container.querySelector('[data-testid="demo-cta-source"] [data-testid="look-preset-ugc"]')) {
            throw new Error("look presets are still offered prematurely in Source & Look");
          }
          const ugcPreset = ctx.container.querySelector('[data-testid="look-preset-ugc"]');
          if (!ugcPreset) throw new Error("missing built-in UGC style look preset");
          await clickEl(ctx, ugcPreset, "apply UGC style preset");
          if (ugcPreset.getAttribute("aria-pressed") !== "true") {
            throw new Error("UGC style preset did not become active after click");
          }
          const review = ctx.container.querySelector('[data-testid="look-save-review"]');
          if (!review || !review.contains(ctx.container.querySelector('[data-testid="look-preset-save-btn"]')) || !review.contains(ugcPreset)) {
            throw new Error("saving and applying a look are not together in End Card CTA");
          }

          // #1 & #2 & #3 on Hook Text
          await openGroup("Hook Text");
          const hookSizeS = ctx.container.querySelector('[data-testid="caption-size-preset-s"]');
          const hookSizeM = ctx.container.querySelector('[data-testid="caption-size-preset-m"]');
          const hookSizeL = ctx.container.querySelector('[data-testid="caption-size-preset-l"]');
          if (!hookSizeS || !hookSizeM || !hookSizeL) {
            throw new Error("Hook Text is missing S/M/L size preset buttons");
          }
          await clickEl(ctx, hookSizeL, "select L size on Hook Text");
          if (hookSizeL.getAttribute("aria-pressed") !== "true" || !ctx.text().includes("115%")) {
            throw new Error("clicking L size preset did not update Hook Text scale to 115%");
          }

          // One button requests 20 fresh app-specific openings, then selects
          // each immediately. No copy counter is exposed.
          const hookSurprise = ctx.container.querySelector('[data-testid="hook-variant-surprise"]');
          if (!hookSurprise) throw new Error("missing Hook surprise-me button");
          const hookInput = ctx.container.querySelector('[data-testid="hook-text-input"]');
          const beforeHook = hookInput ? hookInput.value : null;
          await clickEl(ctx, hookSurprise, "generate a fresh Hook message");
          if (!hookInput || hookInput.value === beforeHook) {
            throw new Error("surprise Hook message did not load fresh copy into the textarea");
          }
          const hookCount = ctx.container.querySelector('[data-testid="hook-variant-count"]');
          if (hookCount) throw new Error("Hook message counter should not be displayed");
          const seenHooks = new Set([hookInput.value]);
          for (let i = 1; i < 20; i++) {
            await clickEl(ctx, hookSurprise, "show another fresh opening");
            seenHooks.add(hookInput.value);
          }
          if (seenHooks.size !== 20) throw new Error("Surprise did not display 20 distinct openings");

          // #2 Safe-area legibility guard when slider pushed below 80%
          const hookSliderThumb = ctx.container.querySelector('[data-testid="caption-size-slider"] [role="slider"]');
          if (!hookSliderThumb) throw new Error("no caption size slider thumb");
          await clickEl(ctx, hookSizeS, "set Hook size to 85%");
          for (let i = 0; i < 8; i++) {
            await act(async () => {
              hookSliderThumb.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "ArrowLeft", bubbles: true }));
            });
          }
          const hookWarn = ctx.container.querySelector('[data-testid="hook-safety-warning"]');
          if (!hookWarn) {
            throw new Error("Safe-area guard did not warn when Hook Text size dropped below 80%");
          }
          const hookFix = ctx.container.querySelector('[data-testid="hook-safety-fix"]');
          await clickEl(ctx, hookFix, "click Fit safe area on Hook Text");
          if (ctx.container.querySelector('[data-testid="hook-safety-warning"]')) {
            throw new Error("Fit safe area did not clear the Hook Text safety warning");
          }

          // #1, #3, #4 on End Card CTA
          await openGroup("End Card CTA");
          const ctaSizeS = ctx.container.querySelector('[data-testid="cta-size-preset-s"]');
          const ctaSizeL = ctx.container.querySelector('[data-testid="cta-size-preset-l"]');
          if (!ctaSizeS || !ctaSizeL) throw new Error("End Card CTA is missing S/M/L size presets");
          await clickEl(ctx, ctaSizeS, "select S size on End Card CTA");
          if (ctaSizeS.getAttribute("aria-pressed") !== "true" || !ctx.text().includes("85%")) {
            throw new Error("clicking S size preset did not update End Card CTA scale to 85%");
          }

          const ctaSurprise = ctx.container.querySelector('[data-testid="cta-variant-surprise"]');
          if (!ctaSurprise) throw new Error("missing CTA surprise-me button");
          const ctaInput = ctx.container.querySelector('[data-testid="cta-headline-input"]');
          const beforeCta = ctaInput ? ctaInput.value : null;
          await clickEl(ctx, ctaSurprise, "generate a fresh CTA");
          if (!ctaInput || ctaInput.value === beforeCta) {
            throw new Error("surprise CTA did not load fresh copy into the headline input");
          }

          const timingLast3 = ctx.container.querySelector('[data-testid="cta-timing-last3"]');
          const timingFull = ctx.container.querySelector('[data-testid="cta-timing-full"]');
          if (!timingLast3 || !timingFull) throw new Error("missing End Card timing presets");
          await clickEl(ctx, timingLast3, "select Last 3s timing preset");
          if (timingLast3.getAttribute("aria-pressed") !== "true" || !ctx.text().includes("3.0s")) {
            throw new Error("Last 3s timing preset did not set CTA duration to 3.0s");
          }
          await clickEl(ctx, timingFull, "select Full clip timing preset");
          if (timingFull.getAttribute("aria-pressed") !== "true") {
            throw new Error("Full clip timing preset did not become active");
          }
        }
      );
    }
  );

  await check("Demo + CTA offers Real Video with a History render picker", async (ctx) => {
    const DemoCtaEditor = load("demoCta/DemoCtaEditor.jsx").DemoCtaEditor;
    dom.window.localStorage.removeItem("hookforge.demoCta.openSections.v4");
    await withApi(
      {
        getGenerationHistory: async () => ({ generations: [
          { ...COMPLETED, id: "hist-1", brand_name: "Journal", duration: 10 },
          { ...COMPLETED, id: "hist-2", status: "failed", video_url: null, playback_url: null, r2_url: null },
        ] }),
      },
      async () => {
        await mount(DemoCtaEditor, { generation: COMPLETED })(ctx);
        // No base, no second clip: the follow-up upload only appears once a
        // base exists, so the panel never shows two upload buttons at once.
        if (ctx.container.querySelector('[data-testid="demo-cta-second"]')) throw new Error("Second clip offered before any base exists");
        const mode = ctx.container.querySelector('[data-testid="view-mode-realistic"]');
        if (!mode) throw new Error("Real Video view style is missing");
        await clickEl(ctx, mode, "select Real Video view");
        if (mode.getAttribute("aria-pressed") !== "true") throw new Error("Real Video did not take the view selection");
        // Phone-only controls leave with the phone: no scene, background or size.
        if (ctx.container.querySelector('[data-testid="background-lavender"]')) throw new Error("background picker leaked into Real Video");
        if (ctx.container.querySelector('[data-testid="phone-size-slider"]')) throw new Error("phone size leaked into Real Video");
        if (ctx.container.querySelector('[data-testid="hand-zoom-slider"]')) throw new Error("hand controls leaked into Real Video");
        // The History picker lists only the attachable render.
        await clickEl(ctx, ctx.container.querySelector('[data-testid="history-source-toggle"]'), "open the History picker");
        const attachable = ctx.container.querySelector('[data-testid="history-source-attach-hist-1"]');
        if (!attachable) throw new Error("the completed History render cannot be attached as source");
        if (ctx.container.querySelector('[data-testid="history-source-attach-hist-2"]')) throw new Error("a failed render was offered as a source");
      }
    );
  });

  await check("Real Video sequences History then upload with a presentation per clip", async (ctx) => {
    const draws = [];
    const clip = installLoadedClipStubs({ width: 1080, height: 1920, onDraw: (frame) => draws.push(frame) });
    const originalFetch = global.fetch;
    const encoder = load("demoCta/exportTikTok.js");
    const originalEncode = encoder.exportTikTok;
    const hand = load("demoCta/handView.js");
    const originalHand = hand.drawHandView;
    const originalPrepare = hand.prepareHandViewImages;
    const handCalls = [];
    let encodedOverlay;
    const overlays = load("demoCta/overlays.js");
    const originalHook = overlays.drawHookOverlay;
    const originalEnd = overlays.drawEndCard;
    const textCalls = [];
    overlays.drawHookOverlay = () => textCalls.push("hook");
    overlays.drawEndCard = () => textCalls.push("cta");
    try {
      await clip.loadClip(ctx);
      const click = async (selector) => {
        await clickEl(ctx, ctx.container.querySelector(selector), selector);
        await clip.flush();
      };
      const base = ctx.container.querySelector("video");
      Object.defineProperty(base, "readyState", { configurable: true, value: 4 });
      await click('[data-testid="view-mode-realistic"]');
      global.fetch = async () => ({ ok: true, blob: async () => new Blob(["clip"], { type: "video/mp4" }) });
      await withApi({ getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "composite-base", brand_name: "History base" }] }) }, async () => {
        await click('[data-testid="history-source-toggle"]');
        await click('[data-testid="history-source-attach-composite-base"]');
      });
      const probe = [...clip.createdVideos].reverse().find((v) => v.onloadedmetadata);
      await act(async () => probe.onloadedmetadata());
      await clip.flush();
      if (!ctx.container.textContent.includes("History base-composit.mp4")) throw new Error("History attachment did not become the base source");
      const source = base.src;
      // The follow-up group arrives with the base, carrying its own upload
      // and style picker. It starts closed (single-open accordion), so open
      // it before driving the added-clip controls below.
      if (!ctx.container.querySelector('[data-testid="demo-cta-second"]')) throw new Error("Second clip group missing once the base exists");
      await click('[data-testid="demo-cta-second"] button');
      if (ctx.container.querySelector('[data-testid="append-upload-button"]')?.textContent !== "Add clip after base") throw new Error("second-clip upload mislabeled with no added clip");
      const input = ctx.container.querySelector('[data-testid="append-upload-input"]');
      Object.defineProperty(input, "files", { configurable: true, value: [new dom.window.File(["phone"], "phone.mp4", { type: "video/mp4" })] });
      await act(async () => input.dispatchEvent(new dom.window.Event("change", { bubbles: true })));
      await clip.flush();
      const overlay = ctx.container.querySelector('[data-testid="append-video"]');
      if (!overlay || base.src !== source) throw new Error("overlay upload replaced the base");
      if (!ctx.container.querySelector('[data-testid="demo-cta-export"]').disabled) throw new Error("unloaded overlay did not block export");
      Object.defineProperty(overlay, "readyState", { configurable: true, value: 4 });
      await act(async () => overlay.dispatchEvent(new dom.window.Event("loadeddata")));
      await clip.flush();
      if (ctx.container.querySelector('[data-testid="demo-cta-export"]').disabled) throw new Error("decoded overlay never enabled export");
      draws.length = 0;
      base.currentTime = 3;
      await act(async () => base.dispatchEvent(new dom.window.Event("seeked")));
      await clip.flush();
      if (draws[0] !== base || draws.includes(overlay)) throw new Error("base preview still composites the added clip");
      if (!overlay.paused || overlay.loop) throw new Error("added clip loops or plays over the base");
      if (ctx.container.querySelector('[data-testid="append-overlays"]').checked) throw new Error("added-clip overlays must default off");
      if (ctx.container.querySelector('[data-testid="append-audio-mute"]').checked) throw new Error("added-clip mute must default off");
      await click('[data-testid="append-audio-mute"]');
      if (!ctx.container.querySelector('[data-testid="append-audio-mute"]').checked) throw new Error("added-clip mute did not take");
      await click('[data-testid="append-audio-mute"]');
      const seek = ctx.container.querySelector('[aria-label="Seek"]');
      if (Number(seek.getAttribute("aria-valuemax")) !== 16) throw new Error("timeline did not sum both 8s clips");
      await act(async () => seek.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "End", bubbles: true })));
      await act(async () => overlay.dispatchEvent(new dom.window.Event("seeked")));
      draws.length = 0;
      await clip.flush();
      if (!draws.includes(overlay) || draws.includes(base)) throw new Error("seek across the cut did not paint only the added clip");
      if (overlay.currentTime !== 8 || Number(seek.getAttribute("aria-valuenow")) !== 16) throw new Error("seek did not use global time");
      await act(async () => seek.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Home", bubbles: true })));
      await click('[data-testid="transport-forward-1s"]');
      encoder.exportTikTok = async ({ appendSource, drawFrame }) => {
        encodedOverlay = appendSource;
        const baseFrame = document.createElement("canvas");
        const addedFrame = document.createElement("canvas");
        draws.length = 0;
        textCalls.length = 0;
        drawFrame(1, baseFrame, 0);
        if (draws[0] !== baseFrame || !textCalls.length) throw new Error("export lost base footage or its overlays");
        if (appendSource) {
          draws.length = 0;
          textCalls.length = 0;
          drawFrame(base.duration + 1, addedFrame, 1);
          if (draws[0] !== addedFrame || draws.includes(baseFrame)) throw new Error("export did not switch to the added frame");
          const enabled = ctx.container.querySelector('[data-testid="append-overlays"]').checked;
          if (Boolean(textCalls.length) !== enabled) throw new Error("added-segment overlays did not follow the opt-in");
        }
        throw new Error("Sequence callback verified");
      };
      await click('[data-testid="demo-cta-export"]');
      if (!encodedOverlay || !ctx.container.textContent.includes("Sequence callback verified")) throw new Error("joined export was not exercised");
      await click('[data-testid="append-overlays"]');
      await click('[data-testid="demo-cta-export"]');
      if (!ctx.container.textContent.includes("Sequence callback verified")) throw new Error("opted-in overlays failed export");
      // Each clip picks its own presentation: the added clip renders inside
      // a floating phone while the base stays full-bleed, and the export
      // keeps both segments.
      hand.drawHandView = (...args) => { handCalls.push(args); };
      hand.prepareHandViewImages = async () => {};
      await click('[data-testid="append-mode-floating"]');
      if (ctx.container.querySelector('[data-testid="append-mode-floating"]').getAttribute("aria-pressed") !== "true") throw new Error("added-clip style did not take the floating selection");
      // Each segment carries its own backdrop and motion: the added clip
      // takes sage + embers while the base keeps lavender + bloom.
      await click('[data-testid="append-background-sage"]');
      if (ctx.container.querySelector('[data-testid="append-background-sage"]').getAttribute("aria-pressed") !== "true") throw new Error("added-clip background did not take the selection");
      await click('[data-testid="append-animation-embers"]');
      if (ctx.container.querySelector('[data-testid="append-animation-embers"]').getAttribute("aria-pressed") !== "true") throw new Error("added-clip animation did not take the selection");
      await click('[data-testid="demo-cta-export"]');
      if (!encodedOverlay || !ctx.container.textContent.includes("Sequence callback verified")) throw new Error("floating added clip was not exported");
      await click('[data-testid="append-mode-hand"]');
      await click('[data-testid="append-env-bedroom"]');
      handCalls.length = 0;
      await click('[data-testid="demo-cta-export"]');
      if (!encodedOverlay || !handCalls.length) throw new Error("hand added clip never reached the hand painter");
      if (!handCalls.some((args) => args[4] === "bedroom")) throw new Error("added clip did not paint its own scene");
      // The base keeps its own presentation too: a hand base plus a hand
      // upload still exports both segments instead of dropping the second.
      // Source & Look closed when Second clip opened (single-open
      // accordion), so reopen it for the base style picker.
      await click('[data-testid="demo-cta-source"] button');
      if (!ctx.container.querySelector('[data-testid="base-audio-mute"]')) throw new Error("base mute toggle missing from Source & Look");
      if (ctx.container.querySelector('[data-testid="base-audio-mute"]').checked) throw new Error("base mute must default off");
      await click('[data-testid="base-audio-mute"]');
      if (!ctx.container.querySelector('[data-testid="base-audio-mute"]').checked) throw new Error("base mute did not take");
      await click('[data-testid="base-audio-mute"]');
      await click('[data-testid="view-mode-hand"]');
      handCalls.length = 0;
      await click('[data-testid="demo-cta-export"]');
      if (!encodedOverlay || handCalls.length < 2) throw new Error("base style change dropped the added clip or its presentation");
      if (!handCalls.some((args) => args[4] === "living_room")) throw new Error("base lost its own scene once the added clip picked another");
      await click('[data-testid="view-mode-realistic"]');
      await click('[data-testid="demo-cta-second"] button');
      await click('[data-testid="append-mode-realistic"]');
      await act(async () => overlay.dispatchEvent(new dom.window.Event("error")));
      if (!ctx.container.querySelector('[data-testid="demo-cta-export"]').disabled) throw new Error("broken overlay still enabled export");
      await click('[data-testid="append-remove"]');
      if (ctx.container.querySelector('[data-testid="append-video"]') || base.src !== source) throw new Error("remove failed or cleared the base");
      if (ctx.container.querySelector('[data-testid="demo-cta-export"]').disabled) throw new Error("removing broken overlay did not recover base-only export");
    } finally {
      encoder.exportTikTok = originalEncode;
      overlays.drawHookOverlay = originalHook;
      overlays.drawEndCard = originalEnd;
      hand.drawHandView = originalHand;
      hand.prepareHandViewImages = originalPrepare;
      global.fetch = originalFetch;
      clip.restore();
    }
  });

  await check("History opens as a clip and expands to its context and actions", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi({
      getGenerationHistory: async () => ({ generations: [
        { ...COMPLETED, id: "dense-1", brand_name: "Journal", hook_line: "Find your next thought.", audience: "People reflecting after work", demo_brief: "Record the emotion suggestions." },
        { ...COMPLETED, id: "dense-2", brand_name: "Journal", hook_line: "A second render." },
      ] }),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
    }, async () => {
      await mount(GenerationHistory)(ctx);
      const grid = ctx.container.querySelector('[data-testid="history-list"].history-grid');
      if (!grid || grid.querySelectorAll('[data-testid="history-card"]').length !== 2) throw new Error("history cards are not in the responsive grid");
      const first = grid.querySelector('[data-testid="history-card"]');
      if (!first.querySelector("video.history-preview")) throw new Error("compact preview missing");
      const expand = first.querySelector('[data-testid="history-expand"]');
      if (!expand) throw new Error("a collapsed tile has no expand control to reach its details");
      if (expand.getAttribute("aria-expanded") !== "false") throw new Error("history tiles do not start collapsed");
      // Identity and result facts remain visible; working controls stay in the drawer.
      if (first.querySelector('[data-testid="history-context"]')) {
        throw new Error("the collapsed tile already shows the demo context");
      }
      for (const label of ["Download", "Delete", "Details", "Demo + CTA"]) {
        if (first.textContent.includes(label)) {
          throw new Error(`the collapsed tile already exposes ${label}`);
        }
      }
      const summary = first.querySelector('[data-testid="history-summary"]');
      for (const text of ["Journal", "Find your next thought.", "Not posted", "Views not recorded", "Not rated"]) {
        if (!summary?.textContent.includes(text)) throw new Error(`collapsed identity/result missing: ${text}`);
      }
      await clickEl(ctx, expand, "expand a history tile");
      const opened = ctx.container.querySelector('[data-testid="history-card"]');
      if (opened.querySelector('[data-testid="history-expand"]').getAttribute("aria-expanded") !== "true") {
        throw new Error("the expand control does not report the drawer it opened");
      }
      if (!opened.querySelector('[data-testid="history-context"]')?.textContent.includes("Record the emotion suggestions.")) throw new Error("useful demo context missing");
      for (const label of ["Download", "Delete", "Details", "Demo + CTA"]) {
        if (!opened.textContent.includes(label)) throw new Error(`History lost ${label}`);
      }
    });
  });

  await check("history sorts most-viewed above uncounted renders", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi({
      getGenerationHistory: async () => ({ generations: [
        { ...COMPLETED, id: "v-old", tiktok_views: 10 },
        { ...COMPLETED, id: "v-top", tiktok_views: 9000 },
        { ...COMPLETED, id: "v-none" },
      ] }),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
    }, async () => {
      await mount(GenerationHistory)(ctx);
      const order = () => [...ctx.container.querySelectorAll('article[id^="generation-"]')].map((e) => e.id);
      const newest = order();
      if (newest.join() !== "generation-v-old,generation-v-top,generation-v-none") {
        throw new Error(`newest-first did not preserve server order: ${newest.join()}`);
      }
      await selectOption(ctx, ctx.container.querySelector('[data-testid="history-sort"]'), "views");
      const ranked = order();
      if (ranked.join() !== "generation-v-top,generation-v-old,generation-v-none") {
        throw new Error(`most-viewed did not rank counted rows first: ${ranked.join()}`);
      }
    });
  });

  await check("History saves update collapsed facts, votes and view order without reloading", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    let fetches = 0;
    const first = { ...COMPLETED, id: "sync-low", tiktok_url: "https://www.tiktok.com/@founder/video/123", tiktok_views: 10 };
    await withApi({
      getGenerationHistory: async () => { fetches++; return { generations: [first, { ...COMPLETED, id: "sync-high", tiktok_views: 100 }] }; },
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
      getGeneration: async () => first,
      setTikTokViews: async (_id, count) => {
        if (count === 1201) throw new Error("Views could not save");
        return { tiktok_views: count };
      },
      setTikTokLink: async (_id, link) => ({ tiktok_url: link || null }),
      recordFeedback: async () => ({}),
    }, async () => {
      await mount(GenerationHistory)(ctx);
      const card = () => ctx.container.querySelector('#generation-sync-low');
      const get = (id) => card().querySelector(`[data-testid="${id}"]`);
      await selectOption(ctx, ctx.container.querySelector('[data-testid="history-sort"]'), "views");
      await clickEl(ctx, get("history-expand"));
      const input = get("history-tiktok-views-input-sync-low");
      for (const invalid of ["1,2", "1.5", "true", "10000000001"]) {
        await typeInto(ctx, input, invalid);
        await clickEl(ctx, get("history-tiktok-views-save-sync-low"));
        if (!card().querySelector('[role="alert"]')) throw new Error(`bad views accepted: ${invalid}`);
        if (!get("history-summary").textContent.includes("10 views")) throw new Error("invalid save changed tile");
      }
      await typeInto(ctx, input, "1,200");
      await clickEl(ctx, get("history-tiktok-views-save-sync-low"));
      if (ctx.container.querySelector('article').id !== "generation-sync-low") throw new Error("saving views did not immediately re-sort");
      await typeInto(ctx, input, "1201");
      await clickEl(ctx, get("history-tiktok-views-save-sync-low"));
      expectText(ctx, "Views could not save");
      if (!get("history-summary").textContent.includes("1,200 views")) throw new Error("failed save changed confirmed list state");
      await clickEl(ctx, get("history-video-feedback-sync-low-thumb-up"));
      if (!get("history-summary").textContent.includes("Winner")) throw new Error("saved vote did not update list");
      await clickEl(ctx, get("history-tiktok-clear-sync-low"));
      if (!get("history-summary").textContent.includes("Not posted") || get("history-summary").textContent.includes("Winner")) throw new Error("clearing link left stale posted/winner state");
      await typeInto(ctx, get("history-tiktok-input-sync-low"), first.tiktok_url);
      await clickEl(ctx, get("history-tiktok-save-sync-low"));
      await clickEl(ctx, get("history-expand"));
      if (!get("history-summary").textContent.includes("1,200 views") || !get("history-summary").textContent.includes("Winner")) throw new Error("collapsed summary lost saved result");
      if (fetches !== 1) throw new Error("result save reloaded the page instead of synchronizing rows");
    });
  });

  await check("History ignores stale filter successes and failures", async (ctx) => {
    const History = load("pages/GenerationHistory.jsx").default;
    const pending = [];
    await withApi({
      getGenerationHistory: () => new Promise((resolve, reject) => pending.push({ resolve, reject })),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
    }, async () => {
      const oldParams = global.__SMOKE_PARAMS;
      global.__SMOKE_ROUTE_CHANGE = (to) => { global.__SMOKE_PARAMS = to.search; ctx.root.render(React.createElement(History)); };
      try {
      await mount(History)(ctx);
      await selectOption(ctx, ctx.container.querySelector('#history-status-filter'), "failed");
      await act(async () => pending[1].resolve({ generations: [{ ...COMPLETED, id: "latest", status: "failed" }] }));
      await act(async () => pending[0].resolve({ generations: [{ ...COMPLETED, id: "stale" }] }));
      if (!ctx.container.querySelector('#generation-latest') || ctx.container.querySelector('#generation-stale')) throw new Error("older request overwrote current filter");
      await selectOption(ctx, ctx.container.querySelector('#history-status-filter'), "completed");
      await selectOption(ctx, ctx.container.querySelector('#history-status-filter'), "archived");
      await act(async () => pending[3].resolve({ generations: [{ ...COMPLETED, id: "archived", status: "archived" }] }));
      await act(async () => pending[2].reject(new Error("stale request failed")));
      expectAbsent(ctx, "stale request failed");
      if (!ctx.container.querySelector('#generation-archived')) throw new Error("stale failure hid current results");
      } finally { global.__SMOKE_ROUTE_CHANGE = null; global.__SMOKE_PARAMS = oldParams; }
    });
  });

  await check("History honors same-page query navigation and opens a new clip anchor", async (ctx) => {
    const History = load("pages/GenerationHistory.jsx").default;
    const oldParams = global.__SMOKE_PARAMS;
    const oldHash = global.__SMOKE_HASH;
    try {
      global.__SMOKE_PARAMS = "q=hidden";
      global.__SMOKE_HASH = "";
      await withApi({
        getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "anchor-one" }, { ...COMPLETED, id: "anchor-two" }] }),
        getAppProfiles: async () => ({ profiles: [PROFILE] }),
      }, async () => {
        await mount(History)(ctx);
        global.__SMOKE_PARAMS = "profile=p1&status=completed";
        global.__SMOKE_HASH = "#generation-anchor-two";
        await mount(History)(ctx);
        if (ctx.container.querySelector('[data-testid="history-search"]').value !== "") throw new Error("old search hid linked clip");
        if (ctx.container.querySelector('#history-status-filter').value !== "completed") throw new Error("URL status ignored");
        const tab = ctx.container.querySelector('#generation-anchor-two [data-testid="history-expand"]');
        if (tab?.getAttribute('aria-expanded') !== 'true') throw new Error("same-page clip anchor stayed closed");
        global.__SMOKE_HASH = "#generation-anchor-one";
        await mount(History)(ctx);
        if (ctx.container.querySelector('#generation-anchor-one [data-testid="history-expand"]')?.getAttribute('aria-expanded') !== 'true') throw new Error("new hash on mounted row stayed closed");
      });
    } finally { global.__SMOKE_PARAMS = oldParams; global.__SMOKE_HASH = oldHash; }
  });

  await check("History retains regenerated post copy across drawer and Details handoffs", async (ctx) => {
    const History = load("pages/GenerationHistory.jsx").default;
    const oldKit = { caption: "Old frozen caption", hashtags: ["#old"] };
    const freshKit = { caption: "Fresh confirmed caption", hashtags: ["#fresh"] };
    const detailKit = { caption: "Confirmed from Details", hashtags: ["#details"] };
    let savedKit = oldKit;
    await withApi({
      getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "kit-sync", post_kit: oldKit }] }),
      getGeneration: async () => ({ ...COMPLETED, id: "kit-sync", post_kit: savedKit }),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
      regeneratePostKit: async () => ({ post_kit: (savedKit = savedKit === oldKit ? freshKit : detailKit) }),
    }, async () => {
      await mount(History)(ctx);
      const tab = () => ctx.container.querySelector('[data-testid="history-expand"]');
      await clickEl(ctx, tab());
      await clickEl(ctx, ctx.container.querySelector('[data-testid="postkit-regenerate"]'));
      await clickEl(ctx, tab());
      await clickEl(ctx, tab());
      expectText(ctx, freshKit.caption, "reopening the drawer restored stale copy");
      await clickEl(ctx, ctx.container.querySelector('[data-testid="generation-details-button"]'));
      const dialog = ctx.container.querySelector('[role="dialog"]');
      await clickEl(ctx, dialog.querySelector('[data-testid="postkit-regenerate"]'));
      await clickEl(ctx, dialog.querySelector('[aria-label="Close details"]'));
      expectText(ctx, detailKit.caption);
      expectAbsent(ctx, freshKit.caption);
      expectAbsent(ctx, oldKit.caption);
    });
  });

  await check("ratings serialize saves and ignore a response for a replaced item", async (ctx) => {
    const { ComponentThumbs } = load("components/ComponentThumbs.jsx");
    let finish;
    let calls = 0;
    const voted = [];
    await withApi({ recordFeedback: () => { calls++; return new Promise(resolve => { finish = resolve; }); } }, async () => {
      const props = { component: "video", resetKey: "first", initialValue: 1, onVoted: (...args) => voted.push(args), testId: "race-rating" };
      await mount(ComponentThumbs, props)(ctx);
      await clickEl(ctx, ctx.container.querySelector('[data-testid="race-rating-thumb-down"]'));
      const up = ctx.container.querySelector('[data-testid="race-rating-thumb-up"]');
      if (!up.disabled) throw new Error("a second save can race the first");
      await clickEl(ctx, up);
      if (calls !== 1) throw new Error("duplicate rating submitted");
      await mount(ComponentThumbs, { ...props, resetKey: "second", initialValue: 0 })(ctx);
      await act(async () => finish({}));
      if (voted.length) throw new Error("old item completion notified new item");
      if (ctx.container.querySelector('[aria-pressed="true"]')) throw new Error("old vote leaked to new item");
    });
  });

  await check("failed ratings restore the last confirmed vote and remain retryable", async (ctx) => {
    const { ComponentThumbs } = load("components/ComponentThumbs.jsx");
    let fail = false;
    const voted = [];
    await withApi({ recordFeedback: async () => { if (fail) throw new Error("offline"); return {}; } }, async () => {
      await mount(ComponentThumbs, { component: "video", resetKey: "confirmed", initialValue: 0, onVoted: (...args) => voted.push(args), testId: "failed-rating" })(ctx);
      const get = (direction) => ctx.container.querySelector(`[data-testid="failed-rating-thumb-${direction}"]`);
      await clickEl(ctx, get("up"));
      fail = true;
      await clickEl(ctx, get("down"));
      if (get("up").getAttribute("aria-pressed") !== "true" || get("down").disabled) throw new Error("failed save lost confirmed vote or blocked retry");
      expectText(ctx, "Could not save your rating");
      if (voted.length !== 1) throw new Error("failed save notified parent");
      fail = false;
      await clickEl(ctx, get("down"));
      if (voted.length !== 2 || get("down").getAttribute("aria-pressed") !== "true") throw new Error("retry did not save");
    });
  });

  // The tab is two gestures in one control. The click path is covered above;
  // this covers the drag, because a tab that only answers clicks is a button
  // with a grip icon drawn on it — and the drag is what a bottom sheet trained
  // people to try.
  await check("History's expand tab opens on a drag, not only a click", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi({
      getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "drag-1" }] }),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
    }, async () => {
      await mount(GenerationHistory)(ctx);
      const tab = ctx.container.querySelector('[data-testid="history-expand"]');
      if (!tab) throw new Error("no expand tab to drag");
      const send = async (type, clientY) => {
        await act(async () => {
          tab.dispatchEvent(new dom.window.MouseEvent(type, { bubbles: true, clientY }));
        });
      };

      await send("pointerdown", 400);
      await send("pointermove", 384);
      if (tab.getAttribute("data-dragging") !== "true") {
        throw new Error("a dragged tab does not report the drag, so the gesture has no feedback");
      }
      await send("pointerup", 384);
      if (tab.getAttribute("aria-expanded") !== "false") {
        throw new Error(
          "a 16px wobble opened the drawer: the click that a shaky press produces " +
            "would be spent on a gesture nobody meant"
        );
      }

      await send("pointerdown", 400);
      await send("pointermove", 320);
      // A real drag ends in a click in the same task, so both go in one act, in
      // that order. A click arriving later is a separate interaction and is
      // rightly allowed through.
      await act(async () => {
        tab.dispatchEvent(new dom.window.MouseEvent("pointerup", { bubbles: true, clientY: 320 }));
        tab.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
      });
      if (tab.getAttribute("aria-expanded") !== "true") {
        throw new Error(
          "an 80px drag up did not open the drawer, so the tab is a click-only " +
            "button with a grip painted on it"
        );
      }

      await clickEl(ctx, tab, "close the drawer");
      if (tab.getAttribute("aria-expanded") !== "false") {
        throw new Error("the expand tab cannot close the drawer it opened");
      }
    });
  });

  await check("History's subtitle renders within the masthead budget", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi(
      {
        getGenerationHistory: async () => ({ generations: [] }),
        getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
      async () => {
        await mount(GenerationHistory)(ctx);
        const lede = ctx.container.querySelector('[data-testid="history-header"] p');
        const copy = ((lede && lede.textContent) || "").trim();
        if (!copy) {
          throw new Error("the History subtitle is missing from the rendered header");
        }
        if (copy.length < 54 || copy.length > 60) {
          throw new Error(
            `the History subtitle is ${copy.length} chars, outside the 54-60 budget`
          );
        }
      }
    );
  });

  await check("History pages past the first hundred renders", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    const seen = [];
    const rows = Array.from({ length: 101 }, (_, i) => ({ ...COMPLETED, id: `page-${i}` }));
    await withApi(
      {
        getGenerationHistory: async (params) => {
          seen.push(params?.limit);
          return { generations: rows.slice(0, params?.limit || 100) };
        },
        getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
      async () => {
        await mount(GenerationHistory)(ctx);
        const more = ctx.container.querySelector('[data-testid="history-show-more"]');
        if (!more) {
          throw new Error("a full first page of history offers no way to see the rest");
        }
        await clickEl(ctx, more, "show the second page of history");
        if (seen.join(",") !== "100,200") {
          throw new Error(`show-more fetched limits [${seen.join(",")}], expected 100 then 200`);
        }
        if (ctx.container.querySelector('[data-testid="history-show-more"]')) {
          throw new Error("show-more stays on screen after the last page arrived");
        }
      }
    );
  });

  await check("History's details modal answers Escape", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi(
      {
        getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "esc-1" }] }),
        getGeneration: async () => ({ ...COMPLETED, id: "esc-1", model: "minimax" }),
        getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
      async () => {
        await mount(GenerationHistory)(ctx);
        await clickEl(ctx, ctx.container.querySelector('[data-testid="history-expand"]'), "open the drawer");
        await clickEl(
          ctx,
          ctx.container.querySelector('[data-testid="generation-details-button"]'),
          "open generation details"
        );
        const dialog = ctx.container.querySelector('[role="dialog"]');
        if (!dialog) throw new Error("the details modal did not open");
        await act(async () => {
          dialog.dispatchEvent(new dom.window.KeyboardEvent("keydown", { key: "Escape", bubbles: true }));
        });
        if (ctx.container.querySelector('[role="dialog"]')) {
          throw new Error("Escape leaves the details modal open, stranding keyboard users");
        }
      }
    );
  });

  await check("History opens the render a #generation- link names", async (ctx) => {
    // Analytics "View render" links land here with a hash, but the rows only
    // arrive after the fetch — so the browser's native anchor scroll has
    // nothing to land on and the named render sits below the fold, closed.
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    global.__SMOKE_HASH = "#generation-deep-1";
    const previousNavigations = global.__SMOKE_NAVIGATIONS;
    global.__SMOKE_NAVIGATIONS = [];
    try {
      await withApi(
        {
          getGenerationHistory: async ({ limit }) => {
            if (limit !== 200) throw new Error("deep link cannot reach Analytics' full result window");
            return { generations: [{ ...COMPLETED, id: "deep-1" }] };
          },
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
        async () => {
          await mount(GenerationHistory)(ctx);
          const destinations = global.__SMOKE_NAVIGATIONS.filter((_, i) => i % 2 === 0);
          if (destinations.some((to) => to.hash !== "#generation-deep-1")) {
            throw new Error("filter URL synchronization erased the clip anchor");
          }
        }
      );
    } finally {
      global.__SMOKE_HASH = "";
      global.__SMOKE_NAVIGATIONS = previousNavigations;
    }
    const tab = ctx.container.querySelector('[data-testid="history-expand"]');
    if (!tab || tab.getAttribute("aria-expanded") !== "true") {
      throw new Error("the deep-linked render is not opened on arrival");
    }
  });

  await check("Asset Library searches its photos by name", async (ctx) => {
    const AssetLibrary = load("pages/AssetLibrary.jsx").default;
    await withApi(
      {
        getAppProfiles: async () => ({ profiles: [PROFILE] }),
        getAssets: async () => ({
          assets: [
            { id: "a1", kind: "character_reference", status: "active", rights_confirmed: true, label: "Founder photo", created_at: new Date().toISOString(), used_in: [] },
            { id: "a2", kind: "character_reference", status: "active", rights_confirmed: true, label: "Group shot", created_at: new Date().toISOString(), used_in: [] },
          ],
        }),
      },
      async () => {
        await mount(AssetLibrary, { profileId: "p1" })(ctx);
        const search = ctx.container.querySelector('[data-testid="asset-search"]');
        if (!search) throw new Error("the standalone library has no photo search");
        await typeInto(ctx, search, "founder", "search the photo library");
        const text = ctx.container.textContent || "";
        if (!text.includes("Founder photo") || text.includes("Group shot")) {
          throw new Error("the search does not narrow the photo list to the match");
        }
        if (!text.includes("1 of 2 match")) {
          throw new Error("the search reports no count of what matched");
        }
      }
    );
  });

  await check("app chrome offers a skip link to the content", async () => {
    // Source-level, like the sidebar order check: mounting AppShell means
    // mounting the sidebar, Clerk and the tour provider for one anchor.
    // The guard against a silent pass is asserting both ends — a link whose
    // target id is gone is a skip link that skips nowhere.
    const src = fs.readFileSync(
      path.join(SRC, "components", "AppShell.jsx"),
      "utf8"
    );
    if (!src.includes('href="#main-content"')) {
      throw new Error("no skip link targets the main content");
    }
    if (!src.includes('id="main-content"')) {
      throw new Error("the skip link's target id is missing from the main element");
    }
  });

  await check(
    "History offers one primary video vote with optional part ratings",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      global.__SMOKE_THUMBS = [];
      try {
        await withApi(
          {
            getGenerationHistory: async () => ({
              generations: [
                {
                  ...COMPLETED,
                  brand_name: "Test App",
                  duration: 10,
                  objective: "demonstrate_feature",
                  angle_kind: "problem_solution",
                  script_version: 2,
                  strategy_version: 3,
                },
              ],
            }),
            getAppProfiles: async () => ({ profiles: [PROFILE] }),
                },
          async () => {
            await mount(GenerationHistory, { onChanged: () => {} })(ctx);
            await clickEl(
              ctx,
              ctx.container.querySelector('[data-testid="history-expand"]'),
              "expand the render tile"
            );
            const videoUp = ctx.container.querySelector(
              `[data-testid="history-video-feedback-${COMPLETED.id}-thumb-up"]`
            );
            if (!videoUp) {
              throw new Error("History is missing the primary video vote");
            }
            if (!ctx.container.textContent.includes("Did this render land?")) {
              throw new Error("the primary vote does not ask about the render as a whole");
            }
            if (!/h-11/.test(videoUp.className)) {
              throw new Error("the primary video vote is not larger than the part votes");
            }
            const goalUp = ctx.container.querySelector(
              `[data-testid="history-goal-feedback-${COMPLETED.id}-thumb-up"]`
            );
            if (!goalUp || !/h-9/.test(goalUp.className)) {
              throw new Error("per-part votes are not subordinate in size to the video vote");
            }
            const parts = ctx.container.querySelector(
              `[data-testid="history-parts-feedback-${COMPLETED.id}"]`
            );
            if (!parts || parts.tagName !== "DETAILS") {
              throw new Error("per-part votes are not demoted into an optional disclosure");
            }
            if (parts.open) {
              throw new Error("per-part votes must start collapsed so they cannot be confused with the video vote");
            }
            await clickEl(ctx, parts.querySelector("summary"), "open the optional part ratings");
            if (!parts.open) {
              throw new Error("clicking the disclosure summary did not expand the part ratings");
            }
            for (const part of ["video", "goal", "template", "plan", "script"]) {
              const up = ctx.container.querySelector(
                `[data-testid="history-${part}-feedback-${COMPLETED.id}-thumb-up"]`
              );
              if (!up) {
                throw new Error(`History is missing thumbs-up for ${part}`);
              }
              await clickEl(ctx, up, `click ${part} thumbs-up`);
            }
            const recorded = global.__SMOKE_THUMBS.map((t) => `${t.step}:${t.verdict}`);
            for (const expected of ["video:1", "goal:1", "template:1", "plan:1", "script:1"]) {
              if (!recorded.includes(expected)) {
                throw new Error(`Expected ${expected} in recorded thumbs, got ${recorded.join(", ")}`);
              }
            }
          }
        );
      } finally {
        global.__SMOKE_THUMBS = [];
      }
    }
  );

  // Votes save already; this is the visual restore. A founder returning to a
  // rated render must see their thumbs still pressed, without the mount
  // itself recording a single new event.
  await check(
    "History restores saved thumb highlights without recording new votes",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      global.__SMOKE_THUMBS = [];
      try {
        await withApi(
          {
            getGenerationHistory: async () => ({
              generations: [
                {
                  ...COMPLETED,
                  brand_name: "Test App",
                  duration: 10,
                  verdicts: { video: 1, goal: -1 },
                },
              ],
            }),
            getAppProfiles: async () => ({ profiles: [PROFILE] }),
            getGeneration: async () => ({ verdicts: { video: 1, goal: -1 } }),
                },
          async () => {
            await mount(GenerationHistory, { onChanged: () => {} })(ctx);
            await clickEl(
              ctx,
              ctx.container.querySelector('[data-testid="history-expand"]'),
              "expand the render tile"
            );
            const up = ctx.container.querySelector(
              `[data-testid="history-video-feedback-${COMPLETED.id}-thumb-up"]`
            );
            const down = ctx.container.querySelector(
              `[data-testid="history-goal-feedback-${COMPLETED.id}-thumb-down"]`
            );
            if (!up || !down) {
              throw new Error("History is missing the saved thumb controls");
            }
            if (up.getAttribute("aria-pressed") !== "true") {
              throw new Error("a saved thumbs-up on the video is not highlighted");
            }
            if (down.getAttribute("aria-pressed") !== "true") {
              throw new Error("a saved thumbs-down on the goal is not highlighted");
            }
            if ((global.__SMOKE_THUMBS || []).length !== 0) {
              throw new Error("restoring highlights recorded votes that were never cast");
            }
          }
        );
      } finally {
        global.__SMOKE_THUMBS = [];
      }
    }
  );

  // A rated part must be visible without opening the disclosure, and the
  // pressed thumb must carry more than a hairline: the collapsed summary
  // names the rated count while each chosen thumb keeps its fill.
  await check(
    "History names rated parts on the collapsed disclosure with a clear selected state",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      global.__SMOKE_THUMBS = [];
      try {
        await withApi(
          {
            getGenerationHistory: async () => ({
              generations: [
                {
                  ...COMPLETED,
                  brand_name: "Test App",
                  duration: 10,
                  verdicts: { video: 1, goal: -1, plan: 1 },
                },
              ],
            }),
            getAppProfiles: async () => ({ profiles: [PROFILE] }),
            getGeneration: async () => ({ verdicts: { video: 1, goal: -1, plan: 1 } }),
          },
          async () => {
            await mount(GenerationHistory, { onChanged: () => {} })(ctx);
            await clickEl(
              ctx,
              ctx.container.querySelector('[data-testid="history-expand"]'),
              "expand the render tile"
            );
            const summary = ctx.container.querySelector(
              `[data-testid="history-parts-feedback-${COMPLETED.id}"] summary`
            );
            if (!summary || !summary.textContent.includes("2 of 4 rated")) {
              throw new Error("the collapsed disclosure does not name the rated part count");
            }
            const goalDown = ctx.container.querySelector(
              `[data-testid="history-goal-feedback-${COMPLETED.id}-thumb-down"]`
            );
            const planUp = ctx.container.querySelector(
              `[data-testid="history-plan-feedback-${COMPLETED.id}-thumb-up"]`
            );
            const templateUp = ctx.container.querySelector(
              `[data-testid="history-template-feedback-${COMPLETED.id}-thumb-up"]`
            );
            if (!goalDown || !planUp || !templateUp) {
              throw new Error("History is missing the part thumb controls");
            }
            for (const [el, name] of [[goalDown, "goal thumbs-down"], [planUp, "plan thumbs-up"]]) {
              if (el.getAttribute("aria-pressed") !== "true" || !el.classList.contains("thumb-selected")) {
                throw new Error(`a saved vote on ${name} is not unmistakably selected`);
              }
            }
            if (templateUp.getAttribute("aria-pressed") === "true" || templateUp.classList.contains("thumb-selected")) {
              throw new Error("an unrated part renders as selected");
            }
            const css = fs.readFileSync(path.join(SRC, "index.css"), "utf8");
            if (!css.includes(".thumb-pair .thumb-selected")) {
              throw new Error("the selected-thumb fill is not defined where it ships");
            }
            if (!css.includes(".thumb-pair > button:focus-visible")) {
              throw new Error("the thumb keyboard focus ring is not defined where it ships");
            }
            if (!css.includes(".history-vote-block .thumb-pair .thumb-selected:focus-visible")) {
              throw new Error("a focused selected thumb is indistinguishable from a selected one");
            }
            const voteBlock = ctx.container.querySelector(
              `[data-testid="history-feedback-${COMPLETED.id}"]`
            );
            if (!voteBlock || !voteBlock.classList.contains("history-vote-block")) {
              throw new Error("the History vote block is missing its focus scope");
            }
          }
        );
      } finally {
        global.__SMOKE_THUMBS = [];
      }
    }
  );

  // Changing a saved vote must move the highlight at once: the other option
  // presses, the old one releases, and exactly one change event is filed.
  await check(
    "History moves the highlight immediately when a saved vote is changed",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      global.__SMOKE_THUMBS = [];
      try {
        await withApi(
          {
            getGenerationHistory: async () => ({
              generations: [
                {
                  ...COMPLETED,
                  brand_name: "Test App",
                  duration: 10,
                  verdicts: { video: 1 },
                },
              ],
            }),
            getAppProfiles: async () => ({ profiles: [PROFILE] }),
            getGeneration: async () => ({ verdicts: { video: 1 } }),
          },
          async () => {
            await mount(GenerationHistory, { onChanged: () => {} })(ctx);
            await clickEl(
              ctx,
              ctx.container.querySelector('[data-testid="history-expand"]'),
              "expand the render tile"
            );
            const up = ctx.container.querySelector(
              `[data-testid="history-video-feedback-${COMPLETED.id}-thumb-up"]`
            );
            const down = ctx.container.querySelector(
              `[data-testid="history-video-feedback-${COMPLETED.id}-thumb-down"]`
            );
            if (!up || !down) {
              throw new Error("History is missing the saved video vote");
            }
            if (up.getAttribute("aria-pressed") !== "true") {
              throw new Error("the saved video thumbs-up is not highlighted before the change");
            }
            await clickEl(ctx, down, "change the video vote to thumbs-down");
            if (down.getAttribute("aria-pressed") !== "true") {
              throw new Error("the newly chosen thumbs-down is not highlighted");
            }
            if (up.getAttribute("aria-pressed") === "true") {
              throw new Error("the old thumbs-up stayed highlighted after the change");
            }
            const recorded = (global.__SMOKE_THUMBS || []).map((t) => `${t.step}:${t.verdict}`);
            if (recorded.join(",") !== "video:-1") {
              throw new Error(`changing the vote should file exactly video:-1, got ${recorded.join(",")}`);
            }
          }
        );
      } finally {
        global.__SMOKE_THUMBS = [];
      }
    }
  );

  // The list's verdicts go stale the moment a vote lands anywhere else, so
  // the drawer revalidates on every expand: fresh server state wins, and a
  // failed refetch keeps the list's verdicts instead of blanking the thumbs.
  await check(
    "History refetches a render's votes when its drawer opens",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      global.__SMOKE_THUMBS = [];
      const row = {
        ...COMPLETED,
        brand_name: "Test App",
        duration: 10,
        verdicts: { video: 1 },
      };
      const fresh = { ...row, verdicts: { video: -1, goal: 1 } };
      try {
        await withApi(
          {
            getGenerationHistory: async () => ({ generations: [row] }),
            getAppProfiles: async () => ({ profiles: [PROFILE] }),
            getGeneration: async () => fresh,
          },
          async () => {
            await mount(GenerationHistory, { onChanged: () => {} })(ctx);
            await clickEl(
              ctx,
              ctx.container.querySelector('[data-testid="history-expand"]'),
              "expand the render tile"
            );
            await act(async () => {});
            const down = ctx.container.querySelector(
              `[data-testid="history-video-feedback-${COMPLETED.id}-thumb-down"]`
            );
            const goalUp = ctx.container.querySelector(
              `[data-testid="history-goal-feedback-${COMPLETED.id}-thumb-up"]`
            );
            if (!down || !goalUp) {
              throw new Error("History is missing the revalidated thumb controls");
            }
            if (down.getAttribute("aria-pressed") !== "true" || !down.classList.contains("thumb-selected")) {
              throw new Error("the drawer kept the stale list vote instead of the fresh server vote");
            }
            if (goalUp.getAttribute("aria-pressed") !== "true") {
              throw new Error("a fresh saved part vote is not highlighted");
            }
            const summary = ctx.container.querySelector(
              `[data-testid="history-parts-feedback-${COMPLETED.id}"] summary`
            );
            if (!summary || !summary.textContent.includes("1 of 4 rated")) {
              throw new Error("the revalidated part vote is not counted on the collapsed disclosure");
            }
            if ((global.__SMOKE_THUMBS || []).length !== 0) {
              throw new Error("revalidating votes recorded votes that were never cast");
            }
          }
        );
      } finally {
        global.__SMOKE_THUMBS = [];
      }
    }
  );

  // A refetch that fails must leave the list's verdicts showing: the drawer
  // degrades to possibly-stale highlights, never to blank thumbs.
  await check(
    "History keeps the list votes when the vote refetch fails",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      global.__SMOKE_THUMBS = [];
      try {
        await withApi(
          {
            getGenerationHistory: async () => ({
              generations: [
                {
                  ...COMPLETED,
                  brand_name: "Test App",
                  duration: 10,
                  verdicts: { video: 1 },
                },
              ],
            }),
            getAppProfiles: async () => ({ profiles: [PROFILE] }),
            getGeneration: async () => { throw new Error("backend is down"); },
          },
          async () => {
            await mount(GenerationHistory, { onChanged: () => {} })(ctx);
            await clickEl(
              ctx,
              ctx.container.querySelector('[data-testid="history-expand"]'),
              "expand the render tile"
            );
            await act(async () => {});
            const up = ctx.container.querySelector(
              `[data-testid="history-video-feedback-${COMPLETED.id}-thumb-up"]`
            );
            if (!up) {
              throw new Error("History is missing the video vote after a failed refetch");
            }
            if (up.getAttribute("aria-pressed") !== "true" || !up.classList.contains("thumb-selected")) {
              throw new Error("a failed refetch cleared the list's saved highlight");
            }
          }
        );
      } finally {
        global.__SMOKE_THUMBS = [];
      }
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
            },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the render tile"
          );
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
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the render tile"
          );
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
  await check(
    "History offers Delete on a failed clip",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      let deleted = null;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, id: "gen-failed", status: "failed", video_url: null, error: "boom" }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
          deleteGeneration: async (id) => { deleted = id; return { deleted: id }; },
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          // A failed row has no clip, so its actions live in the drawer like
          // every other tile's. Open it, then look for the control that keeps a
          // dead render from sitting in history forever.
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the failed tile"
          );
          const del = [...ctx.container.querySelectorAll("button")].find(
            (b) => (b.textContent || "").trim() === "Delete"
          );
          if (!del) {
            throw new Error(
              "no Delete on a failed render: the rail Delete never mounts " +
                "without a preview rail, so the row cannot be removed"
            );
          }
          await act(async () => {
            del.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
          });
          if (deleted !== "gen-failed") {
            throw new Error("the failed-row Delete does not reach the delete endpoint");
          }
        }
      );
    }
  );
  await check(
    "History keeps save and onward actions together and Delete apart from them",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, id: "gen-tiles", status: "completed" }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          const card = ctx.container.querySelector('[data-testid="history-card"]');
          await clickEl(
            ctx,
            card.querySelector('[data-testid="history-expand"]'),
            "expand the action test tile"
          );
          const group = ctx.container.querySelector('[role="group"][aria-label="Work with this render"]');
          if (!group) {
            throw new Error("the Work with this render action group is gone");
          }
          for (const label of ["Download", "Demo + CTA"]) {
            if (!group.textContent.includes(label)) {
              throw new Error(`the action bar lost ${label}`);
            }
          }
          // Delete destroys the file the drawer sits under. Sharing a row with
          // Download is how the two end up one slip apart.
          if (group.textContent.includes("Delete")) {
            throw new Error("Delete is back in the primary action row beside Download");
          }
          if (!card.textContent.includes("Delete")) {
            throw new Error("History lost Delete on a finished clip");
          }
        }
      );
    }
  );

  await check(
    "History offers a New variation entry into the studio draft",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, id: "gen-vary", studio_project_id: "proj-9", brand_name: "Test App", duration: 10 }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the render tile"
          );
          // The duplicate/variation endpoints were retired, so the entry is a
          // deep link into the draft project, not a new endpoint call: the
          // plan arrives intact and the recorded thumbs steer the next plan.
          const entry = [...ctx.container.querySelectorAll("a")].find(
            (a) => (a.textContent || "").trim() === "New variation"
          );
          if (!entry) {
            throw new Error(
              "History has no New variation entry on a finished clip. Without " +
                "it, recorded thumbs have no path into the next draft."
            );
          }
          const href = entry.getAttribute("href") || "";
          if (!href.includes("/create?project=proj-9")) {
            throw new Error(`the variation entry does not reopen the draft: ${href}`);
          }
        }
      );
    }
  );
  await check(
    "History surfaces Another take like this on a winner with a live draft",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, id: "gen-win", hook_line: "A winner", verdicts: { video: 1 }, tiktok_url: "https://www.tiktok.com/@founder/video/5", tiktok_views: 9000, studio_project_id: "wd1", brand_name: "Test App", duration: 10 }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
          getStudioProjects: async () => ({ projects: [{ id: "wd1" }] }),
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the winner tile"
          );
          await act(async () => {});
          const entry = [...ctx.container.querySelectorAll("a")].find(
            (a) => (a.textContent || "").trim() === "Another take like this"
          );
          if (!entry) {
            throw new Error("a winner has no Another take like this entry");
          }
          const href = entry.getAttribute("href") || "";
          if (!href.includes("/create?project=wd1")) {
            throw new Error(`the winner entry does not reopen the draft: ${href}`);
          }
        }
      );
    }
  );
  await check(
    "History never links a deleted draft on a winner",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [{ ...COMPLETED, id: "gen-ghost", hook_line: "A winner", verdicts: { video: 1 }, tiktok_url: "https://www.tiktok.com/@founder/video/5", tiktok_views: 9000, studio_project_id: "ghost", brand_name: "Test App", duration: 10 }],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
          getStudioProjects: async () => ({ projects: [{ id: "something-else" }] }),
        },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the winner tile"
          );
          await act(async () => {});
          const dead = [...ctx.container.querySelectorAll("a")].find((a) =>
            (a.getAttribute("href") || "").includes("project=ghost")
          );
          if (dead) {
            throw new Error(`a winner links a deleted draft: ${dead.getAttribute("href")}`);
          }
          const entry = [...ctx.container.querySelectorAll("a")].find(
            (a) => (a.textContent || "").trim() === "Another take like this"
          );
          if (entry) {
            throw new Error("a winner with no live draft still offers another take");
          }
        }
      );
    }
  );
await check(
    "History plays the durable copy the API signed, not a stripped path",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      // The row a founder actually opens: the durable copy is the media path,
      // and the API signs it on the way out. video_url still holds the
      // provider's link, which is what raw `r2_url || video_url` order can end
      // up reaching for, and what a stripped query string would leave behind.
      const signed = "/api/media/videos/gen-durable.mp4?exp=1791302519&sig=abc123";
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [
              {
                ...COMPLETED,
                id: "gen-durable",
                video_url: "https://openrouter.invalid/temporary.mp4",
                r2_url: "https://account.r2.cloudflarestorage.com/private/clip.mp4",
                playback_url: signed,
              },
            ],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
            },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          const player = ctx.container.querySelector("video");
          if (!player) {
            throw new Error(
              "no player for a clip whose durable copy the API signed: the History " +
                "preview is the screen this row exists for"
            );
          }
          const src = player.getAttribute("src") || "";
          if (!src.includes(signed)) {
            throw new Error(
              `the player is not using the signed durable copy the API handed it: ${src}`
            );
          }
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the durable copy tile"
          );
          const download = [...ctx.container.querySelectorAll("a[download]")].find((a) =>
            (a.textContent || "").trim() === "Download"
          );
          const expectedDownload = signed.replace(".mp4?", ".mp4/download?");
          if (!download || download.getAttribute("href") !== expectedDownload) {
            throw new Error(
              "the download must use the dedicated same-origin route and preserve the playback signature"
            );
          }
        }
      );
    }
  );

  await check(
    "History never plays the provider's temporary link",
    async (ctx) => {
      const GenerationHistory = load("pages/GenerationHistory.jsx").default;
      // A finished render whose durable save failed before any copy was made:
      // the only URL left is the provider's, which needs a bearer token the
      // browser cannot send. There is nothing here a player could load and
      // nothing a download could save, so offering either produces a dead
      // player beside a button that answers 401 — and it says the copy is
      // missing instead, with the one action that can repair it.
      await withApi(
        {
          getGenerationHistory: async () => ({
            generations: [
              {
                ...COMPLETED,
                id: "gen-provider-only",
                video_url: "https://openrouter.invalid/temporary.mp4",
                r2_url: null,
                // No fetchable copy at all: the server mints no playback URL
                // without saved bytes, so the row must carry none either.
                playback_url: null,
              },
            ],
          }),
          getAppProfiles: async () => ({ profiles: [PROFILE] }),
            },
        async () => {
          await mount(GenerationHistory, { onChanged: () => {} })(ctx);
          const player = ctx.container.querySelector("video");
          if (player) {
            throw new Error(
              "a player was mounted for a provider link the browser cannot fetch: " +
                player.getAttribute("src")
            );
          }
          // The repair lives in the drawer. Open it the way a founder would,
          // so the check covers the path that actually offers the button.
          await clickEl(
            ctx,
            ctx.container.querySelector('[data-testid="history-expand"]'),
            "expand the missing-copy tile"
          );
          const download = [...ctx.container.querySelectorAll("a")].find((a) =>
            (a.textContent || "").includes("Download video")
          );
          if (download) {
            throw new Error(
              "a download was offered for a link the browser cannot fetch, so it 401s"
            );
          }
          expectText(ctx, "No durable copy", "the row does not say the copy is missing");
          expectText(
            ctx,
            "Retry durable save",
            "the row offers no way to repair the missing copy"
          );
        }
      );
    }
  );

  await check("History retries its recovered source and waits for actual decoding", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    const initial = "/api/media/videos/retry.mp4?sig=old";
    const fresh = "/api/media/videos/retry.mp4?sig=fresh";
    const calls = [];
    await withApi({
      getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "retry", playback_url: initial }] }),
      getAppProfiles: async () => ({ profiles: [] }),
      retryGenerationStorage: async (id) => { calls.push(id); return { playback_url: fresh }; },
      getGeneration: async () => ({ ...COMPLETED, id: "retry", playback_url: fresh }),
    }, async () => {
      await mount(GenerationHistory, {})(ctx);
      await clickEl(
        ctx,
        ctx.container.querySelector('[data-testid="history-expand"]'),
        "expand the retry tile"
      );
      await act(async () => ctx.container.querySelector("video").dispatchEvent(new dom.window.Event("error")));
      expectText(ctx, "Retry durable save");
      expectAbsent(ctx, "Download it to view.", "a failed source is not a guaranteed download");
      await clickEl(ctx, ctx.container.querySelector('[data-testid="retry-storage-retry"]'), "retry storage");
      if (calls.join() !== "retry") throw new Error("retry did not target this video");
      const player = ctx.container.querySelector("video");
      if (!player || player.getAttribute("src") !== fresh) throw new Error("recovered playback URL was not loaded");
      expectText(ctx, "Checking recovered video", "endpoint success must not claim playback success");
      await act(async () => player.dispatchEvent(new dom.window.Event("loadeddata")));
      expectAbsent(ctx, "Checking recovered video", "decode success must finish the recovery check");
    });
  });

  await check("History surfaces recovery failure instead of claiming success", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi({
      getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "lost", video_url: null, r2_url: null, playback_url: null }] }),
      getAppProfiles: async () => ({ profiles: [] }),
      retryGenerationStorage: async () => { throw new Error("No remaining cloud or local copy. Re-upload your export."); },
    }, async () => {
      await mount(GenerationHistory, {})(ctx);
      await clickEl(
        ctx,
        ctx.container.querySelector('[data-testid="history-expand"]'),
        "expand the lost-copy tile"
      );
      await clickEl(ctx, ctx.container.querySelector('[data-testid="retry-storage-lost"]'), "retry lost video");
      expectText(ctx, "Re-upload your export", "recovery error must be visible");
      if (ctx.container.querySelector("video")) throw new Error("failed recovery cannot mount a player");
    });
  });

  // History owns the kit: the drawer and the details modal read the same
  // frozen object the output moment showed, and a pre-kit row shows nothing.
  await check("History shows the frozen post kit with copy buttons", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi({
      getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "kit-1", post_kit: POST_KIT }] }),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
    }, async () => {
      await mount(GenerationHistory)(ctx);
      // Collapsed means the clip and nothing else: the kit lives in the
      // drawer, so finding it on the closed tile means it leaked out.
      const card = ctx.container.querySelector('[data-testid="history-card"]');
      if (card.textContent.includes("Caption 1")) {
        throw new Error("the collapsed tile leaks the post kit");
      }
      await clickEl(
        ctx,
        ctx.container.querySelector('[data-testid="history-expand"]'),
        "expand the kit tile"
      );
      assertFrozenKit(ctx.container.querySelector('[data-testid="post-kit"]'), "History");
    });
  });

  await check("History shows no post copy for a render without a kit", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi({
      getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "nokit-1" }] }),
      getAppProfiles: async () => ({ profiles: [PROFILE] }),
    }, async () => {
      await mount(GenerationHistory)(ctx);
      await clickEl(
        ctx,
        ctx.container.querySelector('[data-testid="history-expand"]'),
        "expand the pre-kit tile"
      );
      if (ctx.container.querySelector('[data-testid="post-kit"]')) {
        throw new Error("a pre-kit render invents post copy in History");
      }
    });
  });

  await check("History's details modal shows the same frozen kit", async (ctx) => {
    const GenerationHistory = load("pages/GenerationHistory.jsx").default;
    await withApi(
      {
        getGenerationHistory: async () => ({ generations: [{ ...COMPLETED, id: "kitmodal-1", post_kit: POST_KIT }] }),
        getGeneration: async () => ({ ...COMPLETED, id: "kitmodal-1", post_kit: POST_KIT }),
        getAppProfiles: async () => ({ profiles: [PROFILE] }),
        },
      async () => {
        await mount(GenerationHistory)(ctx);
        await clickEl(ctx, ctx.container.querySelector('[data-testid="history-expand"]'), "open the drawer");
        await clickEl(
          ctx,
          ctx.container.querySelector('[data-testid="generation-details-button"]'),
          "open generation details"
        );
        const dialog = ctx.container.querySelector('[role="dialog"]');
        if (!dialog) throw new Error("the details modal did not open");
        assertFrozenKit(dialog.querySelector('[data-testid="post-kit"]'), "details modal");
      }
    );
  });

  // The export card reads the parent's frozen kit off the save response —
  // never a second fetch, never re-derived. jsdom has no MediaRecorder or
  // canvas.captureStream, so this pins the shape, not a driven export.
  await check(
    "the Demo + CTA export shows the inherited frozen kit",
    async () => {
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      for (const marker of [
        'import { PostKitSection } from "../components/PostKitSection"',
        "saved?.post_kit",
        "postKit={saved.post_kit}",
        "generationId={saved.id}",
      ]) {
        if (!src.includes(marker)) {
          throw new Error(
            `the export result lost a piece of the frozen kit: ${marker}. The ` +
              "save response already carries the parent's kit, so showing " +
              "nothing there means the founder leaves the export without post copy."
          );
        }
      }
      // The kit belongs to the render; anything the editor assembles here
      // would be a second, unfrozen copy.
      if (/post_kit:\s*\{|post_kit = \{|generate_post_kit|generatePostKit/i.test(src)) {
        throw new Error(
          "the export result builds its own kit instead of reading the " +
            "frozen one the save response carries."
        );
      }
    }
  );

await check(
    "a finished export puts itself in view",
    async () => {
      // jsdom has no layout, so this cannot assert that the page actually
      // scrolled. What it can pin is the shape that makes the scroll possible:
      // the card carries a ref, the ref is scrolled into view, and it happens
      // on the two transitions that matter. Without all three, tapping Export
      // looks like it did nothing and the natural next action is to press it
      // again.
      const src = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      for (const marker of [
        "const resultCardRef = useRef(null)",
        "ref={resultCardRef}",
        "scrollIntoView",
      ]) {
        if (!src.includes(marker)) {
          throw new Error(
            `the post-export scroll lost a piece: ${marker}. Tapping Export ` +
              "leaves the result below the fold with no indication it worked."
          );
        }
      }
      // scrollIntoView, not window.scrollTo: the card lives in the preview
      // column, which is its own scroll container at lg+, so scrolling the
      // window moves nothing where the user is looking.
      if (/window\.scroll(To|IntoView)/.test(src)) {
        throw new Error(
          "the post-export scroll targets the window, but the Export ready card " +
            "is inside the preview column's own scroll container."
        );
      }
      // Both transitions: the recording landing, and the History save landing.
      // Only the first leaves the "In History" badge and View in History unseen.
      // Anchored to the call itself, not the bare method name: the name also occurs
      // in a comment explaining the choice, and searching for it there slices
      // the file from the wrong place and finds somebody else's array.
      const scrollAt = src.indexOf("card.scrollIntoView(");
      const tail = src.slice(scrollAt, scrollAt + 600);
      const depMatch = tail.match(/\}, \[([^\]]*)\]\);/);
      if (!depMatch || !depMatch[1].includes("result") || !depMatch[1].includes("saved?.id")) {
        throw new Error(
          "the post-export scroll must fire on both the recording landing and " +
            "the History save landing, or the confirmation is never revealed. " +
            `dependency array found: ${depMatch ? depMatch[1].trim() : "none"}`
        );
      }
      // It must not fight the founder: reduced motion honoured, and the card
      // has to be laid out before it is measured.
      if (!src.includes("useReducedMotion")) {
        throw new Error(
          "the post-export scroll ignores prefers-reduced-motion. A programmatic " +
            "smooth scroll cannot be switched off by a Tailwind motion-reduce variant."
        );
      }
      if (!/requestAnimationFrame/.test(src)) {
        throw new Error(
          "the post-export scroll does not wait a frame, so it can measure the " +
            "card before it has been laid out."
        );
      }
    }
  );

  await check("export reads source audio samples independently of preview mute", async () => {
    const src = fs.readFileSync(path.join(SRC, "demoCta", "exportTikTok.js"), "utf8");
    for (const marker of ["new AudioSampleSink(audioTrack)", "sample.trim(start, end)", "trimmed.setTimestamp", "audioSource.add(trimmed)", "audio will not be silently removed"]) {
      if (!src.includes(marker)) throw new Error(`missing direct-audio guarantee: ${marker}`);
    }
    if (/createMediaElementSource|captureStream|createGain/.test(src)) throw new Error("export audio depends on preview playback again");
  });
await check(
    "both phone renderers share one fit, and neither paints a black void",
    async () => {
      // The arithmetic itself is unit-tested in check-frontend-logic against
      // demoCta/fit.js. What is pinned HERE is the thing that let the bug exist:
      // two renderers, two copies of the same maths, one of which implemented
      // "fill" and one of which did not. So this asserts there is only one copy.
      const editor = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx"),
        "utf8"
      );
      const drawSrc = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "usePreviewLoop.js"),
        "utf8"
      );
      const hand = fs.readFileSync(
        path.join(__dirname, "..", "src", "demoCta", "handView.js"),
        "utf8"
      );
      for (const [name, src] of [["usePreviewLoop", drawSrc], ["handView", hand]]) {
        if (!src.includes("fitVideoToScreen(")) {
          throw new Error(
            `${name} does not use the shared fitVideoToScreen. A private copy of ` +
              "this arithmetic is how fill worked in one view and did nothing in the other."
          );
        }
        if (/videoFit === "contain"\s*\n?\s*\?/.test(src) || /Math\.(min|max)\(sw \/ vw, sh \/ vh\)/.test(src)) {
          throw new Error(
            `${name} has its own inline fit arithmetic again. Keep it in fit.js.`
          );
        }
      }
      // The screen behind the footage was hard-coded to #000, which is what
      // turned any uncovered strip into a black band that read as a broken
      // picture rather than as a deliberate pad.
      for (const [name, src] of [["DemoCtaEditor", editor], ["handView", hand]]) {
        if (/fillStyle = "#000";\s*\n\s*ctx\.fillRect\(s[xy], s[xy], sw, sh\)/.test(src)) {
          throw new Error(
            `${name} paints the screen pure black again. An uncovered strip has to ` +
              "read as wallpaper, not as a blank picture."
          );
        }
      }
      // And the founder needs to be able to tell the three modes apart: "fill"
      // read as a synonym for "cover" is the whole reason this went unnoticed.
      if (!/VIDEO_FIT_HINTS/.test(editor)) {
        throw new Error(
          "the Video crop group does not explain what each mode does. Fill and " +
            "Cover look identical until you have seen them side by side."
        );
      }
      for (const mode of ["cover", "contain", "fill"]) {
        if (!new RegExp(`${mode}: "`).test(editor.slice(editor.indexOf("VIDEO_FIT_HINTS")))) {
          throw new Error(`VIDEO_FIT_HINTS is missing the "${mode}" entry.`);
        }
      }
      // The hand-view branch once read `palette` above its declaration. A
      // const in the temporal dead zone throws on ANY access — `?.` guards a
      // nullish binding, not an undeclared one — so the first hand-mode frame
      // died before rescheduling the loop and the canvas froze on the old
      // view. The declaration must precede both renderer branches. It reads
      // the per-segment backdrop (`lookBg`), so a sage upload can follow a
      // lavender base in one export.
      const declAt = drawSrc.indexOf("const palette = COLOR_PALETTES[lookBg]");
      if (declAt === -1) {
        throw new Error("the shared palette declaration is gone from the draw path");
      }
      // Strip comments and the import line before looking: the explainer above
      // the declaration names the old `palette` access in prose, and the
      // module import mentions drawHandView — neither is a live read, but a
      // naive slice(0, declAt) match treats both as one and fails forever.
      const beforeDecl = drawSrc
        .slice(0, declAt)
        .replace(/\/\/[^\n]*/g, "")
        .replace(/\/\*[\s\S]*?\*\//g, "")
        .split("\n")
        .filter((line) => !/^\s*import\b/.test(line))
        .join("\n");
      const early = /palette\?\.\w+/.exec(beforeDecl);
      if (early && beforeDecl.includes("drawHandView(")) {
        throw new Error(
          "the hand-view branch reads `palette` above its declaration. A const " +
            "in the temporal dead zone throws even through `?.`, killing the " +
            "draw loop on the first hand-mode frame."
        );
      }
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
/**
 * Move to a step by its pill.
 *
 * Two flushes, not one. Entering Review mounts effects that read the project
 * from the API, so the state they set lands on the next act — with a single
 * flush that update escapes the check entirely and React reports an unwrapped
 * update, which is a real async effect leaking past the assertion that is
 * supposed to be observing it.
 */
async function openStep(ctx, label) {
  const pill = stepPill(ctx, label);
  await act(async () => {
    pill.dispatchEvent(new dom.window.MouseEvent("click", { bubbles: true }));
  });
  await act(async () => {});
  await act(async () => {});
}

/**
 * Pass the angle gate the way a founder does.
 *
 * Landing on Audience & template shows one Generate CTA, never the list. Clicking
 * it reveals a pre-generated set for free (no endpoint call) or generates
 * fresh when there is none. Tests that assert on rows call this first; tests
 * that assert on the gate itself do not.
 */
async function passAngleGate(ctx) {
  const step = ctx.container.querySelector('[data-testid="audience-goal-step"]');
  const cta = step && step.querySelector('[data-testid="generate-angles-button"]');
  if (cta) await clickEl(ctx, cta);
}

/**
 * Reach the ranked templates the way the workflow now requires.
 *
 * The video goal is required, and the merged step refuses to show a ranked
 * list without one. Angle, goal, templates and photo share one screen now,
 * so picking the angle and goal IS arriving: no second step to open after.
 * The fixture enters via the same angle-first suggested-goal control that
 * the founder uses before the list below ranks itself.
 */
async function openTemplateStep(ctx) {
  await openStep(ctx, "Audience & template");
  // The pre-generated six wait behind the Generate CTA: pass it the way a
  // founder does (free reveal, no endpoint call) before picking.
  await passAngleGate(ctx);
  const angleButton = [...ctx.container.querySelectorAll('[data-testid="audience-goal-step"] button')]
    .find((button) => button.textContent.includes(ANGLE.label));
  if (!angleButton) throw new Error("the audience step has no selectable audience angle");
  await clickEl(ctx, angleButton);
  const goalButton = ctx.container.querySelector('[data-testid="recommended-goal-address_user_problem"]');
  if (!goalButton) throw new Error("the audience step has no recommended goal control");
  await clickEl(ctx, goalButton, "no recommended goal control");
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
 * Open a Radix menu the way its own trigger does, and return the item inside.
 *
 * Menu content is portaled onto document.body, so the check's container cannot
 * see it, and jsdom has no pointer pipeline to press the trigger with: the
 * trigger's ArrowDown path is the open route that works here. Opening it
 * matters — a check that reached for an item without opening would be reading
 * markup no founder can get to, and force-mounting the content in every render
 * would leave an invisible menu sitting over the page.
 *
 * Returns null when the item is missing, so a check can assert an item is
 * absent from a menu that did open.
 */
async function openMenu(ctx, triggerTestId, itemTestId) {
  const trigger = ctx.container.querySelector(`[data-testid="${triggerTestId}"]`);
  if (!trigger) throw new Error(`no ${triggerTestId} to open the menu from`);
  await act(async () => {
    trigger.dispatchEvent(
      new dom.window.KeyboardEvent("keydown", { key: "ArrowDown", bubbles: true })
    );
  });
  await act(async () => {});
  return dom.window.document.querySelector(`[data-testid="${itemTestId}"]`);
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


