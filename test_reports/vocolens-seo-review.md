# Vocolens SEO refresh and verification

## Location and release status

Implementation is in the existing checkout `C:/Users/kasra/Documents/vocolens---site`, branch `main`, remote `https://github.com/Kasra1637/vocolens---site.git`. The current HookForge project was not changed except for this requested audit/handoff report. No commit, push, or deployment was performed.

**Release blocker:** the local site checkout contains 10 resource articles; the current live website and remote repository inspected in the browser contain 11, including Mixed Emotions. Apply/reconcile these changes with current source before deploying. Do not deploy this older checkout wholesale. Existing modifications to the alexithymia, autism, and granularity audio files, the general audio-generation script, and the untracked TTS probe were preserved.

## Findings: why granularity may have more impressions

The stronger article has a precise topic in its title, URL, definition heading, examples, and related questions. Older awareness/reflection articles spread their focus across more concepts and product benefits. Relevant newer articles also link to granularity. These are plausible explanations, not confirmed ranking attribution.

All audited live resource articles already return HTTP 200, have unique titles/descriptions, one H1, self-canonicals, readable initial server HTML, parseable Article/FAQ JSON-LD, matching visible FAQ content, internal links with HTTP 200 targets, and sitemap inclusion. Robots directives checked do not block indexing. These checks do not prove Google indexed a page or considers its schema eligible for rich results.

No Google Search Console report was available. Query demand, average rank, query breadth, country/device mix, backlinks, indexing history, and impression totals remain unverified. Search-result order for a site query is not a substitute for those metrics. Impressions measure appearances, not clicks or conversions.

## Implemented

- Emotional Awareness: focused title/H1, definition, everyday examples, four-step check-in, reusable emotion-and-trigger journal template, and distinct explanations of awareness, labeling, and granularity.
- Science of Reflection: focused on affect labeling, research scope and limitations, everyday examples, and a brief suggested exercise.
- Replaced unsupported clinical promises, percentage claims, timelines, and unverifiable quotations in the two refreshed articles. Findings about emotional-image labeling are not portrayed as a clinical trial of Vocolens or proof that speaking is superior to writing.
- Preserved URLs and original publication dates. Updated visible/schema/card modification dates and the affected sitemap entries to October 6, 2026.
- Updated route descriptions/social metadata, resource hub cards, related-card wording, and contextual links to awareness, labeling, alexithymia, and granularity.
- Kept granularity's substantive article content unchanged.
- Regenerated only the two changed narration files with the existing installed neural-voice library. FAQ/related content is excluded from narration; section offsets are derived from separately generated audio-section durations.
- Added `scripts/refresh-resource-audio.cjs` for scoped, repeatable narration updates without altering the already-modified general generator.
- Added `scripts/audit-resource-seo.cjs` for read-only SSR regression checks. It verifies the hub exposes all local article routes; a live baseline mode accepts an explicit article count and omits only newly implemented content expectations, not general SEO checks.

### Changed Vocolens files

- `src/components/vocolens/EmotionalAwareness.tsx`
- `src/components/vocolens/ScienceOfReflection.tsx`
- `src/components/vocolens/Resources.tsx`
- `src/routes/resources.emotional-awareness-patterns.tsx`
- `src/routes/resources.science-of-reflection.tsx`
- `src/lib/articleSections.ts`
- `public/sitemap.xml`
- `public/audio/emotional-awareness-patterns.mp3`
- `public/audio/science-of-reflection.mp3`
- `public/audio/manifest.json` (only the two refreshed entries)
- `scripts/refresh-resource-audio.cjs`
- `scripts/audit-resource-seo.cjs`

## Sources checked

- Lane and Smith (2021), *Levels of Emotional Awareness: Theory and Measurement of a Socio-Emotional Skill*: https://pmc.ncbi.nlm.nih.gov/articles/PMC8395748/
- Lieberman et al. (2007), *Putting Feelings Into Words*: https://pubmed.ncbi.nlm.nih.gov/17576282/
- The PubMed extractor encountered a cookie gate; the paper's abstract was verified through Princeton's publication record: https://collaborate.princeton.edu/en/publications/putting-feelings-into-words-affect-labeling-disrupts-amygdala-act/

## Verification

