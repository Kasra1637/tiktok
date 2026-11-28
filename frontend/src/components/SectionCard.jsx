import { useEffect, useRef, useState } from "react";
import { cn } from "../lib/utils";
/** Profile-style section title: one muted outline glyph, tracked caps, no tile. */
export function SectionHeading({ icon: Icon, as: Tag = "h2", className, children, ...rest }) {
  return (
    <Tag className={cn("section-heading", className)} {...rest}>
      {Icon && <Icon aria-hidden="true" className="h-4 w-4 shrink-0" />}
      <span className="min-w-0">{children}</span>
    </Tag>
  );
}

/**
 * The page's container levels, shared by every sidebar page:
 *
 * - Section card (this): a main block of the page. Profile-style 16px outline
 *   glyph + 14px muted uppercase heading, optional description. Padding lives
 *   in `.surface`.
 * - Group (`GroupLabel`): an uppercase `.eyebrow` label inside a card, divided
 *   from its neighbours by a hairline rather than a nested box.
 * - Inset box (`.inset-panel`): a small bordered aside inside a card.
 *
 * `compact` is for cards that are themselves items in a grid (a render tile):
 * 16px padding and no heading tile.
 *
 * `flush` is for a card whose first child is a full-bleed row (an accordion
 * header, a group bar): the card chrome stays, the gutter goes, and the row
 * brings its own `row-pad`. It replaces `!p-0 !space-y-0` at the call sites.
 *
 * `collapsed` (ADR 0356, HookSnap only so far) stands the card at its
 * headline alone: the heading row renders exactly as it does open, and
 * the body stands in a hidden wrapper — mounted, unchanged, simply not
 * shown. There is no toggle and no new chrome: the caller drives the
 * flag from its own state, and a caller that never passes it renders
 * byte-for-byte as before. When the flag flips open, the body grows
 * open with the unlock reveal and the card wears its glow for the
 * moment (Kasra's order, Nov 28 2026; see useUnlockReveal below).
 *
 * `bare` (Kasra's order, Nov 27 2026, HookSnap only so far) removes
 * the card as a whole: no `.surface` chrome — no border, no
 * background, no padding — so the section stands on the page itself,
 * its heading row and body exactly as they render inside the card.
 * A section holding one small control in a full-width card reads as
 * mostly empty space, and the eye notices the space because the box
 * draws it; with no box there is no empty width to notice. The
 * heading, the rhythm and the collapse behavior are the card's own,
 * unchanged — only the surface goes.
 */
