import { useEffect, useState } from "react";

// Tailwind's lg breakpoint, asked as a media query. At or above it the
// Create wizard stands one step at a time, each step its own page
// (ADR 0141); below it the wizard is the stacked canvas (ADR 0099).
export const DESKTOP_PAGES_QUERY = "(min-width: 1024px)";

function readDesktopWidth() {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia(DESKTOP_PAGES_QUERY).matches;
}

/**
 * Browser-native desktop-width hook, the same guarded shape as
 * useReducedMotionPreference: no matchMedia (a test DOM, an old browser)
 * reads as not-desktop, so the stacked canvas — the long-standing shape —
 * is the fallback, never an exception.
 */
export function useDesktopWidth() {
  const [desktop, setDesktop] = useState(readDesktopWidth);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return undefined;
    const query = window.matchMedia(DESKTOP_PAGES_QUERY);
    const update = () => setDesktop(query.matches);
    update();
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", update);
      return () => query.removeEventListener("change", update);
    }
    query.addListener(update);
    return () => query.removeListener(update);
  }, []);

  return desktop;
}
