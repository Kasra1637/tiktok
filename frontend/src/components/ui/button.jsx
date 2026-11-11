import * as React from "react"
import { Slot } from "@radix-ui/react-slot"
import { cva } from "class-variance-authority";

import { cn } from "@/lib/utils"
import { formatBusyCountdown, BUSY_ETA_THRESHOLD_SECONDS } from "../../lib/busyEta"

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

/* Unified busy state: a looping sheen sweep on the button itself (`.btn-studio[data-busy]`).
   The label names the work concisely ("Tailoring templates", never dotted, never
   a "Reading X of Y…" line beside it) and the sweep carries the wait. Text
   and icons never animate; only the fill layer moves. Callers keep owning
   `disabled`: busy describes the work, not whether the control accepts input.
   Counted jobs pass `progress` (0–1) for a determinate hold; absent progress
   keeps the looping sweep — so a counted job shows real position while an
   unknowable one keeps the breathing sweep.
   A generation wait (busy with etaSeconds >= 10, the mandatory wait every
   generation CTA carries) wears the "Use this photo" dark surface while it
   runs — the `secondary` variant, the same dark slate, hairline border and
   light text — and counts its wait down inside the button ("· 30s" to
   "· 0s", holding at 0s if the endpoint runs long). The CTA's own text,
   icon, size and layout never change; only the surface and the count do, and
   both revert when the work finishes. Determinate jobs keep their real
   position instead of a countdown, and asChild links never take one. */
const Button = React.forwardRef(({ className, variant, size, asChild = false, busy = false, progress = null, etaSeconds = null, style, children, ...props }, ref) => {
  const Comp = asChild ? Slot : "button"
  // `?? NaN`: Number(null) is 0, so a missing progress must not coerce — an
  // absent progress stays indeterminate and keeps the looping sweep.
  const fraction = Number(progress ?? NaN);
  const determinate = Boolean(busy) && Number.isFinite(fraction);
  const clamped = determinate ? Math.min(1, Math.max(0, fraction)) : 0;
  // A generation wait is the only busy state that changes surface and counts
  // down: saves, approvals, deletes and uploads carry no etaSeconds, and a
  // determinate job already shows its real position.
  const generatingWait = Boolean(busy) && !determinate && Number(etaSeconds) >= BUSY_ETA_THRESHOLD_SECONDS;
  const effectiveVariant = generatingWait ? "secondary" : variant;
  const [remainingSeconds, setRemainingSeconds] = React.useState(() => (
    generatingWait ? Math.round(Number(etaSeconds)) : null
  ));
  React.useEffect(() => {
    if (!generatingWait) {
      setRemainingSeconds(null);
      return undefined;
    }
    setRemainingSeconds(Math.round(Number(etaSeconds)));
    const id = setInterval(() => {
      setRemainingSeconds((prev) => (prev === null ? null : Math.max(0, prev - 1)));
    }, 1000);
    return () => clearInterval(id);
  }, [generatingWait, etaSeconds]);
  const countdownSuffix = generatingWait && remainingSeconds !== null
    ? formatBusyCountdown(remainingSeconds)
    : null;
  const showCountdown = !asChild && countdownSuffix !== null;
  if (asChild) {
    // Slot clones the single child element; a second node would break
    // Children.only. asChild links never take a countdown (they are not busy CTAs).
    return (
      <Comp
        className={cn(buttonVariants({ variant: effectiveVariant, size, className }))}
        ref={ref}
        data-busy={busy || undefined}
        data-progress={determinate ? "true" : undefined}
        data-generating={generatingWait || undefined}
        aria-busy={busy || undefined}
        style={determinate ? { ...style, "--busy-progress": `${Math.round(clamped * 100)}%` } : style}
        {...props}
      >
        {children}
      </Comp>
    );
  }
  return (
    <Comp
      className={cn(buttonVariants({ variant: effectiveVariant, size, className }))}
      ref={ref}
      data-busy={busy || undefined}
      data-progress={determinate ? "true" : undefined}
      data-eta={generatingWait ? Math.round(Number(etaSeconds)) : undefined}
      data-generating={generatingWait || undefined}
      aria-busy={busy || undefined}
      style={determinate ? { ...style, "--busy-progress": `${Math.round(clamped * 100)}%` } : style}
      {...props}>
      {children}
      {showCountdown && (
        <span data-testid="busy-eta" className="font-normal opacity-80">{countdownSuffix}</span>
      )}
    </Comp>
  );
})
Button.displayName = "Button"

export { Button, buttonVariants }
