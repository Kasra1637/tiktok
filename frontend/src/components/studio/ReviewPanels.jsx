import { CONTROL_CLASS } from "../formControls";

/**
 * One profile-aware dropdown for a Review-step direction field.
 *
 * The options come from the profile's category group (no free typing), and
 * picking only fills the draft — saving still validates like any edit
 * and the strategy still needs a rebuild, exactly as with typed notes.
 */
export function DirectionSelect({
  id,
  testId,
  label,
  value,
  onPick,
  options,
  placeholder,
  disabled,
  // Fresh-list generation for this dropdown alone. When provided, a small
  // action beside the label spends one text model call for four new options
  // grounded in the profile and the selected angle — the static category
  // list repeats itself across videos, and a founder who has seen all four
  // has nowhere else to go. { onRefresh, refreshing, refreshTestId }.
  refresh = null,
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <label htmlFor={id} className="text-sm font-semibold">{label}</label>
        {refresh && (
          <button
            type="button"
            onClick={refresh.onRefresh}
            disabled={disabled || refresh.refreshing}
            data-testid={refresh.refreshTestId}
            className="shrink-0 text-sm text-muted-foreground underline disabled:opacity-50"
          >
            {refresh.refreshing ? "Finding new options…" : "New options"}
          </button>
        )}
      </div>
      <select
        id={id}
        data-testid={testId}
        className={CONTROL_CLASS}
        value={value}
        disabled={disabled || !options}
        onChange={(e) => onPick(e.target.value)}
      >
        <option value="">{options ? placeholder : "Loading options…"}</option>
        {(options || []).map((option) => (
          <option key={option} value={option}>{option}</option>
        ))}
      </select>
    </div>
  );
}

/**
 * The plan writes in one call with no observable intermediate stages, and
 * the Review step now carries the wait on the progress button itself
 * ("Generating your plan" with a looping sweep) instead of a phase line
 * cycling invented stage names. The export keeps the name the page imports
 * so the panel wiring does not churn; it renders nothing — the button is
 * the only narrator while the plan writes.
 */
export function PlanPhaseLine() {
  return null;
}
