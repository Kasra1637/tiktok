"""Advisory craft score for the two spoken lines.

The score answers "is this a good customer story?" before a render, not "may
this render?" It never refuses anything and is not part of the submit path.
The deterministic gates in `ai_spoken` stay the only hard checks; this module
adds the semantic layer they cannot see: a diary opening, a vague stand-in for
the real action, a written-sounding sentence, or a story that resolves before
the demo has a question to answer.

Pure policy: no HTTP, AI, auth or persistence imports. A function of the two
lines and their seconds, so Review and an offline eval measure the same words
the same way.
"""
import re

import ai_spoken
import final_beat

VERSION = 1

_DIMENSIONS = (
    ("hook_stopping_power", "Hook stopping power", 20),
    ("audience_truth", "Audience truth / customer voice", 15),
    ("clarity", "Clarity / one thought", 10),
    ("concreteness", "Concreteness", 10),
    ("story_arc", "Story arc / payoff", 15),
    ("spoken_naturalness", "Spoken naturalness", 10),
    ("demo_handoff", "Demo handoff", 10),
    ("trust_compliance", "Trust & compliance", 10),
)

# The most each category can actually award (ADR 0300). Every scorer
# clamps to its weight, but two cannot reach it: Hook's positive cues
# sum to 17 of its 20, and Audience truth's to 13 of its 15 — so the
# report's honest ceiling is 95, not the 100 the weights sum to. The
# 0-10 display scale divides by these caps, never by the weights, so
# a perfect pair reads 10, zero reads 0, and every category bar can
# fill. The points themselves do not move: the scorer is untouched.
_ACHIEVABLE_MAX = {"hook_stopping_power": 17, "audience_truth": 13}


def _achievable_max(key, weight):
    return _ACHIEVABLE_MAX.get(key, weight)


def _score10(score, achievable):
    """The honest 0-10 reading of a points score (ADR 0300)."""
    if achievable <= 0:
        return 0.0
    return round(score / achievable * 10, 1)


def with_score10(report):
    """Fill the 0-10 fields into a report stored before ADR 0300.

    Reports are frozen at submit (ADR 0117); one saved before the
    scale change carries points only. The fill is computed from the
    report's own dimensions, so an old render reads on the same
    true scale as a fresh one. A report already carrying the fields
    is returned unchanged.
    """
    if not isinstance(report, dict) or "score10" in report:
        return report
    dimensions = report.get("dimensions") or {}
    achievable_total = 0
    for key, dimension in dimensions.items():
        if not isinstance(dimension, dict):
            continue
        achievable = _achievable_max(
            key, dimension.get("weight") or dimension.get("max") or 0
        )
        dimension.setdefault("achievable_max", achievable)
        dimension.setdefault(
            "score10", _score10(dimension.get("score") or 0, achievable)
        )
        achievable_total += achievable
    if achievable_total <= 0:
        achievable_total = sum(
            _achievable_max(key, weight) for key, _label, weight in _DIMENSIONS
        )
    report["achievable_max"] = achievable_total
    report["score10"] = _score10(report.get("total") or 0, achievable_total)
    report["max10"] = 10
    return report

