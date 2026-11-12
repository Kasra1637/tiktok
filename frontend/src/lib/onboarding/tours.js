// Onboarding tour definitions for every page/section of HookForge.
//
// Each tour is keyed by a tour id and matched to a route in `getTourIdForPath`.
// Every step anchors to a real `data-testid` already present in the app (or a
// small set added specifically for onboarding). Copy is written to explain the
// BENEFIT of each step, not just what it is, and to state the product's honest
// limits: a free script plan is separate from the paid render, publishing is
// always manual, and the demo and the close are the founder's own footage.
//
// Core tours auto-open only when a ready page requests first-run help (see
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
  // The data was deleted rather than left unmapped on purpose. Steps that
  // can never open are steps a reader assumes are reachable, and the
  // "every onboarding tour step points at a real element" check would keep
  // passing on them while verifying nothing a user can see. The landing
  // testids stay on the page — they cost nothing and are what a future test on
  // the home page would hook to.

  // Targets CreateVideo — the four-step studio at /create. The tour walks
  // the whole journey the page now carries: profile (approved right on the
  // step when it starts as a draft), angle/goal/template, the required
  // presenter photo, the one pass that writes the plan and builds the
  // strategy that films it, the advisory Craft check, the paid render whose
  // result lands back in the same panel, and the Demo + CTA finishing step
  // that opens on that render. State-dependent steps are optional so a
  // first-run founder (profile step, nothing picked yet) simply skips them.
  create: {
    id: "create",
    label: "Create Video tour",
    steps: [
      {
        target: '[data-testid="studio-progress-segment-profile"]',
        title: "Start with an approved App Profile",
        body:
          "Everything here is written from one approved App Profile — its facts and audience. A draft can be reviewed and approved right on this step; nothing renders before an approval, wherever it happens.",
      },
      {
        target: '[data-testid="studio-progress-segment-angle"]',
        title: "Angle, then goal, then template",
        body:
          "Angles are audience angles generated from your profile. Pick one and matching goals appear; pick a goal and templates are tailored to the pair. Looking around is free — only the render costs.",
      },
      {
        target: '[data-testid="template-photo"]',
        title: "One clear presenter photo",
        optional: true,
        body:
          "A render needs a photo of the person on camera: one clear face, well lit. It is the identity reference every clip is built from, so the same photo across a series keeps the same presenter.",
      },
      {
        target: '[data-testid="studio-progress-segment-review"]',
        title: "The plan is words; the strategy is filming",
        body:
          "One pass writes both, free: the plan is the words — the hook line and the spoken script — and the strategy is how those words get filmed: the scene, the camera, the opening move. Read them before paying for a render.",
      },
      {
        target: '[data-testid="quality-report"]',
        title: "The Craft check advises, never blocks",
        optional: true,
        body:
          "This scores the saved plan and names its weakest part, with a next step for each weak spot. Advisory only — a low score never stops a render; it tells you what a rewrite would buy.",
      },
      {
        target: '[data-testid="render-generate-button"], [data-testid="paid-render-progress"]',
        title: "The render is the paid step",
        optional: true,
        placement: "top",
        body:
          "Rendering takes minutes and the progress shows here. When it finishes, the video appears here to preview and download, post copy frozen beside it. Posting stays manual; the demo and close are yours, in Demo + CTA.",
      },
      {
        target: '[data-testid="studio-progress-segment-finish"]',
        title: "Finish in Demo + CTA",
        optional: true,
        body:
          "The flow ends in Demo + CTA, with your finished render already loaded — no hunting for the clip you just made. Add the demo you record and your closing message there; the export saves beside the original in History.",
      },
    ],
  },

  // Targets BrandSetup — research, edit and approve an App Profile at /brand.
  // Profiles are created from the website, App Store and Google Play URLs; the details card appears
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
          "Paste your app's website, App Store or Google Play URL, then choose Research app for video. Research creates a draft, not an approved profile.",
      },
      {
        target: '[data-testid="brand-manual-card"]',
        title: "Make it yours in detail",
        body:
          "Review your app's features and outcomes in the details below. Correct anything the research got wrong before approval.",
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
          "Approve only after reviewing the facts. Approval makes this profile available in Create Video; saving alone does not approve it.",
      },
      {
        target: '[data-testid="find-video-to-remix-button"]',
        title: "Next: choose an audience angle",
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
          "Upload a clear photo of your on-camera person — this becomes the character reference every generated video is built from. In Create Video, you finish the upload on Audience & template.",
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
          "Draft or approved — the badge says which. Review this app's facts here. Use App Profile to edit or approve it, Create Video to plan a clip, History for finished clips, and Analytics for saved results."
      },
      {
        target: '[data-testid="profile-facts"]',
        title: "The facts your scripts live on",
        body:
          "Features, use cases, outcomes, audience details, proof points — this is the raw material for every script. The 'Never show in the video' list goes straight to the video generator."
      },
      {
        target: '[data-testid="pending-proposal-alert"]',
        title: "A proposal waits — nothing changed yet",
        optional: true,
        body:
          "Re-research lands as a proposal, never an overwrite. Your approved profile is untouched until you review and approve — approving applies the proposal across every video about this app."
      },
      {
        target: '[data-testid="delete-profile-button"]',
        title: "Delete means everything",
        optional: true,
        body:
          "Deleting a profile takes its drafts, renders, assets, and recorded results with it — type-to-confirm, because the blast radius is every finished video, not one regenerable row."
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
        title: "A base clip, one finished export",
        body:
          "Upload footage or choose a finished render from History. Add a Second clip to play after the base, with its own look. Real Video also supports a separate upload in a phone over the base. Export the result together."
      },
      {
        target: '[data-testid="demo-cta-source"] button[aria-pressed]',
        title: "Mockup or full-frame",
        body:
          "Floating phone, hand-held mockup, or full-frame Real Video — pick the look. Drag the preview to frame it; the hand-held option also lets you set a scene."
      },
      {
        target: '[data-testid="hook-controls"]',
        title: "Hook text, your call",
        body:
          "Optional on-screen text, separate from the clip's spoken hook. Set its words, timing, and position, and check the preview before committing."
      },
      {
        target: '[data-testid="cta-controls"]',
        title: "The End Card gives the next step",
        body:
          "The End Card is a clear next step, plus your social handle if you want it. It sits as an overlay on this clip — it does not publish anything anywhere."
      },
      {
        target: '[data-testid="demo-cta-export"]',
        title: "Export right, once",
        // Optional: the player row (and its Export button) only exists once
        // a clip is loaded. Empty standalone editor, no spotlight — the
        // pinned-render route still gets it.
        optional: true,
        body:
          "One fixed TikTok export — 1080×1920 MP4 at 30 fps, saved to History. A render-based export keeps its original clip unchanged. Preview first, then export once."
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
          "Use the app and status filters to find a render. Completed clips stay here for review; posting is always manual.",
      },
      {
        target: '[data-testid="history-list"]',
        title: "Each card is clip plus record",
        optional: true,
        body:
          "Play a finished clip before downloading it. Its status tells you whether it is ready or still waiting on the provider.",
      },
      {
        target: '[data-testid="history-detail-panel"]',
        title: "Record what TikTok tells you",
        optional: true,
        body:
          "Open Results & actions on a posted clip. Paste its link and record views plus 3-second retention %, Average watch %, Saves and Shares, then Save results. Each save is dated, and the latest reading is the one shown."
      },
      {
        // Centered summary: with no rows both tile steps skip, so a fresh
        // account still leaves the tour knowing where renders land and what
        // to do next. No testid — it names the empty state's own Create
        // action rather than adding a new one.
        target: null,
        title: "Your shelf, not your publisher",
        body:
          "Post in TikTok yourself — nothing publishes automatically. Record the link and results here, and once 3 posted clips carry results and a craft score, they steer the next videos written for you. Create a video to start.",
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
        title: "Scores beside results",
        body:
          "Choose an app or All apps. Each finished clip shows the craft score it was rendered with, beside its recorded views, posted status, and your vote. Views describe reach, not installs or conversions.",
      },
      {
        target: '[data-testid="analytics-performance-summary"]',
        title: "When the results start teaching",
        optional: true,
        body:
          "This line joins craft scores to posted results. Once 3 posted clips have both, it names the craft parts that track with viewers watching past 3 seconds and staying longer. Below 3 joined clips, it only counts so far.",
      },
      {
        target: '[data-testid="analytics-results"]',
        title: "Choose another take",
        optional: true,
        body:
          "Recorded views sort highest first; missing counts stay last. Review the clip in History or reuse its existing draft. Compare your judgment alongside reach; a high count does not prove conversion or cause.",
      },
      {
        target: '[data-testid="analytics-funnel"]',
        title: "Every clip, counted by status",
        optional: true,
        body:
          "Counts use the loaded set of up to 200 recent renders for the selected scope, not lifetime totals. History starts with 100 and can show more. Archived renders are counted separately from completed.",
      },
      {
        target: '[data-testid="analytics-signals"]',
        title: "What happened, counts only",
        optional: true,
        body:
          "Captured automatically as you worked — a count list, not judgments about why. Each row links to the latest render behind it, so a count answers which clip without inventing a mapping.",
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
  // Direct loads and refreshes can carry a trailing slash (/demo-cta/);
  // without this the tour and its replay both vanish on those arrivals.
  const path = pathname.length > 1 ? pathname.replace(/\/+$/, "") : pathname;
  if (path === "/create") return "create";
  if (path === "/brand") return "brand";
  if (path === "/history") return "history";
  if (path === "/analytics") return "analytics";
  if (path === "/assets") return "assets";
  if (path === "/demo-cta" || /^\/demo-cta\/[^/]+$/.test(path)) return "demo-cta";
  if (/^\/app-profiles\/[^/]+\/assets$/.test(path)) return "assets";
  if (/^\/app-profiles\/[^/]+$/.test(path)) return "app-profile";
  return null;
}
