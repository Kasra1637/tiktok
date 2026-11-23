# ADR 0269: Suggestions, not proven — the honesty lines return to the landing copy

Status: accepted

## Context

ADR 0268 left the "Landing claims nothing the product cannot keep"
guard red on purpose. The kept copy pass (commit 97bc842) had
deleted the landing's two honesty disclosures — that template fit
is not proven performance (the word "limitations") and that the
craft grade is advisory only ("no grade ever blocks your renders")
— and its replacement copy presented the openings as proven:
step 3 read "Choose from proven openings ranked for your app" and
the With-HookForge bullet read "Pick proven hooks ranked to hold
your exact buyer's attention." Nothing in the product proves an
opening performs; the guard exists to catch exactly that claim.

Kasra ruled on Nov 22 2026: **"Suggestions, no proven"** — the
landing must present hooks and openings as suggestions, not as
proven performance, and the honesty line is restored rather than
the guard weakened.

## Decision

**The copy changes, in `frontend/src/pages/Landing.jsx` only; the
guard check itself is untouched and now passes on the real words.**

- Step 3's line: "Choose from proven openings ranked for your app,
  then upload one clear presenter photo." becomes **"Choose from
  ranked suggestions for your app, then upload one clear presenter
  photo."**
- The With-HookForge bullet "Pick proven hooks ranked to hold your
  exact buyer's attention." becomes **"Compare suggested openings
  by fit scores, reasons, limitations."** This is the fit
  disclosure's historic home: before the copy pass, this same
  bullet carried the comparison line ("Compare openings by fit
  scores, reasons, limitations."), so the limitations disclosure
  returns where it always lived, now in suggestion language.
- The grade disclosure returns to its historic home, the "Your
  voice, one script" feature description — the card that carried
  it before the copy pass. The description is rewritten to
  **"Get a hook and script written in your own voice, graded on
  craft before you spend a cent. Fix the weak lines early — no
  grade ever blocks your renders. Ship it."** — exactly 160 chars,
  so ADR 0156's uniform feature-description length still holds.

One pin moves with the copy, in this same commit: the rewritten
bullet is 63 chars, so the problem/solution bullet pin (ADR 0268)
for row 2 goes from 63/62 to **63/63** — the pair is now exactly
balanced, and the rows run 3, 0, 6 and 3 chars apart. The headline
and sub-headline pins (ADR 0268) do not change: Kasra kept that
copy, and it stands.

## Consequences

The claims guard is green honestly: the word "limitations" and
the phrase "no grade ever blocks your renders" are back in the
landing's real copy, and no landing text calls an opening or a
hook proven. One deliberate finding from ADR 0268 remains open
(the Dashboard checklist's `font-medium`); it is decided
separately in ADR 0270.
