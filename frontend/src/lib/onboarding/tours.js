// Onboarding tour definitions for every page/section of HookForge.
//
// Each tour is keyed by a tour id and matched to a route in `getTourIdForPath`.
// Every step anchors to a real `data-testid` already present in the app (or a
// small set added specifically for onboarding). Copy is written to explain the
// BENEFIT of each step, not just what it is, and to state the product's honest
// limits: nothing is spent until the last step, publishing is always manual,
// and the demo and the close are the founder's own footage.
//
// Tours auto-OPEN on every arrival of their route (see OnboardingProvider) —
// there is no once-only seen-check — so copy is written to be skippable: every
// step stands alone, and the shortest tour that still explains the page is the
// right one.
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
        title: "The studio, in five steps",
        body:
          "App Profile \u2192 Audience & goal \u2192 Template & photo \u2192 Review \u2192 Hook & middle. Jump between steps with these pills; only approved profiles get in, so every script builds on facts you have reviewed.",
      },
      {
        target: '[data-testid="step-pill-angle"]',
        title: "Say what the video is for",
        body:
          "The objective is required and is the heaviest signal in template ranking; the content angle is optional and narrows the match further. Nothing is spent until the last step.",
      },
      {
        target: '[data-testid="create-what-you-get"]',
        title: "What you get",
        optional: true,
        body:
          "One render of the template's length: a short hook, then a middle that stops where you would reach for your phone. The length comes from the template you pick \u2014 it is not a choice.",
      },
      {
        target: '[data-testid="step-pill-template"]',
        title: "Templates, honestly scored",
        body:
          "Ranked for this app and this goal, each card showing its fit score, why it fits, and where it falls short. The top pick is preselected \u2014 every card also says what the template needs from you.",
      },
      {
        target: '[data-testid="step-pill-review"]',
        title: "Read before you spend",
        body:
          "The plan is free: hook line, script, a demo note for you (it never reaches the model), and a read-only shot timeline. The claim check runs here, and your banned list blocks the render outright.",
      },
      {
        target: '[data-testid="step-pill-hook"]',
        title: "The one paid step",
        body:
          "Build the app-specific strategy first \u2014 free, and it is what makes the render about your app rather than a generic take. Then one render of the hook and the middle, with captions from your approved script.",
      },
      {
        target: '[data-testid="create-no-autopost-note"]',
        title: "Generated here, posted by hand",
        body:
          "You record the demo and add your own close after the middle. Nothing is ever published for you and no platform credentials are involved \u2014 finished renders land in History.",
      },
    ],
  },

  // Targets BrandSetup — research, edit and approve an App Profile at /brand.
  brand: {
    id: "brand",
    label: "Your app tour",
    steps: [
      {
        target: '[data-testid="brand-url-card"]',
        title: "Start with your website",
        body:
          "Analyze reads your site and pre-fills the profile \u2014 name, niche, audience, tone \u2014 so you sharpen what it found instead of typing a form from scratch.",
      },
      {
        target: '[data-testid="app-research-card"]',
        title: "Research the whole app",
        body:
          "Add the App Store and Google Play links, any support pages, and your own notes. AI drafts the full App Profile \u2014 features, audiences, claims, video themes \u2014 as a draft for you to review.",
      },
      {
        target: '[data-testid="brand-manual-card"]',
        title: "Everything is editable",
        body:
          "Refine what the research found: features, use cases, problems solved, what must never show on camera, viewer objections, and your approved / needs-review / banned claim lists. These drive every script.",
      },
      {
        target: '[data-testid="save-brand-button"]',
        title: "Save as often as you like",
        body:
          "Saving stores the draft, and it can be edited and re-saved any time \u2014 nothing is generated from a draft. An app name is the only field required.",
      },
      {
        target: '[data-testid="approve-profile-button"], [data-testid="refresh-profile-button"]',
        title: "Approval is the gate",
        body:
          "Only approved profiles enter the studio, generate content angles, or earn template recommendations. Re-research stages a proposal that changes nothing until you approve it again.",
      },
      {
        target: '[data-testid="find-video-to-remix-button"]',
        title: "Next: the studio",
        optional: true,
        body:
          "Open the studio to turn this profile into a video \u2014 or use Content angles up top to generate the audience angles the studio can target first.",
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
        title: "Assets are per app",
        body:
          "Everything here belongs to the app chosen at the top, and the picker shows which of your apps are still awaiting approval. Upload anything you have the right to use \u2014 each upload records that confirmation.",
      },
      {
        target: '[data-testid="asset-upload-panel"]',
        title: "One upload: your photograph",
        optional: true,
        body:
          "Face-only product: the character reference is the only asset kind. The person on camera in every generated video is the person in this photo \u2014 the room and the scene are invented from your App Profile.",
      },
      {
        target: '[data-testid="asset-rights-alert"]',
        title: "Checked before it costs you",
        optional: true,
        body:
          "Rights are confirmed per upload, and faces are counted up front: a photo with no detectable face \u2014 or several competing ones \u2014 is flagged here, which is what the video provider would otherwise refuse at the paid render.",
      },
      {
        target: '[data-testid="asset-list"]',
        title: "One face per project",
        optional: true,
        body:
          "Attach a character reference to a project and the slot is taken \u2014 the server refuses a render with two. Archive or delete old entries; retired asset kinds can never be re-attached.",
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
        title: "Your app, in one place",
        body:
          "Draft or approved at a glance. New video deep-links the studio with this app preselected, and Edit opens the profile editor \u2014 everything below backs every video you make from this app.",
      },
      {
        target: '[data-testid="profile-facts"]',
        title: "The facts scripts build on",
        body:
          "Features, use cases, problems solved, outcomes, and \u201Cnever show in the video\u201D \u2014 that last list is attached to every render prompt as an instruction to the model, so it is enforced, not advisory.",
      },
      {
        target: '[data-testid="claim-guardrails"]',
        title: "Claim guardrails",
        optional: true,
        body:
          "Approved claims are safe to use, \u201Cneeds review\u201D claims must be verified first, and the never-use list blocks the paid render outright. Fix the flagged claim in the plan and the block clears.",
      },
      {
        target: '[data-testid="what-works"]',
        title: "The part that improves with use",
        body:
          "Log view numbers on finished videos and they land here, aggregated per opening. The next strategy reads this, so what actually carried views for this app shapes what gets written next.",
      },
      {
        target: '[data-testid="app-profile-angles"]',
        title: "Content angles",
        body:
          "Generate audience angles \u2014 the problem, the hook promise, the feature shown \u2014 and pick one in the studio to narrow template matching to that audience.",
      },
      {
        target: '[data-testid="app-profile-videos"]',
        title: "Every draft on this app",
        body:
          "Drafts are independent and resumable, and each one deep-links back into the studio at the right step. The profile is never consumed \u2014 reuse it for as many videos as you like.",
      },
      {
        target: '[data-testid="app-profile-templates"]',
        title: "Suggested templates",
        body:
          "Once the profile is approved, the ranked openings appear here with their fit reasons. Click one to open the studio with it selected \u2014 the full scored list lives on the Template & photo step.",
      },
    ],
  },

  // Targets GenerationHistory, which is what /history serves.
  history: {
    id: "history",
    label: "History tour",
    steps: [
      {
        target: '[data-testid="history-filters"]',
        title: "Every render, accounted for",
        body:
          "Filter by app or status; the totals line shows results, completed, failed, and exactly what you have spent. Publishing stays manual \u2014 this is a production log, not a posting schedule.",
      },
      {
        target: '[data-testid="history-list"]',
        title: "What each card holds",
        optional: true,
        body:
          "The video, its status, model and cost, with downloads, a duplicate button, and verdict controls. Marking a render \u201Clooks good\u201D or \u201Cnot good\u201D is recorded and steers what gets recommended next.",
      },
      {
        target: '[data-testid="generation-details-button"]',
        title: "Open the receipts",
        optional: true,
        body:
          "Details shows the exact prompt sent to the model, the claim check as it stood at render time, and the captions composited afterwards \u2014 the audit trail for any claim in a video you post.",
      },
      {
        target: '[data-testid="record-results-button"]',
        title: "Tell it what worked",
        optional: true,
        body:
          "Log views and a verdict after you post \u2014 typed in by hand, never scraped. This is the one input that makes the next video for this app better: the recorded numbers feed the next strategy.",
      },
    ],
  },

  // Targets Analytics at /analytics.
  analytics: {
    id: "analytics",
    label: "Analytics tour",
    steps: [
      {
        target: '[data-testid="analytics-totals"]',
        title: "Production metrics, from your own history",
        body:
          "Videos created, success and failure rates, average generation time, known spend, rework and variations. Runs that reported no cost are flagged above rather than counted as free.",
      },
      {
        target: '[data-testid="analytics-breakdowns"]',
        title: "Where the work happens",
        body:
          "Volume, success rate and spend broken down by app, model, template, objective, audience and content angle \u2014 the view that tells you what to make next, or what to stop making.",
      },
      {
        target: '[data-testid="analytics-performance"]',
        title: "TikTok numbers, typed by you",
        body:
          "Views, likes, comments, shares and saves are entered by hand and labelled as such. No platform account is connected and nothing is scraped \u2014 these figures are never presented as verified.",
      },
      {
        target: '[data-testid="analytics-feedback"]',
        title: "What happened, and why",
        optional: true,
        body:
          "Workflow facts captured as you worked \u2014 downloads, edits, regenerations \u2014 plus the rejection reasons you stated yourself. Facts about the workflow, not opinions about why.",
      },
    ],
  },
};

/**
 * Resolve which tour (if any) applies to a given route pathname.
 *
 * Order matters: /app-profiles/:id/assets is a prefix-sibling of
 * /app-profiles/:id, so the assets form is matched first and exactly.
 * Redirect-only routes (/app-profiles, /templates, /templates/:id) and the
 * public auth/legal pages map to null — a redirect's destination opens its own
 * tour, and a sign-in page is not a section anyone needs a tour of.
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
  if (/^\/app-profiles\/[^/]+\/assets$/.test(pathname)) return "assets";
  if (/^\/app-profiles\/[^/]+$/.test(pathname)) return "app-profile";
  return null;
}
