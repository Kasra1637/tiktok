# 0100 — The hashtag strategy: a fresh account gets 4 to 6 classified tags, never bait

- **Status:** accepted
- **Date:** 2026-11-06
- **Anchors:** `backend/ai_service.py` (`generate_post_kit`, the prompt's
  hashtag block, `normalize_post_kit_hashtags`, `POST_KIT_BAIT_TAGS`,
  `POST_KIT_JSON_SCHEMA` minItems/maxItems); `backend/routers/post_kit.py`
  (frozen kit; Regenerate is the only writer);
  `backend/test_post_kit_strategy.py`
- **Shapes:** the post-kit half of the render output; display is unchanged

## Context

The kit prompt asked for "3 to 5 highly relevant tags" with one soft line
about trending tags, and the code accepted 3 to 5 tags of any shape. Nothing
enforced a mix, a count ceiling worth the name, or the absence of the
engagement-bait family (#fyp, #foryou, #viral, #trending), which is
mass-tagged and cannot route a clip to anyone in particular. For a fresh
account — no follower base and no authority for the algorithm to lean on —
the tags' actual job is classification: they reinforce what the content is
about so the video reaches the audience already watching that problem.

## Decision

- **4 to 6 tags, single tokens, unique.** Each is grounded in the render's
  hook, caption topic, audience, category, or app name. The JSON schema
  bounds the array at 4–6 and the normalizer enforces it.
- **Balanced volume, stated in the prompt:** one or two tags naming the exact
  problem or behaviour the clip is about (the low-competition classification
  anchor), one or two from the niche's own community or interest vocabulary,
  and one broad app-category tag; the app's own name may be one of them.
- **The bait family is banned outright** (`POST_KIT_BAIT_TAGS`): #fyp,
  #foryou, #foryoupage, #foryourpage, #viral, #trending. A reply carrying one
  fails with the offending tag named.
- **Fail loudly, regenerate to fix.** `normalize_post_kit_hashtags` raises on
  off-strategy sets (count, repeats, spaces, non-ASCII, over-long, bait). The
  completion writer is best-effort and leaves the column NULL; the one-click
  Regenerate is the retry. No silent stripping or patching.
- **Display unchanged.** The frozen kit's hashtags render as the same chips
  in `PostKitSection`; only the logic that chooses them changed.

## Alternatives rejected

- **Keep the soft 3-to-5 guidance.** Nothing enforced it: the mix was a hope,
  and bait tags slipped through whenever the model felt like it.
- **Invent per-tag volume numbers.** There is no trusted volume source here;
  a fabricated "views" figure would be fake data wearing a strategy's name.
  The tiers stay qualitative and the mix is enforced by construction.
- **Strip bait tags silently.** It hides the strategy break, drops the set
  below the count the founder sees, and teaches nothing; a refusal names the
  tag and costs one click to fix.

## Consequences

- Post copy for a fresh account classifies the clip instead of fishing for
  reach: problem anchor first, community vocabulary, one category tag.
- Off-strategy kits fail loudly and are fixed by Regenerate; a finished
  render can still carry a NULL kit, exactly as a failed kit generation
  always could.
- Kits frozen before this record keep their stored tags untouched — the
  strategy governs generation, never history.
- No frontend, request-shape, or storage change.
