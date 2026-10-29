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

/* Unified busy state (idea 1): `busy` paints the slow sweep-fill layer from
   `.btn-studio[data-busy]` and exposes `aria-busy`, while the label names the
   work without trailing dots ("Generating angles", never dotted) — the step
   caption below the button, where one exists, carries the live detail. Text
   and icons never animate; only the fill layer moves. Callers keep owning
   `disabled`: busy describes the work, not whether the control accepts input.
   Determinate waits pass `progress` (0–1): the fill then holds at that width
   instead of looping, and falls back to the loop when it is absent — so a
   counted job (6 angles, 6 goals) shows real position while an unknowable
   one (plan body, render queue) keeps the breathing sweep. */
const Button = React.forwardRef(({ className, variant, size, asChild = false, busy = false, progress = null, style, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  // `?? NaN`: Number(null) is 0, so a missing progress must not coerce — an
  // absent progress stays indeterminate and keeps the looping sweep.
  const fraction = Number(progress ?? NaN);
  const determinate = Boolean(busy) && Number.isFinite(fraction);
  const clamped = determinate ? Math.min(1, Math.max(0, fraction)) : 0;
  return (
    <Comp
      className={cn(buttonVariants({ variant, size, className }))}
      ref={ref}
      data-busy={busy || undefined}
      data-progress={determinate ? "true" : undefined}
      aria-busy={busy || undefined}
      style={determinate ? { ...style, "--busy-progress": `${Math.round(clamped * 100)}%` } : style}
      {...props} />
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
