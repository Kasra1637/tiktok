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
 * One width, and only one:
 *
 * - `default` — the workspace column: 1150px, centred inside the shell frame.
 *   Work and editor pages spend their room on grids, timelines and players,
 *   and 1150 is the widest column this app reads well at. The cap binds only
 *   past ~1480px viewports, so smaller windows keep the layout they had.
 *
 * `max-w-*` only binds once the viewport is wider than the cap, so smaller
 * screens and phones are untouched.
 *
 * The earlier design note called for a third `wide` token, but it was defined
 * as the full frame — identical to `default`. Two names for one value is a way
 * for two pages to drift apart again, so it collapsed into `default`. The
 * `narrow` token collapsed into it for the same reason: two names for the same
 * 1150px value was drift waiting to happen.
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
  default: "mx-auto w-full max-w-[1150px]",
};

export function PageFrame({ width = "default", className, children }) {
  // An unknown token falls back to the full frame rather than rendering an
  // unstyled div, so a typo widens the page instead of collapsing it.
  const token = PAGE_WIDTH_CLASS[width] ? width : "default";
  return <div className={cn(PAGE_WIDTH_CLASS[token], className)}>{children}</div>;
}

export default PageFrame;