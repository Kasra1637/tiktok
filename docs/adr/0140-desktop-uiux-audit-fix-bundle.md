# ADR 0140: The desktop UI/UX audit's fourteen findings land as one bundle

Status: accepted

## Context

The desktop UI/UX audit of Nov 14 2026 (`hookforge-uiux-audit-2026-11-14.md`,
code at `fc74233`) scored desktop UI 8/10 and UX 8/10: a disciplined system
(one page width, one surface system, one primary action per step) held back
by fourteen concrete defects, none of them structural. The founder approved
building all fourteen. The three questions the audit reserved for him —
Review as one column or two on wide screens, the wizard as a stacked canvas
or true separate pages, Analytics dense or calm — are NOT decided here and
nothing in this bundle pre-empts them.

The defects, in the audit's order: error-red text at 3.7:1 on card against
the 4.5:1 AA floor, in 19+ places; no automated contrast gate, which is how
that red drifted in; read-aloud missing from the Create wizard, the longest
page in the app; the Craft check's eight tiles explaining none of their
scores (the explanation build approved Nov 13, never landed); the render
progress percentage staged at 25/85/100 from status alone; Analytics and
the Scene Details spec rows never using the desktop's width; the landing
how-it-works cards hand-rolling the card surface off-token; fit-score
explanations trapped in a hover-only native `title`; muted text passing AA
with no margin and three call sites compositing it to ~3.4:1 with opacity
modifiers; History polling pausing after 20 attempts with no visible
change on the row; the strategy-suggestion modal hand-rolled without focus
management; buttons and inputs disagreeing on height by 4px; tours recorded
as seen on open, so a first-second dismissal suppressed them forever; and
trim-timeline timecodes at 11px, below the app's own 12px floor.

## Decision

- **Text gets text-grade tokens, and a gate holds them.** Error text reads
  `--destructive-text` (0 85% 70%, 6.33:1 on card) via the
  `text-destructive-text` utility; the solid `--destructive` serves fills
  and borders only. `--muted-foreground` rises 58% → 62% (5.41:1 on its
  worst surface), and the three `text-muted-foreground/60|70` sites are
  gone, with a render-smoke ban on the pattern. `scripts/check-contrast.cjs`
  joins the `check` chain and asserts the named text/surface pairs at
  ≥4.5:1, computed deterministically from the tokens — the drift that
  produced finding 1 now breaks the build instead.
- **Scores explain themselves in one way.** Craft tiles and the FitBadge
  both use the shared Radix tooltip behind a focusable trigger (hover,
  keyboard focus, tap). The craft tooltip carries the rubric's own words —
  the per-dimension evidence and next step from `backend/creative_quality.py`'s
  report — so screen and scorer cannot disagree; the weighted maxima and
  the scoring are untouched, and nothing new prints on the card (the
  removed top-fix callout stays removed). The badge keeps its basis string
  verbatim, now reachable by every input instead of mouse-hover only.
- **Waits are narrated, not measured.** The paid render's staged percentage
  is replaced by the stage in words, an elapsed clock anchored to the
  generation row's `created_at`, and an indeterminate bar. History's
  paused poll renders the warning banner on the row — "Still rendering —
  check again" — instead of a muted line indistinguishable from active.
- **The width gets used where the audit named it.** Analytics' summary/
  verdict band (and the feedback pair, when both exist) grids two-across
  at lg; the clip ledger and weekly chart keep full width. Scene Details'
  spec rows form a two-column definition grid at lg via StrategyBlock's
  `specGrid` opt-in; prose blocks stay stacked. The landing `.how-step`
  carries the shared surface-compact spec (10% background, 16px padding).
  Fields and hand-written selects rise to h-11, the button default's 44px.
- **Read-aloud reaches the wizard.** The Review step header mounts the
  shared ListenButton with a builder over the plan (hook, script, demo
  brief, craft check) and the strategy (hook concept, why it works, scene
  details), from the data model like every other section's — ADR 0088's
  pattern, no new infrastructure.
- **The suggestion modal rides the shared Dialog.** ADR 0133's modal moves
  from a hand-rolled overlay to `ui/dialog.jsx`, gaining initial focus,
  focus trap and return-focus. The no-dismiss design becomes structural:
  DialogContent gains a `hideClose` opt-in (no X offered) and Escape /
  outside press are refused on the content. Copy and the side-by-side
  layout are byte-identical.
- **Tours are seen on completion.** `seenTours` keeps completions;
  dismissals go to a second ledger (`hookforge_dismissed_tours.v1`). The
  pure rule `shouldAutoOpenTour`: never after completion, one re-offer
  after a first early dismissal, no offers after a second. Manual replay
  is untouched.

## Consequences

- Every finding has a regression pin: the contrast gate itself, smoke
  checks for the token wiring, the tooltip contents, the progress words,
  the paused-poll banner, the grids, the modal's dialog semantics and the
  tour arithmetic in the frontend-logic suite.
- The smoke suite's suggestion-modal checks now read the dialog from the
  document (Radix portals it), following the delete-dialog checks'
  established purge-and-query pattern.
- What the audit scored as already at/near 10 is untouched: PageFrame's
  width, the sticky wizard bar, the busy-button system, History's card
  layout. The three reserved founder decisions remain open exactly as
  the audit left them.
