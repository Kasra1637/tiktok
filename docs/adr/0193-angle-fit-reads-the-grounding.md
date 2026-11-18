# ADR 0193: Angle fit is scored from the angle's grounding, not its rank

Status: accepted

Across Kasra's Nov 14 and Nov 17 2026 screenshots, every angle
in a set scored Fit 3/10 or 4/10 — the selected angle 4/10, the
rest 3/10 — while every template scored 9-10/10 (that half is
ADR 0195). A fit number that is the same for every card cannot
help the founder choose between them.

## What the trace found

Angle fit was computed in the frontend
(`frontend/src/lib/angleSubtitle.js`, `angleFitScore`) from the
angle's suggestion rank alone: `goalFitScore`'s rank term
(`floor(rank * 3 + tally * 6 + 1)`, thin-capped at 6), floored
at 3 for untested angles. With no verdicts — the normal state —
the tally is zero, so for six untested angles the score was
**{4,3,3,3,3,3} in rank order, whatever the angles said**. The
computation never read the angle.

The signal that does differ between angles already existed on
the server: `angle_policy.angle_grounding` resolves whether an
angle's feature text links to a recorded profile feature
(tier 1 exact wording, tier 2 unique near match) and whether
its stated outcome is the certified outcome for that feature —
the same verified pair the plan and strategy briefs trust.

## Decision

- `angle_policy.angle_content_fit(profile, angle)` scores the
  angle's content: feature link +4 exact / +3 unique near /
  +0 ungrounded; stated outcome is the certified one +2 (a
  certified outcome exists but the angle states another +1);
  problem stated in full +2, thinly +1; promise likewise.
  Rank plays no part; identical content scores identically.
- `_serialize_angle_row` carries the result as `content_fit`
  (score + a basis naming the strongest grounding fact) on
  every path that has the profile: the list, generate,
  manual create, update, template recommendations, and
  objective templates. Without a profile the field is null —
  no invented number.
- The frontend prefers `content_fit` for an untested angle,
  with the basis shown and "no results yet" kept (content is
  not evidence). Tested angles are unchanged: verdict evidence
  decides, and it outranks the content fit. Rows without a
  content fit fall back to the previous rank path.

## Measured distribution

On the pinned fixture (`backend/test_angle_content_fit.py`,
a Vocolens-shaped profile and six angles like the screenshot
set): **{4,3,3,3,3,3} before → [10, 8, 10, 4, 9, 4] after** —
fully grounded angles at the top, an angle whose feature
paraphrases past the profile at 4, a thin-problem angle at 9.
The two 10s tie because their grounding genuinely ties.

## Consequences

Pins: `backend/test_angle_content_fit.py` (the distribution
and each factor), an API pin in `test_template_library_api.py`
that created and listed angles carry the fit, and jest pins in
`angleSubtitle.test.js` (content fit preferred, evidence
outranks it, rank fallback intact). A rank-band rescale of the
old frontend transform was considered and rejected: spreading
the same rank signal across a wider band manufactures spread
without reading the angle, which is the cosmetic fix this
record exists to avoid.