# Normalized cues: punctuation is stripped before matching, so "can't" is
# "can t" and "weren't" is "weren t". Every cue is a whole phrase surrounded
# by spaces, never a substring.
_PROBLEM_CUES = (
    "can t", "cannot", "couldn t", "don t", "doesn t", "didn t", "won t",
    "never", "always", "kept", "keeps", "again", "stuck", "tired", "hate",
    "waste", "wasting", "hard", "harder", "hardest", "wrong", "lost",
    "losing", "overwhelmed", "random", "flat", "slump", "crash", "numb",
    "off", "dread", "mess", "struggle", "struggling", "wish", "why",
    "how come", "what if", "until", "problem", "failing", "forgetting",
    "guessing", "endless", "too much", "bad", "worse", "worst", "heavy",
    "exhausted", "burned out", "burnt out", "spiraling", "anxious",
    "lonely", "foggy", "unpredictable",
)
_CURIOSITY_CUES = (
    "until", "thought", "wasn t", "weren t", "didn t", "never", "but",
    "not", "actually", "turns out", "used to", "random", "kept",
    "every time", "still", "even though", "instead", "then",
)
_CONCRETE_CUES = (
    "morning", "mornings", "afternoon", "afternoons", "evening", "evenings",
    "night", "nights", "week", "weeks", "weekend", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "garden",
    "desk", "kitchen", "commute", "car", "bus", "train", "shower", "bed",
    "office", "gym", "walk", "run", "stretch", "stretching", "coffee",
    "phone", "journal", "notebook", "calendar", "meeting", "lunch",
    "dinner", "breakfast", "door", "window", "street", "park", "store",
    "shop", "school", "work", "couch", "sofa", "porch", "yard", "table",
    "mirror", "teeth", "hair", "shoes", "bag", "keys", "email", "inbox",
    "laundry", "bakery", "cafe", "paper bag",
    # The lived environment between the landmarks (ADR 0188): the steps,
    # platforms and queues a moment actually happens on. Real scripts
    # named these and scored as if the scene were abstract, because the
    # lists stopped at rooms and furniture.
    "steps", "stairs", "hallway", "platform", "station", "counter",
    "queue", "doorway", "parking lot", "sidewalk", "bench", "bus stop",
    "waiting room", "driveway", "elevator", "announcement",
)
_PLACE_CUES = (
    "garden", "desk", "kitchen", "office", "car", "bus", "train", "shower",
    "bed", "couch", "sofa", "porch", "yard", "street", "park", "store",
    "shop", "school", "gym", "bathroom", "bedroom", "balcony", "patio",
    "bakery", "cafe",
    # ADR 0188: the in-between places a scene is actually set in.
    "steps", "stairs", "hallway", "platform", "station", "counter",
    "queue", "doorway", "parking lot", "sidewalk", "bench", "bus stop",
    "waiting room", "driveway", "elevator",
)
_ACTION_CUES = (
    "stretch", "stretching", "walk", "walking", "talk", "talked", "talking",
    "speak", "speaking", "write", "wrote", "writing", "run", "running",
    "cook", "cooking", "clean", "cleaning", "drive", "driving", "sit",
    "sitting", "stand", "standing", "breathe", "breathing", "shower",
    "journal", "note", "coffee", "tea",
    # ADR 0188: the small physical verbs of waiting and getting there.
    "climb", "climbing", "climbed", "wait", "waiting", "carry",
    "carrying", "hold", "holding",
)
_TIME_CUES = (
    "morning", "mornings", "afternoon", "afternoons", "evening", "evenings",
    "night", "nights", "week", "weeks", "weekend", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "lunch",
    "dinner", "breakfast",
    # ADR 0188: the day's named appointments anchor a moment like a
    # mealtime does.
    "commute", "school run", "workout", "break time",
)
_SENSORY_CUES = (
    "warm", "cold", "tight", "breath", "shoulders", "chest", "jaw", "light",
    "rain", "sun", "coffee", "tea", "blanket", "pillow", "water", "sweat",
    "heartbeat", "quiet", "loud", "paper bag",
    # ADR 0188: what a place sounds like grounds the scene too.
    "announcement", "announcements", "noise", "noisy", "buzzing", "ringing",
)
_ABSTRACT_NOUNS = (
    "mood", "moods", "feeling", "feelings", "energy", "vibes", "mental",
    "space", "journey", "healing", "shift", "shifts", "surprise", "rhythm",
    "pattern", "awareness", "mindset", "wellness", "balance", "calm",
    "anxiety", "stress",
)
_APP_BEHAVIOR_CUES = (
    "look back", "check my week", "review my week", "open the app", "scroll",
    "log my", "track my", "chart", "graph", "dashboard", "weekly view",
    "streak", "insights", "speak my days", "speak my day", "record my day",
    "voice note", "tap the", "tap my", "screen", "app",
)
_FOUNDER_CUES = (
    "we", "our", "users", "founders", "solution", "empower", "transform",
    "journey", "seamless", "revolutionary", "game changer",
)
_PROMOTION_CUES = (
    "download", "install", "sign up", "try it", "follow", "link in bio",
    "get the app", "our app", "buy", "subscribe", "comment below",
    "tag a friend",
)
_INSIGHT_CUES = (
    "tend to", "notice", "noticed", "realized", "realised", "understood",
    "figured out", "pattern", "kept", "keeps", "always", "after", "when",
    "because", "there it was", "every time", "that s why", "turns out",
)
_RESOLUTION_CUES = (
    "now", "so i", "instead", "finally", "turns out", "the fix", "fixes",
    "fixed", "solves", "solved", "helps", "helping", "lets you", "let me",
    "no more", "never again", "since then", "started", "made it", "makes it",
    "gives you", "which is why", "that s why", "the answer", "written down",
    "stops", "worked", "steadier", "calmer", "lighter", "clearer", "spot",
    "name", "know", "understood", "realized", "figured",
)
_GAP_CUES = (
    "but not", "still", "don t know", "didn t know", "wish", "can t",
    "couldn t", "what sets", "why", "how", "need", "want", "looking for",
    "not sure", "no idea", "left me", "open question", "only just",
)
_CLOSURE_CUES = (
    "feels steadier", "feel steadier", "i can spot", "finally", "now i know",
    "fixed", "solved", "better", "calm", "at peace", "figured it out",
    "i m fine", "it s fine",
)
_WRITTEN_CUES = (
    "journey", "space", "rhythm", "steadier", "surprise feels", "tend to",
    "notice", "in my body", "held space", "leaning into", "unpack",
    "narrative", "chapter", "season of life", "self care", "wellness",
)
_UNCLEAR_CUES = ("that surprise feels", "this feels", "that feels", "it feels")
# Journal-entry framings: the line opens by reporting the speaker's own
# diary ("I've been...", "I keep...") instead of stepping into a moment.
# Time-led openers ("Friday morning...", "every morning I...") are NOT
# here (ADR 0145): they anchor the moment, and the founder's strongest
# hooks lead with the moment in first person. Only the self-reporting
# frames remain — the diary is the framing, never the person.
_JOURNAL_OPENERS = (
    "i ve been", "i have been", "i was", "i m just", "i keep",
)

_FRONTED_MODIFIER = re.compile(
    r"^(?:in|at|on|from|through|after|before)\s+[^,]{0,50}\w+(?:ing|ed)\s*,",
    re.IGNORECASE,
)
_CONTRACTION = re.compile(r"\b\w+['\u2019](?:t|re|ve|ll|d|m)\b", re.IGNORECASE)
_FIRST_PERSON = re.compile(r"\b(?:i|me|my|mine|myself)\b")


def _clamp(value, low, high):
    return max(low, min(high, int(value)))


def _norm(text):
    return ai_spoken._normalize_spoken(text)


def _sentences(text):
    return ai_spoken._split_sentences(text)


def _words(text):
    return _norm(text).split()


def _hits(text, cues):
    """Whole-phrase hits in normalized text; never a substring match."""
    normalized = f" {_norm(text)} "
    return [cue for cue in cues if f" {cue} " in normalized]


def _first_person(text):
    return _FIRST_PERSON.findall(_norm(text))


def _has_trigger(text):
    words = _words(text)
    triggers = {"after", "before", "when", "whenever", "every", "on", "during"}
    for index, word in enumerate(words):
        if word in triggers and any(
            candidate in _CONCRETE_CUES for candidate in words[index + 1:index + 4]
        ):
            return True
    return False


