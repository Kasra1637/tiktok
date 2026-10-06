/**
 * Asserts the pure helpers in src/lib/videoLength.js against the values the API
 * actually returns.
 *
 * Why this exists: `npm run build` type-checks and lints but never evaluates a
 * comparison at runtime, and the backend suite cannot see frontend code at all.
 * That gap is exactly how `project.extend_intent === 0` survived against a
 * boolean return (the toggle could never turn off) and `Number("target")`
 * survived to become a silent 5s request.
 *
 * The source is read and evaluated directly rather than imported, because the
 * frontend package is CommonJS to Node and the module uses ESM exports.
 * Evaluating the real file means the assertions cannot drift from what ships.
 *
 * The videoLength section was rewritten when a video became one render: the
 * extend lock, the coverage counter and the multi-pass trim math it asserted are
 * gone from the product, and the checks that protected real properties were
 * re-pointed at the checks that protect the same properties now. The specific
 * substitutions are called out where they are made.
 *
 * Run: node scripts/check-frontend-logic.cjs
 */
const fs = require("fs");
const path = require("path");
const vm = require("vm");

const SRC = path.resolve(__dirname, "..", "src", "lib", "videoLength.js");

const failures = [];
function check(label, condition, detail) {
  if (condition) {
    console.log(`  [PASS] ${label}`);
  } else {
    console.log(`  [FAIL] ${label}`);
    if (detail !== undefined) console.log(`         got: ${JSON.stringify(detail)}`);
    failures.push(label);
  }
}

function loadModule(src = SRC, extraGlobals = {}) {
  const source = fs.readFileSync(src, "utf8");
  // Strip the ESM export keywords so the file can be evaluated as a script, and
  // re-expose whatever it declared. Only the export syntax changes; the code
  // under test is evaluated verbatim, so the assertions cannot drift from what
  // ships.
  const stripped = source.replace(/^export\s+/gm, "");
  const names = new Set();
  const decl = /^(?:const|let|var|function|class)\s+([A-Za-z_$][\w$]*)/gm;
  let m;
  while ((m = decl.exec(stripped))) names.add(m[1]);
  if (names.size === 0) {
    throw new Error("found no top-level declarations in " + src);
  }
  const expose = `\n;module.exports = { ${[...names].join(", ")} };`;
  // `process` is in the sandbox because app modules read `process.env.PUBLIC_URL`
  // to build asset paths, and CRA inlines that at build time. Handing over the
  // real object keeps the evaluated code identical to what ships; an undefined
  // PUBLIC_URL is exactly what a plain dev server sees.
  const sandbox = {
    module: { exports: {} },
    exports: {},
    process: { env: { ...process.env } },
    // Test-only globals (a stubbed MediaRecorder, say). The shipped code reads
    // them as bare identifiers, which resolve against this sandbox rather than
    // Node's global — so stubbing `global.X` in the test would silently test
    // nothing. Anything passed here is explicit and visible at the call site.
    ...extraGlobals,
  };
  vm.createContext(sandbox);
  vm.runInContext(stripped + expose, sandbox, { filename: SRC });
  return sandbox.module.exports;
}

const L = loadModule();
// MiniMax H3 is the only studio-eligible model, and it is the only one these
// helpers are predicting against. WIDE is a hypothetical longer-range
// capability, kept so the ceiling math is asserted against two shapes instead
// of one — which is the point: the helpers must read the ceiling off the
// capability rather than hard-code 15.
const WIDE = { min_duration: 4, max_duration: 30 };
const MINIMAX = { min_duration: 5, max_duration: 15 };

console.log("=".repeat(70));
console.log("frontend/src/lib/videoLength.js");
console.log("=".repeat(70));

// ---------------------------------------------------------------------------
// DEFAULT_DURATION
// ---------------------------------------------------------------------------
// The property the old `a fresh wizard starts on a single-pass length` check
// protected, at the level it now lives. The founder no longer picks a length, so
// there is no "default the user starts on" — there is a fallback the product
// uses when neither the project nor the template states one, and it has to be a
// length the one eligible model can actually render in a single pass.
console.log("\nDEFAULT_DURATION - the fallback, not a user choice");
check("it is 10s", L.DEFAULT_DURATION === 10, L.DEFAULT_DURATION);
check("the fallback is inside the only eligible model's single pass",
  !L.exceedsSinglePass(L.DEFAULT_DURATION, MINIMAX), L.DEFAULT_DURATION);
check("the fallback is also inside a longer model's single pass",
  !L.exceedsSinglePass(L.DEFAULT_DURATION, WIDE), L.DEFAULT_DURATION);
check("it is a real number, not a string the template math would swallow",
  Number.isFinite(L.DEFAULT_DURATION), typeof L.DEFAULT_DURATION);

console.log("\nDEFAULT_DURATION - the old helper it replaced is really gone");
// Not a style rule. `resolveExtendLock` and `plannedCoverage` were the two
// exports that only existed to govern repeated extension, and both read fields
// the server deleted. Left in place they would be callable, and the first person
// to call one would get a confident null or a number computed from
// `max_planned_index`, which no longer exists on any strategy.
for (const retired of ["resolveExtendLock", "plannedCoverage", "readExtendIntent", "highestSegmentIndex"]) {
  check(`${retired} is no longer exported`, L[retired] === undefined, L[retired]);
}

console.log("\n" + "-".repeat(70));
console.log("The hook is a boundary, not a clip");
console.log("-".repeat(70));

// The replacement for `readExtendIntent`, which read a field the server deleted.
// Same failure shape it was written for — a raw SQLite integer leaking through
// where a boolean was expected — except the field is now a length, and the
// server's answer to an out-of-range value is to CLAMP it rather than reject
// the save. A UI that trusted its own stored number could therefore display a
// 9s hook the server had already moved to 4s, and nothing downstream would
// catch it.
console.log("\nclampHookSeconds - the boundary the backend will actually use");
check("3s is left alone", L.clampHookSeconds(3) === 3, L.clampHookSeconds(3));
check("2s is left alone", L.clampHookSeconds(2) === 2, L.clampHookSeconds(2));
check("4s is left alone", L.clampHookSeconds(4) === 4, L.clampHookSeconds(4));
check("5s is pulled down to the ceiling", L.clampHookSeconds(5) === 4, L.clampHookSeconds(5));
check("9s is pulled down to the ceiling, not refused",
  L.clampHookSeconds(9) === 4, L.clampHookSeconds(9));
