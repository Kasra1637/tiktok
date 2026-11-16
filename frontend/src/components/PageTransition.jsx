import { useLocation } from "react-router-dom";
import { useReducedMotionPreference } from "../lib/reducedMotion";

/**
 * The route entrance: the one rise-and-settle every entrance in the app
 * shares (ADR 0165), distinct only in that it runs on every path change.
 * It never delays the route or its requests, and reduced motion shows the
 * page immediately: the animation itself is owned by CSS (gated on
 * `prefers-reduced-motion: no-preference`), with the inline
 * `animation: none` as the JS belt for a preference live in React.
 */
export function PageTransition({ children }) {
  const location = useLocation();
  const reduceMotion = useReducedMotionPreference();

  return (
    <div
      key={location.pathname}
      className="route-entry"
      style={reduceMotion ? { animation: "none" } : undefined}
    >
      {children}
    </div>
  );
}

export default PageTransition;
