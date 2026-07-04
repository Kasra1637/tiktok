import { motion, useReducedMotion } from "framer-motion";
import { useLocation } from "react-router-dom";

/**
 * Wraps route content with a subtle fade + rise entrance so navigating
 * between pages feels intentional rather than an abrupt content swap.
 * Respects prefers-reduced-motion by skipping the transform.
 */
export function PageTransition({ children }) {
  const location = useLocation();
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      key={location.pathname}
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.22, ease: "easeOut" }}
    >
      {children}
    </motion.div>
  );
}

export default PageTransition;
