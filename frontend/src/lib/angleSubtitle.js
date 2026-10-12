/**
 * How an angle reads in the picker: one scannable line closed, its full set of
 * fields open.
 *
 * An angle carries several text fields (target_audience, user_problem,
 * hook_promise, app_feature, desired_emotion), and the field that says the
 * most useful thing differs by kind: a feature demonstration is best
 * summarized by the feature it shows, a before/after by the promise, a
 * problem/solution by the problem. `angleSubtitle` picks the kind's most
 * relevant field and falls back through the others, so a sparse angle still
 * gets a line and an angle with none of them simply has no subtitle — which is
 * what keeps a list of angles comparable at a glance. `angleDetails` then
 * shows a picked angle's own fields, unsummarized.
 *
 * `formatVerdicts` is the third job: the verdict tally the server attaches per
 * angle KIND. It is counts, never a rate or a score. One win is one verdict,
 * and presenting it as a percentage would dress a coin flip as a measurement —
 * the same rule that keeps `summarize_angle_feedback` a count list for the
 * generation prompt. Empty string when there is no evidence, so a new app's
 * picker looks exactly as it did before any of this existed.
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

/** The angle's fields in the order the generation prompt asks for them, each
 *  labelled in the prompt's own words — the founder reads the sentences the
 *  plan will be built from, not a paraphrase of them. */
const DETAIL_FIELDS = [
  ["Audience", "target_audience"],
  ["Problem", "user_problem"],
  ["First 3 seconds promise", "hook_promise"],
  ["Feature shown", "app_feature"],
  ["Emotion by the end", "desired_emotion"],
];

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

/**
 * Everything the angle carries, for the picked angle's own panel.
 *
 * The subtitle points at the one field that says most about this KIND of
 * angle, which is what makes the collapsed list scannable. This is the
 * opposite job: the same fields unsummarized, so an angle chosen from one line
 * is not finally read on the Review step.
 *
 * Only fields with text travel. A generated angle regularly has no promise or
 * feature recorded, and a labelled blank reads as a missing answer rather than
 * an absent one. `claims_to_respect` is a list of boundaries rather than one
 * more sentence about the angle, so it joins into a single "Bounded by" line
 * and is skipped entirely when there is nothing bounding the angle.
 */
export function angleDetails(angle) {
  if (!angle) return [];
  const rows = [];
  for (const [label, field] of DETAIL_FIELDS) {
    const value = sentenceCaseTrimmed(String(angle[field] || ""));
    if (value) rows.push({ label, value });
  }
  const claims = (Array.isArray(angle.claims_to_respect) ? angle.claims_to_respect : [])
    .map((claim) => sentenceCaseTrimmed(String(claim || "")))
    .filter(Boolean);
  if (claims.length) rows.push({ label: "Bounded by", value: claims.join("; ") });
  return rows;
}

/**
 * "3 wins · 1 flop" for an angle's own tally, or "" when there is none.
 *
 * Counts only, and deliberately not a percentage or a score: the tally is
 * keyed by angle KIND (verdicts attribute through the fixed vocabulary, so it
 * survives an angle regeneration), and with one or two verdicts behind it any
 * rate would read as precision the founder's own history does not have.
 *
 * Both halves are named only when non-zero, so "3 wins" is not padded into
 * "3 wins · 0 flops" — an empty half is not information.
 */
export function formatVerdicts(evidence) {
  const wins = Math.max(0, Number(evidence?.wins) || 0);
  const flops = Math.max(0, Number(evidence?.flops) || 0);
  if (!wins && !flops) return "";
  const parts = [];
  if (wins) parts.push(`${wins} win${wins === 1 ? "" : "s"}`);
  if (flops) parts.push(`${flops} flop${flops === 1 ? "" : "s"}`);
  return parts.join(" · ");
}
