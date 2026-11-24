# ADR 0296: The picked-template panel is removed

Status: accepted

## Context

Under the template cards on Audience & template, picking a
template opened a detail panel restating the pick: the template's
name and category, a Suggested badge when the pick was the
preselection, the piece's length and section split ("15s piece: a
3s hook, then a 12s middle"), the template's middle text, and —
while a required photo was still missing — an "Add your photo
below" jump button. On Nov 23 2026 Kasra sent a screenshot of the
panel and ordered the section removed too, in the same pass that
shed the Hook + CTA drafts section (ADR 0287): the step should
state the pick once, on the card itself.

## Decision

The panel is removed whole. The selected card in the templates
grid is the pick's only statement; the presenter photo section
stands immediately below the grid, so the photo jump goes with
the panel and nothing is left pointing at a section one screen
away. TemplateShape and its middleStructure helper leave
SelectionPanels with their only caller, and the smoke pins move
honestly: the preselection check now asserts the panel's strings
are absent, and the failed-library check keeps only its surviving
claim — the recommendation rows still render.

## Consequences

The step reads shorter by one box, and the pick is stated exactly
once. The piece's length is no longer spelled out on this step;
it is still the template's declared duration everywhere the plan
and the render consume it, and Review states the finished plan's
own shape. The preselected-versus-hand-picked distinction the
Suggested badge carried is no longer shown on this step; the
pick's behavior is unchanged either way.
