import { HelpCircle } from "lucide-react";
import { useOnboarding } from "./OnboardingProvider";

/**
 * Floating "replay the tour for this page" trigger. Hidden while a tour is
 * already active (the tooltip's own close/progress controls take over) and
 * on pages with no defined tour.
 *
 * Positioning note: this is pinned bottom-left, which is exactly where the
 * app's left sidebar now lives. `--app-sidebar-w` is published on :root by
 * AppShell (and reset to 0px on pages without a shell, e.g. Landing), so the
 * button slides clear of the panel at `lg` and up instead of hiding behind it.
 */
export function TourHelpButton() {
  const { hasTourForPage, activeTour, replayCurrentPageTour } = useOnboarding();

  if (!hasTourForPage || activeTour) return null;

  return (
    <button
      onClick={replayCurrentPageTour}
      className="group fixed bottom-4 left-4 z-40 flex items-center gap-1.5 rounded-full border border-[color:var(--hairline)] bg-[hsl(228_14%_10%_/_0.9)] px-3 py-2 text-xs font-medium text-muted-foreground shadow-[var(--shadow-lg)] backdrop-blur-md transition-colors hover:border-[color:var(--indigo-35)] hover:text-[color:var(--brand-teal)] lg:left-[calc(var(--app-sidebar-w,0px)+1rem)]"
      data-testid="onboarding-replay-tour-button"
      title="Replay the guided tour for this page"
    >
      <HelpCircle className="h-3.5 w-3.5" />
      <span className="hidden sm:inline">Show me around</span>
    </button>
  );
}

export default TourHelpButton;
