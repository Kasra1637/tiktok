import * as React from "react"

import { cn } from "@/lib/utils"

const Textarea = React.forwardRef(({ className, ...props }, ref) => {
  return (
    <textarea
      className={cn(
        "flex min-h-[72px] w-full rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3.5 py-2.5 text-sm",
        "shadow-[var(--shadow-xs)] transition-colors placeholder:text-muted-foreground/70",
        "hover:border-[color:var(--hairline-strong)]",
        "focus-visible:border-[color:var(--indigo-35)] focus-visible:bg-secondary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)]",
        "disabled:cursor-not-allowed disabled:opacity-50",
        className
      )}
      ref={ref}
      {...props} />
  );
})
Textarea.displayName = "Textarea"

export { Textarea }
