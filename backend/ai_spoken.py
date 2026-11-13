"""Spoken-word budgets, trimming and story checks.

Pure normalization + lexical diversity for the copy a video is asked to
speak: budgets (chars/sec), sentence trimming, hook stripping, spoken-word
partitioning/binding and the story-shape checks that grade a script.
Split out of `ai_service` by flow; `ai_service` re-exports these names so
existing callers and tests keep working.
"""
import json
import re

import final_beat


# A claimed history with the product ("I've used this every shift for two
# years") is an invented testimonial when the presenter is generated from a
# photo: no record can substantiate it, so the draft check below rejects it.
# "I used to <verb>" is deliberately NOT matched: a past habit is not a usage
# claim, and half of all natural first-person hooks are built on it. Same for
# "be used to" ("I am used to waking early" is accustomed, not a claim).
FIRST_PERSON_PATTERNS = [
    r"\bi (?:have |ve |am )?(?:been )?us(?:e[sd]?|ing)\b(?! to\b)",
    r"\bi (?:rely on(?: it)?|depend on)\b",
    r"\bi (?:swear|promise|guarantee)\b",
    r"\bas an? \w+,? i\b",
    r"\bmy (?:patients|clients|customers|students|team) (?:say|told me|use)\b",
    r"\bi built (?:this|it)\b",
    r"\bwe (?:built|developed|shipped) (?:this|it)\b",
]


_PROMOTION_MARKERS = (
    "you won t believe", "you wont believe", "mind blown", "mind blowing",
    "this changed everything", "changed my life", "life changing",
    "shocking", "shockingly", "game changer",
    "no one talks about", "nobody talks about", "little did i know",
    "guaranteed", "miracle", "cured", "cure for",
    "download", "install it", "install the app", "sign up", "try it free",
    "try the app", "get the app", "our app", "our product", "we built",
    "as the founder", "as the developer", "link in bio", "follow for more",
    "hit the follow", "smash that", "comment below", "tag a friend",
)
_AI_FLUFF_MARKERS = (
    "in today s fast paced world", "fast paced world", "digital age",
    "ever evolving", "ever changing", "let s dive in", "lets dive in",
    "dive into", "diving into", "unlock the power", "unleash the",
    "supercharge", "to the next level", "imagine a world where",
    "the best part", "look no further", "here s the thing",
)
def _spoken_marker_hit(text: str, markers: tuple) -> str:
    """The first phrase from `markers` that appears in `text`, else "".

    Normalized the same way the other spoken checks normalize: lowercased with
    punctuation gone, so "It's a GAME-CHANGER!" and "game changer" match.
    """
    normalized = _normalize_spoken(text)
    for marker in markers:
        if marker in normalized:
            return marker
    return ""
_FIRST_PERSON_I = re.compile(r"\bI(?:['\u2019][A-Za-z]+)?\b")
SPOKEN_CHARS_PER_SECOND = 15
def spoken_budget(seconds) -> int:
    """
    What a section of `seconds` holds at the middle's conversational pace.

    This is the length for a natural read, not a hard technical ceiling the
    video model imposes: 10 seconds is about 150 characters at 15 characters a
    second. It is the same number the prompt asks the model to aim for and the
    render measures against, so the words the founder approves are the words
    that fit — and it is what `spoken_targets` caps a line's natural target
    with when the piece is shorter than the target.
    """
    try:
        secs = float(seconds or 0)
    except (TypeError, ValueError):
        secs = 0.0
    return max(60, int(round(secs * SPOKEN_CHARS_PER_SECOND)))
HOOK_CHARS_PER_SECOND = 20
def hook_ceiling(seconds) -> int:
    """The character ceiling for an opening line of `seconds`, at the brisk pace."""
    try:
        secs = float(seconds or 0)
    except (TypeError, ValueError):
        secs = 0.0
    return max(60, int(round(secs * HOOK_CHARS_PER_SECOND)))
HOOK_TARGET_CHARS = 70
SCRIPT_TARGET_CHARS = 150
TARGET_BAND = 0.25
_PROBLEM_MARKERS = (
    "why", "how come", "can t", "cannot", "won t", "don t", "doesn t", "didn t",
    "no one", "nothing", "nobody", "stop", "stuck", "struggle", "struggling",
    "tired", "hate", "waste", "wasting", "wish", "keeps", "always", "never",
    "problem", "hard", "harder", "hardest", "wrong", "failing", "forgetting",
    "losing", "lost", "dread", "mess", "chaos", "guessing", "overwhelmed",
    "endless", "too much", "again", "every time",
)
_RESOLUTION_MARKERS = (
    "now", "so i", "instead", "finally", "turns out", "the fix", "fixes",
    "fixed", "solves", "solved", "helps", "helping", "lets you", "let me",
    "ends with", "one tap", "no more", "never again", "since then", "started",
    "made it", "makes it", "gives you", "which is why", "that s why",
    "the answer", "written down", "stops", "worked",
)

# Live-POV surface defects (future generation only). A quoted span is a
# quotation, not direct speech — contractions ("can't", "don't") are not
# quotes; a quote opens at the start of the line or after space/comma and
# closes before space/punctuation.
_QUOTED_SPAN_RE = re.compile(
    r"(?:\"|\u201c|\u201d)|\u2018[^']+\u2019|(?:^|(?<=[\s,;:\u2014]))'[^'\n]{1,80}'(?=[\s,.;:!?]|$)"
)
# Self-narration / stage directions: the speaker reports having said or done
# something instead of saying it, live, in the moment. Matched on the words
# the speaker would not say out loud while filming.
_SELF_NARRATION_RE = re.compile(
    # Reporting speech with a manner adverb ("I said quietly") reports past
    # words instead of speaking them. A bare "I spoke instead" is a story
    # beat, not a report, so the verb alone is not flagged.
    r"\bi\s+(said|whispered|shouted|murmured|yelled|spoke)\s+"
    r"(quietly|loudly|softly)\b"
    r"|\bi\s+said\b[^\n]{0,40}?['\"\u201c\u201d]"
    r"|\bi\s+told\s+myself\b"
    r"|\bi\s+(lean|leans|leaned|grip|grips|gripped|stare|stares|stared|look|looks|looked)\s+"
    r"(?:into|at|toward|towards)?\s*(?:the\s+)?(camera|lens|railing|frame)\b"
    r"|\bi\s+(turn|turns|turned)\s+(?:to|toward|towards|into)\s+(?:the\s+)?(camera|lens|frame)\b"
    r"|\bi\s+(point|points|pointed|raise|raises|raised|show|shows|showed)\s+"
    r"(?:my\s+hand|the\s+camera|the\s+lens|the\s+frame)\b"
    r"|\b(?:lean|leans|leaned|grip|grips|gripped|stare|stares|stared|look|looks|looked)\s+"
    r"(?:[a-z]+\s+){0,3}?(?:camera|lens|railing|frame)\b",
    re.I,
)
# Vague payoff stands in for the specific thing the line should name:
# "a word", "that vague sense", "that feeling" — never a payoff.
_VAGUE_PAYOFF_RES = (
    re.compile(r"\b(?:a|the|that|this)\s+(?:word|words)\b", re.I),
    re.compile(r"\b(?:a|the|that|this)\s+vague\s+\w+\b", re.I),
    re.compile(r"\bvague\s+(?:sense|feeling|thing|idea)\b", re.I),
    re.compile(r"\b(?:that|this)\s+(?:sense|feeling|idea)\b", re.I),
    re.compile(r"\b(?:a|some)\s+(?:thing|stuff|idea)\b", re.I),
    re.compile(r"\ba\s+(?:feeling|thought)\b", re.I),
)


