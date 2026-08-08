import { cn } from "@/lib/utils"

/**
 * Loading placeholder. Uses a travelling highlight instead of a flat pulse so
 * long lists of skeletons read as "loading" rather than "broken".
 */
function Skeleton({
  className,
  ...props
}) {
  return (
    <div
      className={cn(
        "relative overflow-hidden rounded-xl border border-[color:var(--hairline)] bg-secondary/40",
        "after:absolute after:inset-0 after:-translate-x-full after:bg-gradient-to-r after:from-transparent after:via-white/[0.06] after:to-transparent after:content-['']",
        "motion-safe:after:animate-[shimmer-sweep_1.6s_ease-in-out_infinite] motion-reduce:animate-pulse",
        className
      )}
      {...props} />
  );
}

export { Skeleton }
