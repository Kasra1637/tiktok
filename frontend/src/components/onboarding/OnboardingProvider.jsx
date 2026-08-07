import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { TOURS, getTourIdForPath } from "../../lib/onboarding/tours";
import TourOverlay from "./TourOverlay";
import TourHelpButton from "./TourHelpButton";

const STORAGE_KEY = "hookforge_onboarding_seen_tours";

function loadSeenTours() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const arr = raw ? JSON.parse(raw) : [];
    return new Set(Array.isArray(arr) ? arr : []);
  } catch {
    return new Set();
  }
}

function persistSeenTours(set) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(Array.from(set)));
  } catch {
    // localStorage unavailable (private mode, quota, etc) — onboarding will
    // just replay each visit. Non-fatal, so we swallow the error.
  }
}

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
 *  - Auto-starts the relevant page tour the first time a user visits a route
 *    that has one, tracked per-browser via localStorage so it never repeats.
 *  - Exposes controls (next/back/skip/replay) consumed by <TourOverlay />.
 *  - Renders a small floating "Tour" button on any page with a tour so users
 *    can replay it on demand, and the spotlight/tooltip overlay itself.
 */
export function OnboardingProvider({ children }) {
  const location = useLocation();
  const [seenTours, setSeenTours] = useState(loadSeenTours);
  const [activeTourId, setActiveTourId] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  const autoStartTimerRef = useRef(null);

  const pageTourId = getTourIdForPath(location.pathname);
  const activeTour = activeTourId ? TOURS[activeTourId] : null;
  const currentStep = activeTour ? activeTour.steps[stepIndex] : null;

  const markSeen = useCallback((tourId) => {
    setSeenTours((prev) => {
      if (prev.has(tourId)) return prev;
      const next = new Set(prev);
      next.add(tourId);
      persistSeenTours(next);
      return next;
    });
  }, []);

  const startTour = useCallback(
    (tourId) => {
      if (!TOURS[tourId]) return;
      setActiveTourId(tourId);
      setStepIndex(0);
      markSeen(tourId);
    },
    [markSeen]
  );

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

  // Auto-start the page's tour once per browser, a beat after navigation so
  // async data (niche list, hook analysis, etc.) has a moment to load before
  // the overlay starts probing the DOM for its first target.
  useEffect(() => {
    if (autoStartTimerRef.current) {
      clearTimeout(autoStartTimerRef.current);
      autoStartTimerRef.current = null;
    }
    if (!pageTourId || seenTours.has(pageTourId) || activeTourId) return;
    autoStartTimerRef.current = setTimeout(() => startTour(pageTourId), 700);
    return () => {
      if (autoStartTimerRef.current) clearTimeout(autoStartTimerRef.current);
    };
    // Re-evaluate only when the resolved tour for this page changes, not on
    // every location change (e.g. query-string-only navigation within the
    // same page/tour shouldn't retrigger this).
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [pageTourId, seenTours, activeTourId]);

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
