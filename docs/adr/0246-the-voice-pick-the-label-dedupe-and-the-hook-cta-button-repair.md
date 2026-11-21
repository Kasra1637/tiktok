# 0246 — The voice pick, one header per card, and the Hook + CTA render button repaired

Status: accepted

## Context

Three follow-ups from Kasra on the Nov 20 2026 evening call, all
about the live Hook + CTA page (ADR 0244):

1. The render section's "Generate the hook" button "does not work
   and is not clickable." His full-page screenshot showed it greyed
   at the Render card's foot behind the gate "Generate the hook
   first — there is no hook yet," while the page's own drafts list
   showed other drafts with hooks.
2. A voice pick where movement and direction are set — his words:
   "a simple simple toggle inside the same place like where it is
   right now for movement and direction" — choosing whether she
   talks or stays silent, on both Hook + CTA and Create Video.
3. Duplicated icons and content: nearly every card stacked a card
   header AND an inner group label restating it, each with its own
   icon; the Render card stacked three.

Kasra's packaging order for this whole run: everything — the
phone-frame preview (ADR 0245), the button repair, the voice pick
and the dedupe — lands as one commit.

## Decision

1. **The button: three defects, one symptom.** The gate text was
   honest about the draft the page had open; the defects were in
   which draft that was, and in a save that could never settle.

   - **The page opened the wrong draft.** On load it minted a
     brand-new empty draft and opened THAT, on every visit, while
     the founder's hooked draft sat unopened in the list below.
     The drafts read now reopens the app's newest draft (the list
     is newest-first); a new draft is created only once the read
     settles empty *for that app* — the page records which profile
     the settled list belongs to, so a stale list from a previous
     app pick cannot trigger a duplicate create. A `?project=`
     link still names its own draft and wins.
   - **The length pick could never save.** The hook-length choice
     rides the shared studio PATCH, which applied the wizard's
     duration rules to hook-cta rows: the clamp snaps 4/5s to 8
     (the wizard's durations are 8/10/12/15), and once a hook
     exists the plan-timeline guard refuses a duration change with
     a 409. So before a hook, the pick silently stored 8s — a
     length the hook endpoints then refuse ("A hook runs 4 or 5
     seconds.") — and after a hook, every autosave failed, the
     page's edits never cleared, and the render gate read them as
     "still saving" forever: the button permanently disabled
     behind a gate that lied. The repair is in
     `update_studio_project`: a hook_cta row's `duration_seconds`
     validates against `SHORT_HOOK_SECONDS` and saves as itself —
     no clamp, no 409. The wizard's rules are untouched for wizard
     rows; both directions are pinned in `test_hook_cta_api.py`.
   - **Attaching a photo wiped the page.** The asset library calls
     `onProjectChanged` with NO argument after an attach, and the
     page adopted the argument as its project — dispatching the
     empty signal and unmounting every stage card until the
     follow-up read landed, and for good if that read failed.
     Create Video's wiring already guards this (`fresh || project`);
     the Hook + CTA page now guards the same way.
   - **The half-clipped look in the screenshot** was investigated
     as a fourth suspect: no overflow, overlap or z-order defect
     exists in the card — `.surface` does not clip, the button
     sits in normal flow at the card's foot, and no fixed or
     sticky element overlays this page. What the screenshot shows
     is the disabled button in its gated state. The repair is the
     state fixes above, not a CSS change.

2. **The voice pick.** `voice_mode` rides the project row
   (migration step 10; default `"talking"`; an editable studio
   field beside `camera_setup` — deliberately NOT a studio text
   field, so the words never move when the voice does). Exactly
   two choices, Kasra's settled binary — there is no voiceover
   middle option: **She talks** (today's behavior: voice, lips
   move with the words) and **She stays silent** (no voice, and
   no lip movement at all). One shared control,
   `VoiceModeControl`, stands in both direction areas: the Hook +
   CTA direction card beside the camera setup, and Create Video's
   Visual & audio direction section in the same position. A silent
   render submits two ways at once: the panels send
   `generate_audio: false` only when the pick is silent (an
   explicit true could hand a model a field its catalog does not
   list), AND `_submit_generation` forces audio off from the saved
   pick — so retries and older callers cannot resurrect the voice —
   and appends a plain direction at the prompt's tail: she does
   not speak, does not mouth the words, her mouth stays closed and
   still, while the opening and closing actions still happen, in
   silence. The direction's length is reserved from the builder's
   prompt budget; the provider's real ceiling still governs the
   check. The behavior bookends are unchanged — only voice and
   mouth turn off.

3. **The silent note.** When silent is picked, a note at the
   control says the character will be silent and shows the exact
   text for TikTok's text-to-speech: the hook line on Hook + CTA,
   the hook and script on Create Video — quoted verbatim when the
   lines exist, and naming what will show before they are written.
   The same guidance also rides the post kit (`PostKitSection`'s
   `ttsText`) on both creation surfaces, because the kit is the
   copy the founder holds at posting time; History's kit does not
   carry it.

4. **One header per card (Hook + CTA page).** The SectionCard
   header is the one icon+label header; an inner group label
   survives only where it names a sub-group the header does not.
   Kept wording, per card: **Choose an app** (header was "App",
   the inner label won); **Camera, place and wardrobe** (header
   was "Moment and direction" — the informative inner wording
   won); **The hook** (inner "The line" dropped; the editor's own
   "The spoken line" survives — it names the editor, not the
   card); **Render the hook** (header "Render", the page's "The
   finished hook" and the panel's own "Render the hook" — three
   layers became the one header; the panel keeps only its status
   badge row); **Demo + CTA** (inner "Finish the video" dropped);
   **Post kit** (inner "Copy for the post" dropped). Subtitles and
   body copy are unchanged — this is a label and icon cleanup
   only.