check("1s is pulled up to the floor", L.clampHookSeconds(1) === 2, L.clampHookSeconds(1));
check("a negative length becomes 0, which means 'follow the template'",
  L.clampHookSeconds(-4) === 0, L.clampHookSeconds(-4));
// Zero is the sentinel that means "decide from the template", so it must not be
// clamped UP to the floor. A 2 would silently override every template's own
// hook length, which is the one thing the field is allowed to defer on.
check("0 stays 0 rather than becoming the floor",
  L.clampHookSeconds(0) === 0, L.clampHookSeconds(0));
check("a missing value is 0, not NaN", L.clampHookSeconds(undefined) === 0);
check("null is 0, not NaN", L.clampHookSeconds(null) === 0);
check("garbage is 0, not NaN", L.clampHookSeconds("junk") === 0, L.clampHookSeconds("junk"));
check("a legacy string integer still clamps",
  L.clampHookSeconds("9") === 4, L.clampHookSeconds("9"));
check("a 2.6s boundary rounds to a whole second",
  L.clampHookSeconds(2.6) === 3, L.clampHookSeconds(2.6));
check("the floor and ceiling are the numbers the server uses",
  L.MIN_HOOK_SECONDS === 2 && L.MAX_HOOK_SECONDS === 4,
  { min: L.MIN_HOOK_SECONDS, max: L.MAX_HOOK_SECONDS });
check("the default boundary is inside the range",
  L.clampHookSeconds(L.DEFAULT_HOOK_SECONDS) === L.DEFAULT_HOOK_SECONDS,
  L.DEFAULT_HOOK_SECONDS);

console.log("\n" + "-".repeat(70));
console.log("The length is computed, so it is read rather than chosen");
console.log("-".repeat(70));

// New surface: this is the read-only statement the "Audience & goal" step
// renders. The property it has to hold is that every branch produces a usable
// number, because a NaN here does not fail a render — it prints "NaN seconds" in
// the one sentence telling the founder what they are about to get.
console.log("\nreadPieceSeconds - the project's own number wins");
const TEMPLATE_T = { id: "t1", default_duration: 12 };
check("a project at 10s reads 10s", L.readPieceSeconds({ duration_seconds: 10 }, TEMPLATE_T) === 10);
check("a project at 15s reads 15s even against a 12s template",
  L.readPieceSeconds({ duration_seconds: 15 }, TEMPLATE_T) === 15);
// Before a project exists the template's declared length is not a guess, it is
// literally what create_studio_project will seed the project from.
check("with no project the template's declared length is used",
  L.readPieceSeconds(null, TEMPLATE_T) === 12, L.readPieceSeconds(null, TEMPLATE_T));
check("with neither, the library default is used",
  L.readPieceSeconds(null, null) === L.DEFAULT_DURATION);
check("a project with no length yet falls through to the template",
  L.readPieceSeconds({ duration_seconds: 0 }, TEMPLATE_T) === 12);
check("a template with no declared length falls through to the default",
  L.readPieceSeconds(null, { id: "t1" }) === L.DEFAULT_DURATION);
check("a null project and a null template are safe",
  L.readPieceSeconds(null, null) === L.DEFAULT_DURATION);
check("no arguments at all is safe", L.readPieceSeconds() === L.DEFAULT_DURATION);
check("a string length is coerced, not concatenated",
  L.readPieceSeconds({ duration_seconds: "12" }, null) === 12,
  L.readPieceSeconds({ duration_seconds: "12" }, null));
check("garbage lengths never reach the copy",
  L.readPieceSeconds({ duration_seconds: "junk" }, TEMPLATE_T) === 12,
  L.readPieceSeconds({ duration_seconds: "junk" }, TEMPLATE_T));
for (const bad of [null, 0, -5, "x", undefined, NaN]) {
  const got = L.readPieceSeconds({ duration_seconds: bad }, TEMPLATE_T);
  check(`a length of ${JSON.stringify(bad)} still yields a positive number`,
    Number.isFinite(got) && got > 0, got);
}

console.log("\n" + "-".repeat(70));
console.log("The replacement for the extend lock");
console.log("-".repeat(70));

// The property `resolveExtendLock` was asserting — "a remainder beyond one pass
// is null, not guessed" — is real and still load-bearing. What changed is who
// enforces it: the extend lock refused to offer a second step, and there is no
// second step, so the endpoint refuses the whole request with a 400. The UI's
// job is now to say so before the click rather than to compute a step.
console.log("\nsinglePassCeiling - read off the model, never assumed");
check("15s on MiniMax", L.singlePassCeiling(MINIMAX) === 15, L.singlePassCeiling(MINIMAX));
check("30s on a longer model", L.singlePassCeiling(WIDE) === 30, L.singlePassCeiling(WIDE));
check("an unknown capability is 0, not a hard-coded 15",
  L.singlePassCeiling(null) === 0, L.singlePassCeiling(null));
check("a missing capability is 0", L.singlePassCeiling({}) === 0);
check("a non-numeric ceiling is 0", L.singlePassCeiling({ max_duration: "lots" }) === 0);
check("a zero or negative ceiling is 0", L.singlePassCeiling({ max_duration: 0 }) === 0);

console.log("\nexceedsSinglePass - the refusal the endpoint will make");
check("10s on MiniMax fits", L.exceedsSinglePass(10, MINIMAX) === false);
check("15s on MiniMax is exactly the ceiling and still fits",
  L.exceedsSinglePass(15, MINIMAX) === false);
