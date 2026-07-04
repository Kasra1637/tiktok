import { motion, useReducedMotion } from "framer-motion";
import { Card } from "./ui/card";

export function EmptyState({ icon: Icon, title, description, action }) {
  const reduceMotion = useReducedMotion();

  return (
    <motion.div
      initial={reduceMotion ? { opacity: 1 } : { opacity: 0, y: 8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.28, ease: "easeOut" }}
    >
      <Card className="flex flex-col items-center justify-center text-center gap-3 p-10 rounded-2xl border-dashed border-2 border-border bg-white/50">
        {Icon && (
          <motion.span
            initial={reduceMotion ? { scale: 1 } : { scale: 0.85 }}
            animate={{ scale: 1 }}
            transition={{ duration: 0.3, ease: "easeOut", delay: 0.05 }}
            className="flex h-12 w-12 items-center justify-center rounded-full bg-[color:rgba(13,148,136,0.10)] text-[color:var(--brand-teal)]"
          >
            <Icon className="h-6 w-6" />
          </motion.span>
        )}
        <h3 className="font-display text-lg font-semibold">{title}</h3>
        {description && <p className="text-sm text-muted-foreground max-w-md">{description}</p>}
        {action}
      </Card>
    </motion.div>
  );
}
export default EmptyState;
