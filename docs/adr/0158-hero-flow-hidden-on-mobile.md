# ADR 0158: The hero flow is hidden on mobile

Status: accepted

Follows ADR 0154 (the flow has no pause control) and ADR 0157
(the hero headline's treatment); neither changes — this record
governs only where the flow's figure renders.

## Context

Kasra, on Nov 15 2026, screenshotted the live landing page on
his phone: the hero's cycling picture section — the portrait
frame (471/710) holding the five step illustrations, the badge
and title under the art, and the dots row — filled the screen
with mostly empty dark space. Below the hero's desktop
breakpoint the layout stacks, so the frame stands alone under
the pitch at full portrait height and earns nothing there: the
same five steps run again, in full, in the How it works section
immediately below. Asked to choose between removing just the
dots row and removing the whole cycling section on mobile, he
picked the whole section — mobile only, desktop untouched.

## Decision

The figure wrapping the flow (`data-testid="landing-hero-shot"`)
carries a named class, `.hero-shot`, and index.css hides it by
default and restores it at the hero's own desktop breakpoint:

```css
.hero-shot { display: none; }
@media (min-width: 1024px) {
    .hero-shot { display: block; }
}
```

1024px is the Tailwind `lg` width where the hero grid turns
two-column (`lg:grid-cols-[1.02fr_1fr]`) and the figure's own
`lg:` utilities engage — the width where the pitch and the flow
stand side by side is exactly the width where the flow appears.
The mechanism is the codebase's standing mobile-first display
flip (`.history-secondary-filters`, `.history-compact-toggle`):
a named class in index.css, never conditional rendering, so the
markup is identical at every width and the flow's source-based
smoke pins keep meaning what they mean. The headline, the
sub-headline, the CTAs and the sign-in line are untouched and
stay fully visible on phones; the hero section itself remains,
so its tour target is unaffected.

## Consequences

On phones and tablets the hero is the pitch alone — headline,
sub-headline, actions, proof line — with no portrait frame
below it. At 1024px and up nothing changes: same frame, same
four-second cycle, same dots, same closer dots spacing
(c4dae9a), same absence of a pause control. A smoke check pins
the arrangement: the figure carries `.hero-shot`, the base rule
hides it, and the 1024px media query restores it; the existing
HeroFlow pins (five slides, auto-advance, no pause control,
centered dots) pass unchanged.
