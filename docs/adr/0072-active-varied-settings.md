# 0072 — Strategies stage active, varied settings from the usage moment

Status: accepted

## Context

Strategies kept coming back sitting indoors — bedrooms and car
interiors. Both are the model's lazy defaults: enclosed, easy to hold
stable across the hook-to-middle handoff. The existing rule already
forbade generic kitchens and desks and grounded the setting in
usage_moments, but grounding is not direction: a concrete indoor room
satisfies the old rule while every video looks the same. Founders
noticed the redundancy; a feed of identical rooms reads as manufactured
content, not a life being lived.

## Decision

The setting guidance now demands the opposite default: stage the
setting where the app's promise lives (the usage moment or the outcome,
dramatized), prefer outdoor and in-motion over indoor and sitting, and
treat sitting as right only when the usage moment demands it — a car
interior almost never is. Three vivid worked examples (hilltop path at
sunrise, night market, coastal trail) set the register, because the
model copies the style of whatever examples it sees. The
usage_moments-grounding rule stays word for word; the new lines are
extracted beside it as `scene_setting_guidance()`, mirroring the spoken
line craft block, so the wording has one owner and a regression test.

Alternatives rejected: a fixed location list per app category (a list
goes stale and caps the model at our imagination instead of the
profile's); post-hoc variety tracking across renders (real, but a
second system — prompt steering first, loop-level dedup only if
redundancy survives it); leaving bedrooms/cars available as equals
(they are the defaults already; an instruction that lists everything
equally changes nothing).

## Consequences

- New strategies come back active and varied without touching the
  continuity lock, the render prompt, or any schema — the scene lock
  pins whatever gets chosen.
- Prompt cost: net-zero. The first draft added ~140 tokens and tripped the
  strategy-prompt ceiling guardrail (`TestStrategyBudget`), so the block was
  condensed to fit: the ceiling held, the guidance survived. The setting is
  the highest visual-variance field per token on the page, and it cost none.
- Anchor: `backend/ai_service.py:scene_setting_guidance`.
