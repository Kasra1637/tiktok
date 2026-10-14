/**
 * Selectable pill used for filters, categories and segmented choices.
 *
 * Consolidates the hand-rolled chip styles used across filter and
 * category pickers. Purely presentational: it renders a <button> and forwards
 * click/aria state.
 */
export function Chip({
  children,
  active = false,
  onClick,
  icon: Icon,
  size = "sm",
  tone = "indigo",
  title,
  testId,
  type = "button",
  disabled,
  /**
   * Overrides the accessible name. Use when the visible label only makes sense
   * next to its group heading — e.g. a duration chip reading "0-15s".
   * The chip's group should also carry a role="group" + aria-label so the
   * pressed state is announced with the thing it filters.
   */
  ariaLabel,
}) {
  const sizing =
    size === "md" ? "px-3.5 py-1.5 text-sm gap-1.5" : "px-2.5 py-1 text-xs gap-1";

  const activeTone =
    tone === "coral"
      ? "btn-bevel-brand border-white/15 bg-[color:var(--brand-coral)] text-white"
      : "btn-bevel-accent border-white/15 bg-[color:var(--brand-indigo)] text-white";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      aria-label={ariaLabel}
      title={title}
      data-testid={testId}
      className={`pill-studio inline-flex shrink-0 items-center rounded-full border font-semibold disabled:cursor-not-allowed disabled:opacity-50 ${sizing} ${
        active
          ? activeTone
          : "border-[color:var(--hairline)] bg-secondary/40 text-muted-foreground hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] hover:text-foreground"
      }`}
    >
      {Icon && <Icon className={size === "md" ? "h-3.5 w-3.5" : "h-3 w-3"} />}
      {children}
    </button>
  );
}

export default Chip;
