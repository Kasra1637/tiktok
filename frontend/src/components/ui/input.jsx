import * as React from "react"

import { cn } from "@/lib/utils"

const Input = React.forwardRef(({ className, type, ...props }, ref) => {
  return (
    <input
      type={type}
      className={cn(
        "flex h-10 w-full rounded-xl border border-[color:var(--hairline)] bg-secondary/40 px-3.5 py-1 text-base",
        "shadow-[var(--shadow-xs)] transition-colors placeholder:text-muted-foreground/70",
        "file:border-0 file:bg-transparent file:text-sm file:font-medium file:text-foreground",
        "hover:border-[color:var(--hairline-strong)]",
        "focus-visible:border-[color:var(--indigo-35)] focus-visible:bg-secondary/70 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-[color:var(--indigo-15)]",
        "disabled:cursor-not-allowed disabled:opacity-50 md:text-sm",
        className
      )}
      ref={ref}
      {...props} />
  );
})
Input.displayName = "Input"

export { Input }
