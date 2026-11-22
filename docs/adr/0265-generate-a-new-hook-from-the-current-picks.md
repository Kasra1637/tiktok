# 0265 — Generate a new hook: a fresh hook from the current picks, beside the suggestion

Status: accepted (Kasra's explicit order, Nov 22 2026; it supersedes
the withdrawn regenerate float ADR 0249 recorded — "I'm just
kidding," not built — which he named himself when he reversed it:
the new button regenerates "based on the new goal, not based on
the old goals")

## Context

On the Hook + CTA page, once a hook line exists, changing a
steering pick (ADR 0247) marks the line as predating the picks and
shows the stale note. But the card offered only one remedy:
"Suggest a clearer hook," the stateful button's written-line state
(ADR 0249), which runs the rewrite — a refinement of the OLD line,
written from the old focus, offered as a suggestion the founder
accepts or keeps theirs against.

Kasra hit the gap live (Nov 22 2026, with screenshots of the two
buttons): he changed the Focus pick and there was no way to
generate a brand-new hook from the new focus. His order: a NEW,
separate button that regenerates from the new goal — and, in the
same breath, the hard limits around it: "Use this line / Keep mine
should both be kept alive and don't touch that shit," and "don't
even touch the Suggest a clearer hook button. Just make a new
button."

## Decision

1. **A separate button, "Generate a new hook."** It stands in the
   spoken-line area's foot (ADR 0254's seat), directly under the
   stateful button, and only while a hook line exists
   (`data-testid="hook-generate-new"`). Before a line exists it
   does not stand: the stateful button's Generate state already
   writes the first hook. It wears the first-generate button's own
   dress — accent variant, Sparkles glyph, the same plain busy
   state ("Writing the hook," no countdown, per ADR 0249) — because
   it is the same action.

2. **It runs the first generation again, unchanged.** The button
   calls the page's existing `generateHook` handler: pending picks
   are flushed first, then `POST /hook-cta/projects/{id}/hook`,
   then the returned row is adopted whole. `generate_hook_line`
   reads the saved picks (focus, tone, shape — ADR 0247), so the
   fresh line is written from the picks exactly as they stand when
   the button is pressed. Its result is the line on file directly —
   no suggestion panel, no "Use this line" / "Keep mine" step; the
   rewrite endpoint is never called on this path. The stale flag
   the pick change raised clears with the generation, as it does
   for the first generate, so the stale note goes away once the
   line on file is written from the current picks.

3. **Nothing else moved.** The stateful button's conditional —
   Generate the hook / Suggest a clearer hook, labels, behavior
   and seat — is byte-for-byte as ADR 0249/0254 left it; the new
   button is a sibling rendered after it. `LineRewriteAction`,
   including "Use this line" and "Keep mine," is untouched; a
   suggestion still pending for the replaced line hides itself,
   as it always has when its line changes. No pick change
   generates anything (ADR 0122 stands) — the pick still only
   marks the line stale. The stale note's wording is unchanged:
   it names the clearer-hook suggestion, which remains one of the
   two remedies; the other now stands visibly in the same card.

4. **No backend change.** The hook endpoint never guarded on an
   existing line: by ADR 0244's design it writes the draft's hook
   line and its render strategy on every call, overwriting both.
   Verified in `backend/routers/hook_cta.py` before building — the
   fresh generate needed no guard adjusted anywhere.

## Checks

Two render-smoke checks pin the contract, red before green (the
main check failed on the old page with "the fresh-generate button
does not stand beside the written hook"):

- "no fresh-generate button stands before a hook line exists" —
  the empty card carries only the stateful Generate button.
- "a fresh hook from the current picks replaces the line on
  file" — with a line on file, both controls stand (the untouched
  Suggest a clearer hook and Generate a new hook); the Focus pick
  is changed (spending no generation call), the new button is
  pressed, and the generation is requested with the NEW focus
  saved on the row; the editor then holds the fresh line, no
  rewrite suggestion ever appears, the rewrite endpoint is never
  called, the stale note is gone, and the suggestion control
  still stands unchanged.

The ADR 0247/0249/0254 checks pass unchanged around them —
including the suggestion's accept-only-on-"Use this line" flow
and the sweep that no button reads "Regenerate the hook" (the
new label is "Generate a new hook").