check("16s on MiniMax does not fit", L.exceedsSinglePass(16, MINIMAX) === true);
check("30s on MiniMax does not fit", L.exceedsSinglePass(30, MINIMAX) === true);
check("30s on a 30s model fits", L.exceedsSinglePass(30, WIDE) === false);
check("31s on a 30s model does not", L.exceedsSinglePass(31, WIDE) === true);
// Every length the facets endpoint offers is one render, which is the invariant
// that replaced the old "a length that needs more than one render says so up
// front" label check. A new supported length that needs two passes would break
// the product, so it is asserted here against the real set.
for (const d of [8, 10, 12, 15]) {
  check(`${d}s is one render on the only eligible model`,
    L.exceedsSinglePass(d, MINIMAX) === false, d);
}
// Fail OPEN on an unknown ceiling. The one thing this must never do is block a
// render the model would have accepted: a hard-coded fallback would tell a
// founder their 20s video is impossible when the only studio-eligible model was
// swapped for a longer one, which is a false refusal, and the server is the
// authority anyway.
check("an unknown ceiling never blocks a render",
  L.exceedsSinglePass(60, null) === false, L.exceedsSinglePass(60, null));
check("garbage against an unknown ceiling never blocks",
  L.exceedsSinglePass("junk", {}) === false);
check("a zero length never trips the guard", L.exceedsSinglePass(0, MINIMAX) === false);
check("a negative length never trips the guard", L.exceedsSinglePass(-9, MINIMAX) === false);

console.log("\n" + "-".repeat(70));
console.log("Two sections, in render order");
console.log("-".repeat(70));

console.log("\nsectionSplit - the two numbers the founder is shown");
const split = L.sectionSplit(10, 3);
check("a 10s piece with a 3s hook splits 3 / 7",
  JSON.stringify(split) === JSON.stringify({ hookSeconds: 3, middleSeconds: 7 }), split);
check("the two sections always add up to the piece",
  split.hookSeconds + split.middleSeconds === 10, split);
// The regression a naive subtraction would ship: a hand-edited or legacy
// boundary longer than the piece produces a negative middle, which reads on
// screen as though the product had already filmed footage it does not have.
check("a boundary longer than the piece never yields a negative middle",
  L.sectionSplit(8, 12).middleSeconds === 0, L.sectionSplit(8, 12));
check("a boundary longer than the piece is itself pulled back to it",
  L.sectionSplit(8, 12).hookSeconds === 8, L.sectionSplit(8, 12));
check("a zero boundary leaves the whole piece as middle",
  JSON.stringify(L.sectionSplit(10, 0)) === JSON.stringify({ hookSeconds: 0, middleSeconds: 10 }),
  L.sectionSplit(10, 0));
check("a piece with no boundary is all middle, not NaN",
  L.sectionSplit(10, null).middleSeconds === 10, L.sectionSplit(10, null));
check("a missing piece is all zeroes, never NaN",
  JSON.stringify(L.sectionSplit(null, 3)) === JSON.stringify({ hookSeconds: 0, middleSeconds: 0 }),
  L.sectionSplit(null, 3));
check("garbage on both sides is all zeroes, never NaN",
  JSON.stringify(L.sectionSplit("x", "y")) === JSON.stringify({ hookSeconds: 0, middleSeconds: 0 }),
  L.sectionSplit("x", "y"));
for (const [piece, hook] of [[10, 3], [8, 2], [15, 4], [8, 12], [10, 0]]) {
  const s = L.sectionSplit(piece, hook);
  check(`[${piece}, ${hook}] survives a JSON round trip`,
    Number.isFinite(s.hookSeconds) && Number.isFinite(s.middleSeconds), s);
}

console.log("\n" + "-".repeat(70));
console.log("plannedSections - the two the render actually produces");
console.log("-".repeat(70));

// The replacement for the `plannedCoverage` checks. Those answered "how many more
// beats can this finite plan produce", which was a question about a chain. The
// property that still matters is sharper: whatever the strategy says, the review
// surface shows exactly two sections, in render order, and never a role the
// product does not generate.
const TWO = [
  { index: 0, role: "hook", seconds: 3, goal: "stop the scroll", script: "You do not have a focus problem.", action: "look up" },
  { index: 1, role: "middle", seconds: 7, goal: "develop it, stop at the reach", script: "You have too many lists.", action: "count on fingers" },
];
const shown = L.plannedSections({ segments: TWO });
check("a well-formed strategy shows two sections", shown.length === 2, shown.length);
check("the first is the hook", shown[0].role === "hook", shown[0].role);
check("the second is the middle", shown[1].role === "middle", shown[1].role);
check("the seconds survive", shown[0].seconds === 3 && shown[1].seconds === 7, shown);
check("the goal, script and action survive",
  shown[1].goal === "develop it, stop at the reach" && shown[1].action === "count on fingers",
  shown[1]);
check("the roles come from position, not from the model",
  L.plannedSections({ segments: [{ role: "cta" }, { role: "fix" }] }).map((s) => s.role).join() === "hook,middle",
  L.plannedSections({ segments: [{ role: "cta" }, { role: "fix" }] }).map((s) => s.role));
// A strategy saved by a model that remembered the old eight-beat shape is the
// case that matters. Truncating alone is not enough — the eighth beat's role is
// "cta", and the render prompt reads the role.
const LEGACY = [
  { role: "hook", seconds: 5, goal: "hook it" },
  { role: "problem", seconds: 6, goal: "state it" },
  { role: "fix", seconds: 7, goal: "solve it" },
  { role: "cta", seconds: 4, goal: "close it" },
  { role: "cta", seconds: 4, goal: "close harder" },
];
const fromLegacy = L.plannedSections({ segments: LEGACY });
check("an old eight-beat strategy is shown as two sections", fromLegacy.length === 2, fromLegacy.length);
check("no retired role survives", fromLegacy.every((s) => s.role === "hook" || s.role === "middle"),
  fromLegacy.map((s) => s.role));
check("a legacy 'cta' goal is not rendered as a close of its own",
  !fromLegacy.some((s) => s.role === "cta"), fromLegacy.map((s) => s.role));
check("the two sections take the first two beats, in order",
  fromLegacy[0].goal === "hook it" && fromLegacy[1].goal === "state it",
  fromLegacy.map((s) => s.goal));
check("no strategy at all still renders two rows",
  L.plannedSections({}).length === 2, L.plannedSections({}));
check("a null strategy still renders two rows", L.plannedSections(null).length === 2);
check("no arguments at all still renders two rows", L.plannedSections().length === 2);
check("a non-array segments value is safe",
  L.plannedSections({ segments: "junk" }).length === 2, L.plannedSections({ segments: "junk" }));
