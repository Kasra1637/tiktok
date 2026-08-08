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
          "This 30-second tour shows how to turn any viral TikTok hook into your own branded video \u2014 discover, analyze, swap your face in, and generate, all in one pipeline.",
      },
      {
        target: '[data-testid="landing-stats"]',
        title: "The core loop",
        body:
          "Discover a viral hook, swap in your face, and generate an AI video \u2014 powered by MiniMax H3 at 2K resolution, up to 15 seconds. Hooks are muted by default so you can add a trending sound on TikTok.",
      },
      {
        target: '[data-testid="landing-how-it-works"]',
        title: "Four steps, one pipeline",
        body:
          "Discover \u2192 Analyze & Save \u2192 Face Swap \u2192 Generate. Each step automatically feeds the next \u2014 you never re-enter the same information twice.",
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
          "We pulled 8 frames from the first 3 seconds of this video. Click any frame to choose it as the target scene for your face swap \u2014 the default is the AI-picked peak hook moment.",
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
          "Each card breaks down one mechanic \u2014 expression, gesture, pacing, text, or audio \u2014 so you know exactly what to preserve when you recreate it with your own face.",
      },
      {
        target: '[data-testid="face-swap-hook-button"]',
        title: "Put yourself in it",
        body:
          "Swap your face into this exact frame. Pose, lighting, outfit, and background all stay identical \u2014 only the identity changes.",
      },
      {
        target: '[data-testid="bookmark-hook-button"]',
        title: "Save it for later \u2014 free",
        body:
          "Like this hook? Bookmark it. Next time you reuse it \u2014 for a different client or brand \u2014 there's zero AI analysis cost, just the video generation.",
      },
    ],
  },

  faceswap: {
    id: "faceswap",
    label: "Face swap tour",
    steps: [
      {
        target: '[data-testid="face-swap-step-indicator"]',
        title: "Three quick steps",
        body:
          "Target scene \u2192 your face \u2192 generate. Your face photo is saved locally so you only ever need to upload it once.",
      },
      {
        target: '[data-testid="target-dropzone"], [data-testid="face-swap-step-indicator"]',
        title: "Your target scene",
        optional: true,
        body:
          "This is the pose, lighting, and background your face will be placed into \u2014 either chosen from a viral hook or uploaded directly.",
      },
      {
        target: '[data-testid="source-dropzone"]',
        title: "Add your face",
        optional: true,
        body:
          "Upload a clear, front-facing photo. Hit \u201cSave\u201d afterward so this app remembers it for every future swap.",
      },
      {
        target: '[data-testid="generate-swap-button"]',
        title: "Generate the swap",
        optional: true,
        body:
          "AI places your face into the exact scene \u2014 matching pose, outfit, lighting, and camera angle for a seamless result.",
      },
      {
        target: '[data-testid="bookmark-picker"]',
        title: "Reuse a saved hook \u2014 free",
        optional: true,
        body:
          "Bookmarked hooks appear in your history, filterable by category."
      },
      {
        target: '[data-testid="generate-hook-button"]',
        title: "Bring it to life",
        body:
          "MiniMax H3 turns your swapped image into a short video with camera motion \u2014 2K resolution, generated in a single pass. Muted by default, since most creators add a trending sound or text-to-speech in TikTok's own editor. Toggle audio on above if you'd rather have H3 generate a track.",
      },
      {
        target: '[data-testid="reroll-hook-button"], [data-testid="extend-video-button"]',
        title: "Re-roll or extend",
        optional: true,
        body:
          "Not quite right? Re-roll gives you another take with the exact same prompt \u2014 no extra analysis cost. Happy with it? Extend adds your brand message and a call-to-action.",
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
          "Every hook you save here keeps its full analysis, generated prompt, and a copy of the source clip \u2014 so reusing it later costs nothing but the video generation itself.",
      },
      {
        target: '[data-testid="bookmarks-savings-summary"]',
        title: "Track your savings",
        optional: true,
        body:
          "This tracks how many times you've reused a saved hook \u2014 each reuse is a fresh AI analysis and prompt rewrite you didn't have to pay for.",
      },
      {
        target: '[data-testid="bookmarks-category-filter"]',
        title: "Organize by category",
        optional: true,
        body:
          "Filter your saved hooks by type \u2014 intrigue, reveal, reaction, and more \u2014 to quickly find the right one for a new client or brand.",
      },
      {
        target: '[data-testid="view-analysis-button"]',
        title: "One click to reuse",
        body:
          "Hit \u201cUse This Hook\u201d to jump straight into Face Swap with this template pre-selected \u2014 no re-analysis needed, ever.",
      },
    ],
  },

  generate: {
    id: "generate",
    label: "Content Remixer tour",
    steps: [
      {
        target: '[data-testid="remix-chat-input"], [data-testid="remix-chat-empty-state"]',
        title: "Chat your way to a brief",
        body:
          "Describe your brand in plain language. AI checks how well the original hook's audience matches yours and asks a couple of quick follow-up questions.",
      },
      {
        target: '[data-testid="reference-images-row"]',
        title: "Your face-swapped reference",
        optional: true,
        body:
          "This is the image that becomes the first frame of your generated video \u2014 carried over automatically from Face Swap.",
      },
      {
        target: '[data-testid="brand-name-input"]',
        title: "Or fill in manually",
        optional: true,
        body:
          "Prefer forms over chat? Fill in your brand name, goal, and details directly \u2014 these stay in sync with the chat either way.",
      },
      {
        target: '[data-testid="remix-for-brand-button"], [data-testid="generate-prompt-button"]',
        title: "Generate your script",
        body:
          "AI writes a full, second-by-second video prompt that adapts the viral hook's proven mechanics to your specific brand and offer.",
      },
      {
        target: '[data-testid="full-prompt-textarea"]',
        title: "Edit before you generate",
        optional: true,
        body:
          "Tweak any part of the AI-written prompt \u2014 camera angle, pacing, brand narrative \u2014 before locking it in.",
      },
      {
        target: '[data-testid="generate-video-button"]',
        title: "Lock it in",
        body:
          "Save this as your video brief \u2014 the reference image, prompt, and target duration are bundled and ready for generation.",
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
          "Every field AI fills in is fully editable. Sharpen your ideal customer profile or differentiation for noticeably better remix scripts.",
      },
      {
        target: '[data-testid="save-brand-button"]',
        title: "Save once, reuse everywhere",
        body:
          "Once saved, this profile auto-fills the Content Remixer on every video you generate \u2014 no need to re-describe your brand each time.",
      },
    ],
  },

  history: {
    id: "history",
    label: "History tour",
    steps: [
      {
        target: '[data-testid="history-list"]',
        title: "Everything you've made",
        body:
          "Every hook you've analyzed, face-swapped, or turned into a video brief lives here \u2014 nothing is lost between sessions.",
      },
      {
        target: '[data-testid="history-customization-thumb"]',
        title: "Revisit a face swap",
        optional: true,
        body:
          "Click any thumbnail to see the full-resolution result and its underlying generation spec \u2014 handy for reusing a look later.",
      },
      {
        target: '[data-testid="history-video-job-item"]',
        title: "Review a video brief",
        optional: true,
        body:
          "See the exact prompt and brand details saved for this generation \u2014 copy it, tweak it, or use it as a starting point for the next one.",
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
  if (pathname.startsWith("/face-swap")) return "faceswap";
  if (pathname.startsWith("/bookmarks")) return "templates";
  if (pathname.startsWith("/generate-video/")) return "generate";
  if (pathname.startsWith("/brand")) return "brand";
  if (pathname.startsWith("/history")) return "history";
  return null;
}
