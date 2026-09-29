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

function loadModule() {
  const source = fs.readFileSync(SRC, "utf8");
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
    throw new Error("found no top-level declarations in " + SRC);
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

console.log("\nparseExtendChoice — the silent NaN");
check("'target' is preserved", L.parseExtendChoice("target") === "target");
check("'5' becomes 5", L.parseExtendChoice("5") === 5);
check("3 becomes 3", L.parseExtendChoice(3) === 3);
check("garbage falls back, never NaN", L.parseExtendChoice("abc") === L.DEFAULT_EXTEND);
check("empty falls back", L.parseExtendChoice("") === L.DEFAULT_EXTEND);
check("negative falls back", L.parseExtendChoice(-3) === L.DEFAULT_EXTEND);
const parsed = L.parseExtendChoice("target");
check("the result is always finite or the sentinel",
  parsed === "target" || Number.isFinite(parsed), parsed);

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

console.log("\ncanFillToTarget — offering an option that cannot work");
check("20s remaining on Seedance (30 max) can fill", L.canFillToTarget(20, SEEDANCE) === true);
check("20s remaining on MiniMax (15 max) cannot", L.canFillToTarget(20, MINIMAX) === false);
check("15s remaining on MiniMax can", L.canFillToTarget(15, MINIMAX) === true);
check("nothing remaining cannot", L.canFillToTarget(0, SEEDANCE) === false);
check("unknown capability does not offer it",
  L.canFillToTarget(20, { min_duration: 4 }) === false);

console.log("\nresolveExtendRequest — what actually goes on the wire");
check("+5s on Seedance requests 5 with no trim",
  JSON.stringify(L.resolveExtendRequest(5, 20, SEEDANCE)) === JSON.stringify({ seconds: 5, trimTo: 0 }),
  L.resolveExtendRequest(5, 20, SEEDANCE));
check("+3s on Seedance requests 3 and records a trim",
  JSON.stringify(L.resolveExtendRequest(3, 20, SEEDANCE)) === JSON.stringify({ seconds: 3, trimTo: 3 }),
  L.resolveExtendRequest(3, 20, SEEDANCE));
check("'+3s' from a select string behaves the same",
  JSON.stringify(L.resolveExtendRequest("3", 20, SEEDANCE)) === JSON.stringify({ seconds: 3, trimTo: 3 }),
  L.resolveExtendRequest("3", 20, SEEDANCE));
// The bug: "Fill to target" used to become NaN and then null on the wire.
const fill = L.resolveExtendRequest("target", 12, SEEDANCE);
check("fill to target on a 12s remainder requests 12",
  JSON.stringify(fill) === JSON.stringify({ seconds: 12, trimTo: 0 }), fill);
check("fill to target is never NaN", Number.isFinite(fill.seconds), fill);
check("fill to target beyond the ceiling is refused, not guessed",
  L.resolveExtendRequest("target", 20, MINIMAX) === null,
  L.resolveExtendRequest("target", 20, MINIMAX));
// Whatever comes out must survive JSON, or the server silently substitutes.
for (const choice of [3, 5, 8, 10, "target", "junk"]) {
  const r = L.resolveExtendRequest(choice, 12, SEEDANCE);
  const round = JSON.parse(JSON.stringify(r));
  check(`"${choice}" survives a JSON round trip`,
    round !== null && Number.isFinite(round.seconds), round);
}

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
if (failures.length === 0) {
  console.log("All frontend length/intent logic behaves correctly.");
} else {
  console.log(`${failures.length} FAILURE(S):`);
  failures.forEach((f) => console.log(`  - ${f}`));
}
process.exit(failures.length === 0 ? 0 : 1);