check("a shorter list is padded, not truncated to one",
  L.plannedSections({ segments: [{ role: "hook", seconds: 3 }] }).length === 2);
check("the padded middle is empty rather than undefined",
  L.plannedSections({ segments: [{ role: "hook", seconds: 3 }] })[1].goal === "");
check("a missing middle is present with zero seconds",
  L.plannedSections({ segments: [{ role: "hook", seconds: 3 }] })[1].seconds === 0);
check("a non-dict beat does not throw",
  L.plannedSections({ segments: [null, "junk"] }).length === 2);
check("missing seconds are 0, not NaN",
  L.plannedSections({ segments: [{}, {}] }).every((s) => Number.isFinite(s.seconds) &&
    Number.isFinite(s.seconds)),
  L.plannedSections({ segments: [{}, {}] }).map((s) => s.seconds));
check("garbage seconds are 0, not NaN",
  L.plannedSections({ segments: [{ seconds: "junk" }] })[0].seconds === 0,
  L.plannedSections({ segments: [{ seconds: "junk" }] })[0].seconds);
check("every section is index-labelled in render order",
  shown[0].index === 0 && shown[1].index === 1, shown.map((s) => s.index));

console.log("\n" + "=".repeat(70));
console.log("frontend/src/lib/profileSelection.js");
console.log("=".repeat(70));

const P = loadModule(path.resolve(__dirname, "..", "src", "lib", "profileSelection.js"));

// The regression: the studio's first step used to render only approved
// profiles, so a profile the founder had already created but not yet approved
// was invisible. Five apps and two approvals showed two, with no hint that the
// other three existed. These assert that nothing is ever silently dropped.
console.log("\npartitionProfiles - nothing may be dropped");
const MIXED = [
  { id: "a", brand_name: "Approved App", status: "approved" },
  { id: "b", brand_name: "Waiting One", status: "draft" },
  { id: "c", brand_name: "Waiting Two", status: "metadata_ready" },
  { id: "d", brand_name: "Also Approved", status: "approved" },
];
const part = P.partitionProfiles(MIXED);
check("every profile lands in exactly one bucket",
  part.approved.length + part.unapproved.length === MIXED.length,
  { approved: part.approved.length, unapproved: part.unapproved.length });
check("approved holds only approved", part.approved.every((p) => p.status === "approved"),
  part.approved.map((p) => p.status));
check("unapproved holds none of the approved",
  part.unapproved.every((p) => p.status !== "approved"),
  part.unapproved.map((p) => p.status));
check("both approved profiles are selectable",
  part.approved.map((p) => p.id).join() === "a,d", part.approved.map((p) => p.id));
check("the two drafts are reported, not hidden",
  part.unapproved.map((p) => p.id).join() === "b,c", part.unapproved.map((p) => p.id));
check("a profile never appears in both buckets",
  !part.approved.some((a) => part.unapproved.some((u) => u.id === a.id)));

console.log("\nisProfileSelectable - the gate itself stays strict");
// An unrecognised status must fail closed. If a new status were ever treated as
// approved, a video could be built on facts nobody reviewed.
check("approved is selectable", P.isProfileSelectable({ status: "approved" }) === true);
for (const status of ["draft", "metadata_ready", "pending", "", null, undefined, "Approved"]) {
  check(`status ${JSON.stringify(status)} is NOT selectable`,
    P.isProfileSelectable({ status }) === false, status);
}
check("a missing profile is not selectable", P.isProfileSelectable(null) === false);
check("gate and partition never disagree",
  MIXED.every((p) => P.isProfileSelectable(p) === (part.approved.includes(p))));

console.log("\ndescribeUnapprovedCount - the count a founder reads");
check("zero says nothing", P.describeUnapprovedCount(0) === "", P.describeUnapprovedCount(0));
check("one is singular", P.describeUnapprovedCount(1) === "1 profile waiting for approval",
  P.describeUnapprovedCount(1));
check("three is plural", P.describeUnapprovedCount(3) === "3 profiles waiting for approval",
  P.describeUnapprovedCount(3));
check("a nonsense count says nothing", P.describeUnapprovedCount(NaN) === "");

console.log("\nprofileLabel - never a blank row");
check("a real name is used", P.profileLabel({ brand_name: "Zest" }) === "Zest");
check("a missing name is not blank", P.profileLabel({}) === "Untitled app");
check("a whitespace name is not blank", P.profileLabel({ brand_name: "   " }) === "Untitled app",
  P.profileLabel({ brand_name: "   " }));
check("a null profile is not blank", P.profileLabel(null) === "Untitled app");

console.log("\ndescribeEmptySelection - names the profiles that are waiting");
check("with none waiting it says what to do next",
  P.describeEmptySelection([]) === "Research an app and approve the profile before creating a video.",
  P.describeEmptySelection([]));
const oneWaiting = P.describeEmptySelection([{ brand_name: "Wait", status: "draft" }]);
check("with one waiting it names it", oneWaiting.includes("Wait"), oneWaiting);
check("with one waiting it counts correctly", oneWaiting.includes("1 profile"), oneWaiting);
const twoWaiting = P.describeEmptySelection(MIXED);
check("with several waiting it names them all",
  twoWaiting.includes("Waiting One") && twoWaiting.includes("Waiting Two"), twoWaiting);
check("with several waiting it does not claim an approved app is waiting",
  !twoWaiting.includes("Approved App"), twoWaiting);
check("the empty state agrees with the partition",
  P.describeEmptySelection(MIXED) === P.describeEmptySelection(part.unapproved.map((p, i) => ({
    ...p, id: String(i),
  }))), "same set, different ids");

// The sidebar's Asset Library link carries no profile, so this resolution is
// the only thing between that page and "Choose an App Profile first" with no
// way to choose one.
console.log("\nresolveActiveProfileId - explicit sources win, in order");
const MIXED2 = [
  { id: "recent-approved", brand_name: "Recent Approved", status: "approved" },
  { id: "older-approved", brand_name: "Older Approved", status: "approved" },
  { id: "draft-only", brand_name: "Draft Only", status: "draft" },
];
check("the studio's prop is never overridden by a default",
  P.resolveActiveProfileId({ propId: "from-wizard", profiles: MIXED2 }) === "from-wizard");
