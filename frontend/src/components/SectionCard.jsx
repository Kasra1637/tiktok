import { cn } from "../lib/utils";

/**
 * A content card: the app's one container for a group of related things.
 *
 * Padding lives in `.surface` in `index.css` (24px / 32px) — do not add `p-*`
 * here or at call sites. Outer widths are untouched; this only narrows the
 * inner content with roomier gutters.
 *
 * `title` renders as `.eyebrow`: a GROUP LABEL, and keeping that distinction is
 * the point. Identity in this app is the display face at semibold (which app,
 * which video); a card holding a set of things has no identity and gets a quiet
 * uppercase label instead. Analytics was using a display heading for those,
 * which made a breakdown title compete with the numbers beneath it.
 *
 * Pass no `title` for a card that IS one thing rather than a set.
 */
export function SectionCard({ title, icon: Icon, actions, children, className, ...rest }) {
  return (
    <div className={cn("surface space-y-2 rounded-2xl", className)} {...rest}>
      {(title || actions) && (
        <div className="flex flex-wrap items-center justify-between gap-2">
          {title && (
            <span className="eyebrow flex items-center gap-1.5">
              {Icon && <Icon className="h-3 w-3" />}
              {title}
            </span>
          )}
          {actions}
        </div>
      )}
      {children}
    </div>
  );
}

export default SectionCard;