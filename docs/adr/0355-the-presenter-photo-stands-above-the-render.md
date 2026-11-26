# ADR 0355: The presenter photo stands above the render on HookSnap

## Status

Accepted, Nov 25 2026 — Kasra's order in the web chat and on a
voice call: Demo + CTA and the post kit sit below the presenter
photo section, and the presenter photo section stands above the
Render the hook area. Supersedes the placement half of ADR
0326; 0326's faces-only half stands.

## Context

ADR 0326 moved HookSnap's presenter photo section to the very
bottom of the page, after the Post kit, matching the
end-of-flow spot it holds in the Create wizard. Working the
page, Kasra reversed the placement: the face the render wears
is settled before the render controls, not after the posting
copy, and the finishing work — Demo + CTA, then the Post kit —
closes the page.

## Decision

A pure reorder of `frontend/src/pages/HookCta.jsx`. The
existing PresenterPhotoControl block — the same project gate,
the same props, its own panel and label — moves from below
the Post kit card to directly above the Render the hook card.
Nothing inside any section changes: no content, copy,
subtitle, testid or behavior. HookSnap's order is now: Choose
an app, Place and wardrobe, The hook, Presenter photo, Render
the hook, Demo + CTA, Post kit. The Create wizard is
untouched — the reorder is HookSnap's alone, and ADR 0326's
faces-only embedded library stands exactly as decided there.

## Consequences

The page reads in the order the work happens: settle the app,
the place and wardrobe and the hook, then the face, then
render, finish and post. The render-smoke check that pinned
ADR 0326's bottom placement is replaced by one pinning the
full seven-section order by testid — setup, direction, hook,
presenter photo, render, finish, post kit — red before the
move, green after.
