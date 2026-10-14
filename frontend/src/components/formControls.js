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
 * This is that same skin for the raw `<select>` elements the app still writes
 * by hand.
 *
 * No `appearance-none`: it was on the Demo + CTA selects only, and with no
 * chevron drawn in its place it removed the one affordance a dropdown has.
 * Every raw select keeps its native arrow now.
 *
 * Filter pills are a different control and keep `PILL_SELECT_CLASS`
 * (AppPicker): h-8, rounded-full, a chip beside a heading, not a field.
 */
export const CONTROL_CLASS =
  "input-well h-10 w-full rounded-xl border border-[color:var(--hairline)] px-3 text-sm text-foreground outline-none disabled:cursor-not-allowed disabled:opacity-50";
