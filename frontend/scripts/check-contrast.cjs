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
  ["primary-foreground", "primary"],
  // The deep indigo fills (Kasra's change-the-fills order, Nov 28
  // 2026 — see the branded-text section below): the seats that used
  // to carry white text on the light --brand-indigo now ride these
  // deepened fills, so the branded text that sits on them is
  // measured here like any other pair. The bevel-accent gradient
  // (the default and accent buttons, the selected chip) runs
  // deep -> deep-2, so both stops are measured; the flat seats
  // (the Demo + CTA transport accent, the library picker's count
  // badge, the skip link, the error page's reload button, the
  // landing mock's badges) ride the deep stop.
  ["muted-foreground", "brand-indigo-deep"],
  ["muted-foreground", "brand-indigo-deep-2"],
  ["primary-foreground", "brand-indigo-deep"],
  ["primary-foreground", "brand-indigo-deep-2"],
  ["brand-indigo", "background"],
  ["brand-indigo", "card"],
  ["brand-indigo", "muted"],
  ["brand-indigo", "secondary"],
  // The generated-text highlight (ADR 0258): generated words ride on
  // this wash on every page, so the text grades that appear on it are
  // measured against it like any other surface.
  ["foreground", "generated-highlight"],
  ["muted-foreground", "generated-highlight"],
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

// ---------------------------------------------------------------------------
// The one branded text color (Kasra's order, Nov 28 2026): NO white text
// anywhere in the app. Every text token that read as white takes the
// inactive sidebar link's color — --muted-foreground, the same color the
// Tone/Shape group labels wear — headlines at the top of the main pages
// included, no exceptions. The tokens below therefore stand EQUAL to
// --muted-foreground, and no `text-white` class stands anywhere outside
// the glyph seats at the bottom of this section.
//
// The seats that sit on a saturated fill took the branded color too,
// by Kasra's change-the-fills ruling (Nov 28 2026, reversing the hold
// this section used to pin): instead of keeping their white, their
// FILLS deepened until the branded color clears this gate's AA floor
// on them — --primary 63% -> 31% lightness (the default button, the
// badge, the tooltip panel the Craft card's labels ride, the checked
// checkbox), --destructive 51% -> 21% (a deep red still in family),
// and the light --brand-indigo seats ride the new deep indigo tokens
// (--brand-indigo-deep / --brand-indigo-deep-2, measured in PAIRS
// above). There are no held white-text seats left: change a fill back
// toward the light end and its pair fails here, on purpose.
// ---------------------------------------------------------------------------
const BRANDED = tokens["muted-foreground"];
for (const name of ["foreground", "card-foreground", "popover-foreground", "accent-foreground", "secondary-foreground", "primary-foreground", "destructive-foreground"]) {
  if (tokens[name] === BRANDED) {
    pass(`--${name} stands at the one branded text color (${BRANDED})`);
  } else {
    fail(`--${name} stands at the one branded text color`, `--${name} is ${tokens[name]}, --muted-foreground is ${BRANDED}`);
  }
}

