import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { TOURS, getTourIdForPath } from "../../lib/onboarding/tours";
import TourOverlay from "./TourOverlay";
import TourHelpButton from "./TourHelpButton";

const OnboardingContext = createContext(null);

const SEEN_TOURS_KEY = "hookforge_seen_tours";

/** Tour ids the user has already been shown, from localStorage. */
function readSeenTours() {
  try {
    const parsed = JSON.parse(localStorage.getItem(SEEN_TOURS_KEY) || "null");
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    // Unavailable or corrupt storage. Returning [] means the tour auto-starts
    // again, which is the safe direction to fail: annoying, never broken.
    return [];
  }
}

function markTourSeen(tourId) {
  try {
    const seen = readSeenTours();
    if (!seen.includes(tourId)) {
      localStorage.setItem(SEEN_TOURS_KEY, JSON.stringify([...seen, tourId]));
    }
  } catch {
    // Private mode / quota. The tour will simply offer itself again.
  }
}

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
 *  - Auto-starts a page's tour the FIRST time a user reaches a route that has
 *    one, then never again: seen tour ids are persisted to localStorage under
 *    `hookforge_seen_tours`. Previously the tour re-ran on every visit and
 *    every reload, which meant a returning creator moving between pages
 *    was interrupted by a modal spotlight on each hop. Replay stays available on demand via the sidebar's
 *    "Show me around" button, which bypasses the seen check.
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

  // Auto-start the page's tour the first time its route is entered, a beat
  // after navigation so async data (niche list, hook analysis, etc.) has a
  // moment to load before the overlay starts probing the DOM for its first
  // target.
  useEffect(() => {
    if (autoStartTimerRef.current) {
      clearTimeout(autoStartTimerRef.current);
      autoStartTimerRef.current = null;
    }
    if (!pageTourId) return;
    if (autoStartedForPathRef.current === location.pathname) return;
    // First-run only. Checked here rather than inside the timeout so no timer
    // is even scheduled for a tour the user has already seen.
    if (readSeenTours().includes(pageTourId)) return;
    autoStartTimerRef.current = setTimeout(() => {
      autoStartedForPathRef.current = location.pathname;
      // Marked on start, not on completion: a user who dismisses the tour or
      // reloads midway through has still been shown it, and re-running would
      // be the exact nagging this replaced.
      markTourSeen(pageTourId);
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
