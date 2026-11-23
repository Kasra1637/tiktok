# ADR 0268: The failing checks move to the kept copy; two guards stay red on purpose

Status: accepted (two checks deliberately left red — see Findings)

## Context

On Nov 21–22 2026 a parallel agent's stack landed on main: the hero
headline rose to 48/60px on its named tokens (its own ADR 0263), a
plain-English copy polish across the landing page and the workspace
page headers, a Dashboard first-video checklist, and Demo + CTA
frame-picker work. The stack changed the words and titles the
render-smoke suite pins, and eleven checks went red:

1. Landing claims nothing the product cannot keep
2. Landing separates generated stories from real footage and editor overlays
3. Landing headings, workflow, and navigation have real destinations
4. the hero headline and sub-headline are Kasra's chosen copy
5. the problem/solution bullets are length-matched
6. workspace enforces 4 sizes x 2 weights
7. no signals yet says so instead of showing an empty card
8. topic page headers keep titles and purposeful subtitles
9. every wizard subtitle fits the shared size and length budget
10. unavailable editor sources offer recovery, retry and an upload exit
11. History keeps its title without a redundant subtitle

Kasra reviewed the situation on Nov 22 2026 and ruled: **keep the
other agent's updates exactly as they are** — including their hero
headline — and fix the failing checks. The product does not change;
the checks are what move. He also directed that any check guarding
something truly broken be surfaced rather than papered over.

## Decision

**Each failing check was classified against the current product and
re-pinned to the current truth at the same rigor. Nine checks were
fixed in `frontend/scripts/check-render-smoke.cjs` only; no product
file changed. Two checks were left red as findings (below).**

Per-check classification and what each pin now asserts:

| # | Check | Class | What the pin now asserts |
|---|-------|-------|--------------------------|
| 2 | Landing separates generated stories… | copy pin | The buyer-disclosure pattern for audio now matches the kept FAQ answer verbatim: "Audio depends on the video model you pick; you can generate with sound or silent for voiceover". The generation/editor/review boundary phrases and the other four disclosure patterns were verified against the current copy and stand. |
| 3 | Landing headings, workflow, and navigation… | guard, stale phrases | The behavior holds — one H1, five steps, every anchor and route link resolving, no nested interactives, five complete buyer questions. The workflow phrase list is re-pinned to one verbatim action phrase per step as the steps read today: "approve the facts", "Pick goal + viewer", "presenter photo", "Review then render", "export one ready-to-post MP4". |
| 4 | the hero headline and sub-headline… | copy pin | Headline pinned verbatim: **"Turn your app's URL into a scroll-stopping video in minutes."** Sub-headline pinned verbatim: **"No filming, no editing, no blank page. Turn your product facts into a hook, script, and finished TikTok video — and get sharper with every clip you post."** The gradient-treatment pin and the retired-copy absence pins stand. The size pins still assert the `text-hero` / `sm:text-hero-wide` token classes; only the tokens' values moved (42/50 → 48/60, the parallel ADR 0263), and the check's comment now says so. |
| 5 | the problem/solution bullets… | copy pin | The kept bullets no longer sit within a character of each other (rows run 3, 1, 6, 3 chars apart). The ±1 balance assertion is replaced by the pairs' exact current lengths — without/with per row: **65/62, 63/62, 63/69, 68/71** — so any one-line edit to any bullet still fails. |
| 7 | no signals yet… | copy pin | The guard holds (the signals card still renders nothing when empty, and the empty page still offers a `/create` next action). The explanation pin moves to the EmptyState's current words: title "No posted results yet", plus "add its posted link, views, and your vote in History". |
| 8 | topic page headers… | copy pin | App Profile's subtitle re-pinned: "Lock in your product facts once — every video starts from here." GenerationHistory's entry re-pinned to the shortened title "History" with its subtitle "Review finished clips, copy post kits, and log real results." (purposeful by this check's own standard). The other five pages' pins were verified against source and stand. |
| 9 | every wizard subtitle… | copy pin, exact exception | The 55–60 char budget stands for every `data-subtitle`. One kept subtitle — Hook + CTA's "Pick an approved app to start a fresh hook.", a complete instruction at 43 chars — is exempted **by exact string only**, and the check asserts it stands exactly once: editing it returns it to the budget (and fails), deleting it fails, and no other subtitle may ride the exemption. Its `text-sm` size assertion still applies. |
| 10 | unavailable editor sources… | guard, stale phrase | The behavior holds in full: the alert offers "Try loading again" (verified to refetch — the API is called a second time), a "Review clip in History" link to `/history#generation-<id>`, and an "Upload your own clip" link to `/demo-cta`. Only the pinned recovery phrase moved, to the kept copy: "Retry saving in History". |
| 11 | History keeps its title… | copy pin | Renamed "History keeps its title and its one purposeful subtitle": asserts the H1 is "History" and the header's one subtitle is verbatim "Review finished clips, copy post kits, and log real results." — the drift guard's point (no silent title change, no second redundant line) is preserved against the kept header. |

## Findings — two guards left red on purpose

**Check 1, "Landing claims nothing the product cannot keep", stays
red.** This is a behavior guard, not a copy pin: it asserts the
landing page discloses that template fit is not proven performance
(the word "limitations", from the kept bullet "Compare openings by
fit scores, reasons, limitations.") and that the craft grade is
advisory only ("no grade ever blocks your renders"). The kept copy
pass (commit 97bc842, "sharpen outcome-driven copy") deleted both
disclosures, and the replacement copy presents the openings as
proven: step 3 now reads "Choose from proven openings ranked for
your app" and the With-HookForge bullet "Pick proven hooks ranked
to hold your exact buyer's attention." The behavior the guard
protects therefore does not hold in the current product. Weakening
the guard to match would bless exactly the claim it exists to
catch, and restoring the disclosures would change the product
Kasra said to keep. The check is left untouched and red; the
resolution — restore a limitations/grade disclosure, or rule the
"proven" wording acceptable and retire the assertions — is Kasra's.

**Check 6, "workspace enforces 4 sizes x 2 weights", stays red.**
The checker flags exactly one offender: `pages/Dashboard.jsx`, the
first-video checklist's progress label ("{doneCount} of
{steps.length} complete") carries `font-medium` — a weight the
workspace rule (font-normal / font-semibold only) bans, in product
JSX, not in a fixture the checker should scope out. Blessing it in
the checker would retire the design-system rule for one stack's
convenience; the product-side fix is a one-class change
(`font-medium` → `font-semibold`, the weight the checklist's own
step badges already use), which is outside this change's scope.
The check is left untouched and red for Kasra to rule on.

## Consequences

The render-smoke suite runs 566 checks: 564 pass, and the two
findings above fail by design until Kasra rules. Every other gate
in the frontend check chain (imports, logic, demo-cta draft parity,
contrast, tour targets) passes, and Jest stands at 359/46. Future
copy edits remain guarded: every re-pinned string, length, and
phrase above fails the suite the moment it drifts.
