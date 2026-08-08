// Hook template categories. Must stay in sync with HOOK_TEMPLATE_CATEGORIES
// in backend/server.py — the backend normalizes any unknown value to "other".
export const HOOK_TEMPLATE_CATEGORIES = [
  { key: "intrigue", label: "Intrigue", description: "Curiosity-driven openers that make viewers stay to find out more — \"wait, what?\" moments." },
  { key: "reveal", label: "Reveal", description: "Before/after, transformation reveals, or \"watch what happens next\" style hooks." },
  { key: "reaction", label: "Reaction", description: "Reacting to something — a shocked face, a response to a trend or comment." },
  { key: "tutorial", label: "Tutorial", description: "\"Here's how to...\" — educational or how-to openers that promise value." },
  { key: "lifestyle", label: "Lifestyle", description: "Day-in-my-life, aesthetic, or aspirational content that draws people in." },
  { key: "transformation", label: "Transformation", description: "Glow-ups, makeovers, progress clips — showing dramatic change." },
  { key: "other", label: "Other", description: "Anything that doesn't fit the categories above." },
];

export const categoryLabel = (key) =>
  HOOK_TEMPLATE_CATEGORIES.find((c) => c.key === key)?.label || "Other";
