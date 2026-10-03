// Onboarding tour definitions for every page/section of HookForge.
//
// Each tour is keyed by a tour id and matched to a route in `getTourIdForPath`.
// Every step anchors to a real `data-testid` already present in the app (or a
// small set added specifically for onboarding — see the Landing.jsx section
// wrappers). Copy is written to explain the BENEFIT of each step, not just
// what it is, per the "guide users through what it can do for them" goal.
//
// Step shape:
//   target: CSS selector string (may contain a comma-separated OR list of
//           selectors — the first one found in the DOM wins), or `null` for
//           a centered welcome/summary card with no spotlight.
//   title, body: tooltip copy.
//   optional: if true, the engine gives up finding this target faster and
//             silently skips to the next step (used for state-dependent UI
//             that may not be on screen, e.g. "extend video" before a hook
//             video exists).
//   placement: preferred tooltip side ("bottom" | "top") — auto-flips if
//              there isn't room.

export const TOURS = {
  landing: {
    id: "landing",
    label: "Welcome tour",
    steps: [
      {
        target: null,
        title: "Welcome to HookForge \u{1F44B}",
        body:
          "This 30-second tour shows the current workflow — describe your app once, pick a goal and an opening, review the plan, and render a hook and a middle with you in it.",
      },
      {
        target: '[data-testid="landing-stats"]',
        title: "The core loop",
        body:
          "Approve your app profile, choose what the video is for, review the script and strategy, then render. Publishing stays manual.",
      },
      {
        target: '[data-testid="landing-how-it-works"]',
        title: "Five steps, one pipeline",
        body:
          "App Profile \u2192 Audience & goal \u2192 Template & photo \u2192 Review \u2192 Hook & middle. Each step automatically feeds the next \u2014 you never re-enter the same information twice.",
      },
      {
        target: '[data-testid="landing-features"]',
        title: "Learn from what works",
        body:
          "Record what each video actually did. What worked for this app shows up beside the next opening the studio recommends \u2014 you only pay for the video itself.",
      },
      {
        target: '[data-testid="landing-enter-app-button"]',
        title: "Ready when you are",
        body:
          "Hit Enter App to open the studio on the first step. This tour will pop back up on each new page \u2014 look for the help button if you want to replay it.",
      },
    ],
  },

  brand: {
    id: "brand",
    label: "Your Brand tour",
    steps: [
      {
        target: '[data-testid="brand-url-card"]',
        title: "Start with your website",
        body:
          "Paste your site URL \u2014 AI reads the page and extracts your brand name, niche, audience, and tone automatically, so you don't fill out a long form from scratch.",
      },
      {
        target: '[data-testid="brand-manual-card"]',
        title: "Refine anything",
        body:
          "Every field AI fills in is fully editable. Sharpen your ideal customer profile or differentiation for noticeably better template videos.",
      },
      {
        target: '[data-testid="save-brand-button"]',
        title: "Save once, reuse everywhere",
        body:
          "Once saved, this profile supports App Profiles and template videos \u2014 no need to re-describe your brand each time.",
      },
    ],
  },

  // Targets GenerationHistory, which is what /history serves.
  history: {
    id: "history",
    label: "History tour",
    steps: [
      {
        target: '[data-testid="history-list"]',
        title: "Every video you have made",
        body:
          "Each finished video, newest first, with the model it used, what it cost, and the claim check that ran at the time.",
      },
      {
        target: '[data-testid="generation-details-button"]',
        title: "Open the receipts",
        optional: true,
        body:
          "Details shows the exact prompt sent to the model and the claim check as it stood at generation time.",
      },
      {
        target: '[data-testid="record-results-button"]',
        title: "Tell it what worked",
        optional: true,
        body:
          "Record the view numbers after you post. This is the one thing that makes the next video for this app better — it is how the app learns which opening actually carried.",
      },
    ],
  },
};

/**
 * Resolve which tour (if any) applies to a given route pathname.
 */
export function getTourIdForPath(pathname) {
  if (pathname === "/") return null; // Landing page — no onboarding tour
  if (pathname.startsWith("/brand")) return "brand";
  if (pathname.startsWith("/history")) return "history";
  return null;
}
