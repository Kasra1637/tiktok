import * as React from "react"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const badgeVariants = cva(
  "inline-flex select-none items-center gap-1 rounded-full border px-2.5 py-0.5 text-xs font-semibold shadow-[inset_0_1px_0_0_rgba(255,255,255,0.08)] transition-colors focus:outline-none focus:ring-2 focus:ring-ring focus:ring-offset-2",
  {
    variants: {
      variant: {
        default:
          "border-transparent bg-primary text-primary-foreground shadow-[var(--shadow-xs)] hover:bg-primary/80",
        secondary:
          "border-[color:var(--hairline)] bg-secondary/70 text-secondary-foreground hover:bg-secondary",
        destructive:
          "border-transparent bg-destructive/15 text-destructive hover:bg-destructive/25",
        outline: "border-[color:var(--hairline-strong)] text-foreground",
        // Brand tints — subtle chips that read as accents rather than buttons.
        indigo:
          "border-[color:var(--indigo-15)] bg-[color:var(--indigo-10)] text-[color:var(--brand-indigo)]",
        coral:
          "border-[color:var(--coral-25)] bg-[color:var(--coral-12)] text-[color:var(--brand-coral)]",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

function Badge({
  className,
  variant,
  ...props
}) {
  return (<div className={cn(badgeVariants({ variant }), className)} {...props} />);
}

export { Badge, badgeVariants }
