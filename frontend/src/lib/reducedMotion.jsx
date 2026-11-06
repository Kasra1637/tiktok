import { useEffect, useState } from "react";

const QUERY = "(prefers-reduced-motion: reduce)";

function readReducedMotion() {
  return typeof window !== "undefined"
    && typeof window.matchMedia === "function"
    && window.matchMedia(QUERY).matches;
}

/** Browser-native reduced-motion hook so UI animations do not pull in framer-motion. */
export function useReducedMotionPreference() {
  const [reduced, setReduced] = useState(readReducedMotion);

  useEffect(() => {
    if (typeof window === "undefined" || typeof window.matchMedia !== "function") return undefined;
    const query = window.matchMedia(QUERY);
    const update = () => setReduced(query.matches);
    update();
    if (typeof query.addEventListener === "function") {
      query.addEventListener("change", update);
      return () => query.removeEventListener("change", update);
    }
    query.addListener(update);
    return () => query.removeListener(update);
  }, []);

  return reduced;
}
