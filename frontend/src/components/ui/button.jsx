import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-medium transition-colors transition-shadow transition-transform focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover:-translate-y-[1px] active:translate-y-0 active:scale-[0.98] motion-reduce:hover:-translate-y-0 motion-reduce:active:scale-100",
  {
    variants: {
      variant: {
        default:
          "bg-primary text-primary-foreground shadow-[var(--shadow-sm)] hover:bg-primary/90 hover:shadow-[var(--shadow-md)]",
        destructive:
          "bg-destructive text-destructive-foreground shadow-[var(--shadow-sm)] hover:bg-destructive/90 hover:shadow-[var(--shadow-md)]",
        outline:
          "border border-[color:var(--hairline-strong)] bg-secondary/20 shadow-[var(--shadow-xs)] hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] hover:text-foreground",
        secondary:
          "border border-[color:var(--hairline)] bg-secondary/70 text-secondary-foreground shadow-[var(--shadow-xs)] hover:bg-secondary",
        ghost: "hover:bg-[color:var(--indigo-8)] hover:text-foreground hover:-translate-y-0 active:scale-100",
        link: "text-[color:var(--brand-teal)] underline-offset-4 hover:underline hover:-translate-y-0 active:scale-100",
        /* Brand variants — the primary CTA (coral) and the secondary brand
           action (indigo). Previously every call site hand-rolled these with
           arbitrary `bg-[color:var(--brand-coral)] hover:bg-[#e0264c]` classes. */
        brand:
          "bg-[color:var(--brand-coral)] font-semibold text-white shadow-[var(--glow-coral)] hover:bg-[#e0264c] hover:shadow-[var(--shadow-lg)]",
        accent:
          "bg-[color:var(--brand-teal)] font-semibold text-white shadow-[var(--glow-indigo)] hover:bg-[color:var(--brand-teal-dark)] hover:shadow-[var(--shadow-lg)]",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-xl px-8 text-base",
        icon: "h-10 w-10",
      },
    },
    defaultVariants: {
      variant: "default",
      size: "default",
    },
  }
)

const Button = React.forwardRef(({ className, variant, size, asChild = false, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