def _has_quoted_span(text: str) -> bool:
    return bool(text) and bool(_QUOTED_SPAN_RE.search(str(text)))


def strip_quote_marks(text: str) -> str:
    """`text` with quotation marks removed, the words kept intact.

    Double and curly quotes go entirely. Single-quote delimiters go only
    where they open or close a span (start/space/punctuation), so
    contractions ("can't", "don't") survive untouched. Mechanical, not
    editorial: it is the terminal salvage when a model keeps quoting after
    the bounded repair attempts, so the plan ships instead of failing.
    """
    out = str(text or "")
    out = out.replace('"', "").replace("\u201c", "").replace("\u201d", "")
    out = out.replace("\u2018", "")
    # Curly closing quote: drop it unless it is an apostrophe between letters.
    out = re.sub(r"(?<![A-Za-z])\u2019|(?![A-Za-z])\u2019", "", out)
    # Straight single-quote delimiters: start-of-line or after space/punct to
    # open, and before space/punct/end to close. Contractions (letter ' letter)
    # match neither side and survive.
    out = re.sub(r"(?:^|(?<=[\s,;:\u2014(\u2014]))'(?=[^\s])", "", out)
    out = re.sub(r"'(?=[\s,.;:!?]|$)", "", out)
    out = re.sub(r"\s{2,}", " ", out).strip()
    return out


def _self_narration_hit(text: str) -> str:
    if not text:
        return ""
    match = _SELF_NARRATION_RE.search(_normalize_spoken(text))
    return match.group(0) if match else ""


def _vague_payoff(text: str) -> bool:
    """A vague stand-in in the payoff: the last sentence's 'a word' / 'that
    vague sense' names no specific lived thing."""
    sentences = _split_sentences(text)
    last = sentences[-1] if sentences else str(text or "")
    return any(pattern.search(last) for pattern in _VAGUE_PAYOFF_RES)
def spoken_targets(hook_seconds=3, total_seconds=12) -> dict:
    """
    What each spoken line aims at, and the most its seconds can hold.

    The target is the natural speaking length above, never above the ceiling: a
    2s hook cannot hold 70 characters at any pace this product renders at, so
    aiming there would only guarantee an over-length line. `ceiling` is what
    the render, the arrival clamp and the Review step already measure against —
    `spoken_budget` for the middle, and the brisk `hook_budget` for the
    opening, which is read fast — so this adds the aim, it does not move the
    limit.
    """
    hook_limit = hook_ceiling(hook_seconds)
    middle_seconds = max(1, int(total_seconds or 0) - int(hook_seconds or 0))
    script_ceiling = spoken_budget(middle_seconds)
    return {
        "hook_seconds": int(hook_seconds or 0),
        "middle_seconds": middle_seconds,
        "hook": {"target": min(HOOK_TARGET_CHARS, hook_limit), "ceiling": hook_limit},
        "script": {
            "target": min(SCRIPT_TARGET_CHARS, script_ceiling),
            "ceiling": script_ceiling,
        },
    }
def _split_sentences(text: str) -> list:
    """
    Split a line into sentences, each keeping its own terminator.

    A terminator only ends a sentence when what follows is a space or the end
    of the line, so "Dr. Smith" and "12.5" stay whole. The same rule
    `_first_sentence` applies to the opening, applied to every sentence.
    """
    stripped = str(text or "").strip()
    if not stripped:
        return []
    sentences = []
    start = 0
    for index, ch in enumerate(stripped):
        if ch not in ".!?":
            continue
        following = stripped[index + 1: index + 2]
        if following == "" or following in " \n\t":
            sentence = stripped[start: index + 1].strip()
            if sentence:
                sentences.append(sentence)
            start = index + 1
    tail = stripped[start:].strip()
    if tail:
        sentences.append(tail)
    return sentences
def _keep_tail(text: str, limit: int) -> str:
    """
    The end of a sentence, cut back to a word boundary and stripped of its mark.

    Used only for a resolving sentence that is itself longer than the body can
    speak. The end of that sentence is its conclusion — the payoff beat is the
    last thing said — so the tail is the part worth keeping, where the head of
    it is the setup that led there.
    """
    window = str(text or "").strip()[-max(1, int(limit)):]
    space = window.find(" ")
    if space > 0:
        window = window[space + 1:]
    # Only the front is cleaned: the cut leaves the previous sentence's mark on
    # the way in, and the closing mark is part of the sentence that survives.
    return window.lstrip(" ,.!?;:-").rstrip()
def trim_spoken_body(text: str, limit: int):
    """
    Cut a spoken body to fit `limit`, keeping the sentence that resolves it.

    `trim_to_sentence` keeps the opening and cuts the tail, which for a spoken
    body means cutting the resolution — the payoff the hook set up in the first
    place, and the one sentence the middle exists to say. So a body is cut from
    the MIDDLE outwards instead: whole sentences go from between the opening
    (the line that links back to the hook) and the closing sentence (the one
    that answers it), and only when those two are still too long does the
    opening give way, at its own sentence-then-word boundary. The payoff is the
    last thing cut, never the first.

    Returns (kept, dropped), `dropped` counted in characters, so a caller
    reports exactly how much of the approved words is not spoken.
    """
    text = str(text or "").strip()
    if not text or limit <= 0 or len(text) <= limit:
        return text, 0
    sentences = _split_sentences(text)
    if len(sentences) < 2:
        return trim_to_sentence(text, limit)
    kept = list(sentences)
    while len(kept) > 2 and len(" ".join(kept)) > limit:
        del kept[1]
    joined = " ".join(kept)
    if len(joined) > limit:
        # Only the opening and the payoff are left, and both are the story. The
        # opening gives way first: it is the half a viewer can reconstruct from
        # the hook, and the payoff is the half they cannot.
        payoff = kept[-1]
        if len(payoff) >= limit:
            payoff = _keep_tail(payoff, limit)
        room = limit - len(payoff) - 1
        head = trim_to_sentence(kept[0], room)[0] if room > 0 else ""
        joined = (head + " " + payoff).strip() if head else payoff
    return joined, len(text) - len(joined)


# Question form without the mark is only the inversion: an auxiliary
# first ("Can I say it out loud"), or a wh-word with the auxiliary in the
# second slot ("What does it mean"). A wh-word with no auxiliary there is
# NOT flagged: "What sets it off is still a mystery" is the statement form
# that names the unknown, which is exactly the ending the craft asks for,
# so a fuzzy read would refuse the lines the rule wants.
_QUESTION_AUX = frozenset((
    "am", "is", "are", "was", "were", "do", "does", "did", "can", "could",
    "will", "would", "shall", "should", "have", "has", "had", "may",
    "might", "must",
))
_QUESTION_WH = frozenset((
    "what", "why", "how", "when", "where", "who", "whom", "whose", "which",
))

