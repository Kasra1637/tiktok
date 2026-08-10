// Hook template categories. Must stay in sync with HOOK_TEMPLATE_CATEGORIES
// in backend/server.py — the backend normalizes any unknown value to "other".
export const HOOK_TEMPLATE_CATEGORIES = [
  { key: "curiosity-gap", label: "Curiosity Gap", description: "Irresistible 'wait, what?' — show something partially, make them NEED to stay." },
  { key: "pattern-interrupt", label: "Pattern Interrupt", description: "Break passive scrolling — unexpected movement or visual that jolts the brain." },
  { key: "reveal", label: "Reveal / Transformation", description: "Dramatic before/after snap — start hidden or plain, instantly show the payoff." },
  { key: "reaction", label: "Reaction", description: "Exaggerated emotional response — shocked face, jaw drop, 'what did I just see?'" },
  { key: "authority", label: "Authority", description: "Confident expert energy — commanding eye contact, 'listen to me right now.'" },
  { key: "confrontation", label: "Confrontation", description: "Challenge the viewer — 'you're doing it wrong' energy, pointed finger, tough love." },
  { key: "other", label: "Other", description: "Anything that doesn't fit the categories above." },
];

const ANALYSIS_TEXT_FIELDS = [
  "hook_summary",
  "facial_expressions",
  "body_language_gestures",
  "pacing_cuts",
  "text_overlays_timing",
  "audio_cues_inferred",
  "replicable_mechanics",
];

const CATEGORY_SIGNALS = {
  "curiosity-gap": [
    ["curiosity gap", 5], ["wait, what", 4], ["wait what", 4], ["secret", 3], ["mystery", 3],
    ["mysterious", 3], ["cliffhanger", 3], ["unresolved", 3], ["withhold", 3], ["tease", 2],
    ["keep watching", 2], ["you won't believe", 3],
  ],
  "pattern-interrupt": [
    ["pattern interrupt", 5], ["scroll-stopping", 4], ["scroll stopping", 4], ["stop the scroll", 4],
    ["jarring", 3], ["unexpected", 3], ["sudden", 2], ["abrupt", 2], ["visual transition", 2],
    ["jump cut", 2], ["contradictory", 2], ["disrupt", 2],
  ],
  reveal: [
    ["before and after", 5], ["before/after", 5], ["transformation", 4], ["transform", 2],
    ["reveal", 3], ["unveil", 3], ["hidden", 2], ["obscured", 2], ["concealed", 2],
    ["payoff", 3], ["glow-up", 4], ["makeover", 4], ["final result", 3],
  ],
  reaction: [
    ["reaction", 4], ["shocked", 4], ["shock", 3], ["gasp", 4], ["jaw drop", 4],
    ["wide eyes", 4], ["wide-eyed", 4], ["double take", 4], ["stunned", 3], ["surprised", 3],
    ["disbelief", 3], ["emotional response", 3],
  ],
  authority: [
    ["authority", 4], ["expert", 4], ["professional", 3], ["tutorial", 3], ["step-by-step", 3],
    ["how to", 2], ["guide", 2], ["tips", 2], ["advice", 2], ["teach", 2], ["instruct", 3],
  ],
  confrontation: [
    ["confront", 4], ["challenge", 3], ["calling out", 4], ["call out", 3],
    ["you're doing it wrong", 5], ["you are doing it wrong", 5], ["stop doing", 4],
    ["hard truth", 4], ["tough love", 3], ["mistake", 2], ["wrong", 1],
  ],
};

/**
 * Classify an existing hook analysis into a bookmark category without another
 * AI request. The first highest score wins, so ties are deterministic and the
 * category chips remain the user's final choice.
 */
export function inferHookTemplateCategory(analysis) {
  const analysisText = ANALYSIS_TEXT_FIELDS
    .flatMap((field) => {
      const value = analysis?.[field];
      return Array.isArray(value) ? value : [value];
    })
    .filter((value) => typeof value === "string")
    .join(" ")
    .toLowerCase();

  let bestCategory = "other";
  let bestScore = 0;

  for (const category of HOOK_TEMPLATE_CATEGORIES) {
    const score = (CATEGORY_SIGNALS[category.key] || []).reduce(
      (total, [signal, weight]) => total + (analysisText.includes(signal) ? weight : 0),
      0,
    );

    if (score > bestScore) {
      bestCategory = category.key;
      bestScore = score;
    }
  }

  return bestCategory;
}

export const categoryLabel = (key) =>
  HOOK_TEMPLATE_CATEGORIES.find((c) => c.key === key)?.label || "Other";
