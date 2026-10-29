// Draft parity: every field the Demo + CTA editor snapshots for autosave must
// restore, and vice versa.
//
// The edit session autosaves `editSnapshot` wholesale (debounced, plus flush
// on hide/unload), and `restoreEdit` re-applies a stored draft on load. A key
// added to one side but not the other silently stops that field surviving a
// reload — the exact "my edit didn't save" report this check prevents. It
// fails loudly naming the offending key and direction.
//
// Media objects (baseMedia/appendMedia) restore through restoreMedia rather
// than the setters map, and the zoom draft is stored under the `framing` key
// and restored via setEditFraming(edit.framing) — both are pinned below so a
// refactor that inlines them has to update this contract, not slip past it.
//
// Run: node scripts/check-demo-cta-draft.cjs
const fs = require("fs");
const path = require("path");

const EDITOR = path.join(__dirname, "..", "src", "demoCta", "DemoCtaEditor.jsx");
const src = fs.readFileSync(EDITOR, "utf8");

let failed = 0;
function fail(label, detail) {
  console.log(`  [FAIL] ${label}`);
  if (detail !== undefined) console.log(`         got: ${JSON.stringify(detail)}`);
  failed++;
}
function pass(label) {
  console.log(`  [PASS] ${label}`);
}

const snapshotBlock = (src.match(/const editSnapshot = \{([\s\S]*?)\n  \};/) || [])[1];
const settersBlock = (src.match(/const setters = \{([\s\S]*?)\n    \};/) || [])[1];
if (!snapshotBlock) fail("editSnapshot literal is present and parseable");
if (!settersBlock) fail("restoreEdit setters map is present and parseable");
if (!snapshotBlock || !settersBlock) {
  console.log(`${failed} MISSING BLOCK(S)`);
  process.exit(1);
}

// Shorthand (`hookText,`) and keyed (`framing: editFraming`) entries alike.
// A value is never a key: `editFraming` follows a colon, so only identifiers
// in key position (after `{`/`,` and before `:`/`,`) count.
const snapshotKeys = [
  ...new Set([
    ...[...snapshotBlock.matchAll(/[{,]\s*(\w+)\s*(?=:)/g)].map((m) => m[1]),
    ...[...snapshotBlock.matchAll(/(?:^|[{,])\s*(\w+)\s*(?=,)/gm)].map((m) => m[1]),
  ]),
];
const setterKeys = [
  ...settersBlock.matchAll(/(\w+): set\w+/g),
].map((m) => m[1]);

// The two documented aliases: stored under one name, restored by another path.
const ALIASES = {
  framing: "setEditFraming(edit.framing)",
  baseMedia: "restoreMedia(edit.baseMedia",
  appendMedia: "restoreMedia(edit.appendMedia",
};
for (const [key, ref] of Object.entries(ALIASES)) {
  if (!snapshotKeys.includes(key)) {
    fail(`snapshot stores the '${key}' field`, snapshotKeys);
  } else if (!src.includes(ref)) {
    fail(`restore path for '${key}' is intact (${ref})`);
  } else {
    pass(`aliased field '${key}' is stored and restored (${ref})`);
  }
}

const aliasKeys = new Set(Object.keys(ALIASES));
const unrestored = snapshotKeys.filter(
  (key) => !aliasKeys.has(key) && !setterKeys.includes(key),
);
if (unrestored.length > 0) {
  fail("every snapshotted field has a restore setter", unrestored);
} else {
  pass(`all ${snapshotKeys.length} snapshotted fields restore`);
}

const unsnapshotted = setterKeys.filter((key) => !snapshotKeys.includes(key));
if (unsnapshotted.length > 0) {
  fail("every restore setter has a snapshotted field", unsnapshotted);
} else {
  pass(`all ${setterKeys.length} restore setters are snapshotted`);
}

console.log(failed === 0 ? "DRAFT PARITY HOLDS" : `${failed} PARITY BREAK(S)`);
process.exit(failed === 0 ? 0 : 1);