check("a route param beats a remembered default",
  P.resolveActiveProfileId({ paramId: "from-url", rememberedId: "older-approved", profiles: MIXED2 })
  === "from-url");
check("?profile= beats a remembered default",
  P.resolveActiveProfileId({ queryId: "from-query", rememberedId: "older-approved", profiles: MIXED2 })
  === "from-query");
check("the prop beats the param",
  P.resolveActiveProfileId({ propId: "a", paramId: "b", queryId: "c" }) === "a");
check("an explicit id is trusted while profiles are still loading",
  P.resolveActiveProfileId({ propId: "not-loaded-yet", profiles: [] }) === "not-loaded-yet");

console.log("\nresolveActiveProfileId - remembered, but only if it still exists");
// The stale case: the id refers to an app from a previous session.
check("a remembered id that still exists is used",
  P.resolveActiveProfileId({ rememberedId: "older-approved", profiles: MIXED2 })
  === "older-approved");
check("a remembered id that is gone is ignored, not used",
  P.resolveActiveProfileId({ rememberedId: "deleted-app", profiles: MIXED2 })
  === "recent-approved",
  P.resolveActiveProfileId({ rememberedId: "deleted-app", profiles: MIXED2 }));
check("whitespace is not treated as an id",
  P.resolveActiveProfileId({ propId: "   ", profiles: MIXED2 }) === "recent-approved");
check("a remembered id with whitespace still matches",
  P.resolveActiveProfileId({ rememberedId: "  older-approved  ", profiles: MIXED2 })
  === "older-approved");

console.log("\nresolveActiveProfileId - never empty while an app exists");
check("the newest approved is the default",
  P.resolveActiveProfileId({ profiles: MIXED2 }) === "recent-approved");
// The API orders by updated_at DESC, so position 0 is the newest. This function
// must not re-sort, or the two would disagree about "newest".
check("newest means position 0, as the API ordered it",
  P.resolveActiveProfileId({ profiles: [...MIXED2].reverse() }) === "older-approved");
check("one unapproved app is still usable, not a dead end",
  P.resolveActiveProfileId({ profiles: [{ id: "solo-draft", status: "draft" }] }) === "solo-draft");
check("a mixture prefers approved over a draft",
  P.resolveActiveProfileId({ profiles: [{ id: "d", status: "draft" }, { id: "a", status: "approved" }] })
  === "a");
check("no profiles resolves to empty, which shows the editor link",
  P.resolveActiveProfileId({ profiles: [] }) === "");
check("a missing profiles array is safe", P.resolveActiveProfileId({}) === "");
check("a non-array profiles value is safe",
  P.resolveActiveProfileId({ profiles: "nonsense" }) === "");
check("no arguments at all is safe", P.resolveActiveProfileId() === "");

console.log("\n" + "=".repeat(70));
console.log("frontend/src/lib/authRecovery.js");
console.log("=".repeat(70));

const A = loadModule(path.resolve(__dirname, "..", "src", "lib", "authRecovery.js"));

// The regression: a 401 fell through to page-level `.catch(() => setX([]))`,
// so a dead session rendered as "no apps" — an existing profile looked
// deleted. The interceptor retries once with a fresh token; these pin the two
// decisions around that retry.
console.log("\nshouldRetryWithFreshToken - exactly one retry, only for 401");
check("a first-time 401 retries",
  A.shouldRetryWithFreshToken({ status: 401, alreadyRetried: false }) === true);
check("an already-retried 401 does not loop",
  A.shouldRetryWithFreshToken({ status: 401, alreadyRetried: true }) === false);
for (const status of [400, 403, 404, 500, null, undefined]) {
  check(`status ${JSON.stringify(status)} never retries`,
    A.shouldRetryWithFreshToken({ status, alreadyRetried: false }) === false);
}
check("no arguments never retries", A.shouldRetryWithFreshToken() === false);

console.log("\nshouldForceSignIn - dead session goes to sign-in, nothing else does");
check("dead session with credentials goes to sign-in",
  A.shouldForceSignIn({ attemptedAuth: true, clerkConfigured: true, pathname: "/create" }) === true);
check("a credential-less 401 never redirects (public page, backend problem)",
  A.shouldForceSignIn({ attemptedAuth: false, clerkConfigured: true, pathname: "/create" }) === false);
check("no-auth mode never redirects (no sign-in exists to go to)",
  A.shouldForceSignIn({ attemptedAuth: true, clerkConfigured: false, pathname: "/create" }) === false);
check("already on /sign-in never redirects (reload loop)",
  A.shouldForceSignIn({ attemptedAuth: true, clerkConfigured: true, pathname: "/sign-in" }) === false);
check("already on /sign-up never redirects",
  A.shouldForceSignIn({ attemptedAuth: true, clerkConfigured: true, pathname: "/sign-up" }) === false);
check("a sub-path of sign-in counts as the auth page",
  A.shouldForceSignIn({ attemptedAuth: true, clerkConfigured: true, pathname: "/sign-in/sso-callback" }) === false);
check("no arguments never redirects", A.shouldForceSignIn() === false);
check("a missing pathname is not an auth page",
  A.shouldForceSignIn({ attemptedAuth: true, clerkConfigured: true }) === true);

console.log("\n" + "=".repeat(70));
console.log("frontend/src/lib/templateRequirements.js");
console.log("=".repeat(70));

const T = loadModule(path.resolve(__dirname, "..", "src", "lib", "templateRequirements.js"));

// Step 2 names what a template needs; step 3 attaches it. Without a
// have/missing state the founder holds the requirement in memory across
// steps. These pin the matching rule behind the have/missing rows.
console.log("\nrequiredAssetStatus - the draft's kinds decide, nothing else");
const ATTACHED = [{ kind: "screenshot" }, { kind: "Character_Reference" }];
let rows = T.requiredAssetStatus(["character_reference", "screenshot", "logo"], ATTACHED);
check("matching ignores case and whitespace",
  rows[0].have === true && rows[1].have === true && rows[2].have === false, rows);
check("template order is preserved",
  rows.map((r) => r.kind).join() === "character_reference,screenshot,logo");
check("an attached asset with no kind never matches",
  T.requiredAssetStatus(["screenshot"], [{}, { kind: null }])[0].have === false);
