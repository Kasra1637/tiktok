# ADR 0353: A caption preview from the hook line

## Status

Accepted, Nov 25 2026 — Kasra's pick from the HookSnap
enhancement review: an auto caption preview showing the
caption against its 50–80 character window (rated 9/10
on the call, the top of the three he scored; he ordered
this and ADR 0352 built, and declined the third).

## Context

The post kit is written once, at render completion
(`routers/post_kit.py::_maybe_write_post_kit`). Until a
HookSnap render finishes, the page's Post kit card shows
placeholder text — the founder commits to the render
without ever seeing the caption the clip will carry,
even though the caption is written from copy that
already exists: the hook line. And when the kit does
arrive, nothing anywhere shows the caption's length
against the 50–80 window the kit's own rule enforces,
so the founder cannot see the finished caption sits in
it.

## Decision

A caption-only sibling path answers the caption early.
`ai_service.generate_caption_preview` writes ONE caption
from the hook line under the kit's own rules — sells
the watch, everyday-user voice, ends in its question,
50 to 80 characters including the '?', no content word
twice (ADR 0346) — and refuses a reply outside them,
loudly, exactly as the kit refuses. It is grounded in
the hook ONLY: the project's script never reaches its
prompt, because on this surface the hook is the whole
spoken piece, and a preview written from words the
clip does not carry would promise copy the finished
kit cannot confirm. Its endpoint
(`POST /hook-cta/projects/{id}/caption-preview`, in
`routers/hook_cta.py`) writes NOTHING — no kit row, no
generation, the project row untouched; the frozen kit
still arrives at render completion and replaces the
preview exactly as before.

The trigger is the Post kit card's own button,
"Preview the caption" — not the hook's generation.
ADR 0122's rule is that a section's own action owns its
generation, and the card is where the preview is read:
firing it from the hook endpoint would couple the hook
call to a second model spend and a second failure mode,
and would silently stale-date the preview the moment
the founder edits the line. The card's click flushes
pending edits first (the hook endpoint's own pattern),
so the preview is written from the line on screen; the
result is keyed to that line, and an edited or
regenerated line retires it. The preview shows with a
live count against the window ("62 / 50–80"), and the
same readout joins the finished kit's caption row in
the shared `PostKitSection`, so Create's kits show it
too — intended: the count is a property of the caption,
not of the surface that previewed it.

## Consequences

The founder sees the caption and its fit before
spending a render, and can regenerate the hook with
that knowledge; the preview itself is spent only on
its own click, never on navigation, page load, or the
hook's generation. Pinned by backend tests (window
enforcement, hook-only grounding, the endpoint's
409-before-a-hook and its writes-nothing proof) and by
smoke checks (no control before a hook, no preview call
spent by writing the hook, the preview and its count in
the card, the count on the finished kit).