def _journal_opener(hook):
    normalized = _norm(hook)
    return any(normalized.startswith(prefix) for prefix in _JOURNAL_OPENERS)


def _app_behavior(text):
    return bool(_hits(text, _APP_BEHAVIOR_CUES))


def _last_sentence(text):
    sentences = _sentences(text)
    return sentences[-1] if sentences else ""


def _has_gap(last):
    return bool(_hits(last, _GAP_CUES))


def _has_closure(last):
    return bool(_hits(last, _CLOSURE_CUES))


def _names_question(last):
    return bool(_hits(last, ("what sets", "why", "how", "what if", "what makes")))


def _score_hook(hook, cover=""):
    if not hook.strip():
        return 0, ["No hook line to score."], "Write a hook that names the viewer's problem."
    # The opening moment is scored whole (ADR 0145): the spoken hook and
    # the cover text land in the same first two seconds, so the cues are
    # read over both. The cover can carry the anchor the spoken line
    # leaves out — and the evidence says when it did, so the founder sees
    # the cover's contribution instead of a number that silently moved.
    opening = f"{hook} {cover}".strip()
    score = 7
    evidence = []
    problems = _hits(opening, _PROBLEM_CUES)
    if problems:
        score += 3
        evidence.append(f"Names a cost or recurring problem ('{problems[0]}').")
    else:
        evidence.append("No clear cost or problem cue; the line states a situation.")
    concrete = _hits(hook, _CONCRETE_CUES)
    if concrete:
        score += 2
        evidence.append(f"Has a concrete anchor ('{concrete[0]}').")
    elif cover and (cover_concrete := _hits(cover, _CONCRETE_CUES)):
        score += 2
        evidence.append(f"The cover text carries the concrete anchor ('{cover_concrete[0]}').")
    else:
        evidence.append("No concrete time, place or object in the hook.")
    if _hits(opening, _CURIOSITY_CUES):
        score += 2
        evidence.append("Creates a contrast or curiosity gap.")
    if len(hook.strip()) <= 60 and len(_words(hook)) <= 12:
        score += 2
        evidence.append("Compressed enough to land in the first three seconds.")
    # First person is deliberately NOT paid here (ADR 0188): it was
    # earning in Hook, Audience truth and Demo handoff at once, so one
    # trait moved three scores. Its one home is Audience truth, the
    # customer-voice category; this category pays for what stops the
    # scroll — the problem, the anchor, the gap, the compression.
    if _has_trigger(opening):
        score += 1
        evidence.append("Names a trigger the viewer can recognise.")
    if _journal_opener(hook):
        score -= 3
        evidence.append("Opens as a journal entry, so the viewer is overhearing rather than being addressed.")
    if _app_behavior(opening):
        score -= 2
        evidence.append("Narrates using the app ('look back' / a screen) that the generated clip never shows.")
    if _hits(opening, _PROMOTION_CUES):
        score -= 5
        evidence.append("Asks for a download, follow or sign-up instead of opening a problem.")
    abstract = _hits(opening, _ABSTRACT_NOUNS)
    if abstract:
        score -= min(3, len(abstract))
        evidence.append(f"Abstract mood words carry the idea ({', '.join(abstract[:3])}).")
    return _clamp(score, 0, 20), evidence, (
        "Open on the moment, one concrete detail, the "
        "resolution withheld; cut any app-behavior cue."
    )


def _score_audience(hook, script):
    if not hook.strip() and not script.strip():
        return 0, ["No spoken lines to score."], "Write a hook and a script first."
    combined = f"{hook} {script}"
    score = 9
    evidence = []
    # First person is how the viewer talks about their own life (ADR
    # 0145): a hook spoken as the person living it sounds true; a hook
    # that only reports the viewer in the third person sounds written
    # about them. This is first person's ONE home (ADR 0188): Hook and
    # Demo handoff used to pay for it too, so the same words moved
    # three category scores at once.
    first = _first_person(hook)
    if first:
        score += 2
        evidence.append("The hook speaks in first person, the way the viewer talks about their own life.")
    else:
        score -= 1
        evidence.append("The hook never speaks as the viewer; it reports them in the third person.")
    abstract = _hits(combined, _ABSTRACT_NOUNS)
    if abstract:
        score -= min(2, len(abstract))
        evidence.append(f"Generic mood language ({', '.join(abstract[:2])}) stands in for the viewer's own words.")
    if _hits(combined, _CONCRETE_CUES):
        score += 1
        evidence.append("Uses a routine or object the viewer recognises.")
    if _app_behavior(combined):
        score -= 2
        evidence.append("Describes using the app rather than a moment in the viewer's life.")
    if _hits(combined, _PROMOTION_CUES):
        score -= 2
        evidence.append("A promotional ask appears in a customer line.")
    if _hits(combined, _FOUNDER_CUES):
        score -= 2
        evidence.append("Founder or marketer voice appears in a customer line.")
    if _hits(combined, ("you", "your")):
        score += 1
        evidence.append("Addresses the viewer directly.")
    return _clamp(score, 0, 15), evidence, (
        "Write it as something the viewer would say about their own week, not "
        "a report of using the app."
    )


def _score_clarity(hook, script):
    if not hook.strip() and not script.strip():
        return 0, ["No spoken lines to score."], "Write a hook and a script first."
    score = 7
    evidence = []
    sentences = _sentences(hook) + _sentences(script)
    long = [sentence for sentence in sentences if len(_words(sentence)) > 24]
    if long:
        score -= min(3, len(long))
        evidence.append(f"{len(long)} sentence(s) run past 24 words.")
    else:
        score += 2
        evidence.append("Every sentence stays short enough to follow on one listen.")
    if len(_words(hook)) <= 12:
        score += 1
        evidence.append("The hook is one short thought.")
    if _hits(f"{hook} {script}", _UNCLEAR_CUES):
        score -= 1
        evidence.append("A demonstrative ('that surprise feels') makes the subject unclear.")
    return _clamp(score, 0, 10), evidence, (
        "Keep one thought; replace 'shifts' / 'that surprise' with the concrete "
        "thing that happened."
    )


