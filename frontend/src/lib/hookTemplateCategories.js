// Hook template categories. Must stay in sync with HOOK_TEMPLATE_CATEGORIES
// in backend/server.py — the backend normalizes any unknown value to "other".
export const HOOK_TEMPLATE_CATEGORIES = [
  { key: "intrigue", label: "Intrigue" },
  { key: "reveal", label: "Reveal" },
  { key: "reaction", label: "Reaction" },
  { key: "tutorial", label: "Tutorial" },
  { key: "lifestyle", label: "Lifestyle" },
  { key: "transformation", label: "Transformation" },
  { key: "other", label: "Other" },
];

export const categoryLabel = (key) =>
  HOOK_TEMPLATE_CATEGORIES.find((c) => c.key === key)?.label || "Other";
