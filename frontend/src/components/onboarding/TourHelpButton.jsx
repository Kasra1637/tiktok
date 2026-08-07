import { HelpCircle } from "lucide-react";
import { useOnboarding } from "./OnboardingProvider";

/**
 * Floating "replay the tour for this page" trigger. Hidden while a tour is
 * already active (the tooltip's own close/progress controls take over) and
 * on pages with no defined tour.
 */
export function TourHelpButton() {
  const { hasTourForPage, activeTour, replayCurrentPageTour } = useOnboarding();

  if (!hasTourForPage || activeTour) return null;

  return (
    <button
      onClick={replayCurrentPageTour}
      className="fixed bottom-4 left-4 z-40 flex items-center gap-1.5 rounded-full border border-border bg-card/95 backdrop-blur-sm px-3 py-2 text-xs font-medium text-muted-foreground shadow-md hover:text-[color:var(--brand-teal)] hover:border-[color:rgba(13,148,136,0.35)] transition-colors"
      data-testid="onboarding-replay-tour-button"
      title="Replay the guided tour for this page"
    >
      <HelpCircle className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">Show me around</span>
    </button>
  );
}

export default TourHelpButton;
