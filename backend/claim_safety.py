"""
Deterministic claim-safety checking for generated scripts.

Why this is separate from the AI layer: a model asked to police its own
output is not a safety net. It is asked to produce a plan, then this module
independently reads the resulting text and decides whether a promo would
break the rules. The model's self-declared `claims_used` is treated as an
unverified hint and reconciled against what actually appears in the text.

Everything here is pure string logic — no network, no model calls — so it is
unit-testable and cannot be talked out of a verdict by prompt drift.
"""
import re
from typing import Iterable, Optional

# ---------------------------------------------------------------------------
# Risk vocabularies
# ---------------------------------------------------------------------------

# Outcomes that no app promo may promise. Matched as phrases so "guaranteed
# results" is caught without flagging "guarantee" inside unrelated prose.
GUARANTEE_PATTERNS = [
    r"\bguarantee[ds]?\b",
    r"\b100%\s+(?:effective|success|guaranteed)",
    r"\b(no|zero)\s+(?:side effects|risks?|downside)",
    r"\bwill\s+(?:definitely|certainly)\b",
    r"\bnever\s+(?:fail|hurt|break)\b",
    r"\bproven\s+to\s+work\b",
    r"\bmiracle\b",
]

# Medical / legal / financial claims need substantiation the profile almost
# never carries, so their presence is a warning rather than an auto-pass.
REGULATED_PATTERNS = [
    (r"\b(cure[sd]?|cures|treats?|heals?|diagnos(?:e|is|ed))\b", "medical claim"),
    (r"\b(depress(?:ion|ed)|anxiety|anxious|bipolar|adhd|ptsd)\b", "mental-health framing"),
    (r"\b(therapy|therapeutic|medication|prescription|clinical(?:ly)? proven)\b", "clinical claim"),
    (r"\b(guaranteed (?:income|profit|roi)|make money|financial freedom|invest(?:s|ing)? returns?)\b", "financial claim"),
    (r"\b(legally|legal guarantee|law[- ]compliant|gdpr[- ]compliant by design)\b", "legal claim"),
]

# Testimonial / review fabrication. A promo may quote a real, supplied
# testimonial but must never imply social proof the app has not earned.
#
# Digit runs tolerate internal spaces because normalize() strips the thousands
# separator, turning "500,000" into "500 000" before these patterns run.
TESTIMONIAL_PATTERNS = [
    r"\b\d+[\d\s]*\+?\s*(?:five[- ]star|5[- ]star)\s+reviews?\b",
    r"\b(love[d]? by|trusted by)\s+\d+[\d\s]*[km]?\+?\s*(?:users|people|downloads)\b",
    r"\bone user said\b",
    r"\bour users (?:say|love|report)\b",
    r"\bjoin \d+[\d\s]*[km]?\+?\s*(?:happy )?users\b",
    r"\b#1 (?:app|download)\b",
]

# First-person experience claims by the on-camera presenter.
#
# The presenter is an AI stand-in for the founder's photograph, and nothing in
# the system records their real relationship to the product -- a founder-entered
# "are you a nurse who uses this?" field was considered and dropped, because
# asking a model for a fact only a person can supply is how you get a confident
# wrong answer. So the honest move is to forbid the claim outright rather than
# gate it on a field the model might contradict.
#
# Without this, a strategy that omits the relationship leaves the model to invent
# one and then write "I've used this every shift for two years" from a face that
# has never held anything. A real user-presenter loses the ability to say "I use
# this too", which is the right trade: an invented testimonial is far worse than
# a missing one.
FIRST_PERSON_PATTERNS = [
    # "I use / I have used / I am using [it]" — a claimed history with the
    # product, which no record can substantiate (see the note above).
    #
    # "I used to <verb>" is deliberately NOT matched: a past habit is not a
    # usage claim, and half of all natural first-person hooks are built on it
    # ("I used to dread mornings"). Before this exclusion the rule fired on the
    # very lines the plan generator is told to write, so every honest customer
    # voice arrived with a warning attached. Same for "be used to" ("I am used
    # to waking early" is accustomed, not a claim).
    r"\bi (?:have |ve |am )?(?:been )?us(?:e[sd]?|ing)\b(?! to\b)",
    r"\bi (?:rely on(?: it)?|depend on)\b",
    r"\bi (?:swear|promise|guarantee)\b",
    r"\bas an? \w+,? i\b",
    r"\bmy (?:patients|clients|customers|students|team) (?:say|told me|use)\b",
    r"\bi built (?:this|it)\b",
    r"\bwe (?:built|developed|shipped) (?:this|it)\b",
]