- Final TypeScript check: `npx tsc --noEmit` passed.
- ESLint on changed source and new scripts passed without suppressions.
- Final production build passed after stopping an owned local Worker that locked build assets on Windows. Build reports the existing Cloudflare warning that Wrangler `main` is overridden.
- Production output served successfully through local `wrangler dev --local` using the generated Worker configuration.
- SSR regression audit passed for all 10 local production-Worker article pages.
- Read-only live baseline audit passed for all 11 live article pages, including Mixed Emotions.
- New MP3s decode completely with ffmpeg. ffprobe durations: awareness 258.672 seconds (1,035,116 bytes), labeling 252.192 seconds (1,009,196 bytes).
- Narration content hashes match the final article-body extraction. Browser durations are about 258.72 and 252.24 seconds, consistent with the files. Chapter selection does not auto-start paused audio; playback and pause work and time advances. This is playback/state verification, not a full human transcription/listening review.
- FAQ expansion works on both revised articles. App CTA URLs still point to the expected Google Play app without initiating external app-store actions.
- Desktop screenshot of the labeling page was visually inspected. Mobile rendered DOM/state checks found no horizontal overflow. Subsequent screenshot captures repeatedly failed because the shared browser was not compositing; a complete mobile visual review remains a limitation.
- Internal link destinations passed HTTP checks. A mobile contextual-link click did not establish successful client navigation in the shared browser, so full client-side navigation is not claimed as verified.
- Inspected browser console logs contained no captured application errors during tested interactions.
- `git diff --check` passed. Existing unrelated edits remained present and uncommitted.

### Checks that failed or are limited

- Full `npm run lint` fails before and after changes: 131 pre-existing Prettier errors in RejectionSensitivity and its route, plus 10 existing warnings. These were not suppressed or changed as part of the focused refresh.
- `npm run preview` starts but returns HTTP 500 because its plugin expects `dist/server/server.js`, while this build emits `.output`. Production behavior was instead tested through the generated Cloudflare Worker; preview configuration was not altered.
- Build initially encountered a Windows asset-directory lock from the owned preview Worker; after stopping that process, the final rebuild passed.
- Initial audit-script failures (wrong route count, partial-word claim matching, and live mode applying new-content expectations) were repaired and affected audits rerun successfully. Local route coverage is now derived from actual article routes, excluding the layout and hub.
- Local/remote/live version alignment remains a release prerequisite, not a completed deployment step.

## Reproduction

From the Vocolens checkout:

```bash
npx tsc --noEmit
npx eslint src/components/vocolens/EmotionalAwareness.tsx src/components/vocolens/ScienceOfReflection.tsx src/components/vocolens/Resources.tsx src/routes/resources.emotional-awareness-patterns.tsx src/routes/resources.science-of-reflection.tsx src/lib/articleSections.ts scripts/audit-resource-seo.cjs scripts/refresh-resource-audio.cjs
npm run build
# Start this after build; stop it before rebuilding on Windows.
npx --no-install wrangler dev --config .output/server/wrangler.json --port 8799 --ip 127.0.0.1 --local
BASE_URL=http://127.0.0.1:8799 node scripts/audit-resource-seo.cjs
BASE_URL=https://vocolens.com EXPECTED_ARTICLES=11 BASELINE=1 node scripts/audit-resource-seo.cjs
```

Existing installed dependencies were used; no package install or lockfile change was needed. The audit/audio utilities use installed cheerio, which is currently transitive; if it is later removed from the dependency tree, make it an explicit development dependency and synchronize both project lockfiles before relying on the utilities in CI.

## Measurement after an authorized release

1. Obtain Search Console page/query data before rollout: impressions, clicks, CTR, average position, daily trend, search type, country, and device.
2. Compare equal 28-day periods after recrawling; inspect weekly trends for 6–8 weeks. Keep filters consistent and inspect how queries/rank change rather than interpreting page totals alone.
3. Keep granularity unchanged as a reference, not a randomized control. Account for seasonality, article age, demand, indexing, and query overlap.
4. Prioritize further articles using relevant queries where the page already appears but does not answer the intent well. Do not fabricate search-volume numbers or keyword rankings.
5. Track useful clicks and app interest alongside impressions; more appearances alone are not necessarily better outcomes.

No traffic improvement is claimed from these code and rendering checks.
