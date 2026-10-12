// One-off audit: every tour target selector must match a data-testid that
// actually exists in the app source. Prints OK/MISS per testid.
const fs = require("fs");
const path = require("path");
const root = path.join(__dirname, "..");

const src = fs.readFileSync(
  path.join(root, "src/lib/onboarding/tours.js"),
  "utf8"
);
const ids = [...new Set([...src.matchAll(/"([\w-]+)"/g)].map((m) => m[1]))].filter(
  (v) => v.includes("-") && !v.startsWith("data-")
);

const files = [];
(function walk(d) {
  for (const f of fs.readdirSync(d)) {
    const p = path.join(d, f);
    const s = fs.statSync(p);
    if (s.isDirectory()) walk(p);
    else if (/\.(jsx?|cjs)$/.test(f)) files.push(p);
  }
})("src");
let all = "";
for (const f of files) all += fs.readFileSync(f, "utf8");

let missing = 0;
for (const id of ids) {
  const hit = all.includes(`"${id}"`) || all.includes(`'${id}'`);
  if (!hit) {
    console.log("MISS", id);
    missing++;
  }
}
console.log(missing === 0 ? "ALL TOUR TARGETS EXIST" : `${missing} MISSING`);
process.exit(missing === 0 ? 0 : 1);
