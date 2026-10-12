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

### Type scale and the 12px floor

**Minimum type size is 12px (`text-xs`). No exceptions.** The audience is
mobile-heavy and `--muted-foreground` is already a mid-contrast gray; below 12px
it stops clearing WCAG AA.

- Use Tailwind's named steps: `text-xs` (12) → `text-sm` (14) → `text-base` (16) → `text-lg` …
- Arbitrary values (`text-[13px]`, `text-[17px]`, `text-[28px]`) are tolerated
  only for display/heading sizes, never to go below 12px.
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
| `.border-gradient` | Masked pseudo-element for a lit top-left edge |

Elevation ramp: `--shadow-xs` → `--shadow-sm` → `--shadow-md` → `--shadow-lg` →
`--shadow-xl` (layered, not a single flat blur). Brand glows `--glow-indigo` /
`--glow-coral` are for primary CTAs and active states **only**.

Radii: cards `rounded-2xl`, buttons/inputs/chips `rounded-xl`, pills `rounded-full`.

Card padding is unified in `index.css`: `.surface` / `.surface-solid` are
`16px` on phones and `24px` from 768px up; `.surface-compact` (cards that are
items in a grid) stays `16px`. Do not add `p-*` to card JSX. `.inset-panel` is
the one small bordered box allowed inside a card (16px padding, 12px radius).

### Container levels (every sidebar page)

| Level | Built with | Icon | Heading |
|---|---|---|---|
| Page | `PageHeader` | 40px `IconTile size="page"` | page title |
| Section card | `SectionCard` | 32px `IconTile size="section"` | `h2`, 16px semibold |
| Group inside a card | `GroupLabel` + hairline divider, never a nested box | 12px, only on collapsible groups or cards with 3+ groups | `.eyebrow` (all caps) |
| Field / detail row | label + control | none | 14px medium label |

Spacing: 24px between page sections (`space-y-6`), 16px between cards and
between fields (`space-y-4`), 8px from a label to its control. Loading states
use `Skeleton` blocks shaped like the content, not a spinner line. App
switchers use `AppPicker`; generation status uses `StatusBadge`. All caps is
reserved for `.eyebrow` group labels, never section or page titles.

---

## 5. Layout

- **Shell:** `AppShell` — fixed collapsible left sidebar (264px / 76px collapsed,
  persisted to `localStorage`) plus a mobile-only sticky top bar with a drawer.
  Live width is published to `--app-sidebar-w` so fixed chrome outside the
  subtree can dodge the panel.
- **Content width:** `mx-auto w-full max-w-[1400px] px-4 md:px-6 lg:px-8`.
- **Detail pages:** `grid grid-cols-1 gap-5 lg:grid-cols-[380px_1fr]` — media
  rail left, analysis right.
- **Feed:** responsive card grid, 9/16 `AspectRatio`.

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

| Variant | Appearance | Use |
|---|---|---|
| `brand` | Coral + `--glow-coral` | **The** primary action on a screen |
| `accent` | Indigo + `--glow-indigo` | Secondary brand action |
| `outline` / `secondary` | Hairline border | Neutral actions |
| `ghost` / `link` | No fill | Back links, tertiary |

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
