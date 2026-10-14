import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "btn-studio inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-200 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover:-translate-y-[1.5px] active:translate-y-0 active:scale-[0.98] motion-reduce:hover:-translate-y-0 motion-reduce:active:scale-100",
  {
    variants: {
      variant: {
        default:
          "btn-bevel-accent bg-primary text-primary-foreground",
        destructive:
          "bg-destructive text-destructive-foreground shadow-[inset_0_1px_0_0_rgba(255,255,255,0.22),var(--shadow-sm)] hover:bg-destructive/90 hover:shadow-[inset_0_1px_0_0_rgba(255,255,255,0.3),var(--shadow-md)]",
        outline:
          "btn-bevel-neutral border border-[color:var(--hairline-strong)] bg-secondary/30 text-foreground hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] hover:text-foreground",
        secondary:
          "btn-bevel-neutral border border-[color:var(--hairline)] bg-secondary/70 text-secondary-foreground hover:border-[color:var(--indigo-35)] hover:bg-secondary hover:text-foreground",
        ghost: "hover:bg-[color:var(--indigo-8)] hover:text-foreground hover:-translate-y-0 active:scale-100 after:hidden",
        link: "text-[color:var(--brand-indigo)] underline-offset-4 hover:underline hover:-translate-y-0 active:scale-100 after:hidden",
        /* Brand variants — the primary CTA (coral) and the secondary brand
           action (indigo). Specular top bevel + diagonal hover sheen + icon
           micro-nudge are shared across all studio pages and Landing. */
        brand:
          "btn-bevel-brand border border-white/15 bg-[color:var(--brand-coral)] font-semibold text-white hover:border-white/25",
        accent:
          "btn-bevel-accent border border-white/15 bg-[color:var(--brand-indigo)] font-semibold text-white hover:border-white/25",
      },
      size: {
        default: "h-10 px-4 py-2",
        sm: "h-8 rounded-lg px-3 text-xs",
        lg: "h-12 rounded-xl px-8 text-sm",
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