def _sentence_is_question(sentence: str) -> bool:
    """Whether one spoken sentence is in question form (deterministic).

    The terminal mark is the observable case. Without it, only inversion
    gives the form away — see _QUESTION_AUX/_QUESTION_WH for why the line
    is drawn there. Everything else is a statement, however it is phrased.
    """
    plain = str(sentence or "").strip().rstrip('"\u201d\u2019').strip()
    if not plain:
        return False
    if plain.endswith("?"):
        return True
    words = _normalize_spoken(plain).split()
    if not words:
        return False
    if words[0] in _QUESTION_AUX:
        return True
    return (
        words[0] in _QUESTION_WH
        and len(words) > 1
        and words[1] in _QUESTION_AUX
    )

# Words that carry no promise of their own, on top of the continuity
# stopwords: pronouns and possessives a certified outcome is phrased
# with ("without checking YOUR phone") that no hook should have to echo.
_PROMISE_EXTRA_STOPWORDS = frozenset((
    "without", "you", "your", "yours", "our", "ours",
))

def certified_outcome_key_terms(outcome: str) -> list:
    """The words a certified outcome's promise is made of, in order.

    Normalized the way the angle grounding near-match normalizes — the
    same lowercase word tokens — then reduced to the terms that carry
    the promise: at least four letters, not a stopword. Short function
    words ("start before the kettle boils" keeps start/kettle/boils,
    drops "before"/"the") are connective tissue, not the promise.
    """
    stopwords = _CONTINUITY_STOPWORDS | _PROMISE_EXTRA_STOPWORDS
    terms = []
    for word in _normalize_spoken(outcome).split():
        if len(word) >= 4 and word not in stopwords and word not in terms:
            terms.append(word)
    return terms

