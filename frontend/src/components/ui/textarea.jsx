import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef(({ className, onInput, ...props }, ref) => {
  const innerRef = React.useRef(null);

  const fit = React.useCallback(() => {
    const el = innerRef.current;
    if (!el) return;
    // Grow with the text so a full script is visible without scrolling: reset
    // first so shrinking text shrinks the field too. jsdom reports no layout
    // (scrollHeight 0) — leave the style alone there so the min-height class
    // holds the field until there is something to measure.
    if (el.scrollHeight <= 0) return;
    el.style.height = "auto";
    el.style.height = `${el.scrollHeight}px`;
  }, []);

  // Refits on every render, so a value arriving from props (a loaded plan, a
  // regeneration) sizes the field the same way typing does.
  React.useEffect(() => {
    fit();
  });

  return (
    <textarea
      className={cn(
        "input-well flex max-h-[50vh] min-h-[72px] w-full overflow-y-auto rounded-xl border border-[color:var(--hairline)] px-3.5 py-2.5 text-base",
        "placeholder:text-muted-foreground/70",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={(node) => {
        innerRef.current = node;
        if (typeof ref === "function") ref(node);
        else if (ref) ref.current = node;
      }}
      onInput={(e) => {
        fit();
        onInput?.(e);
      }}
      {...props} />
  );
})
Textarea.displayName = "Textarea"

export { Textarea }
