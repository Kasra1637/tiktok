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
        title: "Five steps to a finished clip",
        body:
          "Pick your app, lock a goal, grab a matched template and presenter photo, read your free script plan, then render Hook + Story. These step tabs are your rail — hop around freely; the plan and the render stay separate.",
      },
      {
        target: '[data-testid="step-pill-angle"]',
        title: "Pick the angle that sells",
        body:
          "An audience angle is required — it is the story your strategy and render hang on. Six goal suggestions come with it: tap Shuffle to reorder the same six for free, or Regenerate angles for brand-new material (drafts built on an angle are warned about and reported). Then pick your goal and go.",
      },
      {
        target: '[data-testid="step-pill-template"]',
        title: "Choose a format & presenter",
        body:
          "Tailored to your app and goal — every suggestion carries a fit score, its reasons, and its caveats. The template also sets the clip's length, so swapping it changes how long the piece runs. Add the presenter photo right below: template and photo live on the same step.",
      },
      {
        target: '[data-testid="step-pill-review"]',
        title: "Review the words first",
        body:
          "Your script plan is free and written when you reach Review with the required choices set. Edit the hook, story, and visual directions to taste. Flagged claims get fixed here — a prohibited claim blocks rendering.",
      },
      {
        target: '[data-testid="step-pill-hook"]',
        title: "Render Hook + Story",
        body:
          "The app-specific strategy is built here and shown before you spend anything. Read it, then render the clip from your approved plan and presenter photo. One short clip, exactly as long as its template says. No demo, no CTA, no on-screen text — this is the hook and the story only.",
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
        title: "Research, then trust but verify",
        body:
          "Drop in your App Store or Google Play URL — support pages help. Hit Research app and a draft comes back below. It is a draft: check it against your real product before you approve anything.",
      },
      {
        target: '[data-testid="brand-manual-card"]',
        title: "Make it yours in detail",
        body:
          "Research gets the shape; you supply the truth. Fix the details, add real features and outcomes, ban what must never show, and sort claims into approved, needs review, or banned. Scripts live by these facts.",
      },
      {
        target: '[data-testid="save-brand-button"]',
        title: "Save, then approve when ready",
        body:
          "Save stores your work; it approves nothing and generates nothing. Only the app name is required — but richer detail writes stronger scripts."
      },
      {
        target: '[data-testid="approve-profile-button"], [data-testid="research-menu-button"]',
        title: "Approve a reviewed profile",
        body:
          "Approval unlocks Create Video: audience angles and template suggestions come alive with it. Refresh from the Research menu builds a proposal instead — review it, then approve before it replaces your current profile.",
      },
      {
        target: '[data-testid="find-video-to-remix-button"]',
        title: "Next: choose a video goal",
        optional: true,
        body:
          "Approved and ready? Open Create Video, pick the angle that fits, and let it suggest templates. One profile serves every video about this app.",
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
          "Every asset belongs to one app profile — switch apps here first. Approval unlocks video generation, not uploads: you can add photos before approving anything.",
      },
      {
        target: '[data-testid="asset-upload-panel"]',
        title: "Add the presenter photo",
        optional: true,
        body:
          "Upload a clear photo of your on-camera person — this becomes the character reference every generated video is built from. In Create Video, you finish the upload on Template & photo.",
      },
      {
        target: '[data-testid="asset-rights-alert"]',
        title: "Check the upload before using it",
        optional: true,
        body:
          "Only use images you have the right to publish. Faces are checked: no face, or several faces, and the video provider can bounce it.",
      },
      {
        target: '[data-testid="asset-list"]',
        title: "Use one presenter per video",
        optional: true,
        body:
          "One face per video. In the studio the photo attaches to a draft; swap or remove it before rendering. Archive or delete what you no longer need.",
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
        title: "One profile, every video",
        body:
          "Draft or approved — the badge says which. This page is the reporting center for each video, angle, and claim. Navigate back to the profiles list, or open the library and history from any profile."
      },
      {
        target: '[data-testid="profile-facts"]',
        title: "The facts your scripts live on",
        body:
          "Features, use cases, outcomes, audience details, proof points — this is the raw material for every script. The 'Never show in the video' list goes straight to the video generator."
      },
      {
        target: '[data-testid="claim-guardrails"]',
        title: "Claims with guardrails",
        optional: true,
        body:
          "Approved, needs review, banned. The script plan runs a claim check against these, and a prohibited claim blocks rendering until the script is edited. Do not publish anything you cannot back."
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
        title: "One clip in, one styled clip out",
        body:
          "Bring your own footage or style a finished Hook + Story render. One source clip at a time — stitch separate clips in your own editor."
      },
      {
        target: '[data-testid="view-mode-floating"]',
        title: "Frame the phone, not the screen",
        body:
          "Floating phone or hand-held mockup — pick the look. Drag the preview to frame it; the hand-held option also lets you set a scene."
      },
      {
        target: '[data-testid="hook-controls"]',
        title: "Opening text, your call",
        body:
          "Optional on-screen text, separate from the clip's spoken hook. Set its words, timing, and position, and check the preview before committing."
      },
      {
        target: '[data-testid="cta-controls"]',
        title: "The close that converts",
        body:
          "A clear next step, plus your social handle if you want it. It sits as an overlay on this clip — it does not publish anything anywhere."
      },
      {
        target: '[data-testid="platform-preset-group"]',
        title: "Export right, once",
        body:
          "Output size and format to match where the clip is going next. The advanced controls are optional; preview before exporting."
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
        title: "Every render, in one place",
        body:
          "Filter by app or status in the title bar; every render lands here as its own tile. Completed clips gather here — posting is always your move, and nothing publishes itself.",
      },
      {
        target: '[data-testid="history-list"]',
        title: "Each tile is the clip",
        optional: true,
        body:
          "History opens as a contact sheet of finished clips: play one right there. Facts, actions, and the paper trail stay folded into the tile's drawer until you ask for them.",
      },
      {
        target: '[data-testid="history-expand"]',
        title: "Expand a render for its details",
        optional: true,
        body:
          "Click the tab at the bottom of a tile — or drag it up — to open the render's facts, its download and Demo + CTA, and Details: the generation prompt and the claim-check saved with it. Read them before you publish."
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
        title: "Results per app, verdicts per choice",
        body:
          "Numbers follow the app profile — what works depends on the app. Switch apps here. Your thumbs on goals, templates, plans, and scripts feed every verdict you see; real calls, not guesses.",
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
