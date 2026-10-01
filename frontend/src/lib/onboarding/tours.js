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
          "This 30-second tour shows the internal template workflow — discover reusable hook mechanics, analyze them, save them as research, then generate template-based app videos.",
      },
      {
        target: '[data-testid="landing-stats"]',
        title: "The core loop",
        body:
          "Discover a hook mechanic, analyze and bookmark it as research, then use the creation studio to generate a template-based video. Publishing stays manual.",
      },
      {
        target: '[data-testid="landing-how-it-works"]',
        title: "Four steps, one pipeline",
        body:
          "Discover \u2192 Analyze & Save \u2192 Template Studio \u2192 Generate. Each step automatically feeds the next \u2014 you never re-enter the same information twice.",
      },
      {
        target: '[data-testid="landing-features"]',
        title: "Save what works, for free",
        body:
          "Found a hook that converts? Bookmark it. Bookmarked hooks can be found quickly in your history by category \u2014 you only pay for the video itself.",
      },
      {
        target: '[data-testid="landing-enter-app-button"]',
        title: "Ready when you are",
        body:
          "Hit Enter App to start discovering trending hooks in your niche. This tour will pop back up on each new page \u2014 look for the help button if you want to replay it.",
      },
    ],
  },

  discover: {
    id: "discover",
    label: "Discover tour",
    steps: [
      {
        target: '[data-testid="niche-selector-tabs"]',
        title: "Pick a niche",
        body:
          "Choose the niche closest to your brand \u2014 fitness, beauty, tech, and more. Selecting a niche just sets a filter \u2014 it never fetches videos by itself.",
      },
      {
        target: '[data-testid="mode-toggle"]',
        title: "Trending vs. Curated",
        body:
          "Trending pulls fresh hashtag data ranked by a live virality score. Curated shows hand-picked top creators. Mixed blends both. Switching modes is also free \u2014 no request fires until you search.",
      },
      {
        target: '[data-testid="search-input"]',
        title: "Or search directly",
        optional: true,
        body:
          "Already have a keyword or hashtag in mind? Type it here instead of browsing by niche \u2014 useful when you're chasing a specific trend.",
      },
      {
        target: '[data-testid="search-button"]',
        title: "Click Search to load videos",
        body:
          "Nothing loads until you click this \u2014 whether you picked a niche or typed a keyword. That keeps every video fetch intentional, so you're never surprised by an unexpected search.",
      },
      {
        target: '[data-testid="toggle-filters"]',
        title: "Narrow it down",
        optional: true,
        body:
          "Filter by view count, duration, recency, or sort order to zero in on the hooks most worth analyzing \u2014 less scrolling, more signal.",
      },
      {
        target: '[data-testid="video-feed-grid"]',
        title: "Found one? Analyze it",
        optional: true,
        body:
          "Click \u201cAnalyze Hook\u201d on any video card. AI breaks down exactly what makes the first 2\u20133 seconds work \u2014 expressions, gestures, pacing, and more \u2014 so you know what to replicate.",
      },
    ],
  },

  analysis: {
    id: "analysis",
    label: "Hook analysis tour",
    steps: [
      {
        target: '[data-testid^="filmstrip-frame-button-"]',
        title: "The extracted frames",
        body:
          "We pulled 8 frames from the first 3 seconds of this video. Review the peak hook moment and bookmark the reusable mechanic for template research.",
      },
      {
        target: '[data-testid="effectiveness-score-badge"]',
        title: "Effectiveness score",
        optional: true,
        body:
          "AI scores this hook 1\u201310 on how likely it is to stop the scroll, based on the same signals a viewer reacts to in that first instant.",
      },
      {
        target: '[data-testid="hook-section-facial_expressions"], [data-testid="hook-section-body_language_gestures"]',
        title: "What makes it work",
        body:
          "Each card breaks down one mechanic \u2014 expression, gesture, pacing, text, or audio \u2014 so you know exactly what reusable structure to save for template research.",
      },
      {
        target: '[data-testid="bookmark-hook-button"]',
        title: "Save it for later \u2014 free",
        body:
          "Like this hook? Bookmark it. Next time you reuse it \u2014 for a different client or brand \u2014 there's zero AI analysis cost, just the video generation.",
      },
    ],
  },

  bookmarks: {
    id: "bookmarks",
    label: "Bookmarks tour",
    steps: [
      {
        target: null,
        title: "Your hook library",
        body:
          "Every hook you save here keeps its full analysis and reusable mechanic for template research.",
      },
      {
        // These three were `bookmarks-savings-summary`,
        // `bookmarks-category-filter` and `view-analysis-button`. None of
        // those exist: HookTemplates.jsx names them templates-savings-summary
        // and templates-category-filter, and there is no view-analysis-button
        // on the page at all. TourOverlay advances silently past an unresolved
        // target, so every one of these steps was being skipped without a
        // trace, and the tour still counted as shown.
        target: '[data-testid="templates-savings-summary"]',
        title: "Track your savings",
        optional: true,
        body:
          "This tracks how many times you've reused a saved analysis \u2014 each reuse avoids paying for another fresh AI analysis.",
      },
      {
        target: '[data-testid="templates-category-filter"]',
        title: "Organize by category",
        optional: true,
        body:
          "Filter your saved hooks by type \u2014 intrigue, reveal, reaction, and more \u2014 to quickly find the right one for a new client or brand.",
      },
      {
        target: '[data-testid="use-template-button"]',
        title: "One click to research",
        body:
          "Open the saved analysis whenever you need the reusable mechanic \u2014 no re-analysis needed, ever.",
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

  // Targets GenerationHistory, which is what /history actually serves.
  // These three used to point at History.jsx's testids, and that page now
  // lives at /legacy-history -- a route getTourIdForPath maps to null. So the
  // tour was auto-launching against a page that had none of its targets, and
  // TourOverlay silently advances past an unresolved target, so nothing failed
  // and nothing showed. The first-timer was told this page was about
  // "research and older records", then the tour marked itself seen forever.
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
  if (pathname.startsWith("/discover")) return "discover";
  if (pathname.startsWith("/analysis/")) return "analysis";
  // "templates" was never a key in TOURS, so OnboardingProvider.startTour
  // bailed on it and /bookmarks got no tour at all — while markTourSeen had
  // already fired, so it would never be offered again. The key is "bookmarks".
  if (pathname.startsWith("/bookmarks")) return "bookmarks";
  if (pathname.startsWith("/brand")) return "brand";
  if (pathname.startsWith("/history")) return "history";
  return null;
}