check("a blank requirement is named but never met",
  (() => { const r = T.requiredAssetStatus(["  "], ATTACHED)[0]; return r.kind === "" && r.have === false; })());
check("non-array required is safe", T.requiredAssetStatus(null, ATTACHED).join() === "");
check("non-array attached is safe",
  T.requiredAssetStatus(["screenshot"], "nonsense")[0].have === false);
check("no arguments is safe", T.requiredAssetStatus().join() === "");

console.log("\nallRequiredAssetsAttached - the jump link's condition");
check("all attached", T.allRequiredAssetsAttached(["screenshot"], ATTACHED) === true);
check("one missing",
  T.allRequiredAssetsAttached(["screenshot", "logo"], ATTACHED) === false);
check("no requirements is vacuously complete",
  T.allRequiredAssetsAttached([], ATTACHED) === true);
check("no attachments meets nothing",
  T.allRequiredAssetsAttached(["screenshot"], []) === false);

console.log("\nblocking requirements - only a missing face stops generation");
check("an attached reference never blocks",
  T.blockingRequirements(["character_reference"], ATTACHED).length === 0);
check("a missing reference does block",
  T.blockingRequirements(["character_reference"], []).map((r) => r.kind).join()
    === "character_reference");
check("the blocker is the face even among retired kinds",
  // Retired kinds can still sit on old rows: they never block here because
  // the backend refuses those projects outright before generation.
  T.blockingRequirements(["character_reference", "screenshot"], [{ kind: "screenshot" }])
    .map((r) => r.kind).join() === "character_reference");
check("matching is still case-insensitive when blocking",
  T.blockingRequirements(["Character_Reference"], []).length === 1);
check("nothing required means nothing blocks",
  T.blockingRequirements([], []).length === 0);
check("a blank requirement never blocks",
  T.blockingRequirements([""], []).length === 0);
check("a non-array requirement never blocks",
  T.blockingRequirements(null, []).length === 0);

/**
 * Native Product Demo + CTA engine math.
 *
 * The editor's zoom split — live sliders during preview, locked keyframes
 * during export — is the one behavior here that fails silently: get it wrong
 * and the preview lies about what the export will bake. These pin the pure
 * helpers the canvas loop reads, plus the export naming the file carries into
 * History, against the values the standalone app produced.
 */
const ZOOM_SRC = path.resolve(__dirname, "..", "src", "demoCta", "zoom.js");
const DEMO_CONST_SRC = path.resolve(__dirname, "..", "src", "demoCta", "constants.js");
const Z = loadModule(ZOOM_SRC);
const DC = loadModule(DEMO_CONST_SRC);

const LIVE = { scale: 2, offX: 10, offY: -5, handZoom: 1.5, handPanX: 0.2, handPanY: -0.1 };

// No keyframes: the sliders are the truth, preview or export.
check("no keyframes means live sliders during preview",
  JSON.stringify(Z.getEffectiveZoom({ keyframes: [], live: LIVE, videoTime: 3, isExporting: false }))
    === JSON.stringify({ vScale: 2, vOffX: 10, vOffY: -5, hZoom: 1.5, hPanX: 0.2, hPanY: -0.1 }));
check("no keyframes means live sliders during export",
  Z.getEffectiveZoom({ keyframes: [], live: LIVE, videoTime: 3, isExporting: true }).vScale === 2);

const KF = [
  { id: "a", time: 2, scale: 1.5, offX: 1, offY: 2, handZoom: 1, handPanX: 0, handPanY: 0 },
  { id: "b", time: 5, scale: 2.5, offX: 3, offY: 4, handZoom: 2, handPanX: 0.5, handPanY: 0.5 },
];

// Before the first lock: preview shows the sliders so adjustments are visible,
// export falls back to defaults so the file is deterministic.
check("before the first keyframe the preview shows live sliders",
  Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 1, isExporting: false }).vScale === 2);
check("before the first keyframe the export uses defaults",
  JSON.stringify(Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 1, isExporting: true }))
    === JSON.stringify({ vScale: 1, vOffX: 0, vOffY: 0, hZoom: 1, hPanX: 0, hPanY: 0 }));

// Between locks: the active lock, rigidly, in both modes.
check("between keyframes the active lock applies",
  Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 3, isExporting: false }).vScale === 1.5
    && Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 3, isExporting: true }).vOffX === 1);
check("the second lock takes over at its timestamp",
  Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 6, isExporting: true }).vScale === 2.5);

// Past the last lock: preview returns to the sliders, export keeps the lock.
check("past the last keyframe the preview returns to live sliders",
  Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 9, isExporting: false }).vScale === 2);
check("past the last keyframe the export keeps the last lock",
  Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 9, isExporting: true }).vScale === 2.5
    && Z.getEffectiveZoom({ keyframes: KF, live: LIVE, videoTime: 9, isExporting: true }).hPanX === 0.5);

// Capture: a lock within 0.05s updates in place, otherwise it appends.
const captured = Z.captureZoomLock(KF, 2.02, { scale: 9, offX: 0, offY: 0, handZoom: 1, handPanX: 0, handPanY: 0 });
check("a near-duplicate timestamp updates the lock in place",
  captured.length === 2 && captured.some((k) => k.id === "a" && k.scale === 9));
const appended = Z.captureZoomLock(KF, 3, { scale: 9, offX: 0, offY: 0, handZoom: 1, handPanX: 0, handPanY: 0 });
check("a distinct timestamp appends a lock",
  appended.length === 3 && appended.some((k) => k.time === 3));
check("sorting never mutates the input",
  (() => {
    const unsorted = [KF[1], KF[0]];
    const sorted = Z.sortKeyframes(unsorted);
    return sorted[0].id === "a" && unsorted[0].id === "b";
  })());
check("removing a lock keeps the rest",
  Z.removeZoomKeyframe(KF, "a").length === 1 && Z.removeZoomKeyframe(KF, "a")[0].id === "b");

// Timeline ticks aim for roughly 6–10 visible marks.
check("tick intervals follow duration",
  Z.tickInterval(90) === 10 && Z.tickInterval(40) === 5 && Z.tickInterval(20) === 2
    && Z.tickInterval(8) === 1 && Z.tickInterval(3) === 0.5);
