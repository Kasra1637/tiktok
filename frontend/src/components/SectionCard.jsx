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
 * byte-for-byte as before.
 */
export function SectionCard({
  title,
  icon,
  description,
  actions,
  compact = false,
  flush = false,
  headingLevel = "h2",
  collapsed = false,
  children,
  className,
  ...rest
}) {
  const Heading = headingLevel;
  return (
    <div
      className={cn(
        compact ? "surface-compact" : "surface",
        flush ? "surface-flush space-y-0" : "space-y-5",
        "rounded-2xl",
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
      {collapsed ? <div hidden data-collapsed-body="">{children}</div> : children}
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