def _score_concreteness(hook, script):
    if not hook.strip() and not script.strip():
        return 0, ["No spoken lines to score."], "Write a hook and a script first."
    combined = f"{hook} {script}"
    score = 3
    evidence = []
    if _hits(combined, _PLACE_CUES):
        score += 2
        evidence.append("A place is named.")
    if _hits(combined, _ACTION_CUES):
        score += 2
        evidence.append("A physical action is named.")
    if _time := _hits(combined, _TIME_CUES):
        score += 2
        evidence.append(f"A time or routine is named ('{_time[0]}').")
    if _hits(combined, _SENSORY_CUES):
        score += 1
        evidence.append("A sensory or body detail grounds the scene.")
    abstract = _hits(combined, _ABSTRACT_NOUNS)
    if abstract:
        score -= min(3, len(abstract))
        evidence.append(f"Abstract nouns carry part of the meaning ({', '.join(abstract[:3])}).")
    if ai_spoken._vague_payoff(script):
        score -= 2
        evidence.append("The payoff is a vague stand-in, not a specific lived thing.")
    return _clamp(score, 0, 10), evidence, (
        "Add one place, one routine and one time trigger so the line can be "
        "seen, not just understood; end on a specific payoff, never a vague stand-in."
    )


def _score_story(hook, script, check):
    if not hook.strip() or not script.strip():
        return 0, ["Both lines are needed to score the story."], "Write both lines as one story."
    score = 0
    evidence = []
    problems = _hits(hook, _PROBLEM_CUES)
    if problems:
        score += 3 if len(problems) >= 2 else 2
        evidence.append(f"The hook opens a problem ('{problems[0]}').")
    elif _hits(hook, ("bad", "off", "flat", "heavy", "tired", "numb", "anxious", "lonely")):
        score += 1
        evidence.append("The hook names a negative state, but not yet a concrete problem.")
    else:
        evidence.append("The hook states a situation rather than a problem.")
    if _hits(script, _INSIGHT_CUES):
        score += 3
        evidence.append("The script answers with an insight, not a restatement.")
    # The arc completes in the demo, not in the last line (ADR 0145): a
    # turn or a name earned mid-script is story craft and still earns,
    # but the resolution cues are read before the last sentence only —
    # a script that resolves in its final line closes the very question
    # Demo handoff needs open, and the two dimensions must not pay for
    # opposite endings. The open ending itself is NOT paid here (ADR
    # 0188): it was earning in Story arc and Demo handoff at once. Its
    # one home is Demo handoff, the category that owns the last line;
    # this category keeps the problem, the insight and the mid-script
    # shift.
    sentences = _sentences(script)
    before_last = " ".join(sentences[:-1]) if len(sentences) > 1 else ""
    if before_last and _hits(before_last, _RESOLUTION_CUES):
        score += 3
        evidence.append("The script lands a shift or a name for what changed before its last line.")
    story = check.get("story") or {}
    if story.get("echoes_hook"):
        score += 1
        evidence.append("The script echoes the hook's image.")
    if story.get("sets_scene"):
        score += 1
        evidence.append("The script opens in a scene.")
    if not story.get("restates_hook"):
        score += 1
        evidence.append("The script does not simply repeat the hook.")
    if _hits(script, _ACTION_CUES):
        score += 1
        evidence.append("A concrete action precedes the insight.")
    if not _app_behavior(script):
        score += 1
        evidence.append("The story stays out of the app's screens.")
    if not story.get("dangling_refs"):
        score += 1
        evidence.append("Every reference is established.")
    if story.get("repeats_hook_words"):
        score -= 2
        evidence.append("The script repeats the hook's words instead of continuing it.")
    if story.get("has_quoted_span"):
        score -= 2
        evidence.append("A quotation reports the speaker's words instead of speaking them live.")
    if story.get("self_narrates"):
        score -= 2
        evidence.append("The script narrates itself or describes what the camera shows.")
    if not story.get("answers_hook_first_clause"):
        score -= 1
        evidence.append("The script does not answer the hook in its first clause.")
    if story.get("vague_payoff"):
        score -= 2
        evidence.append("The payoff names a vague stand-in ('a word', 'that vague sense').")
    return _clamp(score, 0, 15), evidence, (
        "Answer the hook in the first clause and land the shift before "
        "the last line; leave the last line open, on the question the "
        "demo answers — that ending is scored in Demo handoff. Never a "
        "quote, a narration, a repeat of the hook, or a vague stand-in."
    )


def _score_naturalness(hook, script):
    if not hook.strip() and not script.strip():
        return 0, ["No spoken lines to score."], "Write a hook and a script first."
    combined = f"{hook} {script}"
    score = 8
    evidence = []
    sentences = _sentences(hook) + _sentences(script)
    long = [sentence for sentence in sentences if len(_words(sentence)) > 18]
    if long:
        score -= min(4, 2 * len(long))
        evidence.append(f"{len(long)} sentence(s) run past 18 words; a spoken line needs a breath.")
    if _FRONTED_MODIFIER.search(script.strip()) or _FRONTED_MODIFIER.search(hook.strip()):
        score -= 2
        evidence.append("A fronted modifier ('In the garden stretching, ...') reads as written copy on first pass.")
    written = _hits(combined, _WRITTEN_CUES)
    if written:
        score -= min(2, len(written))
        evidence.append(f"Written-copy phrasing ({', '.join(written[:2])}) is hard to say out loud.")
    if ai_spoken._has_quoted_span(script):
        score -= 3
        evidence.append("Quotation marks turn live speech into a quote of past words.")
    if ai_spoken._self_narration_hit(script):
        score -= 3
        evidence.append("Self-narration reports the speaker instead of speaking live.")
    if _CONTRACTION.search(combined):
        score += 1
        evidence.append("Contractions make it sound spoken.")
    if sentences and sum(len(_words(sentence)) for sentence in sentences) / len(sentences) <= 14:
        score += 1
        evidence.append("Average sentence length is conversational.")
    return _clamp(score, 0, 10), evidence, (
        "Read it aloud; fix the fronted modifier and written phrase, and split "
        "any sentence over 18 words."
    )