def hook_carries_certified_outcome(hook: str, outcome: str) -> bool:
    """Whether the hook's own words carry the certified outcome's promise.

    The bar is half the outcome's key terms, rounded up — the hook is
    one short spoken line, so demanding every term would refuse hooks
    that plainly promise the outcome, while a single shared word would
    pass hooks that promise something else entirely. Matching is the
    continuity matcher (same word, same stem, or one containing the
    other), so "started" carries "start". An outcome with no key terms
    certifies nothing checkable and always passes: the plan then
    behaves exactly as it did before the promise match existed.
    """
    terms = certified_outcome_key_terms(outcome)
    if not terms:
        return True
    hook_words = _normalize_spoken(hook).split()
    carried = sum(
        1 for term in terms
        if any(_words_match(term, word) for word in hook_words)
    )
    return carried >= -(-len(terms) // 2)

# Determiner-less place phrases (Kasra's grammar gate, ADR 0128).
# "On days at bus stop" reached the founder in a generated hook: the
# place lost its article, which no real person drops for these nouns.
# The set is deliberately the witnessed class — places a speaker
# locates themselves at with "at" — and nothing wider: "at home", "at
# work" and "at night" are idiomatic bare, and "at school" / "at
# church" are the standard US forms for the institution, so a general
# article rule would refuse natural speech to catch one broken shape.
# A determiner or possessive in front ("at the bus stop", "at my
# office") never matches: the pattern starts at the noun itself.
_BARE_PLACE_RE = re.compile(r"\bat (bus stop|office|gym|store|park)\b")

def _bare_place_hit(text: str) -> str:
    """The determiner-less place phrase in a spoken line, else ""."""
    match = _BARE_PLACE_RE.search(_normalize_spoken(text))
    return match.group(0) if match else ""

# Working the app's controls out loud (ADR 0128). The profile's own
# feature names are banned by the shared craft block; what leaked
# instead was generic UI vocabulary — "I choose pleasant and calm
# levels", where "levels" names the app's sliders. The catch is the
# CONSTRUCTION, a control verb governing the noun within a few words,
# never the noun alone: "my stress levels are high" and "energy levels
# crash by three" are a person describing their own state, and must
# never flag. "Tap" stands with the control verbs because in this
# app's own idiom one tap is how a control is worked.
_UI_CONTROL_RE = re.compile(
    r"\b(choose|chooses|chose|pick|picks|picked|set|sets|setting|"
    r"select|selects|selected|adjust|adjusts|adjusted|tap|taps|tapped)"
    r"(?:\s+[a-z0-9]+){0,3}?\s+(levels?|sliders?)\b"
)

def _ui_control_hit(text: str) -> str:
    """The control-verb + levels/slider span in a spoken line, else ""."""
    match = _UI_CONTROL_RE.search(_normalize_spoken(text))
    return match.group(0) if match else ""

# Problem-state vocabulary for the ending check (ADR 0128): words that
# state the unresolved problem itself, as opposed to a response to it.
# Narrower than _PROBLEM_MARKERS on purpose — an ending may look back
# ("the label was wrong in a way I can finally see" closes fine), so
# only words that can only state the problem are here, plus the
# negated auxiliaries that state it as a thing failing to happen.
_ENDING_PROBLEM_WORDS = frozenset((
    "hard", "harder", "hardest", "difficult", "stuck", "struggle",
    "struggling", "failing", "overwhelmed", "endless", "losing",
    "forgetting", "chaos", "dread",
))
_ENDING_PROBLEM_PHRASES = ("won t", "can t", "cannot")
# An ending that names what is still unknown OPENS the discovery — it
# is the ending ADR 0123 asks for — however it is phrased: the unknown
# named outright, or the speaker's own not-knowing stated plainly.
_ENDING_UNKNOWN_PHRASES = (
    "mystery", "unknown", "don t know", "do not know", "doesn t know",
    "no idea", "can t say", "cannot say", "can t name", "cannot name",
    "has no name", "never has a name", "no name for",
)

def _ending_restates_problem(hook: str, script: str) -> bool:
    """Whether the script's last sentence closes on the hook's problem.

    The deterministic slice of "the ending opens the discovery" that
    word arithmetic can see (ADR 0128, extending ADR 0123's question
    check): the final sentence is still talking about the hook's
    problem — it shares one of the hook's image words and is still
    phrased in problem-state words — and it opens nothing: no
    resolution marker, no new place or moment, no naming of what is
    still unknown. Kasra's witnessed ending is the shape: "Words stay
    difficult to find, but I sit with it" shares the hook's "words",
    is phrased around "difficult", and adds no place, time, turn or
    unknown. A restatement in entirely fresh problem words is beyond
    this arithmetic and stays the prompt's business; what is pinned
    here is the witnessed failure, not a theory of endings.
    """
    sentences = _split_sentences(script)
    if not sentences:
        return False
    last = sentences[-1]
    if _sentence_is_question(last):
        return False  # question form is the ending check's own flag
    normalized = _normalize_spoken(last)
    if not normalized:
        return False
    last_words = _continuity_words(last)
    hook_words = _continuity_words(hook)
    if not any(
        _words_match(last_word, hook_word)
        for last_word in last_words
        for hook_word in hook_words
    ):
        return False
    tokens = set(normalized.split())
    padded = f" {normalized} "
    problem = bool(tokens & _ENDING_PROBLEM_WORDS) or any(
        f" {phrase} " in padded for phrase in _ENDING_PROBLEM_PHRASES
    )
    if not problem:
        return False
    if any(f" {marker} " in padded for marker in _RESOLUTION_MARKERS):
        return False
    scene = tokens | {_continuity_stem(token) for token in tokens}
    if scene & _SCENE_PLACES or scene & _SCENE_MOMENTS:
        return False
    if any(phrase in normalized for phrase in _ENDING_UNKNOWN_PHRASES):
        return False
    return True

def _generated_spoken_issues(hook: str, script: str, hook_budget: int, script_budget: int,
                              *, allows_question: bool = False,
                              certified_outcome: str = "") -> list:
    """Reject observable draft defects before any sentence-splitting clamp.

    This is not a general grammar parser or a semantic coherence score. It
    catches empty/oversized lines, missing terminators, dangling function
    words and obvious cross-field continuations. The prompt's editorial
    self-review handles meaning; these checks prevent our own length fitting
    from manufacturing the reported fragments.

    Two more families are rejected because they are observable rather than
    matters of taste, and because the prompt's rules state each as an absolute:
    promotion/marketing wording (a download request, the founder's own voice,
    the app named) and machine-sounding filler openers. Both are matched as
    whole phrases on normalized text, so a genuine customer line never trips
    them — see _PROMOTION_MARKERS for why that constraint is the whole design.
    The hook's first-person count is the same kind of arithmetic, not taste:
    the prompt allows at most one 'I' in the whole hook line. So is the
    statement default: a hook-line question is detectable (it ends in '?'),
    so a non-question plan that drafts one is rewritten through the editorial
    loop instead of shipped. So is the promise match: when the caller
    certifies an outcome, the hook either carries that outcome's key terms
    or it does not — word arithmetic again, never a judgment of quality.
    """
    issues = []
    # Prepositions/pronouns CAN end grammatical English ("look forward to",
    # "I felt like that"). Only unambiguous dangling words are rejected on
    # their own; the reported "typing feels like" needs its local context.
    dangling = {"a", "an", "the", "and", "or", "but", "because"}
    unfinished_endings = ("feels like", "felt like", "seems like", "looks like")
    for name, text, budget in (("hook_line", hook, hook_budget), ("script", script, script_budget)):
        if not text:
            issues.append(f"{name} is empty")
            continue
        if len(text) > budget:
            issues.append(f"{name} has {len(text)} characters, exceeding {budget}; rewrite the thought")
        hit = _spoken_marker_hit(text, _PROMOTION_MARKERS)
        if hit:
            issues.append(f"{name} reads as promotion or hype, not a customer: '{hit}'")
        hit = _spoken_marker_hit(text, _AI_FLUFF_MARKERS)
        if hit:
            issues.append(f"{name} uses a generic AI-sounding phrase: '{hit}'")
        # A spoken line that claims a personal history with the app ("I use",
        # "my patients") states a testimonial no record can substantiate, so
        # a draft that does it is rewritten here instead of accepted. The
        # "I used to <verb>" exclusion is a past habit rather than a usage
        # claim and must keep passing untouched.
        for pattern in FIRST_PERSON_PATTERNS:
            match = re.search(pattern, _normalize_spoken(text))
            if match:
                issues.append(
                    f"{name} claims a personal history with the app "
                    f"('{match.group(0).strip()}'), which no record can substantiate"
                )
                break
        # The generated clip never shows app content, so the spoken lines
        # never narrate working a chart/graph/screen ("I scrolled my week",
        # "saw the worry come back on Monday" from the app). The demo the
        # founder records shows the app; the clip's voice stays on leaning,
        # speaking and breathing instead.
        if final_beat._clause_has_screen_action(_normalize_spoken(text)):
            issues.append(
                f"{name} narrates scrolling or reading a chart/screen the "
                f"generated clip never shows — speak on leaning, breathing and naming "
                f"the worry instead; the founder's demo shows the app"
            )
        # A place keeps its article in real speech (ADR 0128): "at bus
        # stop" is a grammar slip no prompt wording had stopped, so the
        # observable shape is checked like the other form defects.
        bare_place = _bare_place_hit(text)
        if bare_place:
            issues.append(
                f"{name} drops the article before a place ('{bare_place}') — "
                f"a real person says 'at the {bare_place[3:]}'; give the place "
                f"its article or rephrase"
            )
        # The app's controls are never worked out loud (ADR 0128): a
        # control verb governing "levels"/"sliders" speaks the UI, not
        # the feeling — the generic-vocabulary leak the feature-name
        # ban in the craft block could not see.
        ui_control = _ui_control_hit(text)
        if ui_control:
            issues.append(
                f"{name} works the app's controls out loud ('{ui_control}') — "
                f"a person names the feeling, never the slider: say what it "
                f"feels like instead"
            )
        # Live POV: a script line is spoken straight to camera in the moment.
        # Quotation marks or a self-narration verb ("I said quietly",
        # "I lean ... into the camera") turn direct speech into a report of
        # words said or a description of what the camera already shows, so
        # the draft is rewritten rather than shipped. Applies to the script
        # only: the hook is frozen as written for this rule.
        if name == "script":
            if _has_quoted_span(text):
                issues.append(
                    "script uses quotation marks — speak the line directly, "
                    "never as a quote of what the speaker said"
                )
            hit = _self_narration_hit(text)
            if hit:
                issues.append(
                    f"script narrates itself ('{hit.strip()}') — speak live "
                    "in the moment instead of reporting what was said or showing "
                    "what the camera already sees"
                )
        for sentence in _split_sentences(text):
            plain = sentence.rstrip('\"\u201d\u2019')
            if not plain.endswith((".", "!", "?")):
                issues.append(f"{name} has an unfinished sentence")
            words = _normalize_spoken(plain).split()
            if words and words[-1] in dangling:
                issues.append(f"{name} ends a sentence on '{words[-1]}'")
            if any(" ".join(words).endswith(ending) for ending in unfinished_endings):
                issues.append(f"{name} has an unfinished comparison")
        if text[0].islower():
            issues.append(f"{name} begins as a continuation rather than a standalone sentence")
    # The hook leads with the viewer's problem, not the speaker's diary: one
    # 'I' can anchor a real line, two make it narration ("Friday evening, and
    # I feel off, and I cannot say why") and the draft is rewritten through
    # the editorial loop instead.
    if len(_FIRST_PERSON_I.findall(hook)) > 1:
        issues.append(
            "hook_line narrates in first person more than once; open on the "
            "viewer's problem instead, with 'I' used at most once"
        )
    if ";" in hook:
        issues.append("hook_line joins clauses with a semicolon instead of one standalone opening")
    # A question hook is a defect unless the angle/problem itself is a
    # silent self-question (or the plan explicitly requested that shape),
    # which the caller proves with allows_question.
    if not allows_question and str(hook or "").strip().endswith("?"):
        issues.append(
            "hook_line is a question; use a question only when the problem is "
            "something viewers silently ask themselves — otherwise name it "
            "with a statement, confession, or blunt observation"
        )
    # The script never asks: the question lives in the hook, and the script
    # ends on the statement that opens the discovery. A question in the
    # LAST sentence is detectable by its form the same way the hook's
    # question is, so a draft that ends on one is rewritten through the
    # editorial loop instead of shipped. Scoped to the ending on purpose:
    # a question mid-script is the prompt's business, and the ending is
    # where the handoff to the founder's demo lives.
    script_sentences = _split_sentences(script)
    if script_sentences and _sentence_is_question(script_sentences[-1]):
        issues.append(
            "script ends on a question ('" + script_sentences[-1].strip() + "'); "
            "the script never asks one — end on a statement that names what is "
            "still unknown in the story's own terms, so the demo reads as the answer"
        )
    # A statement ending can close the story just as flatly as a
    # question (ADR 0128): if the last sentence is still the hook's
    # problem, phrased in problem words, opening nothing — no turn, no
    # new place or moment, no unknown named — it restates instead of
    # handing off, and the demo that follows has nothing to answer.
    if script_sentences and _ending_restates_problem(hook, script):
        issues.append(
            "script ends on a line that restates the hook's problem ('" + script_sentences[-1].strip() + "'); "
            "the ending must open the discovery — end on the strongest concrete "
            "line: name what is still unknown in the story's own terms, or the "
            "concrete thing that changed, so the demo reads as the answer"
        )
    # The hook must promise the outcome this video's goal certified
    # (ADR 0127). The goal step fitted the goal to the angle's certified
    # outcome; a hook whose words carry none of that outcome is promising
    # something else — the same drift as a script ending that leaves the
    # story's subject, and just as observable: the outcome's key terms
    # are either in the hook or they are not. Enforced here, in the
    # bounded editorial loop, for the same reason as the ending rule —
    # a prompt-only promise drifts. No certified outcome (older
    # projects, uncertified angles) means no check, exactly as before.
    if certified_outcome and str(hook or "").strip():
        if not hook_carries_certified_outcome(hook, certified_outcome):
            terms = certified_outcome_key_terms(certified_outcome)
            issues.append(
                "hook_line does not carry the certified outcome this video's "
                f"goal promises ('{certified_outcome}'): the hook must promise "
                "that outcome in the viewer's own words — carry its key words "
                f"({', '.join(terms)}) in the hook itself rather than "
                "promising something else"
            )
    return issues
def _summarize_line(text: str, spec: dict) -> dict:
    """One line's count, the target it aims at, and the ceiling it must hold."""
    chars = len(str(text or "").strip())
    if chars > spec["ceiling"]:
        verdict = "over_ceiling"
    elif chars < spec["target"] * (1 - TARGET_BAND):
        verdict = "under_target"
    else:
        verdict = "on_target"
    return {
        "chars": chars,
        "target": spec["target"],
        "ceiling": spec["ceiling"],
        "verdict": verdict,
    }
def _opens_a_problem(text: str) -> bool:
    """Whether an opening line names a problem rather than stating a benefit."""
    stripped = str(text or "").strip()
    if not stripped:
        return False
    if stripped.endswith("?"):
        return True
    normalized = _normalize_spoken(stripped)
    padded = f" {normalized} "
    return any(f" {marker} " in padded for marker in _PROBLEM_MARKERS)
def _closes_the_problem(text: str) -> bool:
    """Whether a body reads as resolving, rather than adding more of the same."""
    normalized = _normalize_spoken(text)
    if not normalized:
        return False
    padded = f" {normalized} "
    return any(f" {marker} " in padded for marker in _RESOLUTION_MARKERS)
_CONTINUITY_STOPWORDS = frozenset((
    "the", "a", "an", "and", "or", "but", "if", "then", "than",
    "that", "this", "these", "those", "with", "from", "have", "has",
    "had", "were", "been", "are", "was", "will", "would", "could",
    "should", "just", "very", "really", "still", "even", "also",
    "when", "what", "which", "there", "their", "they", "them",
    "into", "over", "under", "about", "after", "before", "again",
    "every", "each", "more", "most", "much", "many", "some", "such",
))
_PERSON_WORDS = frozenset((
    "mom", "mother", "dad", "father", "mama", "papa", "parent",
    "parents", "boss", "friend", "friends", "kid", "kids", "child",
    "children", "wife", "husband", "partner", "daughter", "son",
    "sister", "brother", "doctor", "therapist", "counselor", "coach",
    "coworker", "coworkers", "colleague", "colleagues", "neighbor",
    "neighbors", "teacher", "nurse", "nurses", "guy", "guys", "man",
    "men", "woman", "women", "person", "people", "team", "family",
    "roommate", "classmate", "client", "clients", "customer",
    "customers", "stranger", "strangers",
))
_BARE_LOCATION_NOUNS = frozenset((
    "place", "meeting", "office", "house", "room", "building",
    "event", "party", "store", "shop", "school", "interview",
    "appointment",
))
_SCENE_PLACES = frozenset((
    "car", "home", "house", "apartment", "flat", "dorm", "kitchen",
    "desk", "office", "couch", "sofa", "bed", "bedroom", "bathroom",
    "shower", "street", "train", "bus", "park", "gym", "store",
    "shop", "cafe", "restaurant", "diner", "bar", "work", "school",
    "library", "classroom", "porch", "driveway", "garage", "yard",
    "backyard", "garden", "sidewalk", "elevator", "lobby", "hall",
    "hallway", "stairs", "parking", "table", "counter", "window",
    "door", "doorway", "closet", "basement", "attic", "balcony",
    "patio", "deck", "playground", "field", "beach", "pool", "lake",
    "river", "trail", "woods", "forest", "city", "town", "farm",
))
_SCENE_MOMENTS = frozenset((
    "morning", "afternoon", "evening", "night", "tonight", "today",
    "yesterday", "tomorrow", "weekend", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "dawn",
    "dusk", "midnight", "noon", "lunch", "dinner", "breakfast",
    "commute", "drive", "driving", "shift", "break", "bedtime",
    "overtime", "deadline", "moment", "time", "after", "before",
    "when", "while", "during", "since", "until",
))
_PAYOFF_VERBS = frozenset((
    "open", "opens", "pull", "pulls", "reach", "reaches", "start",
    "starts", "begin", "begins", "write", "writes", "wrote",
    "written", "tap", "taps", "check", "checks", "look", "looks",
    "read", "reads", "put", "puts", "set", "sets", "close",
    "closes", "shut", "end", "ends", "finish", "finishes", "done",
    "save", "saves", "keep", "keeps", "hold", "holds", "breathe",
    "breathes", "say", "says", "said", "tell", "tells", "name",
    "names", "named", "find", "finds", "found", "leave", "leaves",
    "walk", "walks", "step", "steps", "sit", "sits",
))
def _continuity_stem(word: str) -> str:
    """A light stem so "feeling" meets "feel" and "houses" meets "house".

    Customer speech is short, so the rule is deliberately crude: strip one
    common ending only when four letters remain. A missed inflection is a
    missed echo, which is why the echo check also tries plain containment.
    """
    for suffix in ("ing", "ed", "es", "s"):
        if word.endswith(suffix) and len(word) - len(suffix) >= 4:
            stemmed = word[: -len(suffix)]
            # "houses" strips to "hous" through "es" but to "house"
            # through "s" — the longer stem wins when both survive.
            if suffix == "es" and word.endswith("s") and len(word) - 1 >= 4:
                longer = word[:-1]
                return longer if len(longer) > len(stemmed) else stemmed
            return stemmed
    return word
def _continuity_words(text: str) -> list:
    """The image-carrying words of a line: long enough to mean something."""
    return [
        word for word in _normalize_spoken(text).split()
        if len(word) >= 4 and word not in _CONTINUITY_STOPWORDS
    ]
def _words_match(first: str, second: str) -> bool:
    """Same word, same stem, or one plainly containing the other."""
    if first == second:
        return True
    if _continuity_stem(first) == _continuity_stem(second):
        return True
    short, long = (first, second) if len(first) <= len(second) else (second, first)
    return len(short) >= 5 and long.startswith(short)
def _repeats_hook_words(hook: str, script: str) -> bool:
    """Whether the script repeats the hook's words wholesale.

    One image word carried over is continuity; most of the hook's words
    repeated is restatement. Repeat is counted in distinct content stems
    (continuity words), so the punctuation and function words around them
    do not fake a restatement.
    """
    hook_words = _continuity_words(hook)
    if len(hook_words) < 3:
        return False
    script_words = _continuity_words(script)
    repeated = [
        hook_word for hook_word in hook_words
        if any(_words_match(hook_word, script_word) for script_word in script_words)
    ]
    return len(repeated) >= 2 and len(repeated) / len(hook_words) >= 0.4


def _answers_hook_first_clause(script: str) -> bool:
    """Whether the script answers the hook in its first clause.

    Read as one spoken thought: the script continues the hook and answers
    its question immediately, not after a scene-setting preamble. A first
    sentence that only sets the place carries no resolution or payoff verb.
    """
    first = _first_sentence(script)
    if not first:
        return False
    padded = f" {_normalize_spoken(first)} "
    if any(f" {marker} " in padded for marker in _RESOLUTION_MARKERS):
        return True
    return any(f" {verb} " in padded for verb in _PAYOFF_VERBS)


def _script_echoes_hook(hook: str, script: str) -> bool:
    """Whether the script echoes at least one of the hook's image words.

    A hook with no image words ("Hi.") asks nothing, so there is nothing
    to miss — vacuously true, never a flag.
    """
    hook_words = _continuity_words(hook)
    if not hook_words:
        return True
    script_words = _continuity_words(script)
    return any(
        _words_match(hook_word, script_word)
        for hook_word in hook_words
        for script_word in script_words
    )
def _dangling_references(hook: str, script: str) -> list:
    """Spans in the script that point at nothing the pair established.

    Three shapes, each matched on the words rather than the meaning: motion
    into nowhere ("walk in," with no destination), a distal demonstrative
    whose noun never appeared ("that meeting"), and a third-person pronoun
    with no person mentioned anywhere before it ("he"). "It" is excluded:
    in customer speech it almost always points at the feeling just named.
    """
    refs = []
    seen = set()

    def _add(span: str):
        key = span.lower()
        if key not in seen:
            seen.add(key)
            refs.append(span)

    text = str(script or "")
    lowered = text.lower()
    for match in re.finditer(
        r"\b(walk|go|come|head|step)s? in\b"
        r"(?!\s+(?:to|through|past|around|between|among)\b)",
        lowered,
    ):
        _add(text[match.start(): match.end()])
    tokens = [(m.group(0), m.start()) for m in re.finditer(r"[a-z0-9]+", lowered)]
    hook_stems = {_continuity_stem(word) for word in _normalize_spoken(hook).split()}

    def _established_before(position: int, extra: set = frozenset()) -> set:
        known = set(hook_stems) | set(extra)
        for word, start in tokens:
            if start >= position:
                break
            known.add(_continuity_stem(word))
        return known

    person_stems = {_continuity_stem(word) for word in _PERSON_WORDS}
    for match in re.finditer(r"\b(that|those)\s+([a-z]+)\b", lowered):
        noun = match.group(2)
        known = _established_before(match.start())
        if not any(_words_match(noun, word) for word in known):
            _add(text[match.start(): match.end()])
    for match in re.finditer(r"\b(he|him|his|she|her|they|them)\b", lowered):
        known = _established_before(match.start())
        if not (known & person_stems):
            _add(text[match.start(): match.end()])
    for match in re.finditer(r"\bthe\s+([a-z]+)\b", lowered):
        noun = match.group(1)
        if noun not in _BARE_LOCATION_NOUNS:
            continue
        known = _established_before(match.start())
        if _continuity_stem(noun) not in known:
            _add(text[match.start(): match.end()])
    return refs
def _sets_scene(script: str) -> bool:
    """Whether the opening script sentence names a place or a moment."""
    tokens = _normalize_spoken(_first_sentence(script)).split()
    words = set(tokens) | {_continuity_stem(token) for token in tokens}
    return bool(words & _SCENE_PLACES or words & _SCENE_MOMENTS)
def _ends_on_handoff(script: str) -> bool:
    """Whether the last script sentence lands a first-person payoff.

    The founder's demo and CTA follow immediately, so the script must end on
    the resolved feeling in the customer's own words — a first-person sentence
    carrying a resolution marker or a concrete payoff verb — rather than
    trailing off mid-thought.
    """
    sentences = _split_sentences(script)
    if not sentences:
        return False
    last = sentences[-1]
    padded = f" {_normalize_spoken(last)} "
    if not any(f" {pronoun} " in padded for pronoun in ("i", "me", "my", "mine", "myself")):
        return False
    if _spoken_marker_hit(last, _RESOLUTION_MARKERS):
        return True
    return any(f" {verb} " in padded for verb in _PAYOFF_VERBS)
def check_spoken_story(hook_line, script, hook_seconds=3, total_seconds=12, app_name="") -> dict:
    """
    Both spoken lines measured, and read as ONE story.

    Counts each line against the target it aims at and the ceiling it must
    hold, and reads the two together: the hook should open a problem — a
    question, a cost, something the viewer is doing that keeps failing — and
    the script should close the one the hook opened, rather than restating it
    or answering a different question.

    Nothing here refuses anything. The ceiling is what the render enforces and
    an under-target line is a choice, so the story verdict is reported to the
    founder rather than acted on. The continuity flags below are the same kind
    of report: a dangling reference or an unanswered hook image is craft, not
    an observable defect, so it is flagged for the founder instead of
    rewritten — the third failed editorial attempt must never destroy a plan
    over it. Pure, so the Review step and the render path measure the same
    words the same way.

    `app_name` adds the one check that cannot live in the prompt: whether the
    customer's own line names the product they are talking about, which is
    promotion however the sentence is worded. Reported, never acted on — a veto
    would take a whole plan down the moment an app was named after a common
    noun ("Journal", "Notes"), and the founder can see the flag and fix the
    line themselves.
    """
    targets = spoken_targets(hook_seconds, total_seconds)
    hook = str(hook_line or "").strip()
    body = str(script or "").strip()
    story = {
        "problem_in_hook": _opens_a_problem(hook),
        "resolution_in_script": _closes_the_problem(body),
        # The plan's script is written as the whole piece, so a copy of the
        # hook at its head is the hook being said twice rather than a middle.
        "restates_hook": bool(hook and body) and strip_leading_hook(hook, body) != body,
        # One continuous thought, read across the boundary: every reference
        # established, the hook's image echoed, the scene set, the handoff
        # landed. Reported, never acted on — see the docstring.
        "dangling_refs": _dangling_references(hook, body),
        "echoes_hook": _script_echoes_hook(hook, body),
        "sets_scene": _sets_scene(body),
        "ends_on_handoff": _ends_on_handoff(body),
        # Live-POV checks (future generation only): the script speaks
        # directly, answers the hook's question at once, and never repeats
        # the hook's words wholesale. Reported like the flags above.
        "repeats_hook_words": _repeats_hook_words(hook, body),
        "answers_hook_first_clause": bool(hook) and _answers_hook_first_clause(body),
        "has_quoted_span": _has_quoted_span(body),
        "self_narrates": bool(_self_narration_hit(body)),
        "vague_payoff": _vague_payoff(body),
    }
    # Only a name long enough to be a real product name, and never the short
    # generic one that would match ordinary speech.
    named = str(app_name or "").strip()
    if len(named) >= 5:
        needle = _normalize_spoken(named)
        spoken = f" {_normalize_spoken(hook)} {_normalize_spoken(body)} "
        story["names_the_app"] = bool(needle) and f" {needle} " in spoken
        story["generic_phrasing"] = bool(
            _spoken_marker_hit(hook, _AI_FLUFF_MARKERS)
            or _spoken_marker_hit(body, _AI_FLUFF_MARKERS)
        )
    story["coherent"] = bool(
        story["problem_in_hook"] and story["resolution_in_script"] and not story["restates_hook"]
    )
    return {
        "hook": _summarize_line(hook, targets["hook"]),
        "script": _summarize_line(body, targets["script"]),
        "story": story,
        "hook_seconds": targets["hook_seconds"],
        "middle_seconds": targets["middle_seconds"],
        "over_ceiling": bool(
            len(hook) > targets["hook"]["ceiling"] or len(body) > targets["script"]["ceiling"]
        ),
    }
def repair_spoken_story(plan, hook_seconds=3, total_seconds=12) -> tuple:
    """
    Validate the two spoken lines before a render, and rewrite what cannot be spoken.

    Returns (words, report). `words` holds `hook_line` and `script` exactly as
    the video model must receive them; nothing else from the plan is touched.
    The rewrite is the partition rule and nothing more:

    - a hook line longer than its seconds is cut back to its opening sentence,
      and what comes off is spoken at the head of the middle instead of being
      deleted. The words stay in the video; they simply stop being the opening
      line, which is what "the hook names the problem and the script answers
      it" means in practice — a resolution that had drifted into the hook is
      handed to the middle that has to carry it;
    - a middle longer than its seconds keeps its opening and its resolving
      sentence and gives up the sentences in between, so the payoff survives
      the cut.

    No model call and no provider request: this is arithmetic on the founder's
    own words, run inside the render path so the words measured here are the
    words sent. The report carries the count either side of the rewrite and
    every change made, so a shortened line is reported rather than silent.
    """
    source = plan if isinstance(plan, dict) else {}
    hook_line = str(source.get("hook_line") or "").strip()
    script = str(source.get("script") or "").strip()
    hook_seconds = hook_seconds or 3
    total_seconds = total_seconds or 0

    part = partition_spoken_words(source, hook_seconds, total_seconds)
    spoken_hook = part["hook_line"]

    changes = []
    if spoken_hook != hook_line:
        changes.append({
            "field": "hook_line",
            "reason": "over_ceiling",
            "removed_chars": part["hook_dropped_chars"],
            "moved_to_script": len(part["hook_spill"]),
        })
    if hook_line and strip_leading_hook(hook_line, script) != script:
        # The script opened with the hook, so the two lines said the same thing
        # twice and the hook's characters were charged to the middle's seconds.
        changes.append({"field": "script", "reason": "restated_hook"})
    if part["dropped_chars"]:
        changes.append({
            "field": "script",
            "reason": "over_ceiling",
            "removed_chars": part["dropped_chars"],
            "kept_chars": len(part["kept"]),
        })

    report = {
        "before": check_spoken_story(hook_line, script, hook_seconds, total_seconds),
        "after": check_spoken_story(spoken_hook, part["kept"], hook_seconds, total_seconds),
        "changes": changes,
        "rewritten": bool(changes),
        "middle_seconds": part["middle_seconds"],
    }
    return {"hook_line": spoken_hook, "script": part["kept"]}, report
def trim_to_sentence(text: str, limit: int):
    """
    The longest prefix of `text` that fits `limit` and stops at a sentence.

    Returns (kept, dropped). A mid-sentence cut would lop the payoff — usually
    the last sentence — and a hard cut mid-word is a visible fault in a line
    someone has to debug, so the order is: sentence boundary, then word
    boundary, then a hard cut only when neither exists.
    """
    text = str(text or "").strip()
    if not text or limit <= 0 or len(text) <= limit:
        return text, 0
    window = text[:limit]
    cut = max(window.rfind("."), window.rfind("!"), window.rfind("?"))
    if cut >= 0:
        kept = window[: cut + 1].strip()
    else:
        space = window.rfind(" ")
        kept = (window[:space] if space > 0 else window).strip()
    return kept, len(text) - len(kept)
def _normalize_spoken(text: str) -> str:
    """
    Lowercase, drop punctuation, collapse whitespace. For comparing words only.

    Two strings that would be spoken identically normalize to the same string,
    which is what lets the hook line be found in a script that introduces it
    rather than starting with it verbatim.
    """
    chars = []
    for ch in str(text or "").lower():
        chars.append(ch if ch.isalnum() else " ")
    return " ".join("".join(chars).split())
def _first_sentence(text: str) -> str:
    """
    The opening sentence of `text`, or all of it when it has no terminator.

    A terminator only ends the sentence when what follows is a space, an
    earlier abbreviation's period ("Dr. Smith") is left alone, and the closing
    mark is included so a lead-in is cut with the rest.
    """
    stripped = str(text or "").strip()
    for index, ch in enumerate(stripped):
        if ch not in ".!?":
            continue
        following = stripped[index + 1: index + 2]
        if following == "" or following in " \n\t":
            return stripped[: index + 1]
    return stripped
def strip_leading_hook(hook_line: str, script: str) -> str:
    """
    Remove the hook line from the front of the script, returning what is left.

    The plan's `script` is written as the whole piece, so it normally opens with
    the hook line. Leaving that copy in means the middle speaks the hook a
    second time, and the hook's characters are then charged to the middle's
    budget -- which the render reports as an overflow and refuses.

    This used to be an exact `startswith` test, so any introduction defeated it
    ("So, <hook line>? ..." is the same words, differently opened). The hook is
    therefore matched at the sentence, on normalized text, and the first
    sentence is treated as the hook when it carries the hook's words and is
    little more than a lead-in to them. A script that does not open with the
    hook at all is left completely alone: its two sections are separate texts,
    and nothing needs removing.
    """
    hook = _normalize_spoken(hook_line)
    body = str(script or "").strip()
    if not hook or not body:
        return body

    normalized = _normalize_spoken(body)
    if normalized.startswith(hook):
        return body[len(str(hook_line).strip()):].lstrip(" ,.!?;:-")

    opening = _first_sentence(body)
    opening_normalized = _normalize_spoken(opening)
    # The lead-in tolerance is deliberately small. A first sentence that merely
    # contains the hook somewhere is far more likely to be the middle than the
    # hook, and cutting it would delete the founder's actual words.
    lead_in = len(hook) + 30
    if hook in opening_normalized and len(opening_normalized) <= lead_in:
        return body[len(opening):].lstrip(" ,.!?;:-")
    return body
def partition_spoken_words(plan, hook_seconds=3, total_seconds=12) -> dict:
    """
    The single rule for how the approved words divide between hook and middle.

    Returns hook_line, the middle as written, the part of the middle that fits
    its seconds, and how many characters did not. Every consumer reads this:
    the plan clamp that sizes a freshly generated script, the binding that
    rewrites a strategy's spoken lines, and the render gate that refuses an
    over-length script. A second implementation of the arithmetic here would
    mean a plan the clamp called short and the gate calls long, which is the one
    disagreement a founder cannot act on.

    `total_seconds` and `hook_seconds` must be passed exactly as the render gate
    passes them, or the two will not agree on what fits.
    """
    hook_line = ""
    script = ""
    if isinstance(plan, dict):
        hook_line = str(plan.get("hook_line") or "").strip()
        script = str(plan.get("script") or "").strip()

    targets = spoken_targets(hook_seconds, total_seconds)

    # The hook is counted FIRST, and against its own seconds. It used to pass
    # through untouched, which is how a hook line several times the length of
    # the opening beat was stored, bound into section 0, and cut mid-sentence by
    # the prompt builder with nothing telling the founder. The cut keeps the
    # opening sentence and hands the rest to the middle below, so the words are
    # still spoken — just after the hook, which is where a resolution belongs.
    spoken_hook, hook_dropped = _trim_hook_line(hook_line, targets["hook"]["ceiling"])
    # Only the front is cleaned: the cut can leave a leading mark behind it,
    # and the closing mark belongs to the sentence the spill ends with.
    hook_spill = hook_line[len(spoken_hook):].lstrip(" ,.!?;:-") if spoken_hook else ""

    middle_text = strip_leading_hook(hook_line, script)
    if hook_spill:
        middle_text = f"{hook_spill} {middle_text}".strip() if middle_text else hook_spill

    budget = targets["script"]["ceiling"]
    kept, dropped = trim_spoken_body(middle_text, budget)
    return {
        "hook_line": spoken_hook,
        "hook_spill": hook_spill,
        "hook_dropped_chars": hook_dropped,
        "middle_text": middle_text,
        "kept": kept,
        "dropped_chars": dropped,
        "budget": budget,
        "target": targets["script"]["target"],
        "hook_target": targets["hook"]["target"],
        "middle_seconds": targets["middle_seconds"],
    }
def bind_spoken_words(strategy: dict, plan, hook_seconds=3, total_seconds=12):
    """
    Rewrite the strategy's spoken words from the plan's approved words.

    Returns (strategy, overflow). `overflow` is {} when everything fits and
    {"dropped_chars", "budget", "middle_seconds"} when the approved script is
    longer than the middle can speak. That record is recomputed, not stored: it
    is a pure function of (plan, seconds), so the render gate and the public
    project serializer can derive it fresh and a strategy PATCH cannot drop it.

    When there is no approved plan, nothing is rebound — a strategy built
    without one keeps the model's words, which is the legacy path, and no
    overflow is reported because there is nothing to overflow.

    The returned strategy is a copy: binding mutates the sections, and the
    caller's dict must not gain words it did not ask for.
    """
    import copy

    if not isinstance(strategy, dict):
        return strategy, {}
    part = partition_spoken_words(plan, hook_seconds, total_seconds)
    hook_line = part["hook_line"]
    middle_text = part["middle_text"]
    if not hook_line and not middle_text:
        return strategy, {}

    strategy = copy.deepcopy(strategy)
    kept = part["kept"]

    sections = strategy.get("segments")
    if isinstance(sections, list):
        if hook_line:
            if len(sections) > 0 and isinstance(sections[0], dict):
                sections[0]["script"] = hook_line
            if len(sections) > 1 and isinstance(sections[1], dict):
                sections[1]["script"] = kept
        elif len(sections) > 1 and isinstance(sections[1], dict):
            sections[1]["script"] = kept
    if hook_line:
        strategy["hook_line"] = hook_line

    overflow = (
        {
            "dropped_chars": part["dropped_chars"],
            "budget": part["budget"],
            "middle_seconds": part["middle_seconds"],
        }
        if part["dropped_chars"]
        else {}
    )
    return strategy, overflow
def strategy_text(strategy: dict) -> str:
    """
    Flatten every human-readable string in a strategy.
    Used by claim safety so the strategy's own wording — the hook line, the
    spoken script, the promises — is checked exactly like the plan's is. A
    banned claim that appears only in the strategy is still a banned claim.
    """
    if not isinstance(strategy, dict):
        return ""
    parts: list = []
    for key, value in strategy.items():
        if isinstance(value, str):
            parts.append(value)
        elif isinstance(value, dict):
            parts.extend(v for v in value.values() if isinstance(v, str))
            for nested in value.values():
                if isinstance(nested, list):
                    parts.extend(str(v) for v in nested)
        elif isinstance(value, list):
            for item in value:
                if isinstance(item, str):
                    parts.append(item)
                elif isinstance(item, dict):
                    parts.extend(str(v) for v in item.values() if isinstance(v, str))
    return " \n ".join(p for p in parts if p.strip())
def trend_evidence_sentence(evidence) -> str:
    """
    Render a template's anonymous trend aggregate as one prompt sentence.

    Kept here rather than imported from a research helper so the strategy
    path does not pull in extra modules; the format is a small
    contract between the scan and the prompt, and the two sides assert the same
    fields in the same way.

    Returns "" when there is no signal, and the caller omits the whole section
    rather than printing a heading with nothing under it.
    """
    if isinstance(evidence, str):
        try:
            evidence = json.loads(evidence)
        except (json.JSONDecodeError, TypeError):
            return ""
    if not isinstance(evidence, dict) or not evidence.get("has_signal"):
        return ""
    sample = evidence.get("sample_size") or 0
    if not sample:
        return ""
    return (
        f"Across {sample} public openings of this shape in the last scan, the median one had "
        f"{evidence.get('median_view_band', 'unknown')} views and "
        f"{evidence.get('median_engagement_band', 'unknown')} engagement "
        f"({evidence.get('recency_band', 'unknown')}). This is what similar shapes have "
        f"carried, not a promise about any single video."
    )


def _trim_hook_line(text: str, limit: int):
    """
    Cut a hook line back to fit `limit`, keeping it readable as an opening.

    Sentence boundary first. When the opening sentence is itself longer than
    the limit there is no sentence to cut at, so the cut lands on a word
    boundary — and a line cut that way loses its terminator along with its
    tail. The terminator is restored from the sentence the cut came out of,
    because punctuation is not spoken: "Do you know what triggers your emotions
    and keeps them" is a fragment, while "...and keeps them?" is the question
    it was.
    """
    text = str(text or "").strip()
    if not text or limit <= 0 or len(text) <= limit:
        return text, 0
    kept, _dropped = trim_to_sentence(text, limit)
    if kept and kept[-1] not in ".!?":
        for index, ch in enumerate(text):
            if ch in ".!?" and index >= len(kept) - 1:
                kept = kept + ch
                break
    return kept, len(text) - len(kept)
