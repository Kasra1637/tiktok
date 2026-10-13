import {
  Lightbulb,
  ArrowRightLeft,
  Scale,
  MousePointerClick,
  TriangleAlert,
  Zap,
  Gift,
  Mic,
  Coffee,
  Columns2,
  ShieldCheck,
  Lock,
} from "lucide-react";

/**
 * One glyph per content-angle kind for the audience-angle rows: a muted
 * 16px icon ahead of the uppercase title, the same bar chrome the settings
 * accordion it was taken from uses. Unknown or retired kinds resolve to no
 * icon rather than a crash — the row renders exactly as it did before icons
 * existed.
 */
export const ANGLE_KIND_ICONS = {
  problem_solution: Lightbulb,
  before_after: ArrowRightLeft,
  competitor_alternative: Scale,
  feature_demonstration: MousePointerClick,
  common_mistake: TriangleAlert,
  fast_tutorial: Zap,
  unexpected_benefit: Gift,
  founder_story: Mic,
  daily_life_use_case: Coffee,
  product_comparison: Columns2,
  objection_handling: ShieldCheck,
  privacy_pricing_differentiation: Lock,
};

export function angleKindIcon(kind) {
  return ANGLE_KIND_ICONS[kind] || null;
}
