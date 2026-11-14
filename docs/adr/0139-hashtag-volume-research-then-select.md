# ADR 0139: Post-kit hashtags are researched first, then selected

Status: accepted

## Context

The post kit invented its 4 to 6 hashtags from the clip's wording
alone; the only checks were shape (one token, unique, no engagement
bait). The founder's settled rule (Nov 14 2026): research hashtag
volume FIRST, then select from the research — five hashtags, roughly
three smaller ones around 10k-50k posts and two larger ones around
100k-500k, nothing at a million-plus posts where a small account's clip
gets buried, all specific to the clip's niche. He explicitly chose a
best-effort volume source now over waiting for a stable one, and
explicitly rejected a community/local tag slot, hashtag rotation across
posts, and any learn-from-results layer.

There is no official hashtag-volume API. Every public source checked at
build time was closed from a server context: TikTok's challenge detail
API returned nothing, the Creative Center radar API answered 40101
"no permission" (it expects a Creative Center session), the tag page's
static HTML carries no count, and public API proxies returned nothing.
The design therefore assumes the source is unreliable and possibly
absent, and makes that safe rather than pretending otherwise.

## Decision

- **Pool, then research, then select.** The post-kit prompt now asks
  the model for a candidate pool of 12 to 15 niche tags for the clip,
  ordered most relevant first (relevance stays a hard requirement —
  never generic popular tags; the same problem/community/category
  grounding as before). Each candidate's post count is looked up
  best-effort, and `hashtag_volume.select_hashtags_by_volume` chooses
  exactly five: `HASHTAG_MIX` = 3 small (`SMALL_BAND` 10k-50k posts) +
  2 large (`LARGE_BAND` 100k-500k), never at or over
  `HASHTAG_MAX_POSTS` (1,000,000). All four live as named constants for
  later tuning.
- **Stepwise widening, never invention.** If a band cannot be filled
  from the pool, selection widens to the nearest neighbouring range
  (`SMALL_BAND_WIDENED`, `LARGE_BAND_WIDENED`) and only then to any
  researched tag under the cap. If fewer than five researched tags
  under the cap exist, selection returns nothing rather than padding
  the set with unchecked tags.
- **The lookup is a seam with a cache.** `lookup_hashtag_counts` takes
  an injectable fetcher (tests run fully offline), reads a persisted
  cache first (`hashtag_volume_cache`, migration 0005, TTL 7 days —
  counts are approximate and drift slowly), fetches only the misses,
  and writes successes back. The default fetcher targets the Creative
  Center radar API with a 4s per-call timeout and a 20s overall
  deadline; it is expected to fail in most postures today (see above)
  and every failure mode is a normal outcome, not an error.
- **Fallback is mandatory.** `lookup_hashtag_counts` never raises. On
  any outage — source down, nothing usable returned, selection unable
  to fill the mix — `generate_post_kit` ships the pool's first five on
  wording alone, the pre-research behavior. A finished video never
  loses its post copy over a research outage.
- **Shape contract unchanged, count superseded.** The final five still
  pass the existing gate (one token, plain ASCII, unique, no
  engagement bait) via `normalize_post_kit_hashtags`; exactly five
  supersedes the old 4-to-6 range. A model reply whose cleaned pool
  holds fewer than five candidates fails loudly, as a short reply did
  before. The post-kit flow and UI are untouched — only how the five
  are chosen changed.

## Consequences

- Kits now carry researched sizes when the source speaks, and the
  founder's mix otherwise degrades silently to the wording choice he
  already had — never to an empty or padded set.
- The cache makes repeat niches cost no research and gives the volume
  data a durable home if a better source is wired into the fetcher
  seam later; swapping sources touches one function.
- Tests pin the mix, the million-plus exclusion, widening, cache hits
  avoiding a second lookup, TTL expiry, partial-count caching, the
  fetcher-failure path, and the end-to-end fallback in
  `generate_post_kit`.
