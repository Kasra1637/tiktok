// Token contrast gate: every named text/surface pair in the design tokens
// must clear WCAG AA for normal text (4.5:1).
//
// Why this exists: the error red (--destructive used as text) sat at 3.7:1 on
// card for two audits because nothing measured it. The tokens are the single
// source every surface reads, so asserting the pairs here — deterministically,
// from the HSL values in index.css, no browser — is what stops a token drift
// from silently shipping unreadable text again (UI/UX audit 2026-11-14,
// findings 1, 2 and 9).
//
// Text rides the TEXT-grade tokens: `text-destructive` utilities resolve to
// --destructive-text, never the solid --destructive (that token is fills and
// borders, and its own pair is white text on the fill). Muted text is
// asserted on every surface it lands on, including --secondary, its worst
// case.
//
// Run: node scripts/check-contrast.cjs
const fs = require("fs");
const path = require("path");

const CSS = path.join(__dirname, "..", "src", "index.css");
const css = fs.readFileSync(CSS, "utf8");

let failed = 0;
function fail(label, detail) {
  console.log(`  [FAIL] ${label}`);
  if (detail !== undefined) console.log(`         got: ${JSON.stringify(detail)}`);
  failed++;
}
function pass(label) {
  console.log(`  [PASS] ${label}`);
}

// The :root token block only: later rules reuse the same names as values.
const rootBlock = (css.match(/:root\s*\{([\s\S]*?)\n\s*\}/) || [])[1] || "";
const tokens = {};
for (const match of rootBlock.matchAll(/--([\w-]+):\s*([^;]+);/g)) {
  tokens[match[1]] = match[2].trim();
}

function tokenRgb(name) {
  const raw = tokens[name];
  if (!raw) return null;
  const hex = raw.match(/^#([0-9a-f]{6})$/i);
  if (hex) {
    const n = parseInt(hex[1], 16);
    return [((n >> 16) & 255) / 255, ((n >> 8) & 255) / 255, (n & 255) / 255];
  }
  const hsl = raw.match(/^([\d.]+)\s+([\d.]+)%\s+([\d.]+)%$/);
  if (!hsl) return null;
  const h = Number(hsl[1]);
  const s = Number(hsl[2]) / 100;
  const l = Number(hsl[3]) / 100;
  const k = (n) => (n + h / 30) % 12;
  const a = s * Math.min(l, 1 - l);
  const f = (n) => l - a * Math.max(-1, Math.min(k(n) - 3, Math.min(9 - k(n), 1)));
  return [f(0), f(8), f(4)];
}

function luminance([r, g, b]) {
  const f = (c) => (c <= 0.03928 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4));
  return 0.2126 * f(r) + 0.7152 * f(g) + 0.0722 * f(b);
}

function contrast(fgName, bgName) {
  const fg = tokenRgb(fgName);
  const bg = tokenRgb(bgName);
  if (!fg || !bg) return null;
  const [hi, lo] = [luminance(fg), luminance(bg)].sort((x, y) => y - x);
  return (hi + 0.05) / (lo + 0.05);
}

// [text token, surface token] — every pair must reach AA for normal text.
const PAIRS = [
  ["foreground", "background"],
  ["foreground", "card"],
  ["muted-foreground", "background"],
  ["muted-foreground", "card"],
  ["muted-foreground", "muted"],
  ["muted-foreground", "secondary"],
  ["secondary-foreground", "secondary"],
  ["destructive-text", "background"],
  ["destructive-text", "card"],
  ["destructive-foreground", "destructive"],
  ["brand-indigo", "background"],
  ["brand-indigo", "card"],
  ["brand-indigo", "muted"],
  ["brand-indigo", "secondary"],
];

for (const [fg, bg] of PAIRS) {
  const ratio = contrast(fg, bg);
  if (ratio === null) {
    fail(`${fg} on ${bg} is measurable`, `token missing or unparseable: --${!tokenRgb(fg) ? fg : bg}`);
  } else if (ratio < 4.5) {
    fail(`${fg} on ${bg} clears 4.5:1`, `${ratio.toFixed(2)}:1`);
  } else {
    pass(`${fg} on ${bg}: ${ratio.toFixed(2)}:1`);
  }
}

console.log(failed === 0 ? "CONTRAST GATE HOLDS" : `${failed} CONTRAST BREAK(S)`);
process.exit(failed === 0 ? 0 : 1);
