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

function loadModule(src = SRC) {
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
  const sandbox = { module: { exports: {} }, exports: {} };
  vm.createContext(sandbox);
  vm.runInContext(stripped + expose, sandbox, { filename: SRC });
  return sandbox.module.exports;
}

const L = loadModule();
const SEEDANCE = { min_duration: 4, max_duration: 30 };
const MINIMAX = { min_duration: 5, max_duration: 15 };

console.log("=".repeat(70));
console.log("frontend/src/lib/videoLength.js");
console.log("=".repeat(70));

console.log("\nreadExtendIntent — the toggle that could never turn off");
// The API returns a real boolean (server.py _public_project -> != 0).
check("true stays on", L.readExtendIntent({ extend_intent: true }) === true);
check("false reads as OFF", L.readExtendIntent({ extend_intent: false }) === false);
// The regression, stated as a test: the old code was `=== 0 ? false : true`.
check("false is not mistaken for 0", L.readExtendIntent({ extend_intent: false }) !== true);
check("unset defaults to on", L.readExtendIntent({}) === true);
check("null project defaults to on", L.readExtendIntent(null) === true);
// A legacy row that somehow still carries an int must also read correctly.
check("legacy integer 0 reads as OFF", L.readExtendIntent({ extend_intent: 0 }) === false);
check("legacy integer 1 reads as ON", L.readExtendIntent({ extend_intent: 1 }) === true);

console.log("\nresolveExtendLock — computed, recommended, locked");
check("next planned beat resolves straight through",
  JSON.stringify(L.resolveExtendLock(6, 20, SEEDANCE)) === JSON.stringify({ seconds: 6, planned: 6, render: 6, trimTo: 0 }),
  L.resolveExtendLock(6, 20, SEEDANCE));
check("a remainder smaller than the beat wins (automatic fill)",
  JSON.stringify(L.resolveExtendLock(8, 3, SEEDANCE)) === JSON.stringify({ seconds: 3, planned: 3, render: 4, trimTo: 3 }),
  L.resolveExtendLock(8, 3, SEEDANCE));
check("a 3s beat on Seedance records its trim",
  JSON.stringify(L.resolveExtendLock(3, 0, SEEDANCE)) === JSON.stringify({ seconds: 3, planned: 3, render: 4, trimTo: 3 }),
  L.resolveExtendLock(3, 0, SEEDANCE));
check("no plan and no remainder is null, never NaN",
  L.resolveExtendLock(0, 0, SEEDANCE) === null,
  L.resolveExtendLock(0, 0, SEEDANCE));
check("a remainder beyond one pass is null, not guessed",
  L.resolveExtendLock(0, 20, MINIMAX) === null,
  L.resolveExtendLock(0, 20, MINIMAX));
check("garbage inputs are null, never NaN",
  L.resolveExtendLock("junk", null, SEEDANCE) === null,
  L.resolveExtendLock("junk", null, SEEDANCE));
// Whatever comes out must survive JSON, or the server silently substitutes.
for (const args of [[6, 20], [8, 3], [3, 0]]) {
  const r = L.resolveExtendLock(args[0], args[1], SEEDANCE);
  const round = JSON.parse(JSON.stringify(r));
  check(`[${args}] survives a JSON round trip`,
    round !== null && Number.isFinite(round.seconds), round);
}

console.log("\nresolveLength");
check("3s on Seedance renders 4 and trims to 3",
  JSON.stringify(L.resolveLength(3, SEEDANCE)) === JSON.stringify({ target: 3, render: 4, trimTo: 3 }),
  L.resolveLength(3, SEEDANCE));
check("4s on Seedance needs no trim",
  JSON.stringify(L.resolveLength(4, SEEDANCE)) === JSON.stringify({ target: 4, render: 4, trimTo: 0 }),
  L.resolveLength(4, SEEDANCE));
check("4s on MiniMax renders 5 and trims to 4",
  JSON.stringify(L.resolveLength(4, MINIMAX)) === JSON.stringify({ target: 4, render: 5, trimTo: 4 }),
  L.resolveLength(4, MINIMAX));
check("a 0 or missing target never becomes a 1s clip",
  L.resolveLength(0, SEEDANCE).render === 4, L.resolveLength(0, SEEDANCE));

console.log("\nplannedCoverage");
check("a fresh 8-beat plan with 1 segment reports 7",
  L.plannedCoverage([{ segment_index: 0 }], { max_planned_index: 7 }) === 7,
  L.plannedCoverage([{ segment_index: 0 }], { max_planned_index: 7 }));
check("3 segments used of 8 reports 5",
  L.plannedCoverage([{ segment_index: 0 }, { segment_index: 1 }, { segment_index: 2 }],
    { max_planned_index: 7 }) === 5);
check("an old strategy with no coverage field is unknown, not zero",
  L.plannedCoverage([{ segment_index: 0 }], {}) === null,
  L.plannedCoverage([{ segment_index: 0 }], {}));
check("never goes negative",
  L.plannedCoverage([{ segment_index: 0 }], { max_planned_index: 2 }) === 2);

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

console.log("\n" + "=".repeat(70));
if (failures.length === 0) {
  console.log("All frontend length/intent logic behaves correctly.");
} else {
  console.log(`${failures.length} FAILURE(S):`);
  failures.forEach((f) => console.log(`  - ${f}`));
}
process.exit(failures.length === 0 ? 0 : 1);
