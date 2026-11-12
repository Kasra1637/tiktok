import { HelpCircle } from "lucide-react";
import { useOptionalOnboarding } from "./OnboardingProvider";
import { TOURS } from "../../lib/onboarding/tours";

/**
 * "Show me around" at the moment of confusion: empty states offer the
 * page's own tour inline, instead of help existing only as an up-front
 * auto-open or a sidebar replay the founder has to go looking for.
 *
 * Renders nothing when there is no provider (components also mount bare
 * in the render-smoke suite) or no tour under the given id — the same
 * silent degradation other optional-onboarding consumers use.
 */
export default function TourStartLink({ tourId, className }) {
  const onboarding = useOptionalOnboarding();
  if (!onboarding?.startTour || !TOURS[tourId]) return null;
  return (
    <button
      type="button"
      onClick={() => onboarding.startTour(tourId)}
      data-testid={`tour-start-link-${tourId}`}
      className={
        className ||
        "inline-flex items-center gap-1.5 text-sm font-semibold text-[color:var(--brand-indigo)] transition-colors hover:underline"
      }
    >
      <HelpCircle className="h-3.5 w-3.5" />
      Show me around
    </button>
  );
}