# Disclosure words that, when present, soften a regulated claim.
DISCLOSURE_MARKERS = (
    "not medical advice",
    "not a substitute",
    "consult a",
    "consult your",
    "results vary",
    "individual results",
    "disclaimer",
)

# ---------------------------------------------------------------------------
#
# Framing: what the viewer hears described as a list of what the app contains.
#
# Every other family here checks a CLAIM — that a statement is true, earned or
# permitted. This one checks a SHAPE, and it exists because the whole outcome
# layer above it (profile outcome_statements, mechanism_beat, payoff_beat, the
# template outcome line) is an input. A prompt that says "translate every
# feature into its resulting benefit" is advice, not a guarantee: a model told
# that keeps the feature list and appends an adjective. Nothing downstream
# caught it, and the rendered video said "you can track your emotional states
# and uncover your triggers through voice journaling and mood tracking" — a
# feature inventory, spoken, in the founder's own app.
#
# Two tiers, because the honest cases are not the same shape as the failure:
#
#   FRAMING_PATTERNS — wording that only describes function. A warning. Legitimate
#     copy can name one thing the app does ("a journal you talk to"), so this
#     never blocks: refusing to render over a single accurate noun teaches the
#     founder to ignore the panel.
#
#   FEATURE_ENUMERATION_PATTERNS — two or more capabilities listed in one breath.
#     This blocks. The rule is not that features are forbidden; it is that a list
#     is not an outcome. A run of coordinated verbs or coordinated product nouns
#     ("track X and log Y", "voice journaling and mood tracking") is the failure
#     mode itself, and no honest benefit sentence reads like one.
#
# Matched against normalize() output, so punctuation is already stripped: that
# is what lets the noun patterns key on "journaling and tracking" rather than
# enumerating every comma variant.

FRAMING_PATTERNS = [
    # "X lets you <bare capability verb>" with no consequence attached. The
    # capability verbs are the ones that name an action performed ON the user or
    # the app rather than a change they get.
    r"\b(?:lets? you|allows? you|enables? you|helps? you)\s+"
    r"(?:track|log|record|monitor|measure|capture|list|categoris|categoriz)\w*\b",
    # "you can <capability verb>" is the shape the shipped Vocolens script used.
    r"\byou can\s+(?:track|log|record|monitor|measure|capture)\w*\s+\w+",
    # An explicit inventory, however short.
    r"\b(?:its|the)\s+features?\s+(?:are|include|let you|capable)",
    r"\bfeatures?\s+(?:like|such as|including)\b",
]

FEATURE_ENUMERATION_PATTERNS = [
    # Two coordinated capability verbs on one clause: "track X and uncover Y".
    # The verb list is the tell — an outcome sentence does not coordinate two
    # different things the app records.
    r"\b(?:track|log|record|monitor|measure|capture)\w*\b[^.!?]{0,60}?"
    r"\band\s+(?:you\s+)?(?:can\s+)?(?:track|log|record|monitor|measure|capture|uncover|see|get)\w*\b",
    # Two coordinated product nouns. "-ing" and the analytics/reminder family are
    # the nouns that name a capability; "and" is the join.
    r"\b\w+ing\s+and\s+\w+(?:ing|ers?|ies|ance)\b",
    r"\b(?:tracking|logging|reminders?|analytics|dashboard|widgets?|sync|export)\s+"
    r"and\s+(?:tracking|logging|reminders?|analytics|dashboard|widgets?|sync|export|\w+ing)\b",
    # Three bare comma-separated items: "A, B and C".
    r"\b\w+,\s+\w+,?\s+and\s+\w+\b",
]

