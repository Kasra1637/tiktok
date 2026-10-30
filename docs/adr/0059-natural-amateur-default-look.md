# 0059 — The default look is natural amateur phone footage, never polished

- **Status:** accepted
- **Date:** 2026-10-30
- **Anchors:** `backend/ai_service.py` (`visual_style` in the strategy schema); test `test_the_strategy_schema_defaults_to_unpolished_phone_shot_look`

## Context

The strategy schema hinted the look as "documentary, polished UGC,
cinematic". Whatever the hint names, the model writes into
`scene.visual_style`, and the scene lock (`character_scene_lock`) then
enforces exactly that on the render. Polished studio footage reads as an ad
in a TikTok feed and dies there; the format that survives is a real person
filming themselves on a phone — slightly rough, never graded, never staged.

## Decision

- The `visual_style` schema hint now asks for natural amateur phone UGC,
  explicitly never polished (worded to stay under the 24,500-char strategy
  prompt ceiling — see the ceiling test).
- This changes the default for a new strategy, never a saved one: a stored
  strategy keeps the look it was generated with until rebuilt.
- The founder still steers the look per video through visual direction on
  Review & submit; the default just stops choosing polish for them.

## Alternatives rejected

- **Keep polished as one option among equals.** The model treats the listed
  options as a menu and picks the most premium-sounding one. Only an
  explicit default plus an explicit never holds the line.
- **Grade it in post.** The look is baked into the generated footage
  (lighting, lens, depth of field). No overlay or caption treatment can
  un-polish a studio render.

## Consequences

- New strategies render handheld and rough by default; founders who want
  cinematic can still ask for it in visual direction.
- The fully-populated prompt ceiling test still passes: the hint grows by a
  few dozen characters against a 24,500 ceiling.
- The regression test pins the hint, so a future default flip back to
  polished fails the gate.
