import { cn } from "../lib/utils";

/**
 * One fact about a thing: a model, a length, a version, a date.
 *
 * This exists because the app was showing the same kind of information three
 * different ways. A generation row showed facts as badges opposite the title AND
 * as a run-on middot sentence below it; the template picker showed them as bare
 * spans; Asset Library showed a kind breakdown that could only ever repeat its
 * own total. None of those is wrong alone, which is why it took a card doing
 * all three at once to look unsettled.
 *
 * The rule this encodes: a fact is something measurable about the thing, and it
 * is not the thing's identity. "grok-imagine-video" and "10s" are facts about a
 * video. Which app it is for, and whether it worked, are not — those get the
 * display face and a status badge.
 *
 * `text-xs` and not smaller. The project's floor is 12px, and small muted text
 * is exactly what falls below AA contrast beneath it.
 */
export function FactChip({ children, className }) {
  return (
    <span
      className={cn(
        "select-none rounded-full border border-[color:var(--hairline)] px-2 py-0.5 text-xs text-muted-foreground",
        className
      )}
    >
      {children}
    </span>
  );
}

/**
 * A wrapping row of facts.
 *
 * Deliberately not `role="list"`: a list role obliges its children to be list
 * items and these are spans, so declaring it would produce exactly the invalid
 * ARIA it was meant to avoid. They read in source order either way, which is all
 * a row of chips needs.
 *
 * Earns its place by holding the wrap behaviour, so a facts row looks the same
 * everywhere one is written.
 */
export function FactList({ children, className }) {
  return <div className={cn("flex flex-wrap items-center gap-1.5", className)}>{children}</div>;
}

export default FactChip;