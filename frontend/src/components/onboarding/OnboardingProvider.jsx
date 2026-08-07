import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { TOURS, getTourIdForPath } from "../../lib/onboarding/tours";
import TourOverlay from "./TourOverlay";
import TourHelpButton from "./TourHelpButton";

const OnboardingContext = createContext(null);

export function useOnboarding() {
  const ctx = useContext(OnboardingContext);
  if (!ctx) {
    throw new Error("useOnboarding must be used within an OnboardingProvider");
  }
  return ctx;
}

/**
 * App-wide onboarding tour controller.
 *
 * Wraps the routed app (must live inside <BrowserRouter> since it reads the
 * current location) and:
 *  - Auto-starts the relevant page tour every time a user visits (or
 *    revisits) a route that has one. Unlike a typical one-time onboarding
 *    flow, this is intentionally NOT tracked/suppressed across sessions —
 *    the tour reappears on every page load, per the product requirement
 *    that it act as an always-on guide rather than a first-run-only intro.
 *  - Exposes controls (next/back/skip/replay) consumed by <TourOverlay />.
 *  - Renders a small floating "Tour" button on any page with a tour so users
 *    can replay it on demand, and the spotlight/tooltip overlay itself.
 */
export function OnboardingProvider({ children }) {
  const location = useLocation();
  const [activeTourId, setActiveTourId] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  const autoStartTimerRef = useRef(null);
  // Tracks which page pathname we've already auto-started a tour for during
  // THIS mount, so re-rendering the same page (e.g. state updates) doesn't
  // keep restarting the tour out from under the user — but navigating away
  // and back, or a full page reload, starts it fresh again.
  const autoStartedForPathRef = useRef(null);

  const pageTourId = getTourIdForPath(location.pathname);
  const activeTour = activeTourId ? TOURS[activeTourId] : null;
  const currentStep = activeTour ? activeTour.steps[stepIndex] : null;

  const startTour = useCallback((tourId) => {
    if (!TOURS[tourId]) return;
    setActiveTourId(tourId);
    setStepIndex(0);
  }, []);

  const stopTour = useCallback(() => {
    setActiveTourId(null);
    setStepIndex(0);
  }, []);

  const next = useCallback(() => {
    if (!activeTour) return;
    if (stepIndex + 1 >= activeTour.steps.length) {
      // Last step — close out the tour instead of stepping past the end.
      setActiveTourId(null);
      setStepIndex(0);
      return;
    }
    setStepIndex((i) => i + 1);
  }, [activeTour, stepIndex]);

  const back = useCallback(() => {
    setStepIndex((i) => Math.max(0, i - 1));
  }, []);

  const skip = useCallback(() => {
    stopTour();
  }, [stopTour]);

  // Auto-start the page's tour every time its route is entered, a beat after
  // navigation so async data (niche list, hook analysis, etc.) has a moment
  // to load before the overlay starts probing the DOM for its first target.
  useEffect(() => {
    if (autoStartTimerRef.current) {
      clearTimeout(autoStartTimerRef.current);
      autoStartTimerRef.current = null;
    }
    if (!pageTourId) return;
    if (autoStartedForPathRef.current === location.pathname) return;
    autoStartTimerRef.current = setTimeout(() => {
      autoStartedForPathRef.current = location.pathname;
      startTour(pageTourId);
    }, 700);
    return () => {
      if (autoStartTimerRef.current) clearTimeout(autoStartTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageTourId, location.pathname]);

  // If the user navigates to a page with a different (or no) tour while one
  // is open, close the overlay rather than letting it follow them somewhere
  // its steps no longer apply.
  useEffect(() => {
    setActiveTourId((currentId) => (currentId && currentId !== pageTourId ? null : currentId));
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [location.pathname]);

  const replayCurrentPageTour = useCallback(() => {
    if (pageTourId) startTour(pageTourId);
  }, [pageTourId, startTour]);

  const value = useMemo(
    () => ({
      activeTour,
      currentStep,
      stepIndex,
      totalSteps: activeTour?.steps.length || 0,
      startTour,
      stopTour,
      next,
      back,
      skip,
      pageTourId,
      hasTourForPage: !!pageTourId,
      replayCurrentPageTour,
    }),
    [activeTour, currentStep, stepIndex, startTour, stopTour, next, back, skip, pageTourId, replayCurrentPageTour]
  );

  return (
    <OnboardingContext.Provider value={value}>
      {children}
      <TourOverlay />
      <TourHelpButton />
    </OnboardingContext.Provider>
  );
}

export default OnboardingProvider;
