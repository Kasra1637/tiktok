import { motion, useReducedMotion } from "framer-motion";
import { IconTile } from "./IconTile";

export function EmptyState({ icon, title, description, action, headingLevel = "h2" }) {
  const Heading = headingLevel;
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <div className="relative overflow-hidden rounded-2xl border border-dashed border-[color:var(--hairline-strong)] bg-card/40 px-6 py-14 text-center backdrop-blur-sm">
        {/* Soft indigo pool behind the icon keeps the dashed box from reading
            as an error state. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-40"
          style={{
            background: "radial-gradient(400px circle at 50% 0%, var(--indigo-10), transparent 70%)",
          }}
        />
        <div className="relative flex flex-col items-center justify-center gap-4">
          {icon && (
            <motion.span
              initial={reduceMotion ? { scale: 1 } : { scale: 0.85 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.3, ease: "easeOut", delay: 0.05 }}
            >
              <IconTile icon={icon} size="empty" />
            </motion.span>
          )}
          <Heading className="font-display text-sm font-semibold tracking-tight">{title}</Heading>
          {description && (
            <p className="max-w-md text-base leading-relaxed text-muted-foreground">{description}</p>
          )}
          {action && <div>{action}</div>}
        </div>
      </div>
    </motion.div>
  );
}
export default EmptyState;
