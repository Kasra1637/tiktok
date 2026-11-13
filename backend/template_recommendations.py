"""Deterministic template fit policy, independent of HTTP, persistence and AI.

score_template_for_angle owns weighted reasons, limitations and verdict facts.
split_shared_notes shapes the visible comparison set in place (ADR 0074).
"""
from typing import Optional

import re

import angle_scene
import character_policy
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


# ---------------------------------------------------------------------------
# Relevance to the selected angle (ADR 0089)
# ---------------------------------------------------------------------------
# A tailored template is supposed to be THIS angle's problem turned into a
# shape. Generation is asked for that, and this is the check that proves it: a
# set generated for one problem has no business filling the picker for another,
# and a card about journaling-as-homework under a problem about failing to name
# a feeling is a wrong answer however well it scores on category and goal.
#
# Lexical, deliberately: the Problem and the First 3 Seconds Promise are the
# source of truth, so a template has to share their actual words. Word overlap
# is a floor, not a similarity score — it cannot certify a good template, only
# catch one that is about something else, which is the failure it exists for.
_STOPWORDS = frozenset("""
a about above after again against all almost alone along already also although
always am among an and another any anyone anything are around as at away back
be because been before being below beside between both but by can cannot could
did do does doing done down during each either else enough even ever every few
first for from further get gets getting go goes going got had has have having he
her here hers herself him himself his how however i if in into is it its itself
just keep keeps know last least less let like little long made make makes many
may me might mine more most much must my myself near need needs never new next
no nor not nothing now of off often on once one only onto or other others our
ours ourselves out over own past per put quite rather really said same say says
see seem seems seen several shall she should since so some something sometimes
still such take than that the their theirs them themselves then there these they
thing things think this those though through thus to too toward under until up
upon us use used using very via want wants was way we well were what whatever
when where whether which while who whom whose why will with within without would
yet you your yours yourself
""".split())

_TOPIC_WORD = re.compile(r"[A-Za-z][A-Za-z'-]*")

# The words every neutralized line already contains (ADR 0089). They name who
# is being described, never what the video is about, so they can never be
# evidence that two sentences are about the same problem.
_SUBJECT_WORDS = frozenset((
    "person", "people", "character", "characters", "viewer", "viewers",
    "someone", "anyone", "everyone",
))

# Enough shared words that a match cannot be coincidence for a longer problem;
# a very short problem has few words to share, so one is the honest floor.
MIN_RELEVANCE_HITS = 2
SMALL_ANCHOR_SET = 4


def _stem(word: str) -> str:
    """Crude suffix fold so "type", "types" and "typing" are one word.

    Not linguistics: the check only needs the same idea in two spellings to
    count once. Anything it gets wrong makes the check more forgiving, which is
    the safe direction for a gate that can drop a card.
    """
    text = re.sub(r"[^a-z0-9]", "", str(word or "").lower())
    if len(text) <= 3:
        return text
    if text.endswith("ing") and len(text) > 5:
        text = text[:-3]
    elif text.endswith("ed") and len(text) > 4:
        text = text[:-2]
    elif text.endswith("es") and len(text) > 4:
        text = text[:-2]
    elif text.endswith("s") and not text.endswith("ss") and len(text) > 3:
        text = text[:-1]
    if text.endswith("e") and len(text) > 3:
        text = text[:-1]
    return text


def content_stems(text) -> set:
    """The topic words in `text`, folded so inflections match each other."""
    stems = set()
    for raw in _TOPIC_WORD.findall(str(text or "")):
        word = raw.lower()
        if len(word) < 4 or word in _STOPWORDS or word in _SUBJECT_WORDS:
            continue
        stems.add(_stem(word))
    return stems


def problem_anchors(angle) -> set:
    """The words a template must share to be about this angle at all.

    The Problem and the First 3 Seconds Promise only. The audience and the
    feature describe who it is for and what answers it, and a template can
    match both while depicting an entirely different problem — which is the
    drift this check exists to catch.

    The text is neutralized first: templates are written without a gender or a
    role (ADR 0089), so "a woman on a back step" must not leave "woman" behind
    as a word no template could ever share.
    """
    angle = angle or {}
    return content_stems(
        character_policy.neutralize(
            f"{angle.get('user_problem') or ''} {angle.get('hook_promise') or ''}"
        )
    )


def template_copy(template) -> str:
    """Every word a template would put in front of a viewer, as one string."""
    template = template or {}
    parts = [
        template.get("name"),
        template.get("opening_structure"),
        template.get("middle_structure") or template.get("continuation_structure"),
        template.get("outcome"),
        template.get("example_preview"),
        template.get("visual_style"),
        template.get("camera_pacing"),
    ]
    parts += [
        f"{key} {value}"
        for key, value in (template.get("content_slots") or {}).items()
    ]
    return " ".join(str(part) for part in parts if str(part or "").strip())


