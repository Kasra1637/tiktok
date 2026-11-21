# 0252 — Hook + CTA shoots handheld selfie only

Status: accepted (scopes ADR 0219/0220/0233's fixed-camera machinery to Create Video, where it stands unchanged)

## Context

The Hook + CTA page's direction card offered a camera setup pick —
Handheld selfie or Fixed camera — inherited from the wizard's
direction machinery when the page was built (ADR 0244).

Kasra's ruling (Nov 21 2026): "For only hook plus CTA on that page
remove camera setup and handheld selfie should be the only default
option." His reasoning: "Because the video is shorter I thought a
selfie would be more interesting and engaging than displaying the
character in a zoomed out environment." He sharpened the first
phrasing ("by default") to removal in the same conversation: on
this page there is no camera pick to make. Create Video keeps its
camera choice and the whole Fixed indoor chain exactly as they are.

## Decision

**The control is gone, and handheld is forced at the surface.**
The direction card is headed "Place and wardrobe" (the one
icon+label header pattern, ADR 0246), its subtitle "Place and
wardrobe — the hook is written from these picks." The voice pick
stays in the card. No camera control renders.

**The page reads handheld.** `HookCta.jsx` hands the shared
direction hook (`useWizardDirections`, unchanged) the literal
`"handheld"` instead of the draft's stored value, so the location
list it asks for is the full handheld set. With no fixed camera on
this page, the Fixed indoor machinery cannot engage here: no
indoor-only location list, no "staged indoors" restatement, and the
ineligible-location notice (ADR 0220) — whose computation the page
drops — never renders. A draft stored "fixed" before the ruling
shows its saved outdoor place standing as the pick from the full
list, exactly as a handheld draft does.

**The server forces handheld for the surface**, following ADR
0246's voice_mode precedent (a pick the surface owns is forced at
submit, never trusted to the caller):

- The hook endpoint writes the hook from a working copy whose
  `camera_setup` is "handheld", and stores the strategy with
  `"camera_setup": "handheld"` outright — so the FIXED CAMERA block
  in `generate_hook_line` and the fixed restatements never engage
  for a hook, whatever the row stores.
- `_submit_generation` rebinds its working copy of a `hook_cta`
  project to handheld (the generation row records "handheld"), and
  treats the render's strategy as handheld before the guard and the
  prompt build read its camera — so a strategy stored before the
  ruling cannot put a fixed starting shot into a hook's prompt.

**Stored values are NOT rewritten.** A row that holds "fixed"
keeps it and reads back exactly as stored; the forcing lives in the
working copies, the way the voice pick's forcing does. If the page
ever regains a camera choice, the stored pick is still there to
read.

**Scope is the surface, everywhere.** Every change keys on
`surface == "hook_cta"` or lives inside the Hook + CTA page/router.
Create Video's camera pick, the Fixed indoor chain (ADRs 0219,
0220, 0233, 0224), its ineligible-location notice, and the shared
direction hook are all untouched — pinned by the existing wizard
suites passing unchanged.

## Consequences

- Pins: backend — a stored-fixed hook project submits with a
  HANDHELD SELFIE prompt (no fixed starting shot), its generation
  row records "handheld", and its stored row still reads "fixed";
  the hook write hands the model a handheld working copy and stores
  a handheld strategy. Frontend smoke — the page renders no camera
  control, asks the direction hook for options under "handheld"
  only, shows no ineligible notice, and stands a stored-fixed
  draft's outdoor place as the pick; the card-title pins and the
  tour copy move to "Place and wardrobe" (the tour's direction step
  now says every hook here is shot handheld selfie).
- The hook-cta create payload still accepts a `camera_setup` value
  (default "handheld"); it is stored and then never read for this
  surface's direction, hook, or render. Removing the field is a
  separate cleanup this change does not need.
- A founder who wanted one fixed-camera hook loses the option on
  this page by Kasra's design; Create Video remains the place a
  fixed hook + story is made.