check("time formats as m:ss.d",
  DC.formatTime(0) === "0:00.0" && DC.formatTime(65.25) === "1:05.2" && DC.formatTime(9.99) === "0:09.9");

// Export naming carries the render facts and no product branding.
check("export filenames stay neutral and unbranded",
  DC.buildExportFilename({ device: "s24", preset: "tiktok", width: 1080, height: 1920, ext: "mp4" })
    === "demo-cta-s24-tiktok-1080x1920.mp4");
check("export filenames carry no superseded app branding",
  !/mockreel|phoneframe|hookforge/i.test(
    DC.buildExportFilename({ device: "s24", preset: "tiktok", width: 1080, height: 1920, ext: "mp4" })));
check("export filenames sanitize hostile parts",
  DC.buildExportFilename({ device: "S24 Ultra!", preset: "", width: 1080.7, height: 1920.2, ext: "webm" })
    === "demo-cta-s24-ultra-preset-1081x1920.webm");
check("mp4 is detected by prefix, everything else is webm",
  DC.extensionForMime('video/mp4;codecs="avc1.42E01F,mp4a.40.2"') === "mp4"
    && DC.extensionForMime("video/webm;codecs=vp9") === "webm");

// MIME selection without a recorder fails closed rather than guessing.
check("no recorder means no mime rather than a guess",
  DC.selectExportMime({ transparent: false, exportFormat: "auto" }) === null);

// Candidate order with a recorder that claims everything: High Level 4.0
// first, because Baseline Level 3.1 cannot encode a 1080x1920 canvas and the
// encoder rejects it at record time even though isTypeSupported passes it.
// The stub goes through loadModule's sandbox — the shipped code reads the bare
// `MediaRecorder` identifier, which resolves against the vm context, so a stub
// on Node's global would silently test nothing.
const DC_REC = loadModule(DEMO_CONST_SRC, {
  MediaRecorder: { isTypeSupported: () => true },
});
check("mp4 candidates lead with a 1080p-capable level",
  (() => {
    const list = DC_REC.supportedExportMimes({ transparent: false, exportFormat: "auto" });
    return list[0] === 'video/mp4;codecs="avc1.640028,mp4a.40.2"'
      && list.indexOf('video/mp4;codecs="avc1.42E01F,mp4a.40.2"') > 0
      && list[list.length - 1] === "video/webm"
      && DC_REC.selectExportMime({ transparent: false, exportFormat: "auto" }) === list[0];
  })());
check("transparent and webm choices still prefer webm first",
  (() => {
    const t = DC_REC.supportedExportMimes({ transparent: true, exportFormat: "auto" });
    const w = DC_REC.supportedExportMimes({ transparent: false, exportFormat: "webm" });
    return t.every((m) => m.startsWith("video/webm")) && w[0].startsWith("video/webm");
  })());
check("a recorder that supports nothing yields no candidates",
  DC_REC.supportedExportMimes
    && loadModule(DEMO_CONST_SRC, { MediaRecorder: { isTypeSupported: () => false } })
      .supportedExportMimes({ transparent: false, exportFormat: "auto" }).length === 0);

// A broken recording must never become a download. These pin the pure half of
// that gate: the size floor and the container sniff that run before a blob
// gets a URL, a filename, or a History row.
check("recordings under 32KB are not plausible",
  DC.isPlausibleRecordingSize(0) === false
    && DC.isPlausibleRecordingSize(32767) === false
    && DC.isPlausibleRecordingSize(32768) === true
    && DC.isPlausibleRecordingSize(10 * 1024 * 1024) === true
    && DC.isPlausibleRecordingSize(NaN) === false);
check("an mp4 recording opens with an ftyp box",
  DC.sniffRecordingContainer(new Uint8Array([0x00, 0x00, 0x00, 0x20, 0x66, 0x74, 0x79, 0x70])) === "mp4");
check("a webm recording opens with the EBML header",
  DC.sniffRecordingContainer(new Uint8Array([0x1a, 0x45, 0xdf, 0xa3, 0x93, 0x42, 0x82, 0x88])) === "webm");
check("a truncated header sniffs as nothing, not as a guess",
  DC.sniffRecordingContainer(new Uint8Array([0x00, 0x00, 0x00])) === null
    && DC.sniffRecordingContainer(new Uint8Array(8)) === null
    && DC.sniffRecordingContainer(new Uint8Array([0x3c, 0x21, 0x44, 0x4f, 0x43, 0x54, 0x59, 0x50])) === null);

// Catalog parity with the standalone app: nothing dropped in the port.
check("the device catalog survived the port",
  DC.DEVICES.length === 7 && DC.DEVICES[0].id === "s24" && DC.DEVICES[6].id === "lg_g8");
check("the preset catalog survived the port",
  DC.PRESETS.length === 6 && DC.PRESETS[0].id === "tiktok" && DC.PRESETS[5].id === "source");
check("backgrounds, animations, environments and accents survived the port",
  DC.BACKGROUNDS.length === 8 && DC.ANIMATIONS.length === 6
    && DC.ENVIRONMENTS.length === 5 && DC.ACCENT_SWATCHES.length === 4);
check("defaults match the standalone app",
  DC.DEFAULTS.device === "s24" && DC.DEFAULTS.preset === "tiktok" && DC.DEFAULTS.bg === "lavender"
    && DC.DEFAULTS.anim === "float" && DC.DEFAULTS.scale === 0.82
    && DC.DEFAULTS.hookDuration === 1.8 && DC.DEFAULTS.ctaDuration === 2
    && DC.DEFAULTS.overlayAccent === "#c8ff2e" && DC.DEFAULTS.viewMode === "floating");
check("slider ranges match the standalone app",
  DC.RANGES.scale.min === 0.3 && DC.RANGES.videoScale.max === 3
    && DC.RANGES.handPan.step === 0.005 && DC.RANGES.screen.step === 0.001
    && DC.RANGES.hookDuration.min === 0.8 && DC.RANGES.ctaDuration.max === 5);

