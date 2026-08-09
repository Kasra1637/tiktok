/**
 * Selectable pill used for filters, categories and segmented choices.
 *
 * Consolidates four near-identical hand-rolled chip styles that had drifted
 * apart across NicheFeed, HookTemplates and the save/edit template dialogs.
 * Purely presentational: it renders a <button> and forwards click/aria state.
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
}) {
  const sizing =
    size === "md" ? "px-3.5 py-1.5 text-[13px] gap-1.5" : "px-2.5 py-1 text-xs gap-1";

  const activeTone =
    tone === "coral"
      ? "border-transparent bg-[color:var(--brand-coral)] text-white shadow-[var(--glow-coral)]"
      : "border-transparent bg-[color:var(--brand-indigo)] text-white shadow-[var(--glow-indigo)]";

  return (
    <button
      type={type}
      onClick={onClick}
      disabled={disabled}
      aria-pressed={active}
      title={title}
      data-testid={testId}
      className={`inline-flex shrink-0 items-center rounded-full border font-medium transition-[background-color,border-color,color,box-shadow] duration-200 disabled:cursor-not-allowed disabled:opacity-50 ${sizing} ${
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
