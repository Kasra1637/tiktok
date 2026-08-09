/**
 * Shared step-progress primitives.
 *
 * This file previously exported a four-stage pipeline stepper
 * (find -> analyze -> swap -> video) that nothing ever imported, while
 * FaceSwap hand-rolled its own progress dots and numbered badges inline. Two
 * descriptions of "where am I", one of them dead. The shipped model won: these
 * are the components FaceSwap actually uses, extracted so any other screen
 * gets the same vocabulary instead of rolling a third variant.
 *
 * Progress is deliberately scoped to a single screen's steps rather than the
 * whole app pipeline. Cross-page position is already conveyed by the sidebar's
 * active nav item, and duplicating it here is what made the two models
 * disagree in the first place.
 */
import { Check } from "lucide-react";

/**
 * Dot-and-rail progress for a short, linear flow.
 *
 * @param total    number of steps
 * @param current  1-based index of the active step
 * @param complete when true every step reads as done (the flow has finished)
 */
export function StepDots({ total = 3, current = 1, complete = false, testId }) {
  const steps = Array.from({ length: total }, (_, i) => i + 1);

  return (
    <div
      className="flex items-center justify-center gap-2"
      role="progressbar"
      aria-valuemin={1}
      aria-valuemax={total}
      aria-valuenow={complete ? total : current}
      aria-label={
        complete
          ? `All ${total} steps complete`
          : `Step ${current} of ${total}`
      }
      data-testid={testId}
    >
      {steps.map((step) => {
        const filled = complete || step < current;
        const active = !complete && step === current;
        return (
          <div key={step} className="flex items-center gap-2" aria-hidden="true">
            <div
              className={`h-2 rounded-full transition-all duration-300 ${
                filled
                  ? "w-2 bg-[color:var(--brand-indigo)]"
                  : active
                  ? "w-7 bg-[color:var(--brand-indigo)]"
                  : "w-2 bg-border"
              }`}
            />
            {step < total && (
              <div
                className={`h-px w-8 transition-colors duration-300 ${
                  step < current || complete
                    ? "bg-[color:var(--brand-indigo)]"
                    : "bg-border"
                }`}
              />
            )}
          </div>
        );
      })}
    </div>
  );
}

/**
 * Numbered badge that labels a step inline next to its heading. Shows a check
 * once done. Decorative: the adjacent heading carries the accessible name, so
 * this is hidden from assistive tech to avoid announcing a bare digit.
 */
export function StepBadge({ done, current, children }) {
  return (
    <span
      aria-hidden="true"
      className={`flex h-6 w-6 shrink-0 items-center justify-center rounded-full text-xs font-bold ${
        done
          ? "bg-[color:var(--brand-indigo)] text-white"
          : current
          ? "bg-[color:var(--brand-coral)] text-white"
          : "bg-secondary text-muted-foreground"
      }`}
    >
      {done ? <Check className="h-3 w-3" /> : children}
    </span>
  );
}

export default StepDots;
