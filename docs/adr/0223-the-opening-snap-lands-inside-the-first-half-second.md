# 0223 — The opening snap lands inside the first half second

Status: accepted

## Context

On Nov 19 2026 (late voice call) Kasra reviewed what the first 2–3
seconds of a HookForge video already carry — ADR 0187's rapid,
story-enacting opening movement, the goal-first spoken hook, the
wider framing of ADR 0213 — and ruled out adding anything new to
those seconds. Users already add their own hook text in the Demo +
CTA step, in that same opening area; a second text would compete
with theirs, and the generated clip itself carries no burned-in
text for the cover text to collide with (verified in the code that
day). The grab had to come from tightening what is already there.

The wording was looser than his settled doctrine. ADR 0187's
behavior direction let the opening snap complete "inside roughly
the first second", and renders kept landing the energy late — the
orchard-gate render's snap arrived around a second in, against a
retention curve that falls off a cliff between seconds 1 and 2
(70% still watching at second 1, 40% at second 2, 22% at second 3
on his best video). His doctrine, settled earlier, is stricter:
the snap completes inside the first half second. The render
prompt's opening instruction even said "words come second", which
left the voice free to start after the move — a silent lead-in
beat the hook cannot afford.

## Decision

Generator-side only, in every surface that states the opening
timing; the Craft scorer (`backend/creative_quality.py`) is
untouched, as ever.

1. **The snap completes inside the first half second.** The loose
   phrase "roughly the first second" is replaced everywhere it
   stated the snap: the BEHAVIOR DIRECTION block
   (`backend/ai_service.py`, `_behavior_direction_rules_block`,
   including its requirement summary), the strategy prompt's
   `hook_action` schema line and segment-0 action line, the
   two-section schema (`backend/ai_strategy.py`,
   `_two_section_schema`), the plan prompt's hook beat, and the
   render assembly (`backend/generation_planning.py`: the
   opening-interrupt directive's "snap done inside that
   half-second", its condensed twin's "snap inside the first
   half-second", and the single-pass builder's opening sentence).
2. **The opening action is the story's central action caught at
   its sharpest instant** — not a lead-in to the action and not a
   settle into it. The tie is stated beside the timing on the same
   surfaces: the action lines name the action at its peak.
3. **The presenter is already speaking from the first frame.** The
   hook's first sound lands with the first frame — no lead-in
   pause, breath or silent beat before it. Stated where the
   wording genuinely governs delivery: the behavior block, the
   strategy prompt's `hook_dialogue` line ("the voice starts with
   the first frame"), the render opening directive (replacing
   "words come second"), its condensed twin, and the single-pass
   builder's hook sentence. No new control is invented where the
   wording does not govern the render.
4. **Nothing else is added.** No new element, no on-screen text,
   no change to the protected opening action (still clipped at
   280 characters, still never trimmed) and no change to
   `backend/opening_move.py`: its validator is lexical — it can
   check that a visible move exists, never when it lands — so the
   timing stays prompt doctrine, pinned as instruction text.
5. **The wording is pinned red-before-green.** `TestHalfSecondSnap`
   in `backend/test_behavior_direction.py` pins the half-second
   snap, the sharpest instant and the first-frame voice on every
   surface above, and the absence of the loose phrase; the pins
   were watched failing before the wording moved.

## Alternatives rejected

- **Add an element to the opening** (a second text, a graphic, a
  sound cue): rejected by Kasra outright — the user's own Demo +
  CTA hook text owns the opening's text area, and two texts in
  the same area compete.
- **Keep "roughly the first second" and rely on the strategy's
  280-char opening action to land early**: that is the wording
  the late renders were already produced under.

## Consequences

The fixed render text grows, and the measured floors move with
it, recorded in the ledger beside the constants in
`backend/generation_planning.py`: the full floor rose 3
(4014 → 4017), the condensed floor rose 11 (2464 → 2475), and the
single-pass floor rose 123 (2835 → 2958). The near-zero net on
the segment builder is deliberate, and bought out of the opening
paragraphs themselves: a first pass that let the full floor rise
~70 passed every ceiling test yet silently squeezed the payoff
beat out of a realistic prompt (the `test_prompt_dedup`
regression — the budget scale divides by the space the floor
implies, so fixed growth is taken out of the founder's fields),
and the uncompressed condensed sentence landed the sacred-script
HeyGen build over its 4,090 ceiling. So both twins were
compressed in their own wording — redundant phrases out, every
constraint kept and pinned — until the saturated builds fit with
the payoff intact. Every provider ceiling still fits, saturated
strategies included, pinned by the same tests as before.
Strategies written before this change keep their stored
`hook_action` text — the tightened doctrine governs new plans,
strategies and renders, and a strategy rebuild picks it up.
