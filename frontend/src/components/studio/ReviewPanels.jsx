
/**
 * One profile-aware set of option buttons for a direction field (the
 * section sits on the Audience & template step since ADR 0220; this
 * file keeps the name it shares with the plan-phase narration below).
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
  // Fresh-list generation for this field alone. When provided, the
  // "New options" action beside the label spends one text model call
  // for four new options grounded in the profile and the selected
  // angle — the static category list repeats itself across videos, and
  // a founder who has seen all four has nowhere else to go.
  // { onRefresh, refreshing, refreshTestId }.
  refresh = null,
}) {
  // Three options stand side by side (ADR 0330, as corrected at
  // Kasra's live review): the buttons wear the Voice pick's own
  // design — the rounded pills with the indigo selection, moving
  // with the render panels' resolution buttons' own motion (the
  // 300ms ease and the 1px hover lift) — spaced
  // by the row's gap, never stuck together, and "New options" above
  // brings the next set when none of the three fits. A saved pick
  // outside the shown three still applies: it takes the last seat,
  // so what applies is always on a lit button. The notes beside the
  // control say so, exactly as they did for the dropdown.
  const all = options || [];
  let shown = all.slice(0, 3);
  if (value && all.includes(value) && !shown.includes(value)) {
    shown = [...all.slice(0, 2), value];
  }
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <span id={`${id}-label`} className="text-sm font-semibold">{label}</span>
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
      <div
        className="flex flex-wrap gap-2"
        role="group"
        aria-labelledby={`${id}-label`}
        data-testid={testId}
        data-value={value || ""}
      >
        {!options ? (
          <span className="text-sm text-muted-foreground">Loading options…</span>
        ) : (
          shown.map((option) => {
            const picked = value === option;
            return (
              <button
                key={option}
                type="button"
                aria-pressed={picked}
                data-value={option}
                disabled={disabled}
                onClick={() => onPick(option)}
                className={`rounded-full border px-3 py-1 text-xs font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-300 ease-out hover:-translate-y-[1px] active:translate-y-0 motion-reduce:hover:-translate-y-0 ${
                  picked
                    ? "border-[color:var(--indigo-35)] bg-[color:var(--indigo-6)] text-[color:var(--brand-indigo)]"
                    : "border-[color:var(--hairline)] text-muted-foreground"
                }`}
              >
                {option}
              </button>
            );
          })
        )}
      </div>
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
