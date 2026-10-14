# HookForge Design Guidelines

Reference for the shipped design system. Everything here is verifiable against
`frontend/src/index.css`, `frontend/tailwind.config.js`, and
`frontend/src/components/`. **If you change a token, update this file in the
same commit.**

> This document previously specified a light lavender-white theme
> (`#F8F7FF` background, light cards). That was never built. The app is and has
> always been a dark studio theme. The spec below reflects the real
> implementation.

---

## 1. Personality

A dark, data-dense **studio** tool for TikTok creators. It should feel adjacent
to the editors creators already live in (CapCut, Premiere, DaVinci) — not like a
generic light-mode SaaS dashboard.

- **Energetic but serious** — creator culture meets analytics.
- **Data-first** — scores, counts and frames are the content; chrome recedes.
- **Tactile** — layered elevation, filmstrips, hairline edges.

**Avoid:** purple-heavy "AI" aesthetics, neon gradients, gradients on small
elements, centered single-column marketing layouts inside the app shell.

---

## 2. Color

Defined in `:root` in `frontend/src/index.css`. Two accents only.

### Brand hues

| Token | Value | Use |
|---|---|---|
| `--brand-indigo` | `#818CF8` | Navigation, selection, active state, links |
| `--brand-indigo-dark` | `#6366F1` | Hover state for indigo surfaces |
| `--brand-coral` | `#FE2C55` | Primary CTAs only (TikTok's own red) |

**The split is load-bearing:** indigo means *"this is selected / where you
are,"* coral means *"this performs the action."* Never use coral for a filter
chip or nav item, or a CTA stops being unambiguous.

> Naming history: these were `--brand-teal`, `--brand-teal-dark` and
> `--brand-mint` even though all three resolved to indigo. They are renamed and
> the two dead tokens (`--brand-mint`, `--brand-red`) are deleted. There is no
> teal or mint in this app.

### Shadcn semantic tokens (HSL, dark)

```
--background 228 14% 7%     --foreground        220 20% 93%
--card       228 14% 10%    --muted-foreground  220 10% 55%
--secondary  228 12% 16%    --border            228 12% 17%
--primary    244 75% 63%    --ring              244 75% 63%
--radius     0.75rem
```

### Translucent tints

Use these instead of hand-writing `rgba()`. Suffix = alpha percent.

- Indigo: `--indigo-4` `-6` `-8` `-10` `-15` `-25` `-35` `-45`
- Coral: `--coral-8` `--coral-12` `--coral-25`
- Edges: `--hairline` (6% white), `--hairline-strong` (10% white)

**Rule:** if you are typing `rgba(99, 102, 241, ...)` or
`rgba(254, 44, 85, ...)` in a component, use a token or add one.

### Gradients

Permitted only as section backgrounds and decorative overlays — never on small
UI elements or text-heavy reading areas, never over 20% of the viewport.
The sanctioned ones are `.hero-wash`, `.spotlight-indigo`, `.spotlight-coral`,
`.grid-overlay`, `.noise-overlay`, and the `.text-gradient-*` / `.text-shine`
headline treatments.

---

## 3. Typography

| Role | Family | Applied via |
|---|---|---|
| Display | Space Grotesk | `h1`–`h4`, `.font-display` |
| Body | Figtree | `body` default |
| Mono | IBM Plex Mono | `code`, `.font-mono` — JSON specs, URLs, IDs |

Display text carries tight tracking (`-0.02em`, `-0.03em` on `h1`/`.font-display`).

### Type scale: 3 Sizes × 2 Weights (12px floor)

**Minimum type size is 12px (`text-xs`). No exceptions.** The audience is
mobile-heavy and `--muted-foreground` is already a mid-contrast gray; below 12px
it stops clearing WCAG AA.

The workspace shell uses **3 font sizes** and **2 font weights** only (marketing `Landing` and `LegalPage` retain their own editorial scales):

- **3 sizes:** `text-xs` (12px — `.eyebrow`, badges, chips, metadata, hints), `text-sm` (14px — body copy, inputs, buttons, `.section-heading`, card titles, dialog titles, `EmptyState` heading, sidebar wordmark), and `text-2xl` (24px — `PageHeader` `h1` and auth wordmark). Do not introduce `text-base`, `text-lg`, `text-xl`, or arbitrary pixel sizes (`text-[13px]`, `text-[17px]`, `text-[28px]`) in workspace pages or components.
- **2 weights:** `font-normal` (400 — reading copy, inputs, inactive nav items) and `font-semibold` (600 — headings, labels, buttons, chips, badges, active nav items, and `PageHeader` `h1`). Do not use `font-medium` (500) or `font-bold` (700) in workspace pages or components.
- **Ampersands in headings & labels:** Workspace headings, titles, labels, and button copy use `&` instead of `and` (e.g., `Visual & audio direction`, `Choose a template & add your photo`, `What you have & what is left`).
- `.eyebrow` — uppercase tracked-out label, `0.75rem`/600. Don't override its size.
- **Do not stack an opacity modifier on small muted text.** `text-muted-foreground/70`
  at 12px falls below AA on `--background`. Use the full token.

---

## 4. Surfaces and elevation

Composite classes in `index.css`; prefer them over ad-hoc borders and shadows.

| Class | Use |
|---|---|
| `.surface` | Default card — translucent, hairline border, inner top highlight |
| `.surface-solid` | Opaque variant for overlapping/floating panels |
| `.surface-glass` | Blurred chrome that sits over content (sidebar, top bar) |
| `.surface-sunken` | Inset wells (code panels, empty slots) |
| `.surface-interactive` | Adds hover lift; respects `prefers-reduced-motion` |
| `.inset-panel` | The one bordered aside allowed **inside** a card (12px radius, 16px gutter) |
| `.inset-panel-strong` | The same aside, one step louder, for a group that carries a state the reader must not miss |
| `.surface-flush` | A card that owns its own inner padding — accordion groups and list rows |
| `.row-pad` | The row rhythm inside a card: 16px gutter, 12px block |
| `.border-gradient` | Masked pseudo-element for a lit top-left edge |
| `.pill-studio` | Raised beveled pill (`Chip`, wizard step pills, `AppPicker`) with top specular rim + `-1px` hover lift + icon scale |
| `.card-pickable` | Selectable option card (`aria-pressed`) with lit indigo top rim when selected |
| `.input-well` | Recessed studio field (`Input`, `Textarea`, `CONTROL_CLASS` `<select>`) with inner top shadow and 3px indigo focus aura |

Elevation ramp: `--shadow-xs` → `--shadow-sm` → `--shadow-md` → `--shadow-lg` →
`--shadow-xl` (layered, not a single flat blur). Brand glows `--glow-indigo` /
`--glow-coral` are for primary CTAs and active states **only**.

Radii: cards `rounded-2xl` (16px), asides and rows `rounded-xl` (12px), pills
`rounded-full`. **`.surface` owns its own radius and padding** — do not re-type
`rounded-2xl` or `p-*` on a card; it was re-typed at every call site and a
forgotten utility produced a square card.

Card padding is unified in `index.css`: `.surface` / `.surface-solid` are
`20px` on phones and `28px` from 768px up; `.surface-compact` (cards that are
items in a grid) stays `16px`; `.inset-panel` is `20px`; `.surface-flush` is `0` for a card whose first
child is a full-bleed row. Do not add `p-*` to card JSX.

**Never nest `.surface` inside `.surface`.** A card inside an identical card
is a box in a box: same fill, same border, same gutter. The level inside a
card is `.inset-panel`.

### Container levels (every sidebar page)

| Level | Built with | Icon | Heading |
|---|---|---|---|
| Page | `PageHeader` | 40px `IconTile size="page"` | page title |
| Section card | `SectionCard` + `SectionHeading` | 16px outline glyph, no tile | `h2`, 14px/600 uppercase, tracked 0.08em, muted |
| Wizard step | `StepShell` + `SectionHeading` | 16px outline glyph, no tile | same section heading + muted description |
| Group inside a card | `GroupLabel` + hairline divider, never a nested box | 16px glyph on the bar, 12px on the card's own `.eyebrow` | `.eyebrow` (all caps) |
| Aside inside a card | `.inset-panel` (12px radius, 16px gutter) | none | 14px semibold, or an `.eyebrow` |
| Disclosure row | `.row-pad` inside one `.surface surface-flush` card, hairline between rows | none, or 16px on an accordion bar | 14px semibold label, or uppercase tracked on the bar |
| Pickable option | its own frame — `rounded-xl border bg-card/70`, bar is `px-4 py-3`, `space-y-2` between them | 16px, its own | `text-sm` uppercase tracked, muted |
| Field / detail row | label + control | none | 14px semibold label |

**Every topic-page subtitle fits a 54-60 character budget.** The line under the
page title is the first thing read on a page and it is read at a glance: one
sentence naming what the page is for. The six topic pages — App Profile,
Demo + CTA, Create Video, Asset Library, Generation History, Analytics — share
one length so the subtitle never becomes a paragraph that pushes the page's own
content below the fold, and so its length is not re-decided per page. A detail
page whose subtitle is the user's own text (App Profile detail renders the
researched description) is exempt: that is the founder's app talking, not page
chrome. `frontend/scripts/check-render-smoke.cjs` asserts the budget for all
six and fails on a page that drops its subtitle entirely.

