import { cn } from "../lib/utils";

/**
 * The one place a page's width is decided.
 *
 * Every page inside the sidebar used to open with its own `mx-auto max-w-*`,
 * and they were all different: 1024px on Analytics, 1152px on four pages,
 * 1280px on Demo + CTA, and the full frame on App Profile Details. Moving
 * between two pages therefore re-solved the same centering math and the
 * content moved sideways — which is the one thing navigation must not do,
 * because the reader has to re-find the thing they were looking at.
 *
 * Two states, and only two:
 *
 * - `default` — the workspace column: 1280px, centred inside the shell frame.
 *   Work and editor pages spend their room on grids, timelines and players,
 *   and 1280 is the widest column that keeps record rows and reading blocks
 *   scannable. The cap only binds past ~1610px viewports, so laptops keep the
 *   layout a full-width frame gave them.
 * - `narrow`  — 1150px, centred. For reading-heavy prose; no page uses it.
 *
 * `max-w-*` only binds once the viewport is wider than the cap, so narrow and
 * default are the same element on a phone and nothing about mobile changes.
 *
 * The earlier design note called for a third `wide` token, but it was defined
 * as the full frame — identical to `default`. Two names for one value is a way
 * for two pages to drift apart again, so it collapsed into `default`.
 *
 * The outer frame itself (1400px plus its padding) belongs to AppShell and is
 * deliberately not touched here; this component decides the column inside it.
 * The masthead text caps one step tighter (`PageHeader`'s `max-w-3xl`).
 *
 * `PAGE_WIDTH_CLASS` is exported so a page with a second container that must
 * line up with the first reuses the exact same class string instead of
 * re-typing a pixel value that can drift.
 */
export const PAGE_WIDTH_CLASS = {
  default: "mx-auto w-full max-w-[1280px]",
  narrow: "mx-auto w-full max-w-[1150px]",
};

export function PageFrame({ width = "default", className, children }) {
  // An unknown token falls back to the full frame rather than rendering an
  // unstyled div, so a typo widens the page instead of collapsing it.
  const token = PAGE_WIDTH_CLASS[width] ? width : "default";
  return <div className={cn(PAGE_WIDTH_CLASS[token], className)}>{children}</div>;
}

export default PageFrame;