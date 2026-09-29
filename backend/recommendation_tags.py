"""
Deterministic tag normalization for template recommendations.

Recommendations must be explainable and auditable, so audience and problem
matching is a fixed vocabulary, not an LLM call. Two axes are normalized:

- AUDIENCE: who the video speaks to. Curated templates describe funnel stage
  (cold_audience, power_users, ...); App Profiles and angles describe people
  (busy students, freelancers, ...). Both run through the same normalizer,
  and each angle kind maps to funnel stages with a documented table below,
  so the two axes can actually meet.
- PROBLEM: what hurts. Angle user_problem text and profile problems_solved
  normalize to problem tags; template side text (name, structures, slots)
  normalizes with the same vocabulary, so an overlap is a shared meaning,
  not a brittle full-string equality.

No performance claims live here: matches are structural (audience, problem,
feature), never "this template performs better".
"""

import json
import re

# ---------------------------------------------------------------------------
# Vocabularies. Needles are lowercase; a trailing "+" means prefix-match
# (procrastinat+ matches procrastination/procrastinating). Plain needles
# match on word boundaries so "mom" never fires inside "moment".
# ---------------------------------------------------------------------------

FUNNEL_TAGS = (
    "cold_audience",
    "targeted_audience",
    "existing_users",
    "power_users",
    "scrollers",
    "skeptical_viewers",
    "evaluating_viewers",
)

# Documented mapping: which funnel stage each angle kind naturally speaks to.
# Deterministic and structural - derived from what the angle SHOWS, not from
# any measured performance.
ANGLE_FUNNEL_TAGS = {
    "problem_solution": ("cold_audience", "scrollers"),
    "before_after": ("cold_audience", "targeted_audience"),
    "competitor_alternative": ("skeptical_viewers", "evaluating_viewers"),
    "feature_demonstration": ("targeted_audience", "evaluating_viewers"),
    "common_mistake": ("cold_audience", "scrollers"),
    "fast_tutorial": ("targeted_audience", "evaluating_viewers"),
    "unexpected_benefit": ("cold_audience", "targeted_audience"),
    "founder_story": ("cold_audience", "scrollers"),
    "daily_life_use_case": ("cold_audience", "scrollers"),
    "product_comparison": ("skeptical_viewers", "evaluating_viewers"),
    "objection_handling": ("skeptical_viewers", "targeted_audience"),
    "privacy_pricing_differentiation": ("skeptical_viewers", "targeted_audience"),
}

DEMOGRAPHIC_TAGS = {
    "students": ("student",),
    "professionals": ("professional", "office worker"),
    "parents": ("parent", "mom", "mum", "dad"),
    "founders": ("founder", "entrepreneur", "startup owner"),
    "freelancers": ("freelanc+",),
    "creators": ("creator", "influencer", "youtuber"),
    "developers": ("developer", "programmer", "engineer", "coder"),
    "gamers": ("gamer",),
    "fitness": ("fitness", "gym goer", "athlete", "runner", "workout"),
    "travelers": ("traveller", "traveler", "traveling", "nomad"),
    "teachers": ("teacher", "educator", "professor"),
    "teams": ("team", "coworker", "colleague"),
    "small_business": ("small business", "shop owner", "local business"),
    "beginners": ("beginner", "newcomer", "first time"),
    "remote_workers": ("remote worker", "work from home", "wfh"),
    "musicians": ("musician", "beatmaker"),
    "artists": ("artist", "illustrator", "photographer"),
    "marketers": ("marketer", "marketing"),
}

PROBLEM_TAGS = {
    "time_management": ("time", "hours", "schedule", "deadline", "busy"),
    "procrastination": ("procrastinat+", "putting off", "keep delaying"),
    "distraction": ("distract", "can't focus", "losing focus", "scattered"),
    "disorganization": ("organiz", "clutter", "messy", "chaos", "lose track", "untidy"),
    "money": ("cost", "costs", "expensive", "money", "budget", "overpay", "price", "pricing", "spend too much"),
    "stress": ("stress", "anxious", "anxiety", "overwhelm", "burnout"),
    "motivation": ("motivat", "can't start", "discipline"),
    "learning_curve": ("confus", "complicated", "hard to learn", "steep learning", "onboard", "complex"),
    "forgetting": ("forget", "remember", "miss deadlines"),
    "communication": ("email", "inbox", "messages", "replies", "notifications"),
    "content_creation": ("content", "posting", "video ideas", "what to post"),
    "health": ("health", "workout", "exercise", "diet", "nutrition"),
    "sleep": ("sleep", "insomnia", "bedtime"),
    "security": ("security", "password", "hacked", "breach"),
    "privacy": ("privacy", "tracking me", "my data"),
    "writing": ("writing", "blank page"),
    "storage": ("storage", "files everywhere"),
}

def _needles_match(needles, text):
    for needle in needles:
        if needle.endswith("+"):
            if re.search(r"\b" + re.escape(needle[:-1]), text):
                return True
        elif re.search(r"\b" + re.escape(needle) + r"(?:s|es|ed|d|ing)?\b", text):
            return True
    return False


def text_list(value):
    """Accept a JSON string, a list, or None; return a list of plain strings."""
    if not value:
        return []
    if isinstance(value, str):
        try:
            value = json.loads(value)
        except (json.JSONDecodeError, TypeError):
            return [value] if value.strip() else []
    if isinstance(value, dict):
        value = list(value.values())
    if not isinstance(value, (list, tuple)):
        value = [value]
    return [str(v).strip() for v in value if v is not None and str(v).strip()]


def category_key(text):
    """Normalize an app category so 'Health & Fitness' == 'health and fitness'."""
    key = re.sub(r"[^a-z0-9]+", " ", (text or "").lower()).strip()
    return re.sub(r"\s+", " ", key)


def audience_tags(*texts):
    """Canonical audience tags for one or more free-text audience strings."""
    found = set()
    for text in texts:
        if not text:
            continue
        lowered = text.lower()
        normalized = lowered.replace("_", " ")
        for tag in FUNNEL_TAGS:
            if normalized.strip() == tag.replace("_", " ") or tag in lowered:
                found.add(tag)
        for tag, needles in DEMOGRAPHIC_TAGS.items():
            if _needles_match(needles, lowered):
                found.add(tag)
    return sorted(found)


def problem_tags(*texts):
    """Canonical problem tags for one or more free-text problem strings."""
    found = set()
    for text in texts:
        if not text:
            continue
        lowered = text.lower()
        for tag, needles in PROBLEM_TAGS.items():
            if _needles_match(needles, lowered):
                found.add(tag)
    return sorted(found)


def angle_funnel_tags(kind):
    """Funnel-stage tags implied by a content angle kind."""
    return ANGLE_FUNNEL_TAGS.get((kind or "").strip(), ())
