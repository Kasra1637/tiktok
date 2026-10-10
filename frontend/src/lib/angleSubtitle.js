/**
 * The one-line subtitle shown under an angle's label on its card.
 *
 * An angle carries several text fields (target_audience, user_problem,
 * hook_promise, app_feature, desired_emotion), and the field that says the
 * most useful thing differs by kind: a feature demonstration is best
 * summarized by the feature it shows, a before/after by the promise, a
 * problem/solution by the problem. The subtitle picks the kind's most
 * relevant field and falls back through the others, so a sparse angle still
 * gets a line and an angle with none of them simply has no subtitle.
 */
import { sentenceCaseTrimmed } from "./copyCase";

const PREFERRED_FIELD = {
  problem_solution: "user_problem",
  before_after: "hook_promise",
  competitor_alternative: "hook_promise",
  feature_demonstration: "app_feature",
  common_mistake: "user_problem",
  fast_tutorial: "app_feature",
  unexpected_benefit: "hook_promise",
  founder_story: "desired_emotion",
  daily_life_use_case: "target_audience",
  product_comparison: "hook_promise",
  objection_handling: "user_problem",
  privacy_pricing_differentiation: "app_feature",
};

const FALLBACK_FIELDS = ["hook_promise", "user_problem", "target_audience"];

export function angleSubtitle(angle) {
  if (!angle) return "";
  const preferred = PREFERRED_FIELD[angle.kind];
  const order = preferred ? [preferred, ...FALLBACK_FIELDS] : FALLBACK_FIELDS;
  for (const field of order) {
    const value = String(angle[field] || "").trim();
    if (value) return sentenceCaseTrimmed(value);
  }
  return "";
}