**App Profile is the reference for workspace section headings.** Every section
uses `SectionHeading`: body family, 14px/600, 22px line-height, all caps,
0.08em tracking and full muted color, beside a 16px unboxed outline glyph.
`GroupLabel` is the smaller 12px counterpart with a 12px glyph. Sections can
carry normal-case descriptions; controls and body copy never become all caps.
Page titles retain their display hierarchy and page-sized icon tile. Options
retain their chevrons and click-target frames.

**The frame is what tells the two apart, and it is deliberate.** A row you
*pick* is an object, so it gets its own border and radius — that frame is the
click target and it is what an in-place expansion opens inside. A row you
*open* is part of a card, so it stays inside one `.surface` and is separated
from its neighbours by a hairline. That is why the angle list draws a box per
angle and `SectionGroup` (App Profile) does not: same bar chrome on both sides
(`.row-pad`, 16px glyph, uppercase tracked muted title, chevron, indigo hover —
`SectionGroup`'s own comment says it borrows the angle row's chrome), different
container. `RecommendationCard`'s 2-up grid is the same rule as the angle list:
picked things are objects, so they are framed.

A group's glyph is not decoration: on the App Profile detail page every
`ProfileCard` and `SectionGroup` carries one, and `runIconChecks` fails the page
if any opens text-only (it also pins the page's 10+ cards and exactly 5 groups).
Bars use `h-4 w-4` (16px); the card's own `.eyebrow` uses `h-3 w-3` (12px).
Step pills (`text-xs`, `rounded-full`) encode state in the ring and a tick glyph
— never in position, which is the only thing a reader has while a step is
unreachable.

Spacing, in these steps and no others:

| Gap | Token | Job |
|---|---|---|
| 24px | `space-y-6` / `gap-6` | between page sections — every sidebar page's `PageFrame` |
| 20px | `space-y-5` | between blocks inside a card (`SectionCard`, `StepShell`) |
| 16px | `space-y-4` / `gap-4` | between cards in a list; flush accordion bodies |
| 12px | `space-y-3` / `gap-3` | between related blocks that are not one stack |
| 8px | `space-y-2` / `gap-2` | items in a list; a label to its control; a field's own stack (label, hint, control) |
| 6px | `gap-1.5` | inline clusters only — a glyph beside its label, two controls in a row |
| 4px | `space-y-1` / `mt-1` | a label to its value; text under a title inside a card |

`mt-*` is for a pair only (a title and the line under it) — never for block
spacing, which is `space-y-*` on the parent. An `mt-*` beside a `space-y-*`
parent is not redundant, it is **32px where 16px was designed**: `space-y-*`
keys off DOM position, so it still reserves the gap for a sibling that renders
nothing (`{cond && ...}`), and the `mt-*` adds a second one. A block that opens
with `border-t` takes `pt-4` for the gutter below its own rule — never `mt-4`
to clear the border. `mt-0.5` is reserved for optical alignment of a small icon
beside text. Loading states
use `Skeleton` blocks shaped like the content, not a spinner line. App
switchers use `AppPicker`; generation status uses `StatusBadge`. All caps is
used on `.eyebrow` group labels and `.section-heading` workspace sections;
page titles, descriptions and user content retain normal case.

---

## 5. Layout

### History density

History uses a two-column card grid from 1200px viewport width, one column
below it, with 16px gutters and top-aligned cards (no equal-height stretching).
Each card has a 152px preview rail and a 270px contained video from 480px up;
phones stack a 220px preview above the context. Audience and demo brief use
existing API fields to fill the context column with useful information rather
than filler. File controls remain under the preview; work actions stay beside
it. Related-render links are capped at two per card.

- **Shell:** `AppShell` — fixed collapsible left sidebar (264px / 76px collapsed,
  persisted to `localStorage`) plus a mobile-only sticky top bar with a drawer.
  Live width is published to `--app-sidebar-w` so fixed chrome outside the
  subtree can dodge the panel.
- **Content width:** `AppShell`'s `<main>` owns the outer frame —
  `mx-auto w-full max-w-[1400px] px-4 py-6 md:px-6 md:py-8 lg:px-8`. Every page
  inside the sidebar opens with `PageFrame`, which decides only what sits inside
  that frame. Two tokens, and only two:
  - `default` — the whole frame. Studio and editor pages, which spend their room
    on grids, players and lists: Create Video, Demo + CTA, History, Analytics,
    App Profile, Profile Detail. The App Profile family moved here so moving
    between Create Video and the profile pages never re-solves the centering
    math sideways.
  - `narrow` — 1150px, centred. Reserved for reading-heavy prose where a card
    at 1400px stretches a sentence across a line the eye cannot sweep. No
    current page uses it: the Asset Library grid went full frame so the
    standalone page matches its embedded instance in Create Video.

  **The width must not change between two pages a reader moves between**, so a
  page belongs to a family rather than to itself: Brand Setup links to Profile
  Detail, and Profile Detail is where an app's photos live. `PAGE_WIDTH_CLASS`
  is exported so a second container that has to line up with the first reuses
  the exact class string instead of re-typing a pixel value that can drift. A page embedded in another page
  (Asset Library inside Create Video's template step) passes `default`: it is
  inside a card, not a frame.

### Responsive rules

1. **Every multi-column grid needs a mobile fallback.** Start at
   `grid-cols-1` or `grid-cols-2` and add `sm:` / `md:` / `lg:`. A bare
   `grid-cols-3` is a bug.
2. Comparison layouts stack or drop to 2-up below `md`; the *result* image gets
   the full width (`col-span-2 md:col-span-1`) so the payoff is never a third of
   a phone screen.
3. Horizontal chip rails and filmstrips scroll (`overflow-x-auto`,
   `.no-scrollbar`, `.filmstrip-scroll`) rather than wrapping.
4. Button rows use `flex-wrap` with `min-w-[160px] flex-1` on the primary action.
5. The sidebar becomes a drawer below `lg`.

---

## 6. Components

Build on `frontend/src/components/ui/*` (shadcn). Before hand-rolling anything,
check whether a shared primitive already exists:

`AppShell` · `Sidebar` · `PageHeader` · `Chip` · `StepDots` / `StepBadge` · `EmptyState` ·
`VideoCard` · `Filmstrip` · `HookBreakdown` · `GenerationProgress` ·
`JsonSpecPanel` · `SideBySideCompare` · `HookStyleSelector` · `RemixChat` ·
`PageTransition` · `ErrorBoundary` · `LegalPage`

### Button variants

All `<Button>` variants in `components/ui/button.jsx` share the `.btn-studio` system in `index.css` (including the marketing `Landing` page — never hand-roll coral/indigo background overrides at call sites):

| Variant | Appearance | Use |
|---|---|---|
| `brand` | Coral bevel (`.btn-bevel-brand`) + 1px top specular rim + `--glow-coral` | **The** primary action on a screen |
| `accent` / `default` | Indigo bevel (`.btn-bevel-accent`) + 1px top specular rim + `--glow-indigo` | Secondary brand action |
| `outline` / `secondary` | Hairline border + `.btn-bevel-neutral` top rim | Neutral actions |
| `ghost` / `link` | No fill, no sweep (`after:hidden`) | Back links, tertiary |

**Signal Coral primary rule:** `brand` (`#FE2C55`, white text) is the single primary CTA color — one per screen for the commit action (Generate, Research, Approve, Create draft, Save edits, Export, Landing hero/final CTA). `accent` (indigo) is the secondary brand action (tour Next, Save App Profile, paired secondary); `outline` / `secondary` cover navigation and retries; `ghost` / `link` cover tertiary and destructive-adjacent actions. Never hand-roll `bg-[color:var(--brand-coral)]` or `bg-[color:var(--brand-indigo)]` on a clickable button — use the variant.

**Sizes (roomy inner spacing):** `default` `h-11 px-5 py-2.5`, `sm` `h-9 px-4 py-1.5`, `lg` `h-[52px] px-10 py-3`, `icon` `h-11 w-11`. Header action rows wrap with `gap-x-3 gap-y-3` so wrapped rows clear by 12px top-to-bottom.

**Hover & press micro-interaction (`.btn-studio`, softer):**
- Hover lifts `-1px` over `300ms ease-out`, drifts a soft 105° sheen (`::after`, 40% width, 0.10 alpha) across the button in `850ms`, and brightens the top bevel rim with a shadow tighten.
- Text and icons never animate: no `svg`/text transforms anywhere in `.btn-studio` or `.pill-studio`.
- Active press settles to `translateY(0)` with no scale snap.
- Disabled and `prefers-reduced-motion` states suppress the lift and sheen sweep.

### Badge variants

`indigo` and `coral` are tinted chips (`--indigo-10` / `--coral-12` fills) —
accents, not buttons. Plus shadcn's `default` / `secondary` / `destructive` / `outline`.

**One pattern per job.** `StepDots` (dot-and-rail progress for a screen's own
linear flow) and `StepBadge` (numbered badge beside a step heading) in
`components/Stepper.jsx` are the only progress vocabulary. Don't hand-roll a
second model beside them.

Progress is scoped to a single screen's steps, not the whole app pipeline —
cross-page position is conveyed by the sidebar's active nav item. An earlier
four-stage pipeline stepper (find → analyze → swap → video) was specified here
but never imported by anything, while FaceSwap hand-rolled its own dots; the
shipped model is the one documented above.

---

## 7. Motion

Library: `framer-motion` (page transitions, card entrance). CSS keyframes cover
ambient motion (`float-slow`, `fade-up`, `pulse-ring`, `shimmer-sweep`, `marquee-x`).

Durations: fast `150ms`, base `220ms`, slow `320ms`.

**Hard rules:**

1. **Never `transition: all`** — it breaks transforms. Enumerate properties:
   `transition-[transform,box-shadow,border-color]`.
2. **Always honor `prefers-reduced-motion`** — in CSS via the media query, and
   in JS via `useReducedMotion()` (see `VideoCard`).
3. Hover = 1–2px lift plus shadow tighten. Entrance = fade + 6–12px `y`.
4. Stagger list entrance with a capped delay (`Math.min(index * 0.04, 0.32)`).

---

## 8. Async, empty and error states

- **Skeletons must mirror the real layout** — match the actual aspect ratios and
  rail widths so nothing reflows on load. Never a bare centered spinner.
- Multi-stage progress via `GenerationProgress`: download → extract → analyze →
  prepare spec → generate.
- **Images always degrade gracefully.** `VideoCard`'s chain is direct URL →
  backend `/api/proxy-thumb` → `ImageOff` placeholder that preserves card shape.
- Transient errors → Sonner toast. Job failures → persistent `Alert` with retry.
- Empty states use the shared `EmptyState` component.

---

## 9. Accessibility

- WCAG AA contrast minimum. The 12px floor and the no-opacity-on-small-text
  rule in §3 exist to hold this line.
- Global `:focus-visible` ring (`2px` indigo, `2px` offset) — never remove it.
- `aria-pressed` on toggles/chips, `aria-current="page"` on active nav,
  `aria-label` on every icon-only button, `role="dialog"` + `aria-modal` on drawers.
- Filmstrip frames are real keyboard-navigable `<button>`s.
- Escape closes overlays; drawers close on navigation.

---

## 10. Conventions

- `.jsx` only, no TypeScript.
- Components use **named** exports; pages use **default** exports.
- Toasts via `sonner`. Never hand-roll dropdowns, calendars or toasts — use
  `components/ui/*`.
- Icons from `lucide-react`. **Never emoji as icons.**
- `data-testid` on every interactive and key informational element, kebab-case
  and role-based: `niche-selector-tabs`, `analyze-hook-button`,
  `filmstrip-frame-button-0`, `face-swap-generated-image`.
- Duplicated instances of one nav model must not produce duplicate test ids —
  the mobile sidebar prefixes its ids with `mobile-`.
