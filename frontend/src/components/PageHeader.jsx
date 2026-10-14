import { IconTile } from "./IconTile";

/**
 * Standard page masthead used across every in-app screen.
 *
 * Purely presentational — it exists so titles, ledes, icon tiles and the
 * optional right-hand action slot line up identically on every page instead
 * of each one hand-rolling its own heading block.
 */
export function PageHeader({ icon, eyebrow, title, description, actions, align = "left", ...rest }) {
  const centered = align === "center";

  return (
    <div
      className={`flex flex-col gap-4 ${
        centered ? "items-center text-center" : "sm:flex-row sm:items-center sm:justify-between"
      }`}
      {...rest}
    >
      <div className={`min-w-0 ${centered ? "flex flex-col items-center" : ""}`}>
        <div className={`flex items-center gap-3 ${centered ? "justify-center" : ""}`}>
          {icon && <IconTile icon={icon} size="page" />}
          <div className="min-w-0">
            {eyebrow && <span className="eyebrow block">{eyebrow}</span>}
            <h1 className="font-display truncate text-2xl font-semibold tracking-tight">
              {title}
            </h1>
          </div>
        </div>
        {description && (
          <p
            className={`mt-2 text-sm leading-relaxed text-muted-foreground ${
              centered ? "max-w-xl" : "max-w-2xl"
            }`}
          >
            {description}
          </p>
        )}
      </div>
      {actions && <div className="flex shrink-0 flex-wrap items-center gap-2">{actions}</div>}
    </div>
  );
}

export default PageHeader;