def _score_handoff(script):
    if not script.strip():
        return 0, ["No script to score."], "End the script on the question the demo answers."
    last = _last_sentence(script)
    score = 5
    evidence = []
    if _has_gap(last):
        score += 4
        evidence.append("The last line leaves a gap the demo can answer.")
    # First person is deliberately NOT paid here (ADR 0188): its one
    # home is Audience truth. This category owns the ending alone —
    # the gap, the named question, and the two ways an ending can
    # close the demo's question before it starts.
    if _names_question(last):
        score += 2
        evidence.append("The last line names the question the demo will answer.")
    if _has_closure(last):
        score -= 3
        evidence.append("The last line resolves the feeling, so the demo has no question left.")
    if _app_behavior(last):
        score -= 2
        evidence.append("The last line narrates the app instead of the viewer's next question.")
    return _clamp(score, 0, 10), evidence, (
        "End on the question the demo answers ('what sets it off'), not on the "
        "resolved feeling."
    )


def _score_trust(hook, script, check, app_name, allows_question):
    if not hook.strip() and not script.strip():
        return 0, ["No spoken lines to score."], "Write a hook and a script first."
    score = 10
    evidence = []
    issues = ai_spoken._generated_spoken_issues(
        hook,
        script,
        check.get("hook", {}).get("ceiling") or 60,
        check.get("script", {}).get("ceiling") or 150,
        allows_question=allows_question,
    )
    for issue in issues:
        score -= 3
        evidence.append(issue)
    named = str(app_name or "").strip()
    if len(named) >= 5:
        needle = _norm(named)
        if f" {needle} " in f" {_norm(hook)} {_norm(script)} ":
            score -= 2
            evidence.append(f"The spoken lines name the app ('{named}').")
    if not evidence:
        evidence.append("No promotion, app-name, personal-history or screen-action issue found.")
    return _clamp(score, 0, 10), evidence, (
        "Remove promotion, app naming, personal-history claims or screen "
        "narration before rendering."
    )


def _grade(total):
    if total >= 85:
        return "A", "distinctive"
    if total >= 70:
        return "B", "strong"
    if total >= 55:
        return "C", "competent_but_generic"
    if total >= 40:
        return "D", "performance_risk"
    return "F", "off_brief"


def _weak_next_steps(dimensions):
    """The report's next steps: the lifts of the weak categories.

    Weak is under 70% of a category's weight, weakest first; at most
    three lifts are named. Shared by the deterministic report and the
    model-evaluated report (ADR 0312) so both read the same way.
    """
    ranked = sorted(
        dimensions.values(),
        key=lambda item: (item["score"] / item["weight"], item["key"]),
    )
    weak = [item for item in ranked if item["score"] / item["weight"] < 0.7]
    if weak:
        return [item["next_step"] for item in weak[:3]]
    return ["No craft dimension needs a rewrite; keep this pair."]


def _report(dimensions, next_steps):
    total = sum(item["score"] for item in dimensions.values())
    achievable_total = sum(
        item["achievable_max"] for item in dimensions.values()
    )
    grade, band = _grade(total)
    return {
        "version": VERSION,
        "advisory": True,
        "total": total,
        "max": 100,
        # The honest scale (ADR 0300): what the points can actually
        # reach, and the same standing read out of 10 — the scale
        # every surface shows. `total`/`max` stay as the raw points.
        "achievable_max": achievable_total,
        "score10": _score10(total, achievable_total),
        "max10": 10,
        "grade": grade,
        "band": band,
        "dimensions": dimensions,
        "next_steps": next_steps,
    }


def _empty_report():
    dimensions = {}
    for key, label, weight in _DIMENSIONS:
        achievable = _achievable_max(key, weight)
        dimensions[key] = {
            "key": key,
            "label": label,
            "weight": weight,
            "score": 0,
            "max": weight,
            "achievable_max": achievable,
            "score10": _score10(0, achievable),
            "evidence": ["No spoken lines to score."],
            "next_step": "Write a hook and a script first.",
        }
    return _report(dimensions, ["Write a hook and a script before scoring."])


