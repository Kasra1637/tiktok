import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"

const buttonVariants = cva(
  "btn-studio inline-flex items-center justify-center gap-2 whitespace-nowrap rounded-xl text-sm font-semibold transition-[background-color,border-color,color,box-shadow,transform] duration-300 ease-out focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring focus-visible:ring-offset-1 disabled:pointer-events-none disabled:opacity-50 [&_svg]:pointer-events-none [&_svg]:size-4 [&_svg]:shrink-0 hover:-translate-y-[1px] active:translate-y-0 motion-reduce:hover:-translate-y-0",
  {
    variants: {
      variant: {
        default:
          "btn-bevel-accent bg-primary text-primary-foreground",
        /* Destructive: a dark button that says what it does.
         *
         * The fill was `--destructive` (a solid red), which made the one
         * button in the app that cannot be undone the loudest thing on the
         * screen. The surface is the studio's dark material now, and the red
         * survives where it carries meaning — the label, the icon, and the
         * hover — so the action still reads as destructive without shouting
         * across the page. */
        destructive:
          "btn-bevel-neutral border border-[color:var(--hairline-strong)] bg-secondary/70 text-destructive hover:border-destructive/45 hover:bg-destructive/10 hover:text-destructive",
        outline:
          "btn-bevel-neutral border border-[color:var(--hairline-strong)] bg-secondary/30 text-foreground hover:border-[color:var(--indigo-35)] hover:bg-[color:var(--indigo-8)] hover:text-foreground",
        secondary:
          "btn-bevel-neutral border border-[color:var(--hairline)] bg-secondary/70 text-secondary-foreground hover:border-[color:var(--indigo-35)] hover:bg-secondary hover:text-foreground",
        ghost: "hover:bg-[color:var(--indigo-8)] hover:text-foreground hover:-translate-y-0 after:hidden",
        link: "text-[color:var(--brand-indigo)] underline-offset-4 hover:underline hover:-translate-y-0 after:hidden",
        /* Brand variants — indigo is the studio's action colour; coral was
           retired from button surfaces (ADR 0010). `brand` is now the dark
           *selected* surface: the same slate family as `secondary` with the
           indigo hairline that marks selection everywhere else. Its two call
           sites mean "this one is chosen" (an active thumb verdict, the
           onward Demo + CTA), which a second CTA colour never expressed.
           Soft top bevel + gentle hover sheen are shared across all studio
           pages and Landing. Text and icons never animate. */
        brand:
          "btn-bevel-brand border border-[color:var(--indigo-35)] bg-secondary font-semibold text-foreground hover:border-[color:var(--indigo-45)] hover:bg-secondary",
        accent:
          "btn-bevel-accent border border-white/15 bg-[color:var(--brand-indigo)] font-semibold text-white hover:border-white/25",
      },
      size: {
        default: "h-11 px-5 py-2.5",
        sm: "h-9 rounded-lg px-4 py-1.5 text-xs",
        lg: "h-[52px] rounded-xl px-10 py-3 text-sm",
        icon: "h-11 w-11",
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
