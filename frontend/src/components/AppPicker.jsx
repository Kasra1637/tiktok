import { profileLabel } from "../lib/profileSelection";
import { cn } from "../lib/utils";
import { AppSelect } from "./AppSelect";

/** The pill dropdown used in page headers and filter bars. */
/** Shared by every filter bar, so the 44px coarse-pointer rule lands on all
    of them at once: a 32px pill is a comfortable click and a miss with a thumb.
    It also carries the one filter treatment (ADR 0161): `filter-control`
    states a filter's condition in index.css — an active filter wears the
    selection indigo — and `focus-ring` gives keyboard users the same halo
    the chips get, on every filter bar at once. The menu under the pill is
    the app's own listbox (ADR 0162, `AppSelect`): a native select's
    open menu belongs to the browser and ignores all of this. */
export const PILL_SELECT_CLASS =
  "pill-studio tap-chip filter-control focus-ring h-10 rounded-full border border-[color:var(--hairline)] bg-secondary/30 px-4 text-sm font-semibold text-foreground hover:border-[color:var(--hairline-strong)]";

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
  align,
}) {
  // In its filter form (an "every app" option exists) a chosen app is an
  // active filter and says so on its face (ADR 0161). As a page's app
  // switcher the picker names the current context instead — always
  // chosen, never "filtering" — so it never wears the active state.
  const filterActive = Boolean(allLabel) && Boolean(value);
  const options = [
    ...(allLabel ? [{ value: "", label: allLabel }] : []),
    ...profiles.map((p) => ({
      value: p.id,
      label: `${profileLabel(p)}${showStatus && p.status !== "approved" ? " (needs approval)" : ""}`,
    })),
  ];
  return (
    <AppSelect
      id={id}
      options={options}
      value={value || ""}
      onChange={onChange}
      ariaLabel={ariaLabel}
      testId={testId}
      dataActive={filterActive}
      className={cn(PILL_SELECT_CLASS, className)}
      placeholder={placeholder}
      align={align}
    />
  );
}

export default AppPicker;