export function SectionCard({
  title,
  icon,
  description,
  actions,
  compact = false,
  flush = false,
  bare = false,
  headingLevel = "h2",
  collapsed = false,
  revealOnAppear = false,
  children,
  className,
  ...rest
}) {
  const Heading = headingLevel;
  // The unlock reveal (Nov 28 2026): a card that unlocks in
  // sequence grows its body open and wears the glow for the
  // moment; a card that never collapses renders as before. A
  // card that only mounts once its work exists passes
  // revealOnAppear (armed by its host) to play the same reveal
  // on the mount instead of an unlock edge.
  const { revealing, inFlow } = useUnlockReveal(collapsed, revealOnAppear);
  return (
    <div
      className={cn(
        bare
          ? "space-y-5"
          : cn(
              compact ? "surface-compact" : "surface",
              flush ? "surface-flush space-y-0" : "space-y-5",
              "rounded-2xl"
            ),
        revealing && "section-reveal-glow",
        className
      )}
      {...rest}
    >
      {(title || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-4">
          {title && (
            <div className="min-w-0 space-y-1">
              <SectionHeading as={Heading} icon={icon}>{title}</SectionHeading>
              {description && <p className="text-base text-muted-foreground">{description}</p>}
            </div>
          )}
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      <SectionRevealBody collapsed={collapsed} revealing={revealing} inFlow={inFlow}>
        {children}
      </SectionRevealBody>
    </div>
  );
}

// The reveal arms on the founder's first interaction with the
// page. A page's sections all stand collapsed while its draft
// loads and flip open in the settle commit when the draft
// lands — that flip is page load, not an unlock, and Kasra's
// order is explicit that nothing animates on page load. Every
// genuine unlock follows his own taps or keys (a pick made, a
// generation finished after he started it), so each standing
// section listens for the first interaction and arms itself:
// before it, flips settle silently; after it, the collapsed
// edge reveals. A fresh mount starts unarmed, as a page load
// should.

/**
 * The unlock reveal's state (Kasra's order, Nov 28 2026): a
 * collapsible section that flips from collapsed to open plays
 * the Expand reveal once — the hosts below read `revealing` for
 * the animation's ~950ms and wear the glow meanwhile. A section
 * open at first paint never collapsed in this session, so it
 * never reveals: `inFlow` stays false and its body renders bare,
 * exactly as before this round. A section that re-collapses and
 * re-opens reveals again on that open — the transition is the
 * trigger, not the mount. Ordinary re-renders (autosaves, pick
 * changes) never touch the flag: only the collapsed edge does,
 * and only once the reveal is armed (see above) — the load
 * settle never animates.
 */
export function useUnlockReveal(collapsed, revealOnAppear = false) {
  const prevCollapsedRef = useRef(collapsed);
  // `inFlow`: this section has unlocked in the flow of work at
  // least once, so its body rides the grow wrapper (the home the
  // reveal animates, and its resting shape afterwards). A
  // section whose only opening was the load settle never enters
  // the flow: its body renders bare, exactly as before this
  // round — no wrapper, no clipped overflow around content that
  // never animated.
  //
  // `revealOnAppear` (Nov 28 2026) is for a section that does not
  // stand at all until its work exists — HookSnap's Demo + CTA
  // and Post kit render only once the hook video shows (Kasra's
  // order: no container, no heading, nothing before that). Such
  // a section has no collapsed state to flip from, so its host
  // arms the appearance itself: the host passes the flag only
  // when the appearance is an in-flow unlock (its own page has
  // seen the founder's interaction), and the section then mounts
  // already in the flow, playing the same grow + glow once. A
  // host that loads with the work already done passes no flag —
  // the section stands at first paint, unanimated, exactly as
  // every section does on page load.
  const appearRef = useRef(Boolean(revealOnAppear) && !collapsed);
  const flowedRef = useRef(appearRef.current);
  const armedRef = useRef(false);
  const [revealing, setRevealing] = useState(appearRef.current);
  useEffect(() => {
    if (!appearRef.current) return undefined;
    const timer = setTimeout(() => setRevealing(false), 950);
    return () => clearTimeout(timer);
  }, []);
  useEffect(() => {
    const arm = () => {
      armedRef.current = true;
    };
    window.addEventListener("pointerdown", arm);
    window.addEventListener("keydown", arm);
    window.addEventListener("click", arm);
    return () => {
      window.removeEventListener("pointerdown", arm);
      window.removeEventListener("keydown", arm);
      window.removeEventListener("click", arm);
    };
  }, []);
  useEffect(() => {
    const was = prevCollapsedRef.current;
    prevCollapsedRef.current = collapsed;
    if (was && !collapsed && armedRef.current) {
      flowedRef.current = true;
      setRevealing(true);
      const timer = setTimeout(() => setRevealing(false), 950);
      return () => clearTimeout(timer);
    }
    return undefined;
  }, [collapsed]);
  return { revealing, inFlow: flowedRef.current };
}

/**
 * A collapsible section's body under the unlock reveal: while
 * collapsed it stands in the plain hidden wrapper, exactly as
 * before (mounted, unchanged, simply not shown); once the
 * section has unlocked in the flow of work, its shown body
 * rides the grow wrapper — the `.section-reveal` grid whose
 * inner cell clips the expansion — and the revealing state
 * plays the grow + rise once per unlock. A body whose section
 * never unlocked in flow renders bare. `innerClassName` lets a
 * host whose open body was several root children (the presenter
 * panel) keep its spacing rhythm inside the inner cell.
 */
export function SectionRevealBody({ collapsed, revealing, inFlow, innerClassName, children }) {
  if (collapsed) return <div hidden data-collapsed-body="">{children}</div>;
  if (!inFlow) return children;
  return (
    <div className={cn("section-reveal", revealing && "section-reveal-revealing")}>
      <div className={cn("section-reveal-inner", innerClassName)}>{children}</div>
    </div>
  );
}

/** Uppercase label for a group inside a card. Icons only on groups people scan between. */
export function GroupLabel({ icon: Icon, as: Tag = "span", className, children, ...rest }) {
  return (
    <Tag className={cn("eyebrow flex items-center gap-2", className)} {...rest}>
      {Icon && <Icon aria-hidden="true" className="h-3 w-3 shrink-0" />}
      {children}
    </Tag>
  );
}

export default SectionCard;