_WHITESPACE = re.compile(r"\s+")
_PUNCT = re.compile(r"[^\w\s%$]")

# Money amounts are matched on RAW text with a precise regex, never on the
# punctuation-stripped blob. Stripping punctuation would turn "$4.99" into
# "$4" and make "$4.99" indistinguishable from a profile price of "$4.50".
def normalize(text: str) -> str:
    """Lowercase, strip punctuation, and collapse whitespace for matching."""
    if not text:
        return ""
    return _WHITESPACE.sub(" ", _PUNCT.sub(" ", str(text).lower())).strip()


def _plan_fields(plan: dict):
    """Yield every human-readable leaf value of a creative plan.

    Claim checking must cover what is actually SAID and SHOWN, so this
    includes both beats — not just the spoken script body. `cta` and
    `feature_emphasis` are gone: there is no call to action in a generated
    piece, and `demo_brief` is a note to the founder that never reaches a
    render, so neither is text a viewer could read. `overlays` is gone too:
    burned-in captions were removed, so no on-screen text is planned or
    rendered anymore (the column keeps legacy rows; nothing new is written).

    `strategy` is included because the spoken words live there: the hook line,
    the two section scripts and the outcome promise are generated into the
    strategy, and that text reaches the video model verbatim. A banned claim
    that only appears in the strategy is still a banned claim, so the whole
    nested structure is walked.
    """
    def walk(value):
        if isinstance(value, str):
            yield value
        elif isinstance(value, dict):
            for v in value.values():
                yield from walk(v)
        elif isinstance(value, (list, tuple)):
            for v in value:
                yield from walk(v)

    for key in (
        "hook_line", "script", "visual_direction",
        "voice_direction", "sound_direction",
        "beat_timeline", "strategy",
    ):
        yield from walk(plan.get(key))


def script_text(plan: dict) -> str:
    """Flattened, normalized plan text used for phrase matching."""
    return normalize(" \n ".join(_plan_fields(plan or {})))


def spoken_text(plan: dict) -> str:
    """
    Only the words a viewer actually hears or reads, normalized.

    Separate from `script_text` on purpose. That function walks everything the
    founder reads, including `visual_direction`, `voice_direction`,
    `sound_direction` and the strategy's `scene` / `performance` lock — and a
    scene lock is *made of* comma lists ("camera angle, lighting and wardrobe").
    A framing rule applied to that would refuse nearly every render for
    describing a room, so the blocking tier needs the narrower surface: the hook
    line, the script, both beat texts, and the strategy's spoken hook line and
    its two section scripts.

    Everything else is production direction. A warning on it is informative; a
    block is wrong, because no viewer ever hears "tilt slightly left".
    """
    plan = plan or {}
    parts: list = []

    def add(value):
        if isinstance(value, str) and value.strip():
            parts.append(value.strip())

    add(plan.get("hook_line"))
    add(plan.get("script"))
    for beat in plan.get("beat_timeline") or []:
        if isinstance(beat, dict):
            add(beat.get("text") or beat.get("beat"))

    strategy = plan.get("strategy")
    if isinstance(strategy, dict):
        add(strategy.get("hook_line"))
        for section in strategy.get("segments") or []:
            if isinstance(section, dict):
                add(section.get("script"))

    return normalize(" \n ".join(parts))


def _contains(haystack: str, needle: str) -> bool:
    n = normalize(needle)
    return bool(n) and n in haystack


def find_banned_violations(text: str, banned_claims: Iterable[str]) -> list:
    """
    Banned claims present verbatim in the script.

    These are hard failures: the founder explicitly listed them as unusable,
    so the generator ignoring them is a bug, not a nuance.
    """
    hits = []
    for claim in banned_claims or []:
        if _contains(text, claim):
            hits.append({"claim": str(claim), "reason": "listed as never-use"})
    return hits


