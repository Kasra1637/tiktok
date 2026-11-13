"""Content-angle normalization, source grounding and lexical diversity policy.

No model calls, persistence, or HTTP state: angles, plan briefs and strategy
briefs share these rules. Correction requests remain owned by ai_service.
"""
import re

import character_policy
import final_beat
from template_library import normalize_angle_kind


def _fact_key(value) -> str:
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def _token_set(value) -> frozenset:
    return frozenset(_fact_key(value).split())


def _near_feature_match(angle_tokens: frozenset, feature_tokens: frozenset) -> bool:
    """Tier-2 near match on word tokens: containment either way, or Jaccard >= 0.8."""
    if not angle_tokens or not feature_tokens:
        return False
    if angle_tokens <= feature_tokens or feature_tokens <= angle_tokens:
        return True
    return len(angle_tokens & feature_tokens) / len(angle_tokens | feature_tokens) >= 0.8


def _select_feature(features: list, feature_text) -> str:
    """Resolve a feature text to one recorded profile feature, or "".

    Tier 1 is the historical rule — exact normalized-wording equality,
    first match — and it always wins, so a tier-2 candidate can never
    beat another feature's exact match. Tier 2 accepts a near match
    (see _near_feature_match) only when exactly one profile feature
    qualifies; two qualifying features are ambiguity, not a link, and
    identical recorded features count once. No qualifying feature
    resolves to "".
    """
    selected = next((str(f).strip() for f in features
                     if _fact_key(f) == _fact_key(feature_text)), "")
    if selected:
        return selected
    tokens = _token_set(feature_text)
    qualifying, seen = [], set()
    for f in features:
        key = _fact_key(f)
        if key in seen:
            continue
        seen.add(key)
        if _near_feature_match(tokens, _token_set(f)):
            qualifying.append(str(f).strip())
    return qualifying[0] if len(qualifying) == 1 else ""


def angle_grounding(profile: dict, angle: dict) -> dict:
    """Resolve a recorded feature/outcome pair, never an invented promise.

    Two tiers, both conservative, because the certified feature replaces
    the angle's own app_feature text in normalize_content_angles and the
    pair feeds the plan and strategy briefs as verified material — a
    wrong link would propagate as fact:

    - Tier 1: exact normalized-wording equality with a profile
      core_feature (the historical rule; it always wins).
    - Tier 2: a near match on word tokens — one token set fully
      contained in the other, or token Jaccard >= 0.8 — accepted ONLY
      when exactly one profile feature qualifies. Two qualifying
      features means no link, and a tier-2 candidate never beats
      another feature's exact match.

    Each outcome statement's from_feature is resolved through the same
    two tiers, so an outcome links only to the feature it names, exact
    or uniquely near. Old/manual angles can still paraphrase beyond
    both tiers: their prose remains in the brief but is not certified
    as a source link. Missing profile facts invent no constraint.
    """
    features = profile.get("core_features") or []
    if isinstance(features, str):
        features = [features]
    selected = _select_feature(features, angle.get("app_feature"))
    if not selected:
        return {}
    linked = [str(item.get("outcome") or "").strip()
              for item in profile.get("outcome_statements") or []
              if isinstance(item, dict)
              and _select_feature(features, item.get("from_feature")) == selected
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


def same_moment_angle_pairs(angles: list) -> list:
    """Same moment in different words: token-set overlap, not wording.

    duplicate_angle_pairs compares word trigrams, so a pair retelling
    the same moment with fresh wording passes it — its own docstring
    says it is not a claim of semantic similarity. This check compares
    the token SETS of the same two fields instead: a pair is the same
    moment when BOTH user_problem and hook_promise reach >= 0.6 Jaccard
    similarity on _fact_key tokens. The bar sits below the lexical
    check's 0.8 trigram bar because token sets ignore word order and
    repetition: a retold moment scores high here while its trigrams
    diverge, and requiring both fields keeps a shared topic with a
    different problem (or the reverse) from flagging.

    Deterministic and explainable by construction: this module makes
    no model calls, so "same moment" can only ever mean this token
    rule — a reader can reproduce any flag from the two texts alone.
    """
    def same_moment(left, right):
        a, b = _token_set(left), _token_set(right)
        if not a or not b:
            return False
        return len(a & b) / len(a | b) >= 0.6
    return [(i + 1, j + 1) for i, a in enumerate(angles) for j, b in enumerate(angles[:i])
            if all(same_moment(a.get(field), b.get(field)) for field in ("user_problem", "hook_promise"))]


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
            # A generated clip never shows app content in any setup, so a
            # screen-interaction clause ("scrolls a weekly chart") is not
            # a filmable opening moment. Strip it here so it is never
            # stored; emptying the promise is left for the fallback path.
            # The same holds for a phone in hand ("with a phone in one
            # hand"): in a selfie the phone IS the camera (ADR 0097), and
            # the promise is stored before the setup is picked, so the
            # stored moment must be the filmable one both setups share.
            if field == "hook_promise" and value:
                kept, removed = final_beat.split_screen_clauses(value)
                if removed and kept:
                    value = kept
                value = final_beat.strip_phone_phrases(value)
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
