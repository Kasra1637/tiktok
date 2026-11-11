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
    "laundry",
)
_PLACE_CUES = (
    "garden", "desk", "kitchen", "office", "car", "bus", "train", "shower",
    "bed", "couch", "sofa", "porch", "yard", "street", "park", "store",
    "shop", "school", "gym", "bathroom", "bedroom", "balcony", "patio",
)
_ACTION_CUES = (
    "stretch", "stretching", "walk", "walking", "talk", "talked", "talking",
    "speak", "speaking", "write", "wrote", "writing", "run", "running",
    "cook", "cooking", "clean", "cleaning", "drive", "driving", "sit",
    "sitting", "stand", "standing", "breathe", "breathing", "shower",
    "journal", "note", "coffee", "tea",
)
_TIME_CUES = (
    "morning", "mornings", "afternoon", "afternoons", "evening", "evenings",
    "night", "nights", "week", "weeks", "weekend", "monday", "tuesday",
    "wednesday", "thursday", "friday", "saturday", "sunday", "lunch",
    "dinner", "breakfast",
)
_SENSORY_CUES = (
    "warm", "cold", "tight", "breath", "shoulders", "chest", "jaw", "light",
    "rain", "sun", "coffee", "tea", "blanket", "pillow", "water", "sweat",
    "heartbeat", "quiet", "loud",
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
_DIARY_OPENERS = (
    "every week i", "every morning i", "every night i", "last night i",
    "last week i", "this morning i", "yesterday i", "today i", "i ve been",
    "i have been", "i was", "i m just", "i keep",
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


def _diary_opener(hook):
    normalized = _norm(hook)
    return any(normalized.startswith(prefix) for prefix in _DIARY_OPENERS)


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


def _score_hook(hook):
    if not hook.strip():
        return 0, ["No hook line to score."], "Write a hook that names the viewer's problem."
    score = 7
    evidence = []
    problems = _hits(hook, _PROBLEM_CUES)
    if problems:
        score += 3
        evidence.append(f"Names a cost or recurring problem ('{problems[0]}').")
    else:
        evidence.append("No clear cost or problem cue; the line states a situation.")
    concrete = _hits(hook, _CONCRETE_CUES)
    if concrete:
        score += 2
        evidence.append(f"Has a concrete anchor ('{concrete[0]}').")
    else:
        evidence.append("No concrete time, place or object in the hook.")
    if _hits(hook, _CURIOSITY_CUES):
        score += 2
        evidence.append("Creates a contrast or curiosity gap.")
    if len(hook.strip()) <= 60 and len(_words(hook)) <= 12:
        score += 2
        evidence.append("Compressed enough to land in the first three seconds.")
    first = _first_person(hook)
    if not first:
        score += 2
        evidence.append("Zero first-person markers; the line is about the viewer.")
    elif len(first) == 1:
        score += 1
        evidence.append("One first-person marker; allowed, but zero is the target.")
    else:
        score -= 2
        evidence.append(f"{len(first)} first-person markers make it read as a diary.")
    if _has_trigger(hook):
        score += 1
        evidence.append("Names a trigger the viewer can recognise.")
    if _diary_opener(hook):
        score -= 3
        evidence.append("Opens as a diary entry, so the viewer is overhearing rather than being addressed.")
    if _app_behavior(hook):
        score -= 2
        evidence.append("Narrates using the app ('look back' / a screen) that the generated clip never shows.")
    if _hits(hook, _PROMOTION_CUES):
        score -= 5
        evidence.append("Asks for a download, follow or sign-up instead of opening a problem.")
    abstract = _hits(hook, _ABSTRACT_NOUNS)
    if abstract:
        score -= min(3, len(abstract))
        evidence.append(f"Abstract mood words carry the idea ({', '.join(abstract[:3])}).")
    return _clamp(score, 0, 20), evidence, (
        "Open on the viewer's problem with one concrete detail; cut the diary "
        "frame and any app-behavior cue."
    )


def _score_audience(hook, script):
    if not hook.strip() and not script.strip():
        return 0, ["No spoken lines to score."], "Write a hook and a script first."
    combined = f"{hook} {script}"
    score = 9
    evidence = []
    first = _first_person(hook)
    if not first:
        score += 2
        evidence.append("The hook has no first-person marker; it speaks about the viewer.")
    elif len(first) == 1:
        score += 1
        evidence.append("The hook has one first-person marker; it anchors a real line but is still close to a diary.")
    else:
        score -= 1
        evidence.append(f"The hook uses {len(first)} first-person markers; it reads as the speaker's diary.")
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
    return _clamp(score, 0, 10), evidence, (
        "Add one place, one routine and one time trigger so the line can be "
        "seen, not just understood."
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
    if _hits(script, _RESOLUTION_CUES):
        score += 3
        evidence.append("The script lands a shift or a name for what changed.")
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
    return _clamp(score, 0, 15), evidence, (
        "Make the script answer the hook's problem with a specific insight, "
        "not a restatement."
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
    if re.search(r"\bi\b", _norm(last)):
        score += 2
        evidence.append("The last line is a first-person thought, ready to hand off.")
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


def _score_trust(hook, script, check, app_name, claims_to_respect, allows_question):
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
        claims_to_respect=list(claims_to_respect or ()),
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


def _report(dimensions, next_steps):
    total = sum(item["score"] for item in dimensions.values())
    grade, band = _grade(total)
    return {
        "version": VERSION,
        "advisory": True,
        "total": total,
        "max": 100,
        "grade": grade,
        "band": band,
        "dimensions": dimensions,
        "next_steps": next_steps,
    }


def _empty_report():
    dimensions = {}
    for key, label, weight in _DIMENSIONS:
        dimensions[key] = {
            "key": key,
            "label": label,
            "weight": weight,
            "score": 0,
            "max": weight,
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
    claims_to_respect=None,
    allows_question=True,
    spoken_check=None,
):
    """Score the spoken pair on eight craft dimensions, advisory only.

    Accepts a precomputed `spoken_check` so the Review path computes the
    length/story measurement once. A missing or zero duration falls back to
    fifteen seconds: an old project with no duration should not be scored
    against a one-second middle.
    """
    hook = str(hook_line or "").strip()
    body = str(script or "").strip()
    if not hook and not body:
        return _empty_report()
    hook_seconds = int(hook_seconds or 3)
    total_seconds = int(total_seconds or 0) or 15
    check = spoken_check or ai_spoken.check_spoken_story(
        hook, body, hook_seconds, total_seconds, app_name=app_name
    )

    dimensions = {}
    for key, label, weight in _DIMENSIONS:
        if key == "hook_stopping_power":
            score, evidence, next_step = _score_hook(hook)
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
                hook, body, check, app_name, claims_to_respect, allows_question
            )
        dimensions[key] = {
            "key": key,
            "label": label,
            "weight": weight,
            "score": score,
            "max": weight,
            "evidence": evidence,
            "next_step": next_step,
        }

    ranked = sorted(
        dimensions.values(),
        key=lambda item: (item["score"] / item["weight"], item["key"]),
    )
    weak = [item for item in ranked if item["score"] / item["weight"] < 0.7]
    if weak:
        next_steps = [item["next_step"] for item in weak[:3]]
    else:
        next_steps = ["No craft dimension needs a rewrite; keep this pair."]
    report = _report(dimensions, next_steps)
    # A promotional or personal-history line is off-brief however catchy its
    # other dimensions are. The numeric total still reports the craft points;
    # the letter and band answer the product question: can this pair ship as a
    # customer story? No.
    if dimensions["trust_compliance"]["score"] < 5:
        report["grade"] = "F"
        report["band"] = "off_brief"
        report["capped_by"] = "trust_compliance"
    return report
