import * as React from "react"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const alertVariants = cva(
  "relative w-full rounded-2xl px-4 py-3.5 text-base [&>svg+div]:translate-y-[-3px] [&>svg]:absolute [&>svg]:left-4 [&>svg]:top-4 [&>svg~*]:pl-7",
  {
    variants: {
      variant: {
        default:
          "text-foreground [&>svg]:text-foreground",
        // Destructive stays red text and icon, but never paints a surface or
        // a border: the page background shows through so failures read as
        // guidance, not as filled banners. Severity is carried by the
        // colored text and icon, not by a box around them.
        destructive:
          "text-destructive [&>svg]:text-destructive",
        // Non-error warnings (blocked, stale, awaiting action): transparent
        // like destructive, but in the normal foreground so they do not claim
        // danger.
        warning:
          "text-foreground [&>svg]:text-foreground",
      },
    },
    defaultVariants: {
      variant: "default",
    },
  }
)

const Alert = React.forwardRef(({ className, variant, ...props }, ref) => (
  <div
    ref={ref}
    role="alert"
    className={cn(alertVariants({ variant }), className)}
    {...props} />
))
Alert.displayName = "Alert"

const AlertTitle = React.forwardRef(({ className, ...props }, ref) => (
  <h5
    ref={ref}
    className={cn("font-display mb-1 font-semibold leading-none tracking-tight", className)}
    {...props} />
))
AlertTitle.displayName = "AlertTitle"

const AlertDescription = React.forwardRef(({ className, ...props }, ref) => (
  <div
    ref={ref}
    /* No color class here on purpose — the description inherits from Alert so
       the destructive variant stays red instead of dropping to muted gray. */
    className={cn("text-base leading-relaxed [&_p]:leading-relaxed", className)}
    {...props} />
))
AlertDescription.displayName = "AlertDescription"

export { Alert, AlertTitle, AlertDescription }
