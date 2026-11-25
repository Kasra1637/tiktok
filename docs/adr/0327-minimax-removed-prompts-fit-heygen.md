# 0327 — MiniMax is removed; the prompt fits HeyGen's ceiling by construction

Status: accepted. Kasra's order on the Nov 24 2026 call: "I no longer
need that fucking video model. Fully remove minimax." Supersedes ADR
0255's prompt-length refusal and narrows ADR 0005's per-provider
ceilings to the one provider left.

## Context

Kasra hit the live prompt-length refusal: a script and photo assembled
a 4,108-character prompt, 18 over HeyGen Video's 4,090 ceiling, and the
refusal's advice was to switch to MiniMax H3 Max, whose ceiling was
6,800. He ruled, in order: no automatic routing between video models,
ever (an approval given and reversed in the same call); MiniMax is
removed fully; and the prompt rules are to be matched to HeyGen's
ceiling so the assembled prompt always fits inside 4,090 and that
error cannot come back.

MiniMax H3 Max was the opt-in comparison beside the HeyGen default
(ADR 0221): its catalog entry in `backend/ai_service.py` (`VIDEO_MODELS`),
its capability record in `backend/video_providers.py`
(`_CAPABILITY_NOTES`, `STUDIO_ELIGIBLE`), and the builder's
`RENDER_PROMPT_LIMIT = 6800` in `backend/generation_planning.py` all
carried its shape. The submit path's ceiling guard
(`backend/server.py`) existed to refuse an over-ceiling assembly
before spend, and its refusal (`prompt_ceiling_refusal`, ADR 0255)
named the roomier model as the escape.

## Decision

- **MiniMax is out of the catalog.** `VIDEO_MODELS` and
  `STUDIO_ELIGIBLE` hold exactly one model: HeyGen Video
  (`heygen-video-1`). There is no second video model, no comparison
  entry, and no routing — automatic or suggested — anywhere. A key
  that names a removed model is unknown: submits refuse it loudly
  before spend, and a retry recorded on it refuses rather than
  quietly rendering on the default.
- **The builder's ceiling is HeyGen's 4,090.** `RENDER_PROMPT_LIMIT`
  drops from 6,800 to 4,090, and the submit path passes the same
  number in from the capability record, so the prompt is built
  against 4,090 from the first assembly. `NATURAL_VARIABLE_SPACE`
  keeps its measured value (2,790) rather than its old derivation
  from the gone ceiling.
- **The fit is guaranteed in the builder, not refused at submit.**
  A new tightest tier (`_PROMPT_TIGHTEST`) sits below the existing
  scale walk and condensed tier in both builders
  (`build_segment_prompt`, `build_single_pass_prompt`): when the
  measured walk bottoms out at `FINAL_SCALE` still over budget, the
  fixed direction text gives up its remaining redundant phrasing —
  the handoff, audio rule and opening in their shortest forms, the
  place label shortened, and the one direction line the scene lock
  and identity close already carry dropped. The spoken script is
  never cut, at this tier or any other. Measured against the
  saturated fixture: the worst bottom-out (fixed camera at the
  silent build's reduced 3,631 budget) stood 26 over after the
  walk; with the tier engaged it lands 85 under, and the speaking
  build at the full 4,090 lands 65 under.
- **The refusal is deleted.** `prompt_ceiling_refusal` is gone from
  `generation_planning`, and the submit path's ceiling guard is gone
  from `server.py`: with the fit guaranteed, there is nothing left
  to refuse. An over-limit assembly would be a builder defect,
  pinned by the saturated-fixture tests — never a message shown to
  the founder, and never advice to switch models or cut the script.
- **A budget bug is fixed on the way.** `build_segment_prompt` used
  to normalize an invalid (zero/negative/non-numeric) budget to the
  default number only, leaving the condensed flag and scale derived
  from the caller's nonsense; the fallback now derives all three
  from the default budget it claims to fall back to.

## Consequences

- Rows and saved choices that still name `minimax-h3-max` degrade
  loudly, never silently: the studio's model picker falls back to
  the default rather than sticking on a model that cannot render,
  a fresh submit naming it is refused as unknown, and a retry
  recorded on it refuses with the reason named.
- The head-trim table is unchanged: HeyGen's 0.2s cut (ADR 0181)
  was always the only entry that mattered, and the hook's 0.5s
  composition (ADR 0250) was always model-independent — the trim
  pins that rode on MiniMax now ride on HeyGen and state its truth
  (a floor hook delivers 4.8s: the model's cut lands, the hook
  composition does not engage without a tail).
- Pins: the catalog holds exactly one model; every capability's
  ceiling is at most 4,090; saturated assemblies fit at 4,090 and
  at the silent build's reduced budget with the script held sacred;
  `prompt_ceiling_refusal` no longer exists.
- Rejected alternative: keep the refusal but drop the model advice
  ("shorten the scene and rebuild"). Kasra's order was that the
  error cannot come back — a refusal that can still fire is the
  error, whatever it advises.
