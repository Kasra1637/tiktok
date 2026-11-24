# ADR 0310: Muse Ember is restored

Status: accepted

## Context

On Nov 23 2026 the app's model changed twice at the founder's
order: Muse Ember, the original model, gave way to GPT-6.2 Sol
(ADR 0295), and Sol gave way the same evening to Claude Sonnet
5.5 (ADR 0299). The first live copy on Sonnet followed the app's
rules and landed inside its lengths, but it did not read better
than what Ember produced under the same instructions — the hook
and script both rated 7.5/10, no lift over the Ember-era pairs.
The founder's ruling, the same night: "Put that model back to
the app. The one from Meta. The original one." Muse Ember is
Meta's model (`meta/muse-ember`), and it is the original one —
the model every optimization in the app's prompts was built and
tuned against until ADR 0295.

## Decision

- `DEFAULT_TEXT_MODEL` and `DEFAULT_VISION_MODEL` read
  `meta/muse-ember` again. Angles keep following TEXT_MODEL, so
  one pair of defaults moves every written surface at once:
  profile research, angles, plan and strategy, hooks and
  rewrites, cover text, post kit, and the vision frame analysis.
  The env overrides work exactly as before, and no deployment
  config sets them, so the code default is the production model.
- The settings around the model do NOT revert. Reasoning stays
  at medium app-wide including the plan chain (ADR 0297 — the
  founder's separate later ruling for speed, not part of either
  swap; Ember ran at extra high before ADR 0295, and restoring
  that is a separate order if he gives it). Temperature stays
  0.4 in code (ADR 0199) — and because Ember's endpoints declare
  the field, the declaration guard sends it again, exactly as
  it did before ADR 0295; nothing about the guard changes.
- Structured outputs ride as before: Ember carried every flow
  in this app until ADR 0295, and the parse-and-retry in
  `_chat_json` stays as defense-in-depth. The request-shape
  tests pin the restored shape (Ember slug, temperature sent,
  medium sent for the shipped slug only), and
  `backend/verify_chat_model.py` remains the live proof.
- The video models are untouched — HeyGen and MiniMax still
  make the videos. Listed price, read off OpenRouter on
  Nov 23 2026: $0.10/$0.50 per 1M, against $2/$10 for both
  models it replaces in turn.

## Consequences

Every generation in the app is Ember-written again, under the
same instructions, budgets and attempt loops the ADR 0301–0304
bundle hardened — those live in the prompts and never belonged
to any model, so nothing built for length or craft is lost in
the switch. ADRs 0295 and 0299 stand as the record of the two
days away; this record supersedes their model choice only.