def template_action_copy(template) -> str:
    """What the video actually opens on and develops: name, opening and middle.

    The outcome line, the content slots and the visual notes are left out on
    purpose. They describe the payoff and the look, and a generic one ("hears
    the exact moment a guessed word fails") would let a card about an entirely
    different problem pass a check it should fail. What the viewer sees happen
    is the evidence.
    """
    template = template or {}
    parts = [
        template.get("name"),
        template.get("opening_structure"),
        template.get("middle_structure") or template.get("continuation_structure"),
    ]
    return " ".join(str(part) for part in parts if str(part or "").strip())


def check_template_relevance(template: dict, angle: Optional[dict]) -> dict:
    """Whether `template` is about this angle's Problem and Promise, and why not.

    `passes` is True when the angle states no problem or promise at all — with
    nothing to be relevant to, the check never invents a constraint.
    """
    anchors = problem_anchors(angle)
    if not anchors:
        return {"passes": True, "hits": [], "anchor_count": 0, "reason": ""}
    hits = sorted(anchors & content_stems(template_action_copy(template)))
    need = 1 if len(anchors) <= SMALL_ANCHOR_SET else MIN_RELEVANCE_HITS
    passes = len(hits) >= need
    return {
        "passes": passes,
        "hits": hits,
        "anchor_count": len(anchors),
        "reason": "" if passes else (
            "Opens on a different problem: it shares none of this angle's "
            "problem or first-3-seconds wording."
        ),
    }


def filter_relevant_templates(templates, angle: Optional[dict]) -> list:
    """Only the templates grounded in this angle's Problem and Promise.

    Order is preserved: the caller's ranking is the ranking. A set that comes
    back short stays short — a picker showing three relevant shapes is honest,
    and padding it with off-topic ones is exactly the drift this prevents.
    """
    return [
        template for template in (templates or [])
        if check_template_relevance(template, angle)["passes"]
    ]



