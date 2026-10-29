import { motion, useReducedMotion } from "framer-motion";
import { useLocation } from "react-router-dom";

/**
 * A quick route entrance, separate from the primary-content reveal on pages
 * that wait for data. It never delays the route or its requests, and reduced
 * motion shows the page immediately.
 */
export function PageTransition({ children }) {
  const location = useLocation();
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      key={location.pathname}
      initial={reduceMotion ? false : { opacity: 0, y: 4 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: reduceMotion ? 0 : 0.12, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

export default PageTransition;
