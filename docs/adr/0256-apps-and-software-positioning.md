# 0256 — Broaden App Profiles from mobile-only to any app or software product

- **Status:** accepted
- **Date:** 2026-11-21
- **Anchors:** `backend/ai_service.py` (`analyze_app_profile`,
  `generate_content_angles`, `generate_angle_goals`,
  `generate_opening_messages`, `generate_post_kit`,
  `generate_brand_templates`, `generate_creative_plan`,
  `generate_video_strategy`), `backend/ai_text.py`
  (`_html_meta_descriptions`), `backend/generation_planning.py`
  (`build_segment_prompt`, `build_strategy_video_prompt`,
  `FULL_PROMPT_FLOOR`, `CONDENSED_PROMPT_FLOOR`,
  `FIXED_FULL_PROMPT_FLOOR`, `FIXED_CONDENSED_PROMPT_FLOOR`,
  `SINGLE_PASS_PROMPT_FLOOR`), `backend/routers/brands.py`
  (`APP_RESEARCH_CAPS`, `research_app_profile`),
  `frontend/src/pages/BrandSetup.jsx`,
  `frontend/src/pages/AppProfileDetail.jsx`,
  `frontend/src/pages/Landing.jsx`,
  `frontend/public/index.html`,
  `frontend/src/demoCta/constants.js` (`DEVICES`, `CTA_COPY_VARIANTS`),
  `frontend/src/demoCta/DemoCtaEditor.jsx` (`drawPhone`),
  `frontend/src/demoCta/usePreviewLoop.js` (`drawPhone`),
  `frontend/src/lib/copyCase.js` (`sentenceCase`)

## Context

HookForge's Hook + Story → Demo + CTA architecture already separates the
AI-generated human hook/story clip (which never shows a screen surface under
ADR 0109) from the founder's real screen recording in Demo + CTA. That split
fits web apps, SaaS products, desktop tools, and browser extensions just as
naturally as iOS and Android apps. However, five mobile-only assumptions
narrowed the product:

1. **Prompts and platform extraction.** The eight OpenRouter system prompts
   framed the product strictly as a "mobile app", and `analyze_app_profile`
   gave `["iOS", "Android"]` as the only platform examples and asked why a
   viewer would not "download" the app.
2. **Web metadata and support-page caps.** Modern web/SaaS landing pages carry
   positioning in `og:title`, `twitter:title`, and `og:site_name` and split
   their feature specifications onto `/features` or `/docs` (`support_urls`,
   previously capped at 2,000 characters).
3. **Research form layout.** `BrandSetup.jsx` titled the research card
   "Research a mobile app" and placed Website, App Store, and Google Play
   URLs in an uneven three-cell grid rather than leading with the website URL.
4. **Demo + CTA frames and CTAs.** `DEVICES` contained only seven Android
   phones, with no iPhone frame and no browser/window frame for web screen
   recordings, and `CTA_COPY_VARIANTS` lacked a browser CTA.
5. **Post-period brand casing.** `sentenceCase` protected leading mixed-case
   platform names (`iOS`, `macOS`) at the start of a string but uppercased the
   first letter when one opened a second sentence after a period.

## Decision

- **Keep the entity name "App Profile", drop the mobile-only restriction.**
  All eight generation flows in `backend/ai_service.py` and the prompt builders
  in `backend/generation_planning.py` now address apps and software products
  across `["Web", "iOS", "Android", "macOS", "Windows", "Browser Extension"]`,
  match `usage_moments` to the product's actual platforms (desk/workstation
  moments as well as mobile moments), and ask why a viewer would not "try,
  switch to, or download" the product.
- **Richer web extraction.** `_html_meta_descriptions` in `backend/ai_text.py`
  includes `og:title`, `twitter:title`, `og:site_name`, and `application-name`
  (deduplicated against the body), and `APP_RESEARCH_CAPS["support"]` in
  `backend/routers/brands.py` rises from 2,000 to 4,000 characters.
- **Website-first research card and landing copy.** `BrandSetup.jsx` titles
  the card "Research your app", spans the website/product URL input across the
  top row, marks App Store and Google Play URLs optional on the second row,
  and updates the objections label on `BrandSetup.jsx` and
  `AppProfileDetail.jsx` to "Why they would not try or download". `Landing.jsx`
  updates the hero `h1` to `"Turn your app or website link into tailored
  videos, in minutes."`, types `"yourapp.com/start"` (17 chars, matching the
  existing `steps(17)` typing track) in the hero phone field, leads Step 1 of
  How it works with `"Add your website or store URL"`, and updates
  `frontend/public/index.html` meta description from `"phone mockups"` to
  `"device frames"`.
- **iPhone and Browser/Web frames in Demo + CTA.** `DEVICES` adds
  `iphone_16_pro` (`camera: "dynamic-island"`) and `browser_window`
  (`camera: "window-bar"`, omitting hardware side buttons and painting a
  three-dot window header), and `CTA_COPY_VARIANTS` adds
  `"Start free in your browser — link in bio"`.
- **Sentence-boundary mixed-case protection.** `sentenceCase` in
  `frontend/src/lib/copyCase.js` preserves mixed-case tokens (`macOS`, `iOS`,
  `eBay`) after sentence boundaries as well as at the start of a string.

## Alternatives rejected

- **Opening to non-software physical or e-commerce brands.** Physical goods
  have no screen-recorded product UI for Demo + CTA and require the AI video
  model to depict specific physical SKUs, violating the screen-free and
  carried-prop invariants (ADR 0103, ADR 0109).
- **Renaming `App Profile` or database tables.** Founders and users refer to
  web, desktop, and mobile software alike as "apps"; retaining the entity name
  preserves schema compatibility and existing route contracts.

## Consequences

- Web, SaaS, desktop, and mobile app founders share one unified research,
  planning, rendering, and Demo + CTA workflow.
- Existing 7 device frames and `s24_ultra` default remain intact for saved
  drafts; `DEVICES` now holds 9 frames and `CTA_COPY_VARIANTS` holds 4.