def score_template_for_angle(
    template: dict,
    profile: dict,
    angle: Optional[dict],
    objective: str,
    verdict_rows=(),
    hook_line=None,
    middle=None,
) -> dict:
    """
    Score one template against an App Profile + angle + objective.

    Deliberately transparent and deterministic rather than an LLM call: the
    founder sees WHY a template was picked, and a recommendation can be
    re-derived and audited. Scoring is a weighted sum of explicit signals;
    reasons are ranked by weight so the first one shown is the strongest
    factor. The founder-facing scale is 0–10 (the template step shows
    "Fit X/10"), so the sum is clamped into that range at the single return
    below — after the verdict adjustment, which would otherwise push strong
    matches above 10 or heavily flopped ones below 0. Clamping is monotonic,
    so the ranking the sort uses is unchanged.

    The one learning input is the founder's whole-video verdicts (ADR
    0127), attributed by the template frozen in each verdict bundle:
    `verdict_rows` are {"verdict", "bundle"} rows for this profile. The
    per-element record (thumbs, rejections, behavior, posted outcomes)
    used to adjust this score too; it stays as the founder's record but
    no longer ranks, for the same reason it no longer steers generation
    (ADR 0124) — a posted result cannot be attributed to one element.

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

    # The angle's "claims to respect" are NOT repeated as a template limit.
    # They bound the ANGLE, not this template, and the picked angle's own panel
    # states them as a "Bounded by" row directly above the template list
    # (frontend/src/lib/angleSubtitle.js:angleDetails). Carried here they
    # duplicated that row one surface down, in the model's own imperative voice
    # ("Do not claim clinical insight"), and since they were identical on every
    # card they also landed in the section's shared limits — where the founder
    # read a paragraph of writer instructions with nothing to act on. The
    # constraint still reaches the prompt from the angle row itself.

    if required_assets:
        limitations.append(
            "Needs " + ", ".join(a.replace("_", " ") for a in required_assets) + "."
        )
    if not (template.get("middle_structure") or template.get("continuation_structure")):
        limitations.append("No middle structure recorded; the studio will infer one.")
    if (template.get("review_status") or "approved") != "approved":
        limitations.append("Unpublished research draft - review before using.")

    # Is it about THIS problem at all (ADR 0089)? Tailored rows that fail are
    # dropped before they reach the picker; a curated row keeps its clean card
    # and is not penalized, because a curated template is a SHAPE the plan
    # fills with this angle's problem (see the plan's TEMPLATE rule) rather
    # than content about some other problem.
    #
    # Checked before the scene note below so that note still lands at the top
    # of the list: where the opening happens is the plainer fact of the two,
    # and ADR 0084 pins it there.
    relevance = check_template_relevance(template, angle)
    tailored_here = (template.get("brand_profile_id") or "") == (profile.get("id") or "")
    if not relevance["passes"] and tailored_here:
        score -= 2.0
        limitations.insert(0, relevance["reason"])

    # A template whose own staging contradicts where and when the angle opens
    # stays listed but ranks lower, with the reason first (ADR 0084). The
    # card's shape and development come from the approved hook line and
    # middle when a plan exists, so they never promise words the video never
    # speaks (ADR 0108).
    scene_fit = angle_scene.template_angle_fit(template, angle, hook_line=hook_line, middle=middle)
    if scene_fit["structure"]:
        score -= 3.0
        limitations.insert(0, scene_fit["structure"])

    # Strongest factor first. Stable sort keeps same-weight reasons in
    # insertion order, and the verdict line still lands at the very top below.
    weighted.sort(key=lambda item: -item[0])
    reasons = [reason for _, reason in weighted]

    # Whole-video verdicts are the one learning input (ADR 0127): the
    # founder's up/down calls on finished videos, attributed by the
    # template frozen in each bundle's opening visual. The per-element
    # record — thumbs, rejections, behavior counts, posted outcomes —
    # used to adjust this score through template_feedback_adjustment and
    # template_outcome_adjustment; those functions stay as the record,
    # but ranking stopped reading them, because neither a thumb on one
    # element nor a post's metrics can say the template is what made a
    # video work (ADR 0124). No verdicts yet means no adjustment at all:
    # the base fit order above is the order.
    verdicts = feedback_mod.template_verdict_facts(
        verdict_rows, template.get("id") or ""
    )
    if verdicts["delta"]:
        score += verdicts["delta"]
        if verdicts["worked"]:
            reasons.insert(
                0,
                f"Finished videos with this template worked {verdicts['worked']} time(s).",
            )
        if verdicts["didnt_work"]:
            limitations.insert(
                0,
                f"Finished videos with this template didn't work {verdicts['didnt_work']} time(s).",
            )
    retired = feedback_mod.is_template_retired_by_verdicts(verdicts)
    if retired:
        score -= 3.0
        limitations.insert(
            0,
            "Retired after repeated didn't-work verdicts and no worked ones — "
            "deprioritized until a finished video proves otherwise.",
        )

    # The 0–10 bound lives here, not in the caller: this is the single
    # return every recommendation flows through, so no consumer can ever
    # show a fit outside the scale the template step advertises.
    score = max(0.0, min(10.0, score))
    return {
        "score": round(score, 2),
        "reasons": reasons,
        "limitations": limitations,
        "verdicts": verdicts,
        "matched": matched,
        "retired": retired,
        "relevance": relevance,
        "angle_scene": {
            "moment": scene_fit["moment"],
            "shape": scene_fit["shape"],
            "staging": scene_fit["staging"],
            "development": scene_fit["development"],
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


def _structure_text(value) -> str:
    """Normalized wording for structure comparison: case and punctuation off."""
    return " ".join(re.findall(r"\w+", str(value or "").casefold()))


def template_structure_key(template: dict) -> tuple:
    """What a template IS, structurally — everything except its identity.

    The shape a founder actually picks between: the opening and middle
    segment layout (structure prose plus the hook split), the camera
    setup, the assets a shoot needs, and the content slots the plan must
    fill. Name, outcome, objective, category and audiences are identity
    and fit, not structure — two templates equal on this key differ only
    in how they are labelled and aimed, never in what filming one makes.
    """
    template = template or {}
    slots = template.get("content_slots")
    slot_keys = (
        tuple(sorted(str(k).strip().lower() for k in slots.keys()))
        if isinstance(slots, dict) else ()
    )
    try:
        hook_seconds = int(template.get("hook_seconds") or 0)
    except (TypeError, ValueError):
        hook_seconds = 0
    return (
        _structure_text(template.get("opening_structure")),
        _structure_text(
            template.get("middle_structure")
            or template.get("continuation_structure")
        ),
        hook_seconds,
        _structure_text(template.get("camera_pacing")),
        tuple(sorted(
            str(a).strip().lower()
            for a in (template.get("required_assets") or [])
        )),
        slot_keys,
    )


def same_structure_template_pairs(templates) -> list:
    """Pairs of templates that are one structure under two names (ADR 0127).

    The template-step analogue of the same-moment angle check: equality
    on the structure key, nothing softer — a shared opening with a
    different middle is a different template, and a near miss here would
    hide a real choice. Returned as (later id, earlier id) pairs, the
    convention the angle and goal pair checks use. Deterministic by
    construction: any flag reproduces from the two rows alone.
    """
    rows = list(templates or [])
    keys = [template_structure_key(row) for row in rows]
    return [
        (str(rows[j].get("id") or ""), str(rows[i].get("id") or ""))
        for j in range(len(rows)) for i in range(j)
        if keys[j] == keys[i]
    ]


def diversify_template_recommendations(scored: list, want: int) -> list:
    """Choose the presented set: rank order, structurally distinct first.

    `scored` is the caller's rank-ordered list (retired last, then score,
    then name — the order the picker has always used). The pool rule is
    unchanged (ADR 0096): non-retired entries while at least `want`
    exist, otherwise the whole list. Within the pool, a template whose
    structure an earlier pick already presented is deferred behind
    every structurally distinct candidate; deferred duplicates then
    backfill in rank order, so the presented set never shrinks below
    the count the picker shows today — it only stops spending two of
    its three cards on the same shape under two names.
    """
    rows = list(scored or [])
    active = [r for r in rows if not r.get("retired")]
    pool = active if len(active) >= want else rows
    picked, deferred, seen = [], [], set()
    for rec in pool:
        key = template_structure_key(rec.get("template") or {})
        if key in seen:
            deferred.append(rec)
        else:
            seen.add(key)
            picked.append(rec)
    return (picked + deferred)[:want]
