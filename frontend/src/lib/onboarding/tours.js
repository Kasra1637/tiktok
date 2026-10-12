// Onboarding tour definitions for every page/section of HookForge.
//
// Each tour is keyed by a tour id and matched to a route in `getTourIdForPath`.
// Every step anchors to a real `data-testid` already present in the app (or a
// small set added specifically for onboarding). Copy is written to explain the
// BENEFIT of each step, not just what it is, and to state the product's honest
// limits: a free script plan is separate from the paid render, publishing is
// always manual, and the demo and the close are the founder's own footage.
//
// Tours auto-OPEN on the first arrival at their route and not again (see
// OnboardingProvider — a persisted seen-check, with "Show me around" as the
// deliberate replay) — so copy is written to be skippable: every step stands
// alone, and the shortest tour that still explains the page is the right one.
//
// Step shape:
//   target: CSS selector string (may contain a comma-separated OR list of
//           selectors — the first one found in the DOM wins), or `null` for
//           a centered welcome/summary card with no spotlight.
//   title, body: tooltip copy.
//   optional: if true, the engine gives up finding this target faster and
//             silently skips to the next step (used for state-dependent UI
//             that may not be on screen, e.g. "record results" before any
//             video exists).
//   placement: preferred tooltip side ("bottom" | "top") — auto-flips if
//              there isn't room.

