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

export const categoryLabel = (key) =>
  HOOK_TEMPLATE_CATEGORIES.find((c) => c.key === key)?.label || "Other";