// Onboarding shows itself once. The rule lives in a pure module precisely so it
// can be asserted as behaviour: a tour auto-opens the first time its route is
// reached, never again on its own, and is always re-openable by hand.
const ST = loadModule(path.resolve(__dirname, "..", "src", "lib", "onboarding", "seenTours.js"));
function fakeStorage(initial) {
  const data = new Map(Object.entries(initial || {}));
  return {
    getItem: (k) => (data.has(k) ? data.get(k) : null),
    setItem: (k, v) => data.set(k, String(v)),
    removeItem: (k) => data.delete(k),
  };
}
check("a tour nobody has opened is not seen",
  ST.hasSeenTour({}, "create") === false && ST.hasSeenTour({ create: 1 }, "create") === true);
check("marking a tour seen persists it and is idempotent",
  (() => {
    const s = fakeStorage();
    const once = ST.markTourSeen(s, {}, "create");
    if (!ST.hasSeenTour(once, "create")) return false;
    // Identity on the second call, so a state holder can skip re-rendering.
    return ST.markTourSeen(s, once, "create") === once;
  })());
check("a seen tour survives a reload through storage",
  (() => {
    const s = fakeStorage();
    ST.markTourSeen(s, {}, "create");
    return ST.hasSeenTour(ST.readSeenTours(s), "create");
  })());
check("seen state is per tour, so one page does not suppress another",
  (() => {
    const s = fakeStorage();
    const seen = ST.markTourSeen(s, {}, "create");
    return ST.hasSeenTour(seen, "create") && !ST.hasSeenTour(seen, "brand");
  })());
// The failure that matters: unreadable state must read as EMPTY, never as
// "everything seen". Reading it as full suppresses every tour forever and the
// only symptom is onboarding that never appears again.
check("corrupt or unexpected stored state reads as nothing seen",
  ["not json at all", "[1,2,3]", '"a string"', "42", "null", "[]"].every((raw) => {
    const s = fakeStorage({ [ST.SEEN_TOURS_STORAGE_KEY]: raw });
    return Object.keys(ST.readSeenTours(s)).length === 0;
  }));
check("storage that throws still lets the tour be treated as unseen, then seen",
  (() => {
    const hostile = {
      getItem() { throw new Error("denied"); },
      setItem() { throw new Error("denied"); },
    };
    let seen = ST.readSeenTours(hostile);
    if (ST.hasSeenTour(seen, "create")) return false;
    // Must not throw: the tour opens, it just opens again next visit.
    seen = ST.markTourSeen(hostile, seen, "create");
    return ST.hasSeenTour(seen, "create");
  })());

// How a clip is fitted to the phone screen. The bug these exist for: "fill" was
// unreachable in the floating phone because the only branch was
// `contain ? min : max`, so the one control whose purpose is "no bars" silently
// behaved like cover. The hand-held phone implemented it. These assert the
// behaviour numerically so the two renderers cannot disagree again.
const FIT = loadModule(path.resolve(__dirname, "..", "src", "demoCta", "fit.js"));
// A 9:16 clip in a real s24 screen area: taller than the clip, so cover crops
// the sides, contain pads top and bottom, and fill stretches.
const SCREEN = { screenW: 916, screenH: 2083 };
const CLIP = { videoW: 1080, videoH: 1920 };
const fitOf = (fit, extra = {}) =>
  FIT.fitVideoToScreen({ fit, ...CLIP, ...SCREEN, scale: 1, ...extra });

check("fill stretches to the screen box instead of behaving like cover",
  (() => {
    const f = fitOf("fill");
    // The whole point: exactly the screen, no gap, aspect ignored.
    return f.dw === SCREEN.screenW && f.dh === SCREEN.screenH;
  })());
check("fill is genuinely different from cover for a mismatched aspect",
  (() => {
    // If these were equal, the bug is back. Cover overflows on width; fill does
    // not overflow at all.
    const cover = fitOf("cover");
    const fill = fitOf("fill");
    return cover.dw > SCREEN.screenW && fill.dw === SCREEN.screenW;
  })());
check("cover fills the screen and contain shows the whole clip",
  (() => {
    const cover = fitOf("cover");
    const contain = fitOf("contain");
    const coversBoth = cover.dw >= SCREEN.screenW && cover.dh >= SCREEN.screenH;
    const containsBoth = contain.dw <= SCREEN.screenW && contain.dh <= SCREEN.screenH;
    return coversBoth && containsBoth && contain.dw === SCREEN.screenW;
  })());
check("only contain leaves the screen uncovered",
  (() => {
    const gap = (fit) =>
      FIT.leavesUncoveredScreen({ fit, ...CLIP, ...SCREEN, scale: 1 });
    return gap("cover") === false && gap("fill") === false && gap("contain") === true;
  })());
check("an unknown fit mode falls back to cover rather than breaking",
  (() => {
    const weird = fitOf("nonsense");
    return weird.dw === fitOf("cover").dw && weird.dh === fitOf("cover").dh;
  })());
check("zoom applies in every mode, and below 1 re-opens a gap in cover",
  (() => {
    const coverZoomedOut = fitOf("cover", { scale: 0.85 });
    const fillZoomedOut = fitOf("fill", { scale: 0.85 });
    const zoomed = coverZoomedOut.dw < fitOf("cover").dw;
    return zoomed
      && fillZoomedOut.dw === SCREEN.screenW * 0.85
      && FIT.leavesUncoveredScreen({ fit: "cover", ...CLIP, ...SCREEN, scale: 0.85 }) === true;
  })());
check("missing dimensions produce no box rather than NaN geometry",
  [{}, { videoW: 0, videoH: 1920 }, { videoW: 1080, videoH: 0 },
   { ...CLIP, screenW: 0 }, { ...CLIP, screenH: 0 }].every((bad) =>
    FIT.fitVideoToScreen({ fit: "cover", scale: 1, ...bad }) === null));
check("a nonsense zoom is treated as 1 rather than blanking the screen",
  (() => {
    const zero = fitOf("cover", { scale: 0 });
    const nan = fitOf("cover", { scale: NaN });
    return zero.dw === fitOf("cover").dw && nan.dw === fitOf("cover").dw;
  })());

console.log("\n" + "=".repeat(70));
if (failures.length === 0) {
  console.log("All frontend length/section logic behaves correctly.");
} else {
  console.log(`${failures.length} FAILURE(S):`);
  failures.forEach((f) => console.log(`  - ${f}`));
}
process.exit(failures.length === 0 ? 0 : 1);
