import { motion, useReducedMotion } from "framer-motion";

export function EmptyState({ icon: Icon, title, description, action }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <div className="relative overflow-hidden rounded-3xl border border-dashed border-[color:var(--hairline-strong)] bg-card/40 px-6 py-14 text-center backdrop-blur-sm">
        {/* Soft indigo pool behind the icon keeps the dashed box from reading
            as an error state. */}
        <div
          aria-hidden="true"
          className="pointer-events-none absolute inset-x-0 top-0 h-40"
          style={{
            background: "radial-gradient(400px circle at 50% 0%, rgba(99,102,241,0.10), transparent 70%)",
          }}
        />
        <div className="relative flex flex-col items-center justify-center gap-3.5">
          {Icon && (
            <motion.span
              initial={reduceMotion ? { scale: 1 } : { scale: 0.85 }}
              animate={{ scale: 1 }}
              transition={{ duration: 0.3, ease: "easeOut", delay: 0.05 }}
              className="flex h-14 w-14 items-center justify-center rounded-2xl border border-[color:var(--indigo-15)] bg-[color:var(--indigo-8)] text-[color:var(--brand-indigo)] shadow-[var(--shadow-md)]"
            >
              <Icon className="h-6 w-6" />
            </motion.span>
          )}
          <h3 className="font-display text-lg font-semibold tracking-tight">{title}</h3>
          {description && (
            <p className="max-w-md text-sm leading-relaxed text-muted-foreground">{description}</p>
          )}
          {action && <div className="mt-1.5">{action}</div>}
        </div>
      </div>
    </motion.div>
  );
}
export default EmptyState;
