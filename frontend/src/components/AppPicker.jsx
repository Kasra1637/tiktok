import { profileLabel } from "../lib/profileSelection";
import { cn } from "../lib/utils";

/** The pill dropdown used in page headers and filter bars. */
/** Shared by every filter bar, so the 44px coarse-pointer rule lands on all
    of them at once: a 32px pill is a comfortable click and a miss with a thumb. */
export const PILL_SELECT_CLASS =
  "pill-studio tap-chip h-8 rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-3 text-sm font-semibold text-foreground hover:border-[color:var(--hairline-strong)]";

/**
 * Which app a page is showing. One picker for every sidebar page, so the
 * control looks and reads the same wherever the founder switches apps.
 *
 * `allLabel` adds an "every app" option (a filter); `placeholder` adds a
 * disabled prompt for pages that may start with nothing chosen.
 */
export function AppPicker({
  profiles,
  value,
  onChange,
  allLabel,
  placeholder,
  showStatus = false,
  ariaLabel = "Select App Profile",
  testId,
  id,
  className,
}) {
  return (
    <select
      id={id}
      value={value || ""}
      onChange={(e) => onChange(e.target.value)}
      aria-label={ariaLabel}
      data-testid={testId}
      className={cn(PILL_SELECT_CLASS, className)}
    >
      {allLabel && <option value="">{allLabel}</option>}
      {placeholder && (
        <option value="" disabled>
          {placeholder}
        </option>
      )}
      {profiles.map((p) => (
        <option key={p.id} value={p.id}>
          {profileLabel(p)}
          {showStatus && p.status !== "approved" ? " (needs approval)" : ""}
        </option>
      ))}
    </select>
  );
}

export default AppPicker;
