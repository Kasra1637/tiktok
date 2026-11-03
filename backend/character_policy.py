"""The on-screen person is never given a gender, a role or an identity.

The founder uploads the photograph of the identity they want, and that image
alone decides the look (ADR 0089). A script or a card that says "a woman on a
back step" or "the founder holds up two hands" invents an identity the founder
never chose and contradicts the character reference the render carries as its
first frame. So every video-facing text field — angle fields, template names and
shapes, hooks, scripts, in-your-video lines — passes through `neutralize` on the
way in, and the words always name "the person" / "the character".

Lexical and conservative on purpose. It rewrites person nouns and third-person
pronouns and leaves every other word exactly as written: a rewrite that guessed
at meaning (a gender-neutral paraphrase of a whole sentence) would invent as
much as it removed. It is a floor under the prompts, which ask for neutral
wording first.

Pure policy: no HTTP, AI, auth or persistence imports (ADR 0089).
"""
import re

# The only way a video-facing line may name the character.
SUBJECT = "the person"

# Person nouns that hand the character an identity the founder did not choose.
# Plural forms are still a claim ("two women"), so they map to "people".
_SINGULAR_NOUNS = (
    "business owner", "content creator", "co-founder", "cofounder",
    "entrepreneur", "businesswoman", "businessman", "professional",
    "marketer", "developer", "designer", "founder", "owner", "woman", "man",
    "girl", "boy", "lady", "gentleman", "guy", "female", "male", "ceo",
    "presenter",
)
_PLURAL_NOUNS = (
    "business owners", "content creators", "co-founders", "cofounders",
    "entrepreneurs", "businesswomen", "businessmen", "professionals",
    "marketers", "developers", "designers", "founders", "owners", "women",
    "men", "girls", "boys", "ladies", "gentlemen", "guys", "females", "males",
    "presenters",
)
_PLURAL_SET = frozenset(_PLURAL_NOUNS)

# Longest first: "business owner" must win over "owner", "herself" over "her".
_NOUN_ALTERNATION = "|".join(
    sorted(_SINGULAR_NOUNS + _PLURAL_NOUNS, key=len, reverse=True)
)

_DETERMINERS = (
    "the", "a", "an", "this", "that", "one", "another", "some", "every", "each",
)

_PERSON_NOUN = re.compile(
    r"\b(?:(?P<det>" + "|".join(_DETERMINERS) + r")\s+)?"
    r"(?P<noun>" + _NOUN_ALTERNATION + r")(?P<poss>['\u2019]s)?\b",
    re.IGNORECASE,
)

# Third-person pronouns are the same claim in fewer letters.
_PRONOUN = re.compile(
    r"\b(herself|himself|hers|his|her|him|she|he)\b", re.IGNORECASE
)

# "her" is the one English word here that is both possessive and object. The
# context decides: after a preposition ("to her") or after a verb that takes an
# object ("told her" / "handed her the phone") it is the object form ("them");
# everywhere else it describes ownership ("her guess") and needs "their". A
# following determiner or a full stop is the tell for the object form, so
# "tells her friend" keeps the possessive reading.
_OBJECT_TAKERS = frozenset((
    "to", "for", "with", "at", "of", "from", "on", "in", "into", "around",
    "told", "tell", "tells", "asked", "ask", "asks", "gave", "give", "gives",
    "showed", "show", "shows", "helped", "help", "helps", "remind", "reminds",
    "reminded", "let", "lets", "made", "makes", "make", "took", "take", "takes",
    "hug", "hugs", "hugged", "call", "called", "calls", "texted", "texts",
    "saw", "see", "sees", "met", "meet", "meets", "paid", "pay", "pays",
    "handed", "hands", "hand", "warned", "warn", "stopped", "stop",
))
_OBJECT_FOLLOWERS = frozenset((
    "a", "an", "the", "it", "them", "this", "that", "to", "and", "but", "so",
    "when", "about", "because", "if", "or", "how", "why", "what", "up", "back",
))


def _match_case(source: str, replacement: str) -> str:
    """Carry a leading capital from the replaced word onto its replacement."""
    if source[:1].isupper():
        return replacement[:1].upper() + replacement[1:]
    return replacement


def _noun_replacement(match) -> str:
    plural = match.group("noun").lower() in _PLURAL_SET
    base = "people" if plural else "person"
    if match.group("poss"):
        base += "'s"
    det = (match.group("det") or "").lower()
    if det in ("the", "a", "an", "this", "that"):
        # "a woman" and "the founder" both land on the one neutral subject.
        lead = "the "
    elif det:
        # "one man", "another founder": the count is information, keep it.
        lead = det + " "
    else:
        lead = ""
    return _match_case(match.group(0), lead + base)


def _pronoun_replacement(match) -> str:
    word = match.group(0)
    low = word.lower()
    if low in ("herself", "himself"):
        return _match_case(word, "themselves")
    if low == "hers":
        return _match_case(word, "theirs")
    if low == "his":
        return _match_case(word, "their")
    if low in ("she", "he"):
        # "the person" rather than "they": singular agreement leaves the
        # following verb untouched ("she types" -> "the person types").
        return _match_case(word, "the person")
    before = match.string[: match.start()].rstrip().lower()
    previous = before.rsplit(" ", 1)[-1] if before else ""
    # What follows decides between "told her" and "her friend": a noun after the
    # word means it owned something, a determiner or a full stop means it was
    # the object.
    after = match.string[match.end():].lstrip()
    following = re.match(r"[A-Za-z']+", after)
    next_word = following.group(0).lower() if following else ""
    is_object = previous in _OBJECT_TAKERS and (
        not next_word or next_word in _OBJECT_FOLLOWERS
    )
    return _match_case(word, "them" if is_object else "their")


def neutralize(text) -> str:
    """`text` with every gender, role and pronoun claim replaced, else as written."""
    value = "" if text is None else str(text)
    if not value:
        return ""
    value = _PERSON_NOUN.sub(_noun_replacement, value)
    return _PRONOUN.sub(_pronoun_replacement, value)


def neutralize_fields(record: dict, keys) -> dict:
    """A copy of `record` whose string fields named in `keys` are neutralized."""
    out = dict(record or {})
    for key in keys:
        if isinstance(out.get(key), str):
            out[key] = neutralize(out[key])
    return out


def identity_terms(text) -> list:
    """Every gender, role or pronoun claim still in `text`; empty when neutral.

    Proved from the same pattern set `neutralize` rewrites, so a passing check
    and a rewrite can never disagree about what counts as a claim. The two
    patterns are disjoint (a noun is never a pronoun), so the hits never pair up.
    """
    value = str(text or "")
    if not value:
        return []
    return [m.group(0) for m in _PERSON_NOUN.finditer(value)] + [
        m.group(0) for m in _PRONOUN.finditer(value)
    ]


def is_neutral(text) -> bool:
    """True when `text` names the character without a gender, role or pronoun."""
    return not identity_terms(text)

