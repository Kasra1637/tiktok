/**
 * Verify every named import in the files I added/changed actually resolves.
 *
 * A named import that does not exist is NOT a build error under CRA's CJS
 * interop - it becomes an undefined live binding, which surfaces in a minified
 * bundle as "Cannot access 'x' before initialization" or "x is not a function".
 * This checks the real installed packages, not the docs.
 */
const fs = require("fs");
const path = require("path");

const root = path.resolve(__dirname, "..");
const only = process.argv.slice(2);
const files = only.length
  ? only
  : (() => {
      const out = [];
      const walk = (d) => {
        for (const e of fs.readdirSync(d, { withFileTypes: true })) {
          const p = path.join(d, e.name);
          if (e.isDirectory()) walk(p);
          else if (/\.(js|jsx)$/.test(e.name)) out.push(path.relative(root, p));
        }
      };
      walk(path.join(root, "src"));
      return out;
    })();

const importRe =
  /import\s+(?:([\w*\s{},$]+?)\s+from\s+)?['"]([^'"]+)['"]/g;

function resolveLocal(spec, importer) {
  const base = path.resolve(path.dirname(importer), spec);
  for (const c of [base, base + ".js", base + ".jsx", base + ".json",
                   path.join(base, "index.js"), path.join(base, "index.jsx")]) {
    if (fs.existsSync(c) && fs.statSync(c).isFile()) return c;
  }
  return null;
}

function packageExports(pkgName) {
  // Resolve the package entry and harvest every exported name we can see.
  let entry;
  try {
    entry = require.resolve(pkgName, { paths: [path.join(root, "src")] });
  } catch {
    return null;
  }
  const names = new Set();
  // 1. Real CJS interop
  try {
    const mod = require(pkgName);
    if (mod && (typeof mod === "object" || typeof mod === "function")) {
      Object.keys(mod).forEach((k) => names.add(k));
    }
  } catch { /* ESM-only, fall through */ }
  // 2. Static scan of the dist ESM entry, which lists the real icon names.
  try {
    const src = fs.readFileSync(entry, "utf8");
    const declRe = /(?:export\s*\{|export\s+(?:const|function|class)\s+)([^}]+)\}?/g;
    let m;
    while ((m = declRe.exec(src))) {
      m[1].split(",").forEach((part) => {
        const cleaned = part.trim().split(/\s+as\s+/).pop().replace(/^type\s+/, "").trim();
        if (/^[A-Za-z_$][\w$]*$/.test(cleaned)) names.add(cleaned);
      });
    }
    const namedRe = /export\s*\{([^}]*)\}/g;
    while ((m = namedRe.exec(src))) {
      m[1].split(",").forEach((part) => {
        const cleaned = part.trim().split(/\s+as\s+/).pop().trim();
        if (/^[A-Za-z_$][\w$]*$/.test(cleaned)) names.add(cleaned);
      });
    }
  } catch { /* no dist file, best effort */ }
  return names;
}

const cache = new Map();
let problems = 0;

let problemFiles = 0;
for (const rel of files) {
  const file = path.join(root, rel);
  const src = fs.readFileSync(file, "utf8");
  const before = problems;

  let m;
  importRe.lastIndex = 0;
  while ((m = importRe.exec(src))) {
    const clause = (m[1] || "").trim();
    const spec = m[2];
    if (!clause || /^[\w*\s{},$]+$/.test(clause) === false) continue;
    if (/^\*\s+as\s+/.test(clause)) continue;

    const braces = clause.match(/\{([^}]*)\}/);
    if (!braces) continue;
    const wanted = braces[1]
      .split(",")
      .map((s) => s.trim().split(/\s+as\s+/)[0].trim())
      .filter(Boolean);

    if (spec.startsWith(".")) {
      const target = resolveLocal(spec, file);
      if (!target) {
        console.log(`  ${rel}: MISSING FILE  ${spec}`);
        problems++;
        continue;
      }
      const tsrc = fs.readFileSync(target, "utf8");
      for (const w of wanted) {
        const re = new RegExp(
          `export\\s+(?:default\\s+)?(?:async\\s+)?(?:const|let|var|function|class)\\s+${w}\\b` +
          `|export\\s*\\{[^}]*\\b${w}\\b[^}]*\\}`
        );
        if (!re.test(tsrc)) {
          console.log(`  ${rel}: MISSING EXPORT  ${w}  (from ${spec})`);
          problems++;
        }
      }
    } else {
      if (!cache.has(spec)) cache.set(spec, packageExports(spec));
      const names = cache.get(spec);
      if (!names) continue;
      const missing = wanted.filter((w) => !names.has(w));
      if (missing.length) {
        console.log(`  ${rel}: MISSING FROM ${spec}: ${missing.join(", ")}`);
        problems++;
      }
    }
  }
  if (problems > before) problemFiles++;
}

console.log("\n" + "=".repeat(70));
console.log(`scanned ${files.length} file(s); ${problemFiles} with problems`);
console.log(problems === 0
  ? "All named imports resolve."
  : `${problems} PROBLEM(S) FOUND`);
process.exit(problems === 0 ? 0 : 1);