def assess_spoken_quality(
    hook_line,
    script,
    *,
    hook_seconds=3,
    total_seconds=15,
    app_name="",
    allows_question=True,
    spoken_check=None,
    cover_text="",
):
    """Score the spoken pair on eight craft dimensions, advisory only.

    Accepts a precomputed `spoken_check` so the Review path computes the
    length/story measurement once. A missing or zero duration falls back to
    fifteen seconds: an old project with no duration should not be scored
    against a one-second middle.

    `cover_text` is the clip's on-screen cover text: it lands in the same
    first two seconds as the hook, so Hook stopping power scores the
    opening moment whole — spoken line plus cover (ADR 0145). The report
    echoes it under `cover_text` with whether it was scored, so Review
    can show the founder exactly what the number read.
    """
    hook = str(hook_line or "").strip()
    body = str(script or "").strip()
    cover = str(cover_text or "").strip()
    if not hook and not body:
        report = _empty_report()
        report["cover_text"] = {"text": cover, "scored_with_hook": bool(cover and hook)}
        return report
    hook_seconds = int(hook_seconds or 3)
    total_seconds = int(total_seconds or 0) or 15
    check = spoken_check or ai_spoken.check_spoken_story(
        hook, body, hook_seconds, total_seconds, app_name=app_name
    )

    dimensions = {}
    for key, label, weight in _DIMENSIONS:
        if key == "hook_stopping_power":
            score, evidence, next_step = _score_hook(hook, cover)
        elif key == "audience_truth":
            score, evidence, next_step = _score_audience(hook, body)
        elif key == "clarity":
            score, evidence, next_step = _score_clarity(hook, body)
        elif key == "concreteness":
            score, evidence, next_step = _score_concreteness(hook, body)
        elif key == "story_arc":
            score, evidence, next_step = _score_story(hook, body, check)
        elif key == "spoken_naturalness":
            score, evidence, next_step = _score_naturalness(hook, body)
        elif key == "demo_handoff":
            score, evidence, next_step = _score_handoff(body)
        else:
            score, evidence, next_step = _score_trust(
                hook, body, check, app_name, allows_question
            )
        achievable = _achievable_max(key, weight)
        dimensions[key] = {
            "key": key,
            "label": label,
            "weight": weight,
            "score": score,
            "max": weight,
            "achievable_max": achievable,
            "score10": _score10(score, achievable),
            "evidence": evidence,
            "next_step": next_step,
        }

    report = _report(dimensions, _weak_next_steps(dimensions))
    report["cover_text"] = {"text": cover, "scored_with_hook": bool(cover and hook)}
    # The grade is the total's alone (ADR 0202, Kasra's ruling of
    # Nov 18 2026): Trust & compliance scores and counts toward the
    # total like the other seven categories, but no category caps
    # the letter. Until this ADR a Trust score under 5 forced grade
    # F / band off_brief however high the total ran — a 72 displayed
    # as F, its two charges being unfinished sentences — and the
    # report carried a capped_by marker no surface read.
    return report


# ---------------------------------------------------------------------------
# The model-evaluated check (ADR 0312).
#
# The founder's ruling: an intelligence should evaluate the hook and
# the script, using the same metrics and methodology the checklist
# already uses. So the checklist writes itself out as a rubric — the
# eight categories and caps from _DIMENSIONS/_ACHIEVABLE_MAX, the cue
# vocabularies above, the earns/loses of each scorer transcribed in
# _METHODOLOGY, and each category's lift taken from the scorer itself
# — and `ai_service` hands that rubric to the app's text model on
# every evaluation. The model does not learn between ratings: it is
# handed the rubric fresh each time, so it rates by the checklist's
# methodology the same way every time. Its reply is validated and
# clamped here, into the exact report shape the deterministic scorer
# produces; anything unusable raises, and the caller falls back to
# `assess_spoken_quality`.
# ---------------------------------------------------------------------------