def find_used_claims(text: str, approved_claims: Iterable[str]) -> list:
    """Approved claims that actually appear — the verified claim set."""
    return [str(c) for c in (approved_claims or []) if _contains(text, c)]


def find_unverified_claims(text: str, review_claims: Iterable[str]) -> list:
    """
    Claims that require review but leaked into the script.

    Not a hard failure — the founder may have verified them since. They are
    surfaced so the reviewer decides, which is the point of the claims_review
    tier.
    """
    return [
        {"claim": str(c), "reason": "needs verification before use"}
        for c in (review_claims or [])
        if _contains(text, c)
    ]


def find_risk_patterns(text: str) -> list:
    """
    Regulated, guaranteed, or fabricated-proof language anywhere in the plan.
    """
    blob = normalize(text)
    warnings: list = []

    for pattern in GUARANTEE_PATTERNS:
        if re.search(pattern, blob):
            warnings.append({
                "claim": re.search(pattern, blob).group(0),
                "reason": "promises a guaranteed outcome",
            })

    for pattern, label in REGULATED_PATTERNS:
        match = re.search(pattern, blob)
        if not match:
            continue
        entry = {"claim": match.group(0), "reason": f"{label} needs substantiation"}
        if not any(marker in blob for marker in DISCLOSURE_MARKERS):
            entry["disclosure_missing"] = True
        warnings.append(entry)

    for pattern in TESTIMONIAL_PATTERNS:
        match = re.search(pattern, blob)
        if match:
            warnings.append({
                "claim": match.group(0),
                "reason": "implies social proof the app may not have",
            })

    # Reported separately from the social-proof warnings above because the
    # remedy is different: this is not the app's proof, it is the presenter
    # claiming a personal history nothing on file can support.
    for pattern in FIRST_PERSON_PATTERNS:
        match = re.search(pattern, blob)
        if match:
            warnings.append({
                "claim": match.group(0),
                "reason": "first-person experience claim the presenter cannot substantiate",
            })
            break

    return warnings


def detect_feature_framing(text: str) -> list:
    """
    Spoken or on-screen copy that inventories the app instead of describing what
    it changes for the viewer.

    A warning, not a block. One accurate noun ("a journal you talk to") is
    ordinary copy, and a panel that refuses to render over it is a panel the
    founder learns to ignore — which is how the claim warnings already work and
    why this joins them rather than `blocking`.
    """
    blob = normalize(text)
    warnings: list = []
    for pattern in FRAMING_PATTERNS:
        match = re.search(pattern, blob)
        if match:
            warnings.append({
                "claim": match.group(0),
                "reason": (
                    "states what the app does rather than what it changes for the "
                    "viewer"
                ),
            })
            break
    return warnings


def detect_feature_enumeration(text: str) -> list:
    """
    Two or more capabilities listed in one breath. This blocks.

    The distinction from the warning above is length of list, not sentiment: a
    single capability described plainly is copy, and a run of them is a product
    page read aloud. Nothing after this point would catch it — the model wrote
    it, the founder reads a summary in the review, and the video says it — so
    this is the last place the video can be refused.

    Only high-confidence shapes are listed. A looser rule here would refuse
    renders over honest copy, and a gate that cries wolf gets disabled.
    """
    blob = normalize(text)
    hits: list = []
    for pattern in FEATURE_ENUMERATION_PATTERNS:
        match = re.search(pattern, blob)
        if not match:
            continue
        hits.append({
            "claim": match.group(0),
            "reason": (
                "lists the app's features instead of the outcome it gives the "
                "viewer"
            ),
        })
    return hits


