import { useEffect, useState } from "react";
import { CONTROL_CLASS } from "../formControls";

const PLAN_PHASES = ["Writing the hook…", "Writing the script…", "Placing the shots…", "Adding the demo note…"];

/**
 * One profile-aware dropdown for a Review-step direction field.
 *
 * The options come from the profile's category group (no free typing), and
 * picking only fills the draft — saving still runs the normal claim check
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
 * Live narration while the plan writes. The artifact arrives whole, so there
 * is nothing honest to count — but its sections are known up front (hook,
 * script, shots, demo note), and naming the current one beats a static line
 * that never moves. Unmounts with its branch, so a failure can never strand
 * it beside the error; the interval dies with the component.
 */
export function PlanPhaseLine() {
  const [index, setIndex] = useState(0);
  useEffect(() => {
    const timer = setInterval(() => {
      setIndex((i) => (i + 1) % PLAN_PHASES.length);
    }, 1800);
    return () => clearInterval(timer);
  }, []);
  return (
    <span role="status" data-testid="plan-progress">
      {PLAN_PHASES[index]}
    </span>
  );
}