_METHODOLOGY = {
    "hook_stopping_power": {
        "base": 7,
        "earns": (
            "names a cost or recurring problem (+3)",
            "a concrete anchor — a time, place or object — in the hook (+2; "
            "the cover text can carry the anchor instead, +2)",
            "a contrast or curiosity gap (+2)",
            "compressed enough to land in the first three seconds — at "
            "most 60 characters and 12 words (+2)",
            "names a trigger the viewer can recognise (+1)",
        ),
        "loses": (
            "opens as a journal entry, so the viewer is overhearing rather "
            "than being addressed (-3)",
            "narrates using the app — a screen the generated clip never "
            "shows (-2)",
            "asks for a download, follow or sign-up instead of opening a "
            "problem (-5)",
            "abstract mood words carry the idea (-1 each, up to -3)",
        ),
        "cues": (
            ("problem cues", _PROBLEM_CUES),
            ("curiosity cues", _CURIOSITY_CUES),
            ("concrete anchors", _CONCRETE_CUES),
            ("app-behavior cues", _APP_BEHAVIOR_CUES),
            ("promotion cues", _PROMOTION_CUES),
            ("abstract mood words", _ABSTRACT_NOUNS),
            ("journal-entry openers", _JOURNAL_OPENERS),
        ),
    },
    "audience_truth": {
        "base": 9,
        "earns": (
            "the hook speaks in first person, the way the viewer talks "
            "about their own life (+2)",
            "a routine or object the viewer recognises (+1)",
            "addresses the viewer directly (+1)",
        ),
        "loses": (
            "the hook reports the viewer in the third person instead of "
            "speaking as them (-1)",
            "generic mood language stands in for the viewer's own words "
            "(-1 each, up to -2)",
            "describes using the app rather than a moment in the viewer's "
            "life (-2)",
            "a promotional ask appears in a customer line (-2)",
            "founder or marketer voice appears in a customer line (-2)",
        ),
        "cues": (
            ("concrete anchors", _CONCRETE_CUES),
            ("abstract mood words", _ABSTRACT_NOUNS),
            ("app-behavior cues", _APP_BEHAVIOR_CUES),
            ("promotion cues", _PROMOTION_CUES),
            ("founder and marketer words", _FOUNDER_CUES),
        ),
    },
    "clarity": {
        "base": 7,
        "earns": (
            "every sentence stays short enough to follow on one listen — "
            "24 words at most (+2)",
            "the hook is one short thought — 12 words at most (+1)",
        ),
        "loses": (
            "a sentence runs past 24 words (-1 each, up to -3)",
            "a demonstrative ('that surprise feels') makes the subject "
            "unclear (-1)",
        ),
        "cues": (("unclear demonstratives", _UNCLEAR_CUES),),
    },
    "concreteness": {
        "base": 3,
        "earns": (
            "a place is named (+2)",
            "a physical action is named (+2)",
            "a time or routine is named (+2)",
            "a sensory or body detail grounds the scene (+1)",
        ),
        "loses": (
            "abstract nouns carry part of the meaning (-1 each, up to -3)",
            "the payoff is a vague stand-in, not a specific lived thing (-2)",
        ),
        "cues": (
            ("places", _PLACE_CUES),
            ("physical actions", _ACTION_CUES),
            ("times and routines", _TIME_CUES),
            ("sensory and body details", _SENSORY_CUES),
            ("abstract nouns", _ABSTRACT_NOUNS),
        ),
    },
    "story_arc": {
        "base": 0,
        "earns": (
            "the hook opens a problem (+3 for two or more problem cues, "
            "+2 for one; +1 for a negative state that is not yet a "
            "concrete problem)",
            "the script answers with an insight, not a restatement (+3)",
            "a shift or a name for what changed lands before the last "
            "line (+3 — resolution cues count before the last line only; "
            "the open ending itself is paid in Demo handoff, not here)",
            "the script echoes the hook's image (+1)",
            "the script opens in a scene (+1)",
            "the script does not simply repeat the hook (+1)",
            "a concrete action precedes the insight (+1)",
            "the story stays out of the app's screens (+1)",
            "every reference is established (+1)",
        ),
        "loses": (
            "the script repeats the hook's words instead of continuing "
            "it (-2)",
            "a quotation reports the speaker's words instead of speaking "
            "them live (-2)",
            "the script narrates itself or describes what the camera "
            "shows (-2)",
            "the script does not answer the hook in its first clause (-1)",
            "the payoff names a vague stand-in ('a word', 'that vague "
            "sense') (-2)",
        ),
        "cues": (
            ("problem cues", _PROBLEM_CUES),
            ("insight cues", _INSIGHT_CUES),
            ("shift and resolution cues", _RESOLUTION_CUES),
            ("physical actions", _ACTION_CUES),
            ("app-behavior cues", _APP_BEHAVIOR_CUES),
        ),
    },
    "spoken_naturalness": {
        "base": 8,
        "earns": (
            "contractions make it sound spoken (+1)",
            "average sentence length is conversational — 14 words at "
            "most (+1)",
        ),
        "loses": (
            "a sentence runs past 18 words; a spoken line needs a breath "
            "(-2 each, up to -4)",
            "a fronted modifier ('In the garden stretching, ...') reads "
            "as written copy on first pass (-2)",
            "written-copy phrasing is hard to say out loud (-1 each, up "
            "to -2)",
            "quotation marks turn live speech into a quote of past "
            "words (-3)",
            "self-narration reports the speaker instead of speaking "
            "live (-3)",
        ),
        "cues": (("written-copy phrasing", _WRITTEN_CUES),),
    },
    "demo_handoff": {
        "base": 5,
        "note": "Scored on the script's last line only — this category "
                "owns the ending.",
        "earns": (
            "the last line leaves a gap the demo can answer (+4)",
            "the last line names the question the demo will answer (+2)",
        ),
        "loses": (
            "the last line resolves the feeling, so the demo has no "
            "question left (-3)",
            "the last line narrates the app instead of the viewer's next "
            "question (-2)",
        ),
        "cues": (
            ("gap cues", _GAP_CUES),
            ("question cues in the last line", ("what sets", "why", "how", "what if", "what makes")),
            ("closure cues", _CLOSURE_CUES),
            ("app-behavior cues", _APP_BEHAVIOR_CUES),
        ),
    },
    "trust_compliance": {
        "base": 10,
        "earns": (
            "a clean pair — no promotion, app-name, personal-history or "
            "screen-action issue found — keeps the full 10",
        ),
        "loses": (
            "each spoken-line defect costs -3: a line over its length "
            "ceiling (the hook's seconds at speaking pace, the script's "
            "likewise), an unfinished sentence or a fragment standing in "
            "for one, a question where the plan does not allow one, a "
            "personal-history claim, or screen narration",
            "the spoken lines name the app itself (-2)",
        ),
        "cues": (
            ("promotion cues", _PROMOTION_CUES),
            ("app-behavior cues", _APP_BEHAVIOR_CUES),
            ("founder and marketer words", _FOUNDER_CUES),
        ),
    },
}


def _scorer_lifts():
    """Each category's lift, read out of the scorers themselves.

    The next_step strings are constant for any non-empty pair, so a
    probe pair recovers them exactly — the rubric quotes the
    checklist's own words rather than a paraphrase.
    """
    probe_hook = "I keep losing count every morning"
    probe_script = "I press my palm to my stomach and count again."
    check = ai_spoken.check_spoken_story(probe_hook, probe_script, 3, 15)
    return {
        "hook_stopping_power": _score_hook(probe_hook)[2],
        "audience_truth": _score_audience(probe_hook, probe_script)[2],
        "clarity": _score_clarity(probe_hook, probe_script)[2],
        "concreteness": _score_concreteness(probe_hook, probe_script)[2],
        "story_arc": _score_story(probe_hook, probe_script, check)[2],
        "spoken_naturalness": _score_naturalness(probe_hook, probe_script)[2],
        "demo_handoff": _score_handoff(probe_script)[2],
        "trust_compliance": _score_trust(probe_hook, probe_script, check, "", True)[2],
    }