// The class-level sweep: no `text-white` TEXT anywhere in
// frontend/src. The only white that remains is on ICON GLYPHS — a
// lucide glyph is not font color: the logo tiles' Sparkles, the
// feature tiles' icons, the done badges' Check, the hero video's
// play/pause. They keep their color, in the files named below.
// Every text seat that used to stand in this list (the selected
// chip, the accent button, the Demo + CTA transport accent, the
// library picker's count badge, the skip link, the error page's
// reload button) now wears the branded color on a deepened fill
// (Kasra's change-the-fills ruling, Nov 28 2026), so those files
// carry no text-white at all. Any NEW text-white outside this
// glyph list fails here.
const TEXT_WHITE_SEATS = {
  "components/AppShell.jsx": "the mobile logo tile's glyph",
  "components/LazyHeroVideo.jsx": "the play/pause glyph over the hero video",
  "components/LegalPage.jsx": "the logo tile glyph",
  "components/Marketing.jsx": "the logo tile glyphs",
  "components/Sidebar.jsx": "the LogoMark glyph",
  "pages/CreateVideo.jsx": "the rail done badge's Check glyph on the indigo fill",
  "pages/Dashboard.jsx": "the step done badge's Check glyph on the indigo fill",
  "pages/FeaturesMockups.jsx": "the mock phone's Play glyph",
  "pages/Landing.jsx": "the feature tiles' glyphs",
  "pages/SignIn.jsx": "the logo tile glyph",
  "pages/SignUp.jsx": "the logo tile glyph",
};
const SRC_DIR = path.join(__dirname, "..", "src");
function walk(dir) {
  const out = [];
  for (const entry of fs.readdirSync(dir, { withFileTypes: true })) {
    const full = path.join(dir, entry.name);
    if (entry.isDirectory()) out.push(...walk(full));
    else if (/\.(jsx?|css)$/.test(entry.name)) out.push(full);
  }
  return out;
}
for (const file of walk(SRC_DIR)) {
  const rel = path.relative(SRC_DIR, file).split(path.sep).join("/");
  if (rel === "index.css") continue; // the stylesheet is swept by rule below
  const text = fs.readFileSync(file, "utf8");
  const hits = (text.match(/text-white(?![\w-])/g) || []).length
    + (text.match(/color:\s*"#fff"/g) || []).length;
  if (hits === 0) continue;
  if (Object.prototype.hasOwnProperty.call(TEXT_WHITE_SEATS, rel)) {
    pass(`${rel}: ${hits} white seat(s) stand only as named glyphs — ${TEXT_WHITE_SEATS[rel]}`);
  } else {
    fail(`${rel}: no text-white outside the named glyph seats`, `${hits} occurrence(s)`);
  }
}
// The changed class seats, pinned one by one (Kasra's change-the-fills
// ruling, Nov 28 2026): each seat that carried white text on the light
// indigo now carries the deep indigo fill class — a seat that drifts
// back to --brand-indigo (or keeps a white face the file-level sweep
// above cannot tell apart from a glyph, like the skip link beside
// AppShell's logo glyph) fails here by name.
const DEEP_SEATS = [
  ["components/Chip.jsx", "bg-[color:var(--brand-indigo-deep)]", "the selected chip rides the deep indigo fill"],
  ["components/ui/button.jsx", "bg-[color:var(--brand-indigo-deep)]", "the accent button rides the deep indigo fill"],
  ["demoCta/DemoCtaEditor.jsx", "bg-[color:var(--brand-indigo-deep)]", "the transport accent rides the deep indigo fill"],
  ["demoCta/LibraryPicker.jsx", "bg-[color:var(--brand-indigo-deep)]", "the count badge rides the deep indigo fill"],
  ["components/AppShell.jsx", "focus:bg-[color:var(--brand-indigo-deep)]", "the skip link rides the deep indigo fill"],
  ["components/ErrorBoundary.jsx", "\"#1F1884\"", "the reload button rides the deep indigo fill"],
];
for (const [rel, needle, label] of DEEP_SEATS) {
  const text = fs.readFileSync(path.join(SRC_DIR, rel), "utf8");
  if (text.includes(needle)) {
    pass(`${rel}: ${label}`);
  } else {
    fail(`${rel}: ${label}`, `missing ${needle}`);
  }
}
{
  const shell = fs.readFileSync(path.join(SRC_DIR, "components/AppShell.jsx"), "utf8");
  if (shell.includes("focus:text-white")) {
    fail("components/AppShell.jsx: the skip link's text is the branded color", "focus:text-white still stands");
  } else {
    pass("components/AppShell.jsx: the skip link's text is the branded color");
  }
}

// The Clerk primary button (Kasra's no-white-text order, Nov 28
// 2026): Clerk paints the sign-in/sign-up Continue button from
// AuthProvider's variables — colorPrimary is its fill and
// colorTextOnPrimaryBackground its label — so the fill stands
// pinned to the deep indigo hex and the label to the branded text
// hex (#949BA8, --muted-foreground as a hex value; the pair itself
// is measured in PAIRS above as muted-foreground on
// brand-indigo-deep). The formButtonPrimary class on the provider
// and on both auth pages rides the deep indigo tokens and carries
// the branded text class, like every other seat above.
{
  const auth = fs.readFileSync(path.join(SRC_DIR, "components/auth/AuthProvider.jsx"), "utf8");
  if (auth.includes('colorPrimary: "#1F1884"')) {
    pass("components/auth/AuthProvider.jsx: the Clerk primary fill is the deep indigo");
  } else {
    fail("components/auth/AuthProvider.jsx: the Clerk primary fill is the deep indigo", 'colorPrimary is not "#1F1884"');
  }
  if (auth.includes('colorTextOnPrimaryBackground: "#949BA8"')) {
    pass("components/auth/AuthProvider.jsx: the Clerk primary button's text is the branded color");
  } else {
    fail("components/auth/AuthProvider.jsx: the Clerk primary button's text is the branded color", 'colorTextOnPrimaryBackground is not "#949BA8"');
  }
}
for (const rel of ["components/auth/AuthProvider.jsx", "pages/SignIn.jsx", "pages/SignUp.jsx"]) {
  const text = fs.readFileSync(path.join(SRC_DIR, rel), "utf8");
  const at = text.indexOf("formButtonPrimary");
  // The provider's classes carry Tailwind's ! marker (hover:!bg-…);
  // flatten it so the one needle set reads both class styles.
  const seat = (at === -1 ? "" : text.slice(at, at + 400)).replace(/!bg-/g, "bg-");
  const needles = [
    "bg-[color:var(--brand-indigo-deep)]",
    "hover:bg-[color:var(--brand-indigo-deep-2)]",
    "text-muted-foreground",
  ];
  const missing = needles.filter((n) => !seat.includes(n));
  if (missing.length === 0) {
    pass(`${rel}: the Clerk primary button rides the deep indigo with branded text`);
  } else {
    fail(`${rel}: the Clerk primary button rides the deep indigo with branded text`, `formButtonPrimary missing ${missing.join(", ")}`);
  }
}

