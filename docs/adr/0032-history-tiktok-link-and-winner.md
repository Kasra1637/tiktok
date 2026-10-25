# 0032 — A TikTok link marks a render posted; thumbs up plus link is the winner

Status: accepted

## Context

History showed finished renders but never knew which ones shipped: posting
happened outside the app and left no trace, so the hook-learning loop had
no posted-vs-unposted distinction. The loop's first step needs that mark,
without stats fields and without a TikTok API integration.

## Decision

- `generations.tiktok_url` is one nullable TEXT column, set through
  `POST /generations/{generation_id}/tiktok-link`. Empty string clears it;
  non-TikTok URLs are refused with a 400 rather than stored.
- The field lives next to the thumbs in the tile's vote block
  (`HistoryFeedback`): input plus save, a Posted badge and an "Open live
  video" link once set. History list, detail and the new endpoint all carry
  it; pre-column rows read as not posted.
- Winner rule: a thumbs up on the render is the winner signal, and a link
  alone carries no weight — the Winner badge shows only when both hold.

## Alternatives rejected

- Stats fields (views, retention): explicitly out of scope — the mark of
  posting comes first, numbers later.
- TikTok API push/pull: an OAuth integration for a first loop that manual
  paste answers in one text column.
- A separate posted table or signal: the link belongs to the render row,
  and the History tile already reads that row.

## Consequences

The loop can now count real winners: thumbs up plus posted link. Backend
tests pin the column default, the 400s, clearing, tenant isolation and
every surface carrying the link; the smoke suite pins input, Posted, live
link, link-alone-is-no-winner, and the crowning vote.
