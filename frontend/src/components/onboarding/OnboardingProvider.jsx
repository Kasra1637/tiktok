import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { TOURS, getTourIdForPath } from "../../lib/onboarding/tours";
import TourOverlay from "./TourOverlay";
import TourHelpButton from "./TourHelpButton";

const OnboardingContext = createContext(null);

/**
 * How long after a route is entered its tour opens.
 *
 * Short enough to feel immediate, long enough for the page to render before
 * the overlay starts probing the DOM for its first target. TourOverlay keeps
 * polling for a missing target for up to 3.5s anyway, so this is a feel, not
 * a correctness deadline.
 */
const AUTO_START_DELAY_MS = 400;

// The retired first-run gating persisted seen tour ids under this key. Tours
// now open on every arrival, so the key is dead state — dropped on mount so it
// can never resurface as a reason a tour did not open.
const RETIRED_SEEN_TOURS_KEY = "hookforge_seen_tours";

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
 *  - Auto-opens a page's tour EVERY time the user lands on a route that has
 *    one — no "Show me around" click needed and no seen-check. Arriving at a
 *    section is the trigger; Escape, the close button, or a click outside
 *    dismiss the tour, and the next arrival opens it again. The old
 *    localStorage seen-check showed each tour at most once ever, which is why
 *    the pop-up stopped greeting anyone: the code existed, the trigger did not.
 *  - Exposes controls (next/back/skip/replay) consumed by <TourOverlay />.
 *  - Publishes `hasTourForPage` so the sidebar can offer "Show me around" as
 *    an explicit replay, and renders the spotlight/tooltip overlay itself.
 */
export function OnboardingProvider({ children }) {
  const location = useLocation();
  const [activeTourId, setActiveTourId] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  const autoStartTimerRef = useRef(null);
  // Tracks which page pathname we've already auto-opened a tour for during
  // THIS mount, so re-rendering the same page (e.g. state updates) doesn't
  // keep restarting the tour out from under the user — while navigating away
  // and back, or a full page reload, opens it fresh again.
  const autoStartedForPathRef = useRef(null);
  // The auto-start timer deliberately closes over the state of its effect run,
  // so it reads this mirror to avoid clobbering a tour the user opened by hand
  // inside the delay window.
  const activeTourIdRef = useRef(null);

  const pageTourId = getTourIdForPath(location.pathname);
  const activeTour = activeTourId ? TOURS[activeTourId] : null;
  const currentStep = activeTour ? activeTour.steps[stepIndex] : null;

  useEffect(() => {
    activeTourIdRef.current = activeTourId;
  }, [activeTourId]);

  // Drop the retired first-run bookkeeping so nothing can read it again.
  useEffect(() => {
    try {
      window.localStorage.removeItem(RETIRED_SEEN_TOURS_KEY);
    } catch {
      // Private mode / storage disabled — nothing to clean up.
    }
  }, []);

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

  // Auto-open the page's tour every time its route is entered, a beat after
  // navigation so the page has a moment to render before the overlay starts
  // probing the DOM for its first target.
  useEffect(() => {
    if (autoStartTimerRef.current) {
      clearTimeout(autoStartTimerRef.current);
      autoStartTimerRef.current = null;
    }
    if (!pageTourId) return;
    // Re-renders of the same page must not restart the tour out from under
    // the user; navigating away and back is a fresh arrival and does re-open.
    if (autoStartedForPathRef.current === location.pathname) return;
    autoStartTimerRef.current = setTimeout(() => {
      autoStartTimerRef.current = null;
      autoStartedForPathRef.current = location.pathname;
      // Never clobber a tour that is already open — e.g. one the user opened
      // from the sidebar's "Show me around" button inside the delay window.
      if (activeTourIdRef.current) return;
      startTour(pageTourId);
    }, AUTO_START_DELAY_MS);
    return () => {
      if (autoStartTimerRef.current) clearTimeout(autoStartTimerRef.current);
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageTourId, location.pathname]);

  // If the user navigates to a page with a different (or no) tour while one
  // is open, close the overlay rather than letting it follow them somewhere
  // its steps no longer apply. The arrival effect above then opens the new
  // page's own tour.
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
