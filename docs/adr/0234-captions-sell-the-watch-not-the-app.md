# 0234 — Captions sell the watch, not the app

Status: accepted (amends 0044's caption instruction; its length band
and voice stand)

## Context

Kasra's ruling on Nov 20 2026, on a voice call. The post-kit caption
instruction in `generate_post_kit` (`backend/ai_service.py`) told the
model to "name what the app did for you using the profile facts and
plan above, then end with a short question" — so the captions it
produced narrated the app: what it did, where she was recording, the
using of it. His words: "nobody cares that she's recording or where
she is — people care about what they get." A caption sits at the top
of a feed next to the clip itself; its job is to give a scroller a
reason to watch, and a caption about the app spends that space on the
one thing the viewer has not yet been given a reason to care about.

## Decision

1. **The caption instruction is replaced.** The caption SELLS THE
   WATCH, not the app: it leads with what the viewer gets from
   watching — the clip's moment and its tension, with the payoff
   withheld — so the caption itself is a reason to watch.
2. **The app is never the caption's subject.** The instruction now
   forbids narrating the recording, the place, or using the app, and
   forbids making the app the caption's subject at all.
3. **The closing question is the viewer's own.** It must be a short
   question about the viewer's own experience — one anyone would
   care to answer, never about the app, because not everybody knows
   the app. The final character stays '?' and the existing guard
   that enforces it stands.
4. **Everything around the instruction stands.** ADR 0044's length
   band (50 to 80 characters including the final '?') and its
   everyday-user voice — a real person posting, first person or
   plain observation, never promotional, never founder or marketer
   voice — are unchanged. Grounding is unchanged: the clip's own
   hook, script and plan facts plus the profile's verified facts,
   no invented claims or numbers. ADR 0139's hashtag strategy is
   unchanged — this ruling is about the caption text only. The
   cover text is untouched (ADRs 0145/0232). And no wording
   validator is added: the caption guards stay shape-only (length,
   the closing question, the hashtag set), per ADR 0119 — the
   ruling governs what the model is asked for, never a gate on
   what it answered.

## Consequences

- Newly generated and regenerated post kits write captions under
  the new instruction; frozen kits on finished renders are
  untouched, as ever.
- `test_post_kit_api.py` pins the new instruction in the brief the
  model receives (sells the watch, viewer benefit first, payoff
  withheld, the three narration bans, the app never the subject,
  the viewer-experience question) and pins the old instruction's
  absence ("name what the app did for you" is gone). The canned
  captions that embodied the old rule — the frozen-kit fixtures
  and the caption guards' model doubles — are refreshed to
  captions that follow the new one. Two old-wording fixtures
  deliberately stand: `LEGACY_KIT`, a historical frozen kit whose
  purpose is proving old kits read through exactly as stored, and
  the ADR 0119 strong-wording double, which proves the guards
  still refuse nothing on wording.
- ADR 0044's index status becomes "partially superseded by 0234":
  its length band, its voice and its grounding stand; only the
  caption's subject — set by the prompt instruction its era
  introduced — is replaced.