def detect_sensitive_targeting(text: str) -> list:
    """
    Copy that diagnoses or labels the viewer rather than describing the app.

    Naming one accurate thing the app does is ordinary copy and stays legal --
    `detect_feature_framing` draws that line. Assuming a condition of the viewer
    is not, because the research never established it. This is a warning, not a
    hard block, because legitimate copy can mention a category name.
    """
    blob = normalize(text)
    out = []
    for pattern, label in REGULATED_PATTERNS:
        if label != "mental-health framing":
            continue
        if re.search(pattern, blob):
            out.append({
                "claim": re.search(pattern, blob).group(0),
                "reason": "describes the viewer instead of the app's functionality",
            })
    return out


def build_safety_report(plan: dict, profile: dict) -> dict:
    """
    Full safety verdict for a generated plan.

    Returns:
        {
"passed": bool,            # False blocks generation
          "blocking": [...],         # banned claims / feature inventories
          "claims_used": [...],      # verified against claims_approved
          "unverified": [...],       # from claims_review
            "risk_warnings": [...],    # regulated / guaranteed / testimonial /
                                       # functional-without-benefit
          "sources_used": [...],     # which profile fields fed the plan
          "self_declared_claims": [...],  # what the model said it used
        }

    `passed` is False only for hard failures. Warnings are returned but do
    not block, so the founder keeps editorial control over tone while
    prohibited claims can never reach a video.

    Two kinds of hard failure, deliberately: a claim the founder banned, and a
    spoken inventory of the app's features. The second is here because the
    outcome layer — profile outcome statements, mechanism and payoff beats, the
    template outcome line — is enforced only by prompt advice, and advice does
    not survive contact with a model that wants to be helpful. A list of
    capabilities is the one shape that reliably survives that, and by the time it
    is a video the founder is watching it rather than deciding it.

    There is deliberately no price check. The App Profile no longer carries
    pricing, so there is nothing to verify a stated price against — and a check
    with no anchor flags every price in every script, which teaches the founder
    to ignore the panel that actually matters. Prices are kept out of the video
    at the prompt instead: generation_planning's no-render rule tells the model
    never to put one on screen.
    """
    text = script_text(plan)
    spoken = spoken_text(plan)
    self_declared = [
        str(c) for c in ((plan or {}).get("claims_used") or []) if str(c).strip()
    ]

    blocking = find_banned_violations(text, profile.get("claims_banned"))
    # The framing tier, deliberately split by surface: blocking reads only the
    # spoken words (see `spoken_text` for why the wider walk cannot be used
    # here), while the warning may read all of it, since naming the app is a
    # legitimate thing to do in copy and only wrong in a bare inventory.
    blocking += detect_feature_enumeration(spoken)
    risk_warnings = (
        find_risk_patterns(text)
        + detect_sensitive_targeting(text)
        + detect_feature_framing(spoken)
    )

    used = find_used_claims(text, profile.get("claims_approved"))
    unverified = find_unverified_claims(text, profile.get("claims_review"))

    sources = []
    for field in (
        "brand_name", "app_category", "core_features", "primary_use_cases",
        "problems_solved", "known_limitations",
    ):
        value = profile.get(field)
        if value and (isinstance(value, list) and value or isinstance(value, str) and value.strip()):
            sources.append(field)

    return {
        "passed": not blocking,
        "blocking": blocking,
        "claims_used": used,
        "unverified": unverified,
        "risk_warnings": risk_warnings,
        "sources_used": sources,
        "self_declared_claims": self_declared,
        "unverified_self_claims": sorted(set(self_declared) - set(used)),
    }


def summarize(report: dict) -> str:
    """One-line reviewer-facing summary. Never claims safety it did not find."""
    if report.get("passed") and not (
        report.get("risk_warnings") or report.get("unverified")
    ):
        return "Clean: no banned claims or risky language detected."
    bits = []
    if report.get("blocking"):
        bits.append(f"{len(report['blocking'])} prohibited claim(s)")
    if report.get("unverified"):
        bits.append(f"{len(report['unverified'])} claim(s) needing review")
    if report.get("risk_warnings"):
        bits.append(f"{len(report['risk_warnings'])} risk warning(s)")
    return "Needs review: " + ", ".join(bits) + "."
