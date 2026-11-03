"""Content-angle normalization, source grounding and lexical diversity policy.

No model calls, persistence, or HTTP state: angles, plan briefs and strategy
briefs share these rules. Correction requests remain owned by ai_service.
"""
import re

import character_policy
from template_library import normalize_angle_kind


def _fact_key(value) -> str:
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def angle_grounding(profile: dict, angle: dict) -> dict:
    """Resolve a recorded feature/outcome pair, never an invented promise.

    Exact normalized source matching is intentionally conservative. Old/manual
    angles can paraphrase a feature: their prose remains in the brief but is
    not certified as a source link. Missing profile facts invent no constraint.
    """
    features = profile.get("core_features") or []
    if isinstance(features, str):
        features = [features]
    selected = next((str(f).strip() for f in features
                     if _fact_key(f) == _fact_key(angle.get("app_feature"))), "")
    if not selected:
        return {}
    linked = [str(item.get("outcome") or "").strip()
              for item in profile.get("outcome_statements") or []
              if isinstance(item, dict) and _fact_key(item.get("from_feature")) == _fact_key(selected)
              and str(item.get("outcome") or "").strip()]
    outcomes = linked or profile.get("desired_outcomes") or []
    if isinstance(outcomes, str):
        outcomes = [outcomes]
    outcomes = [str(value).strip() for value in outcomes if str(value).strip()]
    chosen = next((o for o in outcomes if _fact_key(o) == _fact_key(angle.get("viewer_outcome"))), "")
    result = {"feature": selected}
    if outcomes:
        result["outcome"] = chosen or outcomes[0]
    return result


def duplicate_angle_pairs(angles: list) -> list:
    """Conservative lexical overlap, not a claim of semantic similarity.

    Short fields only match exactly. Longer fields need >=80% shared word
    trigrams on BOTH the problem and promise; different arguments may use the
    same feature, outcome, or kind without being duplicates.
    """
    def similar(left, right):
        a, b = _fact_key(left).split(), _fact_key(right).split()
        if not a or not b:
            return False
        if a == b:
            return True
        if min(len(a), len(b)) < 6:
            return False
        aa = {tuple(a[i:i + 3]) for i in range(len(a) - 2)}
        bb = {tuple(b[i:i + 3]) for i in range(len(b) - 2)}
        return len(aa & bb) / max(len(aa), len(bb)) >= 0.8
    return [(i + 1, j + 1) for i, a in enumerate(angles) for j, b in enumerate(angles[:i])
            if all(similar(a.get(field), b.get(field)) for field in ("user_problem", "hook_promise"))]


def normalize_content_angles(parsed, max_angles: int, profile: dict) -> list:
    if isinstance(parsed, dict):
        parsed = parsed.get("angles") or parsed.get("content_angles") or []
    if not isinstance(parsed, list):
        raise RuntimeError("Content angles response was not a list.")
    angles = []
    for item in parsed:
        if not isinstance(item, dict):
            continue
        normalized = {"kind": normalize_angle_kind(item.get("kind")), "claims_to_respect": []}
        for field, limit in (("label", 120), ("target_audience", 400), ("user_problem", 600),
                             ("hook_promise", 300), ("app_feature", 300),
                             ("desired_emotion", 200), ("viewer_outcome", 300)):
            # Identity-neutral (ADR 0089): the founder's uploaded photo decides
            # who is on screen, so no angle field may name a gender, a role or a
            # pronoun. app_feature is the app's own feature name — product text,
            # not a description of a person — so it is left exactly as written.
            value = str(item.get(field) or "").strip()
            if field != "app_feature":
                value = character_policy.neutralize(value)
            normalized[field] = value[:limit]
        raw_claims = item.get("claims_to_respect")
        if isinstance(raw_claims, str):
            raw_claims = [raw_claims]
        if isinstance(raw_claims, list):
            normalized["claims_to_respect"] = [str(c).strip()[:200] for c in raw_claims if str(c).strip()][:6]
        if not normalized["target_audience"] or not normalized["user_problem"]:
            continue
        source = angle_grounding(profile, normalized)
        if source:
            normalized["app_feature"] = source["feature"]
            if source.get("outcome"):
                normalized["viewer_outcome"] = source["outcome"][:300]
        angles.append(normalized)
        if len(angles) >= max_angles:
            break
    if not angles:
        raise RuntimeError("Content angles response contained no usable angles.")
    return angles
