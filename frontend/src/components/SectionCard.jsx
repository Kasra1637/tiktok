import { cn } from "../lib/utils";
import { IconTile } from "./IconTile";

/**
 * The page's container levels, shared by every sidebar page:
 *
 * - Section card (this): a main block of the page. 32px icon tile + 16px
 *   heading, optional one-line description. Padding lives in `.surface`.
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
 */
export function SectionCard({
  title,
  icon,
  description,
  actions,
  compact = false,
  flush = false,
  headingLevel = "h2",
  children,
  className,
  ...rest
}) {
  const Heading = headingLevel;
  return (
    <div
      className={cn(
        compact ? "surface-compact" : "surface",
        flush ? "surface-flush space-y-0" : "space-y-4",
        "rounded-2xl",
        className
      )}
      {...rest}
    >
      {(title || actions) && (
        <div className="flex flex-wrap items-start justify-between gap-4">
          {title && (
            <div className="flex min-w-0 items-start gap-3">
              {icon && <IconTile icon={icon} size="section" />}
              <div className="min-w-0">
                <Heading className="font-display text-base font-semibold leading-8">{title}</Heading>
                {description && <p className="text-sm text-muted-foreground">{description}</p>}
              </div>
            </div>
          )}
          {actions && <div className="flex shrink-0 items-center gap-2">{actions}</div>}
        </div>
      )}
      {children}
    </div>
  );
}

/** Uppercase label for a group inside a card. Icons only on groups people scan between. */
export function GroupLabel({ icon: Icon, as: Tag = "span", className, children, ...rest }) {
  return (
    <Tag className={cn("eyebrow flex items-center gap-2", className)} {...rest}>
      {Icon && <Icon className="h-3 w-3 shrink-0" />}
      {children}
    </Tag>
  );
}

export default SectionCard;
