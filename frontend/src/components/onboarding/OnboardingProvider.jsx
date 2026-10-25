import { createContext, useCallback, useContext, useEffect, useMemo, useRef, useState } from "react";
import { useLocation } from "react-router-dom";
import { TOURS, getTourIdForPath } from "../../lib/onboarding/tours";
import { readSeenTours, markTourSeen, hasSeenTour } from "../../lib/onboarding/seenTours";
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

// The retired first-run gating persisted seen tour ids under this key. Once
// seen-checking came back (see lib/onboarding/seenTours) this older key is dead
// state, and it is dropped on mount so it can never resurface as a reason a
// tour did not open — nor be read as seen-state for the key that now owns that
// job.
const RETIRED_SEEN_TOURS_KEY = "hookforge_seen_tours";

export function useOnboarding() {
  const ctx = useContext(OnboardingContext);
  if (!ctx) {
    throw new Error("useOnboarding must be used within an OnboardingProvider");
  }
  return ctx;
}

/**
 * The nullable twin: pages and cards that are also mounted outside the
 * provider (the render-smoke suite mounts components bare) read tours when
 * there is a provider and degrade to plain links when there is not, instead
 * of crashing the whole page on a missing context.
 */
export function useOptionalOnboarding() {
  return useContext(OnboardingContext);
}

/**
 * App-wide onboarding tour controller.
 *
 * Wraps the routed app (must live inside <BrowserRouter> since it reads the
 * current location) and:
 *  - Auto-opens a page's tour the FIRST time that page is reached, then not
 *    again. Arriving at a section is the trigger; Escape, the close button, or a
 *    click outside dismisses it. Reaching the same page later is silent, because
 *    a tour that re-greets you every time you navigate back is noise rather than
 *    onboarding — and the sidebar's "Show me around" is one click away for
 *    anyone who wants it again.
 *  - Exposes controls (next/back/skip/replay) consumed by <TourOverlay />.
 *  - Publishes `hasTourForPage` so the sidebar can offer "Show me around" as
 *    an explicit replay, and renders the spotlight/tooltip overlay itself.
 */
export function OnboardingProvider({ children }) {
  const location = useLocation();
  const [activeTourId, setActiveTourId] = useState(null);
  const [stepIndex, setStepIndex] = useState(0);
  // Read once at mount and then owned here, so the auto-start effect below
  // compares against a value it can also update without a storage round-trip.
  const [seenTours, setSeenTours] = useState(() => readSeenTours(window.localStorage));
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
    // Recorded here rather than only on the auto-start path, so a tour opened
    // by hand also counts as seen: it is on screen now, so auto-opening it
    // again on the next arrival would greet someone who just read it.
    setSeenTours((prev) => markTourSeen(window.localStorage, prev, tourId));
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

  // Auto-open the page's tour the first time its route is reached, a beat
  // after navigation so the page has a moment to render before the overlay
  // starts probing the DOM for its first target.
  useEffect(() => {
    if (autoStartTimerRef.current) {
      clearTimeout(autoStartTimerRef.current);
      autoStartTimerRef.current = null;
    }
    if (!pageTourId) return;
    // Once per tour, forever. This is the whole difference between onboarding
    // and an overlay that ambushes you every time you open a page you use
    // daily; "Show me around" covers the deliberate revisit.
    if (hasSeenTour(seenTours, pageTourId)) return;
    // Re-renders of the same page must not restart the tour out from under
    // the user; navigating away and back is a fresh arrival and does open it,
    // until it has been seen.
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
  }, [pageTourId, location.pathname, seenTours]);

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
      // Exposed so a caller can tell "this page has a tour you have already
      // seen" from "this page has no tour at all" — the first is what the
      // sidebar's "Show me around" is replaying, the second means there is
      // nothing to replay.
      hasSeenPageTour: hasSeenTour(seenTours, pageTourId),
      replayCurrentPageTour,
    }),
    [activeTour, currentStep, stepIndex, startTour, stopTour, next, back, skip, pageTourId, seenTours, replayCurrentPageTour]
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
