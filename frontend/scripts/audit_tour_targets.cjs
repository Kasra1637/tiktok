// One-off audit: every tour target selector must match a data-testid that
// actually exists in the app source. Prints MISS per missing testid.
//
// The tour definitions themselves are excluded from the search corpus: they
// contain every id by definition, so including them would pass vacuously.
// Dynamic testids built by template (e.g. data-testid={`view-mode-${id}`})
// are resolved by prefix: the template must exist in app source and the
// suffix must appear as a quoted literal there too.
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..");
const TOUR_FILE = path.join(root, "src/lib/onboarding/tours.js");

const src = fs.readFileSync(TOUR_FILE, "utf8");
// Only testids referenced by step targets — never tour keys or labels.
// A target may hold an OR list of selectors; each data-testid counts.
const ids = [
  ...new Set(
    [...src.matchAll(/data-testid=\"([^\"]+)\"/g)].map((m) => m[1])
  ),
];

const files = [];
(function walk(d) {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f);
    const s = fs.statSync(p);
    if (s.isDirectory()) walk(p);
    else if (/\.(jsx?|cjs)$/.test(f)) files.push(p);
  }
})(path.join(root, "src"));
let app = "";
for (const f of files) {
  if (path.resolve(f) === path.resolve(TOUR_FILE)) continue;
  app += fs.readFileSync(f, "utf8") + "\n";
}

// Prefixes of template-built testids, e.g. [`view-mode-`] from
// data-testid={`view-mode-${id}`}.
const dynamicPrefixes = [
  ...new Set(
    [...app.matchAll(/data-testid=\{`([\w-]+)-\$\{/g)].map((m) => m[1])
  ),
];

let missing = 0;
for (const id of ids) {
  if (app.includes(`"${id}"`) || app.includes(`'${id}'`)) continue;
  // Dynamic id: template prefix exists and the suffix is a quoted literal
  // in app source (e.g. "floating" for `view-mode-${id}`).
  const dyn = dynamicPrefixes.find((p) => id.startsWith(`${p}-`));
  if (dyn) {
    const suffix = id.slice(dyn.length + 1);
    if (app.includes(`"${suffix}"`) || app.includes(`'${suffix}'`)) continue;
  }
  console.log("MISS", id);
  missing++;
}
console.log(missing === 0 ? "ALL TOUR TARGETS EXIST" : `${missing} MISSING`);
process.exit(missing === 0 ? 0 : 1);