def evaluation_rubric():
    """The checklist written out for the evaluating model (ADR 0312).

    Assembled from this module's own material: the categories, weights
    and reachable caps, the cue vocabularies the scorers match, the
    earns/loses of each scorer transcribed in _METHODOLOGY, and each
    scorer's own lift. Nothing here is a second methodology.
    """
    lifts = _scorer_lifts()
    achievable_total = sum(
        _achievable_max(key, weight) for key, _label, weight in _DIMENSIONS
    )
    lines = [
        "THE CRAFT CHECKLIST — the app's own methodology. Rate by this "
        "and nothing else.",
        "",
        "The check is advisory: it answers \"is this a good customer "
        "story?\" for two spoken lines — a hook (the opening seconds) "
        "and a script (the story that follows it) — plus the cover "
        "text, which lands in the same first two seconds as the hook, "
        "so Hook stopping power reads the opening whole: the spoken "
        "line plus the cover.",
        "Eight categories, each scored in points. The app adds the "
        "eight scores into a total and grades it: 85 or more is A "
        "(distinctive), 70 or more B (strong), 55 or more C (competent "
        "but generic), 40 or more D (performance risk), under 40 F "
        "(off brief). You return only the per-category scores, "
        "findings and lifts — the app does the adding and the grading.",
        f"Score within the cap each category can actually award, "
        f"given in its heading: the eight caps add to {achievable_total}, "
        "not 100, because two categories' cues cannot reach their "
        "nominal weights.",
        "For each category return \"score\" (a number), \"evidence\" "
        "(the findings: short lines naming what THIS pair does, in the "
        "checklist's own style — e.g. \"Names a cost or recurring "
        "problem ('never').\" or \"The hook states a situation rather "
        "than a problem.\") and \"next_step\" (the lift: the one change "
        "that would most raise this category's score).",
        "",
    ]
    for index, (key, label, weight) in enumerate(_DIMENSIONS, start=1):
        achievable = _achievable_max(key, weight)
        method = _METHODOLOGY[key]
        lines.append(
            f"{index}. {label} — worth {weight} points, "
            f"can actually award {achievable}."
        )
        lines.append(f"   The deterministic checklist starts this category at {method['base']}.")
        if method.get("note"):
            lines.append(f"   {method['note']}")
        lines.append("   What earns: " + "; ".join(method["earns"]) + ".")
        lines.append("   What loses: " + "; ".join(method["loses"]) + ".")
        for cue_label, cues in method["cues"]:
            lines.append(
                f"   {cue_label}: " + ", ".join(f"'{cue}'" for cue in cues) + "."
            )
        lines.append(f"   The checklist's own lift: \"{lifts[key]}\"")
        lines.append("")
    return "\n".join(lines).strip()


def evaluation_prompt(hook, script, *, cover_text="", app_name="",
                      hook_seconds=3, total_seconds=15, allows_question=True):
    """The full evaluation request: the rubric plus the pair to score."""
    cover = str(cover_text or "").strip()
    named = str(app_name or "").strip()
    parts = [
        evaluation_rubric(),
        "",
        "THE PAIR TO SCORE",
        f"Hook line (spoken in the first {int(hook_seconds or 3)} seconds): {hook}",
        f"Cover text (on screen in the same first two seconds): {cover or '(none)'}",
        f"Script (the story that follows, spoken inside a "
        f"{int(total_seconds or 15)}-second clip): {script}",
    ]
    if named:
        parts.append(
            f"The app's name is \"{named}\" — under Trust & compliance, "
            "the spoken lines must never name it."
        )
    if not allows_question:
        parts.append(
            "For this pair the plan does not allow a question hook — "
            "under Trust & compliance a question counts as a defect."
        )
    parts.append(
        "Return one JSON object: {\"dimensions\": {\"hook_stopping_power\": "
        "{\"score\": <number>, \"evidence\": [\"<finding on this clip>\"], "
        "\"next_step\": \"<the lift>\"}, ...}} — all eight categories, "
        "keyed exactly: " + ", ".join(key for key, _label, _weight in _DIMENSIONS) + "."
    )
    return "\n".join(parts)


def report_from_evaluation(data, *, cover_text="", hook_line=""):
    """Build the stored report shape from the model's evaluation.

    Validates the reply against the checklist's structure: every
    category present, a numeric score, at least one finding and a
    lift. Scores are clamped to the cap each category can actually
    award (ADR 0300), so the total, grade and 0-10 reading flow
    through the same math as a deterministic report. Anything
    unusable raises ValueError — the caller falls back to the
    deterministic scorer.
    """
    if not isinstance(data, dict):
        raise ValueError("craft evaluation is not a JSON object")
    raw_dimensions = data.get("dimensions")
    if not isinstance(raw_dimensions, dict):
        raise ValueError("craft evaluation carries no dimensions object")
    dimensions = {}
    for key, label, weight in _DIMENSIONS:
        entry = raw_dimensions.get(key)
        if not isinstance(entry, dict):
            raise ValueError(f"craft evaluation is missing {key}")
        raw_score = entry.get("score")
        if isinstance(raw_score, bool) or not isinstance(raw_score, (int, float)):
            raise ValueError(f"craft evaluation score for {key} is not a number")
        evidence = entry.get("evidence")
        if (
            not isinstance(evidence, list)
            or not evidence
            or not all(isinstance(line, str) and line.strip() for line in evidence)
        ):
            raise ValueError(f"craft evaluation findings for {key} are unusable")
        next_step = entry.get("next_step")
        if not isinstance(next_step, str) or not next_step.strip():
            raise ValueError(f"craft evaluation lift for {key} is unusable")
        achievable = _achievable_max(key, weight)
        score = _clamp(int(round(raw_score)), 0, achievable)
        dimensions[key] = {
            "key": key,
            "label": label,
            "weight": weight,
            "score": score,
            "max": weight,
            "achievable_max": achievable,
            "score10": _score10(score, achievable),
            "evidence": [line.strip() for line in evidence],
            "next_step": next_step.strip(),
        }
    report = _report(dimensions, _weak_next_steps(dimensions))
    cover = str(cover_text or "").strip()
    report["cover_text"] = {
        "text": cover,
        "scored_with_hook": bool(cover and str(hook_line or "").strip()),
    }
    return report