export const TOURS = {
  // No landing tour. The home page used to have one that pointed at
  // landing-hero, landing-how-it-works, landing-your-week, landing-features and
  // landing-enter-app-button, and it fired on every arrival. See
  // getTourIdForPath for why it is gone.
  //
  // The data was deleted rather than left unmapped on purpose. Five steps that
  // can never open are five steps a reader assumes are reachable, and the
  // "every onboarding tour step points at a real element" check would keep
  // passing on them while verifying nothing a user can see. The landing
  // testids stay on the page — they cost nothing and are what a future test on
  // the home page would hook to.

  // Targets CreateVideo — the five-step studio at /create.
  create: {
    id: "create",
    label: "Create Video tour",
    steps: [
      {
        target: '[data-testid="step-pill-profile"]',
        title: "Build a video in five steps",
        body:
          "Choose an approved app, set a video goal, pick a matched template and presenter photo, review your free script plan, then render Hook + Story. Use these step tabs to move around; the plan and render are separate.",
      },
      {
        target: '[data-testid="step-pill-angle"]',
        title: "Choose a goal and audience",
        body:
          "Select the required goal first: it shapes template suggestions and the script. An audience angle is also required — the strategy and the render are built around it. Tone stays optional. The free script plan appears in Review; the video renders in the final step.",
      },
      {
        target: '[data-testid="create-what-you-get"]',
        title: "Know what this creates",
        optional: true,
        body:
          "The final render is one short Hook + Story clip. Its template sets the length. Your filmed product demo and closing call to action are separate footage you add afterwards.",
      },
      {
        target: '[data-testid="step-pill-template"]',
        title: "Choose a format and presenter",
        body:
          "Suggestions are tailored to the selected app and goal. Compare each fit score, reasons, and caveats; the top suggestion starts selected, but you can choose another. Add the presenter photo below—the template and photo belong to the same step.",
      },
      {
        target: '[data-testid="step-pill-review"]',
        title: "Review the words first",
        body:
          "Your script plan is free and is created when you reach Review with the required choices set. Read and edit the hook, story, and visual directions; check flagged claims, then save edits. A prohibited claim blocks rendering.",
      },
      {
        target: '[data-testid="step-pill-hook"]',
        title: "Render Hook + Story",
        body:
          "The app-specific strategy is built here and shown before you spend on a render. Read it, then generate the Hook + Story clip from your approved plan and presenter photo. This clip has no product demo, closing CTA, or on-screen text.",
      },
      {
        target: '[data-testid="create-no-autopost-note"]',
        title: "Finish the promo separately",
        body:
          "Record your product demo and add your closing call to action after Hook + Story. Demo + CTA styles one clip at a time; combine clips in your own editor. Renders are saved to History, and nothing is published automatically.",
      },
    ],
  },

  // Targets BrandSetup — research, edit and approve an App Profile at /brand.
  // Profiles are created from store listings only; the details card appears
  // once research returns one, so every step below targets something that
  // exists from that point on.
  brand: {
    id: "brand",
    label: "App Profile tour",
    steps: [
      {
        target: '[data-testid="app-research-card"]',
        title: "Research from the store listings",
        body:
          "Add your app's App Store URL, Google Play URL, or both, plus support pages if useful. Add notes if useful, then choose Research app. The result is a draft—check it against your actual product before saving and approving. The details appear below once research finishes.",
      },
      {
        target: '[data-testid="brand-manual-card"]',
        title: "Add accurate product detail",
        body:
          "Correct the research and add real features, audience segments, use moments, proof points, and feature-to-outcome statements. Set what must never appear and sort claims into approved, needs review, or banned; scripts use these details.",
      },
      {
        target: '[data-testid="save-brand-button"]',
        title: "Save, then approve when ready",
        body:
          "Save stores your profile details; it does not approve the profile or generate a video. Review the key facts and claims first. Only the app name is required to save, but fuller details make stronger scripts.",
      },
      {
        target: '[data-testid="approve-profile-button"], [data-testid="refresh-profile-button"]',
        title: "Approve a reviewed profile",
        body:
          "Approval makes this profile available in Create Video and creates its audience angles and template suggestions. Refreshing from sources creates a proposal; review and approve it before it replaces your current profile.",
      },
      {
        target: '[data-testid="find-video-to-remix-button"]',
        title: "Next: choose a video goal",
        optional: true,
        body:
          "Once approved, open Create Video to set a goal, optionally choose one of these audience angles, and get template suggestions. Reuse this profile for multiple videos.",
      },
    ],
  },

  // Targets AssetLibrary at /assets and /app-profiles/:id/assets.
  assets: {
    id: "assets",
    label: "Asset Library tour",
    steps: [
      {
        target: '[data-testid="asset-profile-picker"], [data-testid="asset-library-header"]',
        title: "Choose which app owns the photo",
        body:
          "Assets belong to one App Profile. Switch apps here when needed; then upload a photo you have permission to use. Approval is needed to generate a video, not to add a photo.",
      },
      {
        target: '[data-testid="asset-upload-panel"]',
        title: "Add the presenter photo",
        optional: true,
        body:
          "Upload a clear photo of the person you want on camera. This is the character reference used in generated videos; the setting and scene come from the App Profile. In Create Video, upload it on Template & photo.",
      },
      {
        target: '[data-testid="asset-rights-alert"]',
        title: "Check the upload before using it",
        optional: true,
        body:
          "Confirm you have the right to use the image. The upload is checked for faces; a photo with no clear face or several faces may be rejected by the video provider.",
      },
      {
        target: '[data-testid="asset-list"]',
        title: "Use one presenter per video",
        optional: true,
        body:
          "A video uses one character-reference photo. In the studio, the uploaded photo attaches to that draft; you can remove it or replace it before rendering. Archive or delete photos you no longer need.",
      },
    ],
  },

  // Targets AppProfileDetail at /app-profiles/:id.
  "app-profile": {
    id: "app-profile",
    label: "App detail tour",
    steps: [
      {
        target: '[data-testid="app-profile-header"]',
        title: "Manage this app profile",
        body:
          "Check whether the profile is a draft or approved. Edit opens its details. Reuse it for every video about this app.",
      },
      {
        target: '[data-testid="profile-facts"]',
        title: "Review the product facts",
        body:
          "These features, use cases, outcomes, audience details, and proof points ground your video scripts. The “Never show in the video” list is passed as an instruction to the video generator.",
      },
      {
        target: '[data-testid="claim-guardrails"]',
        title: "Review claim categories",
        optional: true,
        body:
          "Check approved, needs-review, and banned claims here. The script plan runs a claim check; a prohibited claim blocks rendering until you edit the plan and the check passes. Verify claims yourself before publishing.",
      },
      // The results card moved off this page (bound for Analytics); the step
      // goes with it rather than pointing at nothing. Angles and drafts used
      // to live on this page; both moved to Create
      // Video (angles) and History (drafts), so there is nothing to point at
      // here any more. The wizard's own tour covers the angle picker.
    ],
  },

  // Targets DemoCtaStudio at /demo-cta.
  "demo-cta": {
    id: "demo-cta",
    label: "Demo + CTA tour",
    steps: [
      {
        target: '[data-testid="demo-cta-source"]',
        title: "Start with one clip",
        body:
          "Upload your own footage or style a finished Hook + Story render. This editor handles one source clip at a time; join separate demo and story clips in your video editor.",
      },
      {
        target: '[data-testid="view-mode-floating"]',
        title: "Choose the phone look",
        body:
          "Pick a floating phone or hand-held mockup. Drag the preview to frame it; the hand-held option also lets you choose a scene.",
      },
      {
        target: '[data-testid="hook-controls"]',
        title: "Add opening text",
        body:
          "This is an optional on-screen overlay, separate from the clip's spoken hook. Set its text, timing, and position, then check the preview.",
      },
      {
        target: '[data-testid="cta-controls"]',
        title: "Add a closing card",
        body:
          "Write a clear next step and optional social handle. The card is an overlay on this clip; it does not join another clip or publish the video.",
      },
      {
        target: '[data-testid="platform-preset-group"]',
        title: "Choose export settings",
        body:
          "Select an output size and format for where you plan to edit or share the clip. Advanced controls are optional; preview before exporting to History.",
      },
    ],
  },

  // Targets GenerationHistory, which is what /history serves.
  history: {
    id: "history",
    label: "History tour",
    steps: [
      {
        target: '[data-testid="history-header"], [data-testid="history-list"]',
        title: "Find a video in History",
        body:
          "Filter videos by app or status from the title bar. Each row shows its render state and available actions. Completed videos are saved here; posting and publishing are always up to you.",
      },
      {
        target: '[data-testid="history-list"]',
        title: "Play, download, or reuse a render",
        optional: true,
        body:
          "A completed row offers its video, status, model, download, and actions to duplicate or open it in Demo + CTA. Finished videos are not rated here: the thumbs you give goals, templates, plans, and scripts while creating are what teach the studio.",
      },
      {
        target: '[data-testid="generation-details-button"]',
        title: "Inspect the render details",
        optional: true,
        body:
          "Open Details to see the generation prompt and the claim-check report saved with this render. Use them to understand what the system generated; review claims before you publish.",
      },
    ],
  },

  // Targets Analytics at /analytics.
  analytics: {
    id: "analytics",
    label: "Analytics tour",
    steps: [
      {
        target: '[data-testid="analytics-profile-picker"], [data-testid="analytics-header"]',
        title: "Pick the app you are reading",
        body:
          "Results are per App Profile, because which opening works depends on the app. Switch apps here to read another one's numbers.",
      },
    ],
  },
};