// The stylesheet's own text colors: NO `color: #fff` / `color: white`
// stands anywhere in index.css — ::selection included (selected text
// takes the branded color too). The landing mock's indigo seats (the
// how-it-works badge, the hero story's research/generate buttons, its
// step badge and its play badge) and the bevel-accent gradient the
// real buttons wear now run on the deep indigo tokens with the
// branded text color, and the pins below hold those exact treatments:
// a rule that drifts back to the light indigo or to white fails here.
{
  // Comments stripped first: a rule's leading comment would otherwise
  // be captured as part of its selector text.
  const bareCss = css.replace(/\/\*[\s\S]*?\*\//g, "");
  const ruleRe = /([^{}]+)\{([^{}]*)\}/g;
  let m;
  let stray = 0;
  const bodies = {};
  while ((m = ruleRe.exec(bareCss)) !== null) {
    const selector = m[1].trim();
    // Bodies merge across a selector's rules: the landing mock's
    // base rules are followed by animation-only rules under the
    // same selector, and the pins below assert presence, not
    // exclusivity.
    bodies[selector] = (bodies[selector] || "") + m[2];
    if (!/color:\s*(#fff|white)(?![\w-])/.test(m[2])) continue;
    stray++;
    fail(`index.css ${selector}: no white text color anywhere`);
  }
  if (stray === 0) pass("index.css carries no white text color anywhere");
  const DEEP_GRADIENT = "linear-gradient(180deg, var(--brand-indigo-deep) 0%, var(--brand-indigo-deep-2) 100%)";
  const BRANDED_CSS = "color: hsl(var(--muted-foreground))";
  const pinRule = (selector, needles, label) => {
    const body = bodies[selector];
    if (body === undefined) {
      fail(`index.css ${selector}: ${label}`, "rule missing");
    } else if (needles.every((needle) => body.includes(needle))) {
      pass(`index.css ${selector}: ${label}`);
    } else {
      fail(`index.css ${selector}: ${label}`, body.trim().slice(0, 200));
    }
  };
  pinRule(".btn-bevel-accent", [DEEP_GRADIENT], "the buttons' bevel gradient runs on the deep indigo stops");
  pinRule(".btn-bevel-accent:hover:not(:disabled)", [DEEP_GRADIENT], "the buttons' hover bevel keeps the deep indigo stops");
  pinRule(".how-badge", ["linear-gradient(135deg, var(--brand-indigo-deep), var(--brand-indigo-deep-2))", BRANDED_CSS], "the how-it-works badge rides the deep indigo with branded text");
  pinRule(".hero-story-research", [DEEP_GRADIENT, BRANDED_CSS], "the hero research button rides the deep indigo with branded text");
  pinRule(".hero-story-generate", [DEEP_GRADIENT, BRANDED_CSS], "the hero generate button rides the deep indigo with branded text");
  pinRule(".hero-story-step-badge", ["background: var(--brand-indigo-deep)", BRANDED_CSS], "the hero step badge rides the deep indigo with branded text");
  pinRule(".hero-story-play", [DEEP_GRADIENT, BRANDED_CSS], "the hero play badge rides the deep indigo with branded text");
}

console.log(failed === 0 ? "CONTRAST GATE HOLDS" : `${failed} CONTRAST BREAK(S)`);
process.exit(failed === 0 ? 0 : 1);
