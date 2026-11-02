"""Deterministic template fit policy, independent of HTTP, persistence and AI.

score_template_for_angle owns weighted reasons, limitations and feedback.
split_shared_notes shapes the visible comparison set in place (ADR 0074).
"""
from typing import Optional

import angle_scene
import feedback as feedback_mod
import recommendation_tags
import template_library


# Terminal punctuation for an objective outcome spliced into a reason.
#
# OBJECTIVE_OUTCOMES are complete sentences with no trailing period, because the
# goal picker shows them as a standalone line where a trailing dot would be
# noise. The scorer composes them INTO a sentence, so it has to close the one it
# opens -- hence this. It is not a bare f"{outcome}." because an outcome ending
# in "?" or "!" would then come out as "?." / "!.".
def _outcome_as_sentence(outcome: str) -> str:
    text = str(outcome or "").strip()
    if not text:
        return ""
    return text if text[-1] in ".!?" else text + "."


def score_template_for_angle(
    template: dict,
    profile: dict,
    angle: Optional[dict],
    objective: str,
    feedback_events=(),
    outcome_rows=(),
) -> dict:
    """
    Score one template against an App Profile + angle + objective.

    Deliberately transparent and deterministic rather than an LLM call: the
    founder sees WHY a template was picked, and a recommendation can be
    re-derived and audited. Scoring is a weighted sum of explicit signals;
    reasons are ranked by weight so the first one shown is the strongest
    factor. The founder-facing scale is 0–10 (the template step shows
    "Fit X/10"), so the sum is clamped into that range at the single return
    below — after feedback, which would otherwise push strong matches above
    10 or heavily rejected ones below 0. Clamping is monotonic, so the
    ranking the sort uses is unchanged.

    URL-analysis factors are real inputs, with the angle taking precedence
    and the profile as fallback: app category, target audience (normalized
    to tags, plus funnel stages implied by the angle kind), the core problem
    (normalized to problem tags), and the main feature. Matching is tag
    overlap via recommendation_tags, never brittle full-string equality.
    Reasons describe what the footage DOES for the viewer — where it leaves
    them — which is still a structural claim about the video, not a promise
    about what it will earn. No performance claims, ever.
    """
    score = 0.0
    weighted = []  # (weight, reason), sorted by weight at the end
    limitations = []
    matched = {"category": None, "audience_tags": [], "problem_tags": [], "feature_keyword": ""}

    def add(weight, reason):
        weighted.append((weight, reason))

    # Brand-tailored templates were generated from this exact profile, so
    # they start with a head start. The bonus is silent now: the tailored
    # set is already labelled "Tailored for this app" on the template step,
    # so a per-card bullet repeating it was noise, not evidence. Ranking is
    # unchanged — the +2.0 still applies, it just no longer narrates itself.
    if (template.get("brand_profile_id") or "") and template.get("brand_profile_id") == (profile.get("id") or ""):
        score += 2.0

    angle = angle or {}
    tpl_objective = (template.get("objective") or "").strip()
    tpl_categories = [
        recommendation_tags.category_key(c)
        for c in (template.get("app_categories") or [])
        if recommendation_tags.category_key(c)
    ]
    tpl_audience_tags = set(
        recommendation_tags.audience_tags(*[str(a) for a in (template.get("audiences") or [])])
    )
    required_assets = [str(a).lower() for a in (template.get("required_assets") or [])]

    if objective and tpl_objective:
        if tpl_objective == objective:
            score += 3.0
            # The objective name stays in the sentence: it is the goal the
            # founder picked, and what follows is what the footage does about
            # that goal. See OBJECTIVE_OUTCOMES.
            #
            # A full stop, not an em dash, between the two: those outcomes are
            # capitalized sentences in their own right (they are shown that way
            # on the goal picker), so splicing one in after a dash produced
            # "Built for 'create curiosity' — Leaves them wanting the answer."
            add(3.0, f"Built for '{objective.replace('_', ' ')}'. "
                     f"{_outcome_as_sentence(template_library.OBJECTIVE_OUTCOMES.get(objective)) or 'Serves the goal you picked.'}")
        else:
            score += 0.5
            add(
                0.5,
                f"Made for '{tpl_objective.replace('_', ' ')}'. "
                f"{_outcome_as_sentence(template_library.OBJECTIVE_OUTCOMES.get(tpl_objective)) or 'Serves that goal.'} "
                f"Close to your '{objective.replace('_', ' ')}' goal.",
            )

    profile_category = (profile.get("app_category") or profile.get("niche") or "").strip()
    if profile_category and tpl_categories:
        key = recommendation_tags.category_key(profile_category)
        hit = next((c for c in tpl_categories if c in key or key in c), None)
        if hit:
            score += 2.5
            add(2.5, f"Lands with {profile_category} viewers before the app is even named — "
                     f"framed for how they talk about the problem.")
            matched["category"] = hit
        else:
            limitations.append(
                f"Framed for {', '.join(tpl_categories)} rather than {profile_category} — "
                f"the opening will need rewording."
            )
    if profile_category and not tpl_categories:
        score += 1.0
        add(1.0, "Carries no category assumptions, so it fits this app without reframing.")

    # ---- Audience: people from the profile/angle, plus the funnel stage
    # the angle kind implies. Curated templates tag funnel stage; profiles
    # describe people; recommendation_tags normalizes both to one axis.
    audience_texts = [angle.get("target_audience") or profile.get("target_audience") or ""]
    audience_texts += recommendation_tags.text_list(profile.get("icp_segments"))
    app_audience_tags = set(recommendation_tags.audience_tags(*audience_texts))
    app_audience_tags |= set(recommendation_tags.angle_funnel_tags(angle.get("kind") or ""))
    if app_audience_tags and tpl_audience_tags:
        overlap = sorted(app_audience_tags & tpl_audience_tags)
        if overlap:
            score += 1.0
            add(1.0, f"Aimed at {', '.join(overlap)} — they're already in the situation this opens on.")
            matched["audience_tags"] = overlap
            if len(overlap) >= 2:
                score += 0.5
    elif app_audience_tags and not tpl_audience_tags:
        score += 0.5
        add(0.5, "Open to anyone, so it reaches viewers outside your usual audience too.")

    # ---- Problem: the core problem from the angle or the profile research.
    problem_text = (angle.get("user_problem") or "").strip()
    if not problem_text:
        problem_text = "; ".join(recommendation_tags.text_list(profile.get("problems_solved")))
    app_problem_tags = set(recommendation_tags.problem_tags(problem_text)) if problem_text else set()
    if app_problem_tags:
        # cta_pattern is gone and continuation_structure is only read as a
        # fallback for a row seeded before middle_structure existed. Matching
        # against a retired CTA string would let a template be recommended for
        # containing the words of a call to action it no longer has.
        template_blob = " ".join(
            [str(template.get("name") or ""), str(template.get("category") or ""),
             str(tpl_objective), str(template.get("opening_structure") or ""),
             str(template.get("middle_structure")
                 or template.get("continuation_structure") or "")]
            + [f"{k} {v}" for k, v in (template.get("content_slots") or {}).items()]
        )
        overlap = sorted(app_problem_tags & set(recommendation_tags.problem_tags(template_blob)))
        foreground = (template.get("category") or "") in (
            "pain-point-question", "contrarian", "before-after",
        ) or tpl_objective == "address_user_problem"
        if overlap:
            score += 1.0
            add(1.0, f"Names {', '.join(overlap)} in the first seconds, so the viewer "
                     f"recognises themselves before your app appears.")
            matched["problem_tags"] = overlap
            if len(overlap) >= 2:
                score += 0.5
        elif foreground:
            score += 0.5
            add(0.5, "Opens on the viewer's problem, which is what this angle leads with.")

    # ---- Angle-kind / structure affinity. The weights are unchanged; only
    # the sentences changed. Each one now leads with what the viewer gets
    # rather than the name of the structure that delivers it.
    angle_kind = (angle.get("kind") or "").strip()
    if angle_kind:
        demo_categories = {"demo", "tutorial", "reveal"}
        story_categories = {"story", "pov", "before-after"}
        if angle_kind in ("feature_demonstration", "fast_tutorial") and template.get("category") in demo_categories:
            score += 2.0
            add(2.0, "Opens where your feature lives, so the demo you attach answers a question the viewer is already holding.")
        elif angle_kind in ("founder_story", "daily_life_use_case") and template.get("category") in story_categories:
            score += 2.0
            add(2.0, "Someone on camera lives it rather than describing it — a story-led angle needs a person, not a pitch.")
        elif angle_kind in ("problem_solution", "common_mistake") and template.get("category") in (
            "pain-point-question", "contrarian", "listicle", "pattern-interrupt"
        ):
            score += 2.0
            add(2.0, "Your angle leads with the problem, and so does the first line of this.")
        elif angle_kind in ("competitor_alternative", "product_comparison") and template.get("category") == "social-proof":
            score += 2.0
            add(2.0, "Leaves the two options side by side on screen, which is what a side-by-side angle needs.")
        elif angle_kind in ("objection_handling", "privacy_pricing_differentiation") and template.get("category") in (
            "contrarian", "social-proof", "curiosity-gap"
        ):
            score += 1.5
            add(1.5, "Asks the doubt out loud and leaves it standing — your demo is what answers it.")
        else:
            score += 0.5

    # ---- Main feature: the angle's feature, or the top core feature from
    # the URL analysis when no angle is selected.
    main_feature = (angle.get("app_feature") or "").strip()
    if not main_feature:
        feats = recommendation_tags.text_list(profile.get("core_features"))
        main_feature = feats[0] if feats else ""
    if main_feature:
        feature_tokens = {t for t in main_feature.replace(",", " ").split() if len(t) > 3}
        slot_blob = " ".join(str(v) for v in (template.get("content_slots") or {}).values()).lower()
        name_blob = f"{template.get('name') or ''} {template.get('category') or ''}".lower()
        hit = next(
            (tok for tok in feature_tokens if tok.lower() in slot_blob or tok.lower() in name_blob),
            None,
        )
        if hit:
            score += 1.0
            # The match is still a token hit on the slot values — that is the
            # honest signal. What changed is the sentence: it names what the
            # viewer gets (the feature as the reason they stayed) instead of
            # naming the field that matched (the content slot).
            add(1.0, f"Puts '{hit}' at the centre of the piece — your main feature "
                     f"arrives as the reason they stayed, not as a bullet.")
            matched["feature_keyword"] = hit

    if angle.get("claims_to_respect"):
        limitations.append(
            "Bounded by: " + "; ".join(str(c) for c in angle["claims_to_respect"][:3])
        )

    if required_assets:
        limitations.append(
            "Needs " + ", ".join(a.replace("_", " ") for a in required_assets) + "."
        )
    if not (template.get("middle_structure") or template.get("continuation_structure")):
        limitations.append("No middle structure recorded; the studio will infer one.")
    if (template.get("review_status") or "approved") != "approved":
        limitations.append("Unpublished research draft - review before using.")

    # A template whose own staging contradicts where and when the angle opens
    # stays listed but ranks lower, with the reason first (ADR 0084).
    scene_fit = angle_scene.template_angle_fit(template, angle)
    if scene_fit["structure"]:
        score -= 3.0
        limitations.insert(0, scene_fit["structure"])

    # Strongest factor first. Stable sort keeps same-weight reasons in
    # insertion order, and feedback still lands at the very top below.
    weighted.sort(key=lambda item: -item[0])
    reasons = [reason for _, reason in weighted]

    feedback = feedback_mod.template_feedback_adjustment(
        feedback_events, template.get("id") or ""
    )
    if feedback["delta"]:
        score += feedback["delta"]
        if feedback["explicit_rejections"] or feedback["automatic_changes"]:
            rejections = feedback["explicit_rejections"] + feedback["automatic_changes"]
            limitations.insert(
                0,
                f"Rejected or replaced {rejections} time(s) for this app.",
            )
        if feedback["thumb_downs"]:
            limitations.insert(
                0,
                f"Rated a poor template {feedback['thumb_downs']} time(s) for this app.",
            )
        if feedback["thumb_ups"]:
            reasons.insert(
                0,
                f"Rated a good template {feedback['thumb_ups']} time(s) for this app.",
            )
        # Behavior beside the verdicts: moving forward with this template is
        # the strongest signal in the loop, so its line leads; dropping it
        # after picking it reads as a limitation; being shown and passed over
        # is only noted, not headlined.
        if feedback["adoptions"]:
            reasons.insert(
                0,
                f"Moved forward with this template {feedback['adoptions']} time(s) for this app.",
            )
        if feedback["abandonments"]:
            limitations.insert(
                0,
                f"Picked then dropped without rendering {feedback['abandonments']} time(s) for this app.",
            )
        if feedback["impressions"]:
            limitations.append(
                f"Shown but not picked {feedback['impressions']} time(s) for this app.",
            )

    # Recorded outcomes beside verdicts: posted clips and winner verdicts lift
    # a template within a small cap. They never bury a template — an unposted
    # template simply gets no boost — and views only nudge inside that budget.
    outcome = feedback_mod.template_outcome_adjustment(
        outcome_rows, template.get("id") or ""
    )
    if outcome["delta"]:
        score += outcome["delta"]
        if outcome["posted_clips"]:
            views = outcome["posted_views"]
            suffix = f", {views} views" if views else ""
            reasons.insert(
                0,
                f"Posted in {outcome['posted_clips']} clip(s){suffix} for this app.",
            )
        if outcome["wins"]:
            reasons.insert(
                0,
                f"Marked a winner {outcome['wins']} time(s) for this app.",
            )
    feedback["outcome"] = outcome
    retired = feedback_mod.is_template_retired(feedback, outcome)
    if retired:
        score -= 3.0
        limitations.insert(
            0,
            "Retired after repeated poor fit — deprioritized until a post proves otherwise.",
        )
    feedback["retired"] = retired

    # The 0–10 bound lives here, not in the caller: this is the single
    # return every recommendation flows through, so no consumer can ever
    # show a fit outside the scale the template step advertises.
    score = max(0.0, min(10.0, score))
    return {
        "score": round(score, 2),
        "reasons": reasons,
        "limitations": limitations,
        "feedback": feedback,
        "matched": matched,
        "retired": retired,
        "angle_scene": {
            "moment": scene_fit["moment"],
            "fits": not scene_fit["structure"],
            "example_conflicts": scene_fit["example_conflicts"],
        },
    }

def split_shared_notes(recs):
    """
    Hoist the fit notes every visible recommendation shares.

    The scorer reasons per factor (goal, category, angle kind, audience), so
    templates ranked for the same angle and goal earn identical bullets —
    showing those on every card turns evidence into wallpaper. Notes present
    on every card move to the section level once; each card keeps only what
    differentiates it. A single recommendation keeps everything: with nothing
    to compare against, hoisting would leave a bare card.

    Returns {"shared_reasons", "shared_limitations"} and strips the shared
    strings from each rec in place, preserving each list's own order.
    """
    shared = {"shared_reasons": [], "shared_limitations": []}
    if len(recs) < 2:
        return shared
    pairs = [
        ("why_it_fits", "shared_reasons"),
        ("limitations", "shared_limitations"),
    ]
    for rec_key, shared_key in pairs:
        first = list(recs[0].get(rec_key) or [])
        rest = [set(r.get(rec_key) or []) for r in recs[1:]]
        common = [note for note in first if all(note in other for other in rest)]
        if not common:
            continue
        shared[shared_key] = common
        common_set = set(common)
        for r in recs:
            r[rec_key] = [note for note in (r.get(rec_key) or []) if note not in common_set]
    return shared