/**
 * Resolve which tour (if any) applies to a given route pathname.
 *
 * Order matters: /app-profiles/:id/assets is a prefix-sibling of
 * /app-profiles/:id, so the assets form is matched first and exactly.
 * Redirect-only routes (/app-profiles, /templates,
 * /templates/:id) and the public auth/legal pages map to null — a redirect's
 * destination opens its own tour, and a sign-in page is not a section anyone
 * needs a tour of.
 *
 * The home page maps to null too, deliberately. It had a five-step "Welcome
 * tour" that fired on every arrival, over marketing copy the visitor can just
 * read: the tour walked them through the hero, the how-it-works strip, the
 * comparison table and the features grid, which is a page tour in the least
 * useful sense — it taught the layout rather than the product. It also popped
 * over the one screen people arrive on before they have any context for a
 * coach mark. The app's own pages still tour on arrival, which is where the
 * tour earns its keep: those are working surfaces with a next action.
 */
export function getTourIdForPath(pathname) {
  if (pathname === "/create") return "create";
  if (pathname === "/brand") return "brand";
  if (pathname === "/history") return "history";
  if (pathname === "/analytics") return "analytics";
  if (pathname === "/assets") return "assets";
  if (pathname === "/demo-cta" || /^\/demo-cta\/[^/]+$/.test(pathname)) return "demo-cta";
  if (/^\/app-profiles\/[^/]+\/assets$/.test(pathname)) return "assets";
  if (/^\/app-profiles\/[^/]+$/.test(pathname)) return "app-profile";
  return null;
}
