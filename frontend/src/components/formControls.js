/**
 * The shared skin for a hand-written form control.
 *
 * There were three, for the same control: Demo + CTA's local CONTROL_CLASS
 * (h-10, rounded-xl, bg-secondary/40), Generation Panel's two selects (auto
 * height, rounded-lg, bg-transparent) and Generation History's variation
 * select (h-10, rounded-xl, bg-transparent). Two radii and two heights for
 * one job, and the doc says inputs are rounded-xl.
 *
 * The canonical skin is `ui/input.jsx`, which every text field already uses.
 * This is that same skin for a form dropdown: since ADR 0163 the dropdown
 * is the app-drawn `AppSelect` everywhere in the app, and this class skins
 * its button in form fields — the chevron and the open menu are the
 * component's own, so there is no native arrow left to keep or remove.
 *
 * Filter pills are a different control and keep `PILL_SELECT_CLASS`
 * (AppPicker): h-8, rounded-full, a chip beside a heading, not a field.
 *
 * One control height: 44px (h-11), the button default's height, so a field
 * and the button beside it in a shared row share top and bottom edges
 * (audit 2026-11-14, finding 12 — the two used to disagree by 4px).
 */
export const CONTROL_CLASS =
  "input-well h-11 w-full rounded-xl border border-[color:var(--hairline)] px-3 text-base text-foreground outline-none disabled:cursor-not-allowed disabled:opacity-50";
