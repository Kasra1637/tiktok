# HookForge landing-page copy review

## Delivered

Updated `frontend/src/pages/Landing.jsx`, the title/description in `frontend/public/index.html`, and regression assertions in `frontend/scripts/check-render-smoke.cjs`.

- Hero: **Give your app a story worth watching.**
- Generation-first positioning for mobile-app founders and marketers.
- Five-step workflow covering profile approval, goal, template/photo, reviewed ready state, and the real product demo/manual publishing.
- Eight distinct benefits instead of 16 overlapping cards.
- Separate explanation of AI-generated Hook + Story and the one-source-clip Demo + CTA editor.
- Buyer questions about existing footage, editing, synthetic presenter/voice, audio/export variability, and manual results.
- Consistent creation actions, standalone editor links, corrected signed-in destinations, mobile sign-in access, and keyboard-operable questions.
- Existing dark studio theme preserved. Local filled-button text contrast corrected; nested link/button controls replaced with the existing `asChild` pattern.
- Unsupported free/price/savings/template-count/revenue/likeness/automatic-assembly claims removed. No billing offer invented.

## Product evidence

| Landing claim | Source inspected |
| --- | --- |
| Research or manually set up and approve an app profile | `frontend/src/pages/BrandSetup.jsx`; backend profile approval handlers |
| Goal-specific recommendations and optional content angle | `frontend/src/pages/CreateVideo.jsx`; backend objective-template and recommendation handlers |
| Review script/directions, mark ready, explicitly render | `CreateVideo.jsx`, `GenerationPanel.jsx`; backend ready/generate handlers |
| Banned-claim matches block generation; other checks are not factual certification | `backend/claim_safety.py`; backend claim/ready/generate gates |
| Photo-guided AI output; audio varies by model | `GenerationPanel.jsx`; `backend/video_providers.py` |
| One-source-clip mockups, framing/zoom, user-written hook/end-card overlays, browser-dependent export | `frontend/src/demoCta/DemoCtaEditor.jsx`, `constants.js`; `DemoCtaStudio.jsx` |
| History, draft variations, manually entered results; manual publishing | `frontend/src/pages/GenerationHistory.jsx`; backend variation/performance handlers |

No backend or in-app behavior was changed. Pre-existing edits in the shared checkout were preserved. No commit, push, deployment, paid generation, or real account login was performed.

## Final checks

- `yarn run check`: passed (import checks, frontend logic checks, all **108 render smoke checks**).
- `yarn run build`: passed. One existing `react-hooks/exhaustive-deps` warning remains in `CreateVideo.jsx` around `visibleRecommendations`.
- Built title and description match the final HTML source.
- Scoped `git diff --check`: passed.
- Signed-out, signed-in, and no-auth landing action branches verified through the real AuthControls implementation with mocked Clerk primitives/configuration. Sign-up/sign-in triggers and creation/editor destinations asserted.
- Actual Chromium page: one meaningful H1, zero nested interactive controls, updated title/description, balanced comparison row heights at desktop and 1024px widths, no horizontal document/header overflow at 320, 390, 768, 1024, and 1440px during review.
- Actual interactions: section anchor lands below fixed header; FAQ opens with Enter while summary retains focus; header creation action navigates to `/create`; standalone footage action navigates to `/demo-cta`, where editor controls render.
- Final landing browser errors: none captured. Local no-auth warning is expected because Clerk is not configured.
- axe WCAG 2A/2AA audit: **zero detected violations** after local button contrast repair. One incomplete contrast rule covers gradient/translucent backgrounds; this is not a certification of full WCAG compliance.
- Final desktop/mobile PNG screenshots captured with agent-browser and checked as valid PNG artifacts. Freebuff embedded-webview screenshot capture was unavailable (no composited frames); full visual acceptance is not claimed from DOM measurements alone.

## Resolved check interruptions

- `yarn check` invoked Yarn 1's built-in dependency audit, not the package script, and reported existing peer/resolution incompatibilities. The intended project gate is **`yarn run check`**, which passed. No dependencies/lockfiles were changed or errors suppressed.
- Full render suite initially found a stale History assertion expecting the retired “Download video” label and the playback URL. Current product uses “Download” and a dedicated same-origin `/download` route. The assertion now verifies that route exactly, including preservation of the signed query string. No product code or signature validation was weakened.
- Landing tests previously prohibited any “CTA” or “end card” mention despite the shipped editor supporting user-authored overlays. Replaced those blanket bans with scoped tests requiring clear generated-footage/editor boundaries and external assembly/manual publishing disclosures.

## Review links

- Live local review: http://127.0.0.1:3000/ (also registered in this thread’s Preview tab).
- `test_reports/hookforge-landing-desktop.png`
- `test_reports/hookforge-landing-mobile.png`
- `test_reports/hookforge-landing-check.log`
- `test_reports/hookforge-landing-build.log`
- `test_reports/hookforge-landing-a11y.json`

## Limits

Real Clerk account/session flows were not tested; auth presentation/triggers were tested with mocks. Create Video navigation rendered its page but API data was unavailable without a running backend; no end-to-end paid render or result upload was attempted. Browser and copy changes do not establish conversion, view, or sales improvements. The existing dependency-audit incompatibilities and gradient contrast review remain separate follow-up work.
