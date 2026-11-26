"""
Planning for a single-pass video generation.

Three jobs live here, all pure functions so they can be tested without a
network or a model:

- build_single_pass_prompt(): turns a reviewed creative plan into ONE prompt
  that covers the hook AND its continuation, so the video is a single
  coherent take rather than two unrelated clips.
- is_recoverable_error(): decides whether a failure is worth retrying.

The prompt contract matters for the product rule that the model renders
everything it shows: the environment, setting, lighting and props are
invented from the verified app facts in the prompt, because nothing is
composited over the footage at all and no text appears on screen. The one thing the model must never invent is the person — they come
from the founder's character reference photograph, which rides along as a
model input. Anything the viewer could read as a factual claim about the
app (prices, ratings, interface text) must come from verified facts or
stay out of frame.
"""
from contextvars import ContextVar
import re
from typing import Optional

import angle_scene
import final_beat
import character_policy


# Hard ceiling on the assembled render prompt, in characters.
#
# This is HeyGen Video's ceiling — founder-specified at 4,090 — and since
# ADR 0327 it is the only video model's ceiling there is: MiniMax H3 Max,
# whose 6,800 this constant used to carry, was removed outright at the
# founder's order, and with it the prompt-length refusal that used to
# offer it as the escape. The prompt is now built against 4,090 from the
# first assembly (the submit path passes the same number in from the
# capability record), and the fit machinery below — scaling, condensing,
# and the tightest tier — guarantees the assembled prompt lands inside
# it: the spoken script is never cut, only the app's own direction
# wording gives. An assembly that still came out over would be a builder
# defect to fix here, never a message shown to the founder.
#
# Enforced structurally, not by truncating the finished string: every variable
# read below goes through _clip, so the worst case is bounded no matter what
# a strategy, plan, template or profile carries — including rows written
# before this ceiling existed. Cutting the finished tail instead would
# amputate the identity close at the end, which is the worst part of the
# prompt to lose.
RENDER_PROMPT_LIMIT = 4090

# How much of the field budgets above to actually grant this render.
#
# The budgets above are sized against this ceiling. A caller working to a
# lower budget cannot be given the same prompt: it 400s, and the founder
# pays for the attempt. Rather than truncate the finished string — which
# would amputate the identity close at the very end, the worst part of
# the prompt to lose — every _clip is scaled, so the bound holds
# structurally at any ceiling.
#
# A ContextVar rather than a parameter threaded through all four helper
# functions: the scale is set once at the top of build_segment_prompt and must
# reach every _clip inside them. Task-local, so two concurrent renders on
# different models cannot see each other's budget.
_PROMPT_SCALE: ContextVar = ContextVar("hookforge_prompt_scale", default=1.0)

# How far into a clip's budget the first acceptable clean ending must be
# before _clean_boundary gives up and takes the raw cut. Lower values end
# cleaner but discard more; this is where the two trade off evenly.
MIN_BOUNDARY = 0.45

# How many times build_segment_prompt will reassemble a prompt that came out
# over its ceiling.
#
# Each pass corrects the scale by the measured overshoot, so it converges
# geometrically and the number of passes needed is a function of how far
# over the first assembly landed, not of which provider it was for. Three was
# enough while the saturated worst case fitted inside the ceiling at scale
# 1.0; adding the opening pattern-interrupt directive and the larger hook
# budgets pushed that worst case about 240 characters past, which three
# passes did not absorb. Six absorbs a far larger saturated strategy than
# this code can currently build, and the passes are pure string work, so
# the headroom is close to free. Still the tail of the mechanism, not the
# mechanism: almost every prompt fits on the first try.
MAX_FIT_ATTEMPTS = 6

# Whether protected values are still holding their full budgets. Set per attempt
# by build_segment_prompt, which withdraws it if the first assembly came out
# over the ceiling.
#
# Protection has to be best-effort rather than absolute. Holding the script,
# the brief and the locked scene at full length is worth ~1,000 characters, and
# a saturated strategy can spend more than that on those three alone — so a
# provider with a 4,090 ceiling would be handed a 4,879 prompt and refused by the
# guard. Insisting on protection is how the model becomes unusable for exactly
# the founders who gave it the most to work with. One attempt tries the good
# version; if it does not fit, the next rebuilds without protection.
#
# The spoken script is the exception, and only on heygen-video-1 (see
# script_sacred in build_segment_prompt): its hook line and section scripts
# hold their full budgets on every attempt while the direction and template
# wording absorbs the whole squeeze. Those words are the founder's approved
# words, already sized upstream to fit their budgets — trimming them to fit a
# ceiling produces a different video, not a shorter prompt.
_PROMPT_PROTECT: ContextVar = ContextVar("hookforge_prompt_protect", default=True)
_PROMPT_SCRIPT_SACRED: ContextVar = ContextVar("hookforge_prompt_script_sacred", default=False)

# The floor _budget_scale already clamps to. Repeated here because the retry
# loop has to recognise when it has run out of room to squeeze.
MIN_SCALE = 0.10

# The floor of the LAST fit attempt, below MIN_SCALE.
#
# MIN_SCALE is a readability floor — it keeps a squeezed prompt from reading as
# one-character stubs — and the fit loop will not go under it. This one is only
# reached when the loop has already bottomed out and the prompt is still over its
# ceiling, so the choice there is a terse brief or a refused render. A field
# reduced to a single character still reads as a field, and the fixed
# instructions and the founder's spoken words are untouched either way.
#
# It was 0.02 until ADR 0255: the traced fixed-camera silent build was
# still 23 characters over its budget AT 0.02, because the assembly's
# floor is set by the count of scaled fields (each holding _clip's own
# eight-character minimum) plus the absolutes and the sacred words, and
# that mass only settles under the budget below ~0.01 — measured
# asymptote 3,616 against the 3,631 budget. The walk's floor is 0.005:
# low enough for that mass to fit, still far above the point where a
# field could reach a single character.
FINAL_SCALE = 0.005

# How the last fit walks, and how far each step shrinks the scale.
#
# This is the stage that decides what a founder's prompt actually says when it
# will not fit whole, so it steps in measured ratios and checks the result each
# time rather than computing one scale and trusting the arithmetic. The decay is
# generous because each step must actually move the assembled length, and many
# fields do not scale with the clip limit at all.
#
# The walk used to stop after eight steps (ADR 0255): starting from a step
# sized off an already-squeezed prompt, eight decays did not reach the scale
# where a full fixed-camera prompt fits, and the walk returned the
# over-budget assembly it exists to prevent. It now steps until the prompt
# fits or FINAL_SCALE is reached — decaying by 0.7 from at most 1.0 takes
# about twelve steps — and this cap only bounds a pathological case.
FINAL_FIT_MAX_STEPS = 24
FINAL_FIT_DECAY = 0.7

# Whether to use the condensed fixed instructions, set the same way as the
# scale and for the same reason: it has to reach the assembler without threading
# a parameter through every helper.
_PROMPT_CONDENSED: ContextVar = ContextVar("hookforge_prompt_condensed", default=False)

# Whether the tightest tier of the fixed instructions is engaged (ADR 0327).
#
# The last resort, reached only when the measured walk has bottomed out at
# FINAL_SCALE and the assembly is still over its budget: the fixed direction
# text itself gives up its remaining redundant phrasing — the handoff and
# the audio rule in their shortest forms, the place label shortened, and
# the one direction line the scene lock and identity close already carry
# between them dropped outright. The spoken script is untouched, as it is
# at every tier. This tier is what makes the fit a guarantee rather than a
# hope: with MiniMax gone there is no roomier model to offer instead, and
# the founder's order is that an over-limit assembly is a builder defect
# to absorb here, never a refusal shown to them. Measured against the
# saturated fixture: the worst bottom-out — fixed camera at the silent
# build's reduced 3,631 budget — stood 26 over after the walk; with the
# tier engaged it lands 85 under, and the speaking build at the full
# 4,090 lands 65 under.
_PROMPT_TIGHTEST: ContextVar = ContextVar("hookforge_prompt_tightest", default=False)

# Any ceiling under this renders with the condensed instructions.
#
# Scaling the variable budget alone is not enough to fit a tight ceiling,
# because the FIXED instructions do not scale: measured against no app data at
# all they are 2,047 characters, over half of a typical prompt. A provider
# capping prompts near 4,000 therefore cannot fit a normal prompt however hard
# the variables are squeezed — the floor alone eats half the budget.
#
# So the redundancy in the fixed text comes out instead. It is genuine
# redundancy: the "ends before the product is shown" block and the UI warning
# both forbid the interface, and the opening sentence restates the section
# structure that the per-section headings state again with their real jobs.
# Merging them costs nothing in meaning and roughly halves the floor, which is
# what buys the app-specific brief enough room to still be worth sending.
# The required selfie/orbit text raises the full floor; budgets near 4,600
# need the condensed form too, rather than an over-budget full prompt.
CONDENSE_BELOW = 5000

# Measured sizes of the fixed instruction text, with no app data at all. The
# difference between the two IS what condensing buys.
#
# These are load-bearing arithmetic, not documentation: the per-provider scale
# below divides by the variable space these imply, so if either drifts the
# prompts stop fitting their ceilings again. A test rebuilds both and pins them,
# which is why they are named rather than inlined.
#
# Both rose when the opening pattern-interrupt directive was added, and again
# when it grew the grounding clause that keeps the opening's beats inside this
# video's own story (its full and condensed forms are the fixed text measured
# here). That is the trade this change makes on purpose: an interrupting
# opening is the product, and it is bought out of descriptive room on the
# providers with the tightest ceilings. The full floor fell by 5 when the
# on-screen-text section became a no-text rule (burned-in captions removed);
# the condensed floor rose by 23 for the same rewrite, which states the rule
# in full rather than pointing at a captions step that no longer exists.
# Both rose by 129 for the voice-only audio rule: with dialogue and music
# synthesized in one inseparable pass, the ban has to be explicit fixed text,
# and it applies in both modes — a music bed under the speech is wrong at any
# budget.
#
# Camera ownership is fixed text: the verbatim selfie shot, model-only orbit
# and gesture, and final-phone visibility survive every provider squeeze.
# Processing alone starts a zoom at 70% of hook_seconds and finishes 0.6s later;
# no numeric timestamp or spoken-word sync is promised to the video model.
#
# The floors also fell when the opening rule was restated as what must be ON
# SCREEN — the visible move in the first 1-2 seconds — and the redundancy that
# bought it came out of the same paragraph, so the added constraint cost
# nothing: the measured values below are the real ones for this text.
#
# The final-moment text became setup-dependent (ADR 0093): the floor is
# measured on the selfie default — the phone handoff is now fixed-camera only,
# and a selfie render gets the physical ending instead. The reach/phone/camera
# and second-free-hand prohibitions (ADR 0093, as superseded) are part of the
# fixed text, which is why both floors rose.
#
# Both moved again for the no-crop framing: the starting shot widened from
# upper-chest to mid-chest with an explicit never-crop-the-forehead-or-chin
# rule, and the selfie hold forbids tightening in both budget modes. Renders
# were coming back with the forehead or chin cut off — a close-up opening
# plus the 1.10x processing zoom — so the margin is stated in fixed text
# rather than left to the model's reading of "headroom". The hold's restated
# distance paid for all of it and more: it now names the framing directly
# above instead of repeating the metre-away setup, per the fixed-text trade
# in ADR 0053 — which is why the full floor fell while the condensed floor
# (whose hold was already terse) rose by the framing alone.
# ADR 0187's behavior rule lands here too: the opening-interrupt directive
# now states that the first beat physically performs the story's central
# action through this video's own channel (hand, face, mouth, body or a
# camera move), with no resting pose standing in for it, and the final-beat
# templates — the selfie ending and the fixed phone handoff, in both
# forms — close sharp with the opening's energy rather than fading or
# holding a passive smile. Measured: the full floor FELL 6 (4019 -> 4013)
# because the enacting sentence replaced the old gesture examples and a
# paragraph-2 clause it made redundant, while the condensed floor rose
# 232 (2244 -> 2476): the condensed wording is compressed harder than the
# full because at HeyGen's 4,090 ceiling with the script held sacred, the
# uncompressed sentence landed the saturated prompt 44 over, and fixed
# text is the only text the squeeze cannot take back.
#
# ADR 0213 widens the handheld frame one more step (amending 0113): the
# market-stall render came back a tight close-up the whole take — head and
# hair cropped at the top, hands out of frame — despite the mid-chest ask
# and the never-tighten hold. The starting shot now asks waist up, the
# full head and all her hair in frame with the headroom measured above
# the hair itself, and the never-crop rule names the hair beside forehead
# and chin; both holds name the hair too, so the wider frame is the frame
# that gets held. The wider sentence added 49; the shot paid 26 of its
# own back by dropping its repeated "Hold straight-on" (the hold below
# restates it) and its second "natural". The rest was paid out of a
# verbatim duplicate both modes carried — "End before the last second"
# stated in the header and again in the middle heading, which is always
# present — and, in the condensed text, the identity close's "one take:
# no cut" (its header's ONE continuous states it; the close keeps the
# black-frame and title-card bans, which appear nowhere else). The
# payment was not optional bookkeeping: unpaid, the growth landed a
# saturated HeyGen prompt 25 over its ceiling and deepened the default
# squeeze enough to clip the payoff out of a realistic brief. Measured:
# full floor rose 1 (4013 -> 4014), condensed fell 12 (2476 -> 2464).
# The single-pass floor did not move: that builder's fixed text carries
# no starting shot.
#
# ADR 0223 tightens the opening snap to the founder's settled doctrine
# (renders kept landing the energy near a full second in): the snap
# completes inside the first half second, the central action is caught
# at its sharpest instant, and the voice starts with the first frame —
# no silent beat before the hook's first sound — replacing the old
# "words come second". The growth is paid almost entirely out of the
# same paragraph in both twins: the full text drops "frame by frame",
# the push-in's "as action", "scrolling", the score's "in order" and
# a doubled possessive, because a first pass that let the full floor
# rise ~70 silently squeezed the payoff out of a realistic prompt
# (the prompt_dedup regression) — the scale divides by the space the
# floor implies, so fixed growth is taken out of the founder's
# fields. The condensed twin merges its beat and snap sentences and
# carries the voice rule as "voice already speaking" alone, because
# at HeyGen's ceiling with the script held sacred the uncompressed
# sentence landed the saturated prompt over 4,090, and fixed text is
# the only text the squeeze cannot take back. Measured: full floor
# rose 3 (4014 -> 4017), condensed rose 11 (2464 -> 2475).
#
# ADR 0256 drops "mobile " from the fixed header ("for the app {app_name}"),
# reducing all five measured floors by 7 characters.
FULL_PROMPT_FLOOR = 4010
CONDENSED_PROMPT_FLOOR = 2468

# The same floors for a FIXED camera (ADR 0255). The pair above is the
# handheld assembly's: a fixed camera swaps the handheld sentences for
# its own — the set-down framing, the indoor restatement rule, the
# room-fit clause — and that text is fixed in exactly the same sense, so
# it has to come out of the budget before the variables get anything.
# It was never measured separately, so every fit computation for a fixed
# render under-counted the fixed text (the condensed floor by 113) and
# the final walk stopped short of the scale that actually fits. Measured
# the same way, on the same empty assembly: full 3981, condensed 2581.
# A test pins both, as it pins the pair above.
FIXED_FULL_PROMPT_FLOOR = 3981
FIXED_CONDENSED_PROMPT_FLOOR = 2581

# The same measurement for the OTHER builder, taken at the same duration (10s)
# so the two are comparable, and identical at 8s and 15s: this builder's fixed
# text has no duration-dependent beat layout, so the measured value holds
# across the supported set. A test rebuilds and pins it for the same reason
# the two above are pinned.
#
# This builder used to take no budget at all, so nothing in it could fit a tight
# provider and a prompt that did not fit could only be refused. That is not how
# the founder hit the ceiling — the submit path refuses a strategy-less project
# before it builds a prompt, so this path is not the one that failed — but it is
# the same ceiling one path had no answer for, and it now scales like its
# sibling rather than relying on the guard.
# The single-pass floor rose by 533 for the same ADR 0187 rule stated
# once in that builder: open mid-motion on the story's own channel, close
# with the opening's energy.
#
# ADR 0223 lands here too: the hook sentence puts the voice on the first
# frame (no lead-in pause or silent beat before the first word) and the
# opening sentence states the half-second snap and the sharpest instant.
# Measured: this floor rose 123 (2835 -> 2958), then fell 7 to 2951 (ADR 0256).
SINGLE_PASS_PROMPT_FLOOR = 2951

# The app's own name, in the prompt, clipped.
#
# Every other value that reaches a prompt goes through _clip and therefore
# scales with the ceiling. The brand name did not, and it appears three times in
# the strategy prompt, so it was the one value that could push a prompt past a
# ceiling no squeezing could pull back: the profile normalizer caps how many
# items a list has and never how long a string is, so a long pasted name arrives
# whole, and past roughly 630 characters the fit loop bottoms out with the
# prompt still over HeyGen's 4,090 — reported, in the refusal era, as the
# script being too long, on the one provider whose ceiling is tight enough for
# the name to matter. Sixty characters is far longer than any real app name.
APP_NAME_PROMPT_CHARS = 60

# The natural size of the variable text at full budgets — the scale's
# denominator. It was derived as the old 6,800 default ceiling minus the
# full floor; ADR 0327 keeps the measured value itself rather than the
# derivation, because the ceiling it was derived from is gone and the
# quantity it names — how much variable text a saturated strategy carries
# at full budgets — did not change when the ceiling did.
#
# This overestimates the variable text the code can actually assemble, which is
# the safe direction. Saturated fields top out around 3,830 characters, not
# 4,753, so a tight budget clips marginally harder than it strictly needs to.
# Erring toward a shorter prompt that fits beats an exact split that does not.
NATURAL_VARIABLE_SPACE = 2790


def _hook_floor_extra(condensed: bool) -> int:
    """The hook surface's own fixed passages, in the form the budget
    selects: the physical opening (ADR 0250), the real scene (ADR
    0250) and the scene motion (ADR 0352).

    The measured floor constants are taken on an assembly with no
    surface marker, so none of these three is inside them — yet on a
    hook render they are fixed text in exactly the floor's sense:
    they do not scale, and the fit correction divides the variable
    text by the room the floor leaves. Uncounted, the correction
    would divide by room this text already spent, and the 4,090 fit
    guarantee (ADR 0327) would rest on the retry loop alone. The
    passages resolve here, at call time, because they are defined
    below this function in the module."""
    if condensed:
        return (
            len(_CONDENSED_HOOK_PHYSICAL_OPENING)
            + len(_CONDENSED_HOOK_REAL_SCENE)
            + len(_CONDENSED_HOOK_SCENE_MOTION)
        )
    return (
        len(_HOOK_PHYSICAL_OPENING)
        + len(_HOOK_REAL_SCENE)
        + len(_HOOK_SCENE_MOTION)
    )


def _prompt_floors(strategy, condensed: bool, hook_surface: bool = False) -> int:
    """The measured fixed-text floor for this render's camera (ADR 0255)."""
    if str((strategy or {}).get("camera_setup") or "handheld") == "fixed":
        floor = FIXED_CONDENSED_PROMPT_FLOOR if condensed else FIXED_FULL_PROMPT_FLOOR
    else:
        floor = CONDENSED_PROMPT_FLOOR if condensed else FULL_PROMPT_FLOOR
    if hook_surface:
        floor += _hook_floor_extra(condensed)
    return floor


def _budget_scale(prompt_budget, condensed: bool, floor=None) -> float:
    """
    What fraction of each field budget this render may use.

    The ceiling is a TOTAL character budget, so the fixed instructions have to
    come out of it before the variables get anything. Scaling by
    budget/RENDER_PROMPT_LIMIT ignores that and silently over-allocates by the
    floor, which is how a 4,096 ceiling still produced a 4,175-character prompt.

    Subtracting the floor first is the whole fix: what remains is the space the
    variables actually have, and dividing that by their natural size gives the
    fraction. The guard in the submit path remains the backstop for the residue.

    `floor` overrides the handheld measurement for a fixed camera (ADR 0255).
    The natural space stays the handheld one, which only squeezes a fixed
    prompt marginally harder — the safe direction.
    """
    if floor is None:
        floor = CONDENSED_PROMPT_FLOOR if condensed else FULL_PROMPT_FLOOR
    available = float(prompt_budget) - float(floor)
    scale = available / float(NATURAL_VARIABLE_SPACE)
    # A ceiling at or below the floor leaves the variables nothing. Squeeze to
    # the floor of the scale rather than to zero: a prompt of one-character
    # stubs reads as corruption, and the fit walk below it takes the rest.
    return max(MIN_SCALE, min(1.0, scale))


def _clean_boundary(head: str) -> str:
    """
    Trim a hard-cut fragment back to the last place it can end cleanly.

    Hard character cutting is what a video model should never be handed: it
    produced lines like "looks up from the phone, tired, into the le" and
    "What this app is abou", which a model either ignores or reads as a
    complete instruction. A fragment is still information; a broken word is
    just noise that costs characters.

    A line end is preferred, then a sentence end, then a word end, then the raw
    cut as a last resort. Line first matters because the two largest protected
    blocks — the locked scene and the strategy brief — are newline-delimited,
    where cutting mid-line loses a whole field's label and value. Boundaries
    earlier than MIN_BOUNDARY of the budget are refused: keeping one short
    opening sentence and discarding the rest of the field is usually a worse
    trade than an imperfect ending.
    """
    floor = len(head) * MIN_BOUNDARY
    line = head.rfind("\n")
    if line >= floor:
        return head[:line].rstrip()
    end = -1
    for i, ch in enumerate(head):
        if ch not in ".!?;":
            continue
        after = i + 1
        if after < len(head) and head[after] in "\"'":
            after += 1
        if after >= len(head) or head[after] == " ":
            end = after
    if end >= floor:
        return head[:end].rstrip()
    space = head.rfind(" ")
    if space >= floor:
        return head[:space].rstrip()
    return head.rstrip()


def _clip(text, limit: int, protect: bool = False, sacred: bool = False,
          absolute: bool = False) -> str:
    """
    Clip one variable prompt value to a fixed budget, stripped.

    `protect` marks a value the render cannot do without — the spoken script,
    the on-camera action, the app's strategy. Under a tight ceiling the
    protected values keep their full budget and the descriptive ones absorb
    the squeeze instead. Losing the tail of a product brief is survivable;
    losing half of what the founder is going to say is not.

    `sacred` is stronger than `protect` and marks only the spoken script (the
    hook line and the two section scripts). Where protection is withdrawn if
    the first assembly does not fit, sacred holds the full budget on every
    attempt — but only when the caller asked for it via script_sacred (today:
    heygen-video-1 only). Anything over the full budget is still trimmed to a
    clean boundary, so a pathological script cannot blow the ceiling alone;
    the guarantee is that fitting the ceiling never costs the script a
    character, only the direction and template wording.

    `absolute` holds the full field budget on every attempt, on every provider,
    in both modes. It is for founder-recorded prohibitions, which are short and
    safety-relevant: a clipped prohibition is worse than none, because
    "a hospita" reads as noise rather than as a rule while still spending the
    characters. Unlike `sacred` it needs no provider flag, because the
    guarantee is about the rule reaching the render, not about a particular
    ceiling tripping the withdrawal.

    `protect` and `sacred` only engage when condensing: at a normal ceiling the
    scale is 1.0 and every value is already whole. `absolute` engages on every
    attempt, including a full-budget refit, which is exactly the case it exists
    for.
    """
    s = str(text or "").strip()
    scale = _PROMPT_SCALE.get()
    if absolute:
        effective = int(limit)
    elif sacred and _PROMPT_CONDENSED.get() and _PROMPT_SCRIPT_SACRED.get():
        effective = int(limit)
    elif protect and _PROMPT_CONDENSED.get() and scale < 1.0 and _PROMPT_PROTECT.get():
        effective = int(limit)
    else:
        effective = max(1, int(limit * scale))
    if len(s) <= effective:
        return s
    head = s[:effective].rstrip()
    # Clean boundary on any squeeze, not only the condensed path: a prompt
    # over budget squeezes to scale < 1.0 with condensed False,
    # and a hard mid-word cut there is noise the model reads as an instruction.
    if _PROMPT_CONDENSED.get() or scale < 1.0:
        return _clean_boundary(head)
    return head

# Words the model must not attempt to draw. Listed so the instruction can be
# explicit rather than relying on the model inferring "don't fake the facts".
# Note what is NOT here: Location, lighting and props ARE
# invented by the model from the verified app facts — nothing is composited
# over the footage and no text appears on screen, so the scene has to be
# rendered, not reserved.
_UI_RENDERING_WARNING = (
    "Do NOT draw or render: app interface elements, app screenshots, button "
    "labels, prices, ratings, review counts, download counts, logos, or any "
    "small on-screen text. Nothing is composited over this footage and no text "
    "appears on screen at all, so use the locked Location, lighting "
    "and props concretely from the verified app facts — but anything the "
    "viewer could read as a factual claim about the app must come from those "
    "facts, never from invention."
)

# Condensed forms of the fixed instructions, for providers whose prompt ceiling
# is too low to carry the full set. See CONDENSE_BELOW for why.
#
# Nothing is dropped, only stated once. The two prohibitions are merged because
# they were the same prohibition said twice; the opening sentence is folded into
# the section headings that already carry the real jobs. What survives is every
# constraint, and what it buys is the room the app-specific brief needs to still
# be worth sending — which is the entire point of the product.
# Equivalent shorter wording buys room for the mandatory camera instructions
# on tight providers; identity, handoff and factual prohibitions are unchanged.
_CONDENSED_HANDOFF = (
    "Founder adds demo/close later. Do NOT film the app in use or render any "
    "interface, screenshot, button, price, rating, review/download count, logo "
    "or text. Use locked Location/light/props from verified app facts; never invent claims."
)

# The tightest tier's forms (ADR 0327, see _PROMPT_TIGHTEST): the same
# rules with their redundant phrasing trimmed — the handoff drops the
# enumerated list the UI warning's condensed twin already implies, and
# the audio rule loses its doubled negatives. Engaged only when the fit
# walk has bottomed out over budget.
_TIGHTEST_HANDOFF = (
    "Founder adds demo/close later. Do NOT film the app in use or render any "
    "interface, price, rating, logo or text. Use locked Location/light/props "
    "from verified facts; never invent claims."
)

_TIGHTEST_AUDIO = (
    "Audio: the presenter's voice only. No music, no sound effects."
)

# The tightest opening: ADR 0187/0223's rule whole — mid-motion, the
# story's own channel, the snap inside the first half second, voice from
# the first frame, escalation, no resting pose — with the two clauses
# the rest of the prompt already carries ("follow the score" is what
# the sections are; the question is the hook's job, stated in its
# heading) trimmed out.
_TIGHTEST_OPENING = (
    "Pattern interrupt: first frame already moving, voice already speaking; "
    "1-2s: clearly visible movement, gesture or position change — no neutral "
    "pose, fade, greeting. One beat enacts this story's central action at its "
    "sharpest instant via this video's channel (hand, face, mouth, body, "
    "camera) — snap inside the first half-second; then escalate via face, "
    "gaze, hands, posture; no resting pose, hand on the chest, or slow "
    "settle. Ground beats in this video's own situation."
)

# The tightest phone handoff (fixed camera): every constraint of the
# condensed framing survives — whole phone, uncropped, margins, eyes on
# it, sharp to the last frame, central 88% — in fewer words.
_TIGHTEST_PHONE_HANDOFF_FRAMING = (
    "Final 1-2s: she raises the phone into view, back to camera, screen to "
    "her; whole phone visible, uncropped, clear margins, eyes on it, "
    "excited, never glancing away, through the last frame; sharp; central 88%."
)

# The one-take / no-cut rule is not restated here: the condensed header's
# "ONE continuous" already states it. The black-frame and title-card bans
# stay — unlike the full header, the condensed one never states them, so
# this close is their only carrier (ADR 0213 paid for the wider selfie
# framing partly out of this duplicate).
_CONDENSED_IDENTITY_CLOSE = (
    "Vertical 9:16 throughout: no black frame or title card. Same person, "
    "face/hair exactly as the reference photograph, in the one outfit specified, "
    "same place, under the same light."
)

# The model owns perspective and performance; processing alone owns zoom.
# This starting shot is verbatim in the strategy and every provider prompt.
# ONE framing ask for a handheld selfie: straight-on at arm's length, no 3/4
# angle and no off-centre bias. The strategy and every provider prompt read
# this same wording so the render is told one framing, not two.
HANDHELD_SELFIE_FRAMING = (
    "HANDHELD SELFIE: held at arm's length, eye-level, straight-on, about a metre away. "
    "Frame waist up, full head and all her hair in frame with clear headroom "
    "above the hair, room at the sides for hand gestures; never crop the hair, "
    "forehead or chin. "
    "No 3/4 angle, no off-centre framing. Natural "
    "facial proportions, no exaggerated wide-angle distortion. Very subtle "
    "handheld sway."
)

SELFIE_STARTING_SHOT = HANDHELD_SELFIE_FRAMING

# The fixed shot as it stood before the set-down (ADR 0216, reversed by
# ADR 0219): the phone rests on a shelf or tripod and the presenter is
# already in frame. The last sentence is ADR 0219's indoor rule at
# render level — the placed camera is an interior setup, so the shot
# itself states the scene is an interior room — extended by ADR 0233
# with its compact activity clause: every action fits that room. The
# fuller restaging instruction lives in the plan and strategy prompts,
# which write the actions the render performs.
FIXED_STARTING_SHOT = (
    "Fixed camera: a stationary phone on a shelf or tripod, eye-level and straight-on. "
    "Frame the standing presenter from head to mid-thigh, full head with headroom, "
    "both hands inside frame with room for gestures. Natural amateur phone footage, "
    "not a polished studio shoot. The scene is indoors: an interior room, never "
    "outdoors or in transit, and every action is one that fits that room."
)


def starting_shot(camera_setup="handheld") -> str:
    return FIXED_STARTING_SHOT if camera_setup == "fixed" else SELFIE_STARTING_SHOT


# Detect explicit conflicting directions, not spoken dialogue. Refuse instead
# of stripping whole fields: a mixed direction may also carry reviewed scene,
# wardrobe or performance details that must not be silently thrown away.
_FIXED_CAMERA_CONFLICT = re.compile(
    r"\b(?:hand[ -]?held|selfie|arm['’]?s[ -]+length|close[ -]?(?:up|framing)|"
    r"(?:chest|waist|shoulders?)[ -]up|full[ -]body|head[ -]to[ -]toe|"
    r"zoom\w*|orbit\w*|(?:pan(?:s|ning)?|tilt(?:s|ing)?)\s+(?:the\s+)?camera|"
    r"(?:camera|lens)\s+(?:(?:slowly|gently|smoothly)\s+)?"
    r"(?:mov\w*|sway\w*|track\w*|tilt\w*|pan\w*)|"
    r"(?:push|pull|dolly)[ -]?(?:in|out|back)|"
    r"(?:walk\w*|step\w*|lean\w*)\s+(?:\w+\s+){0,3}"
    r"(?:towards?|closer to)\s+(?:the\s+)?(?:camera|lens)|"
    r"(?:hold\w*|grip\w*)\s+(?:the\s+)?(?:recording\s+)?(?:phone|camera)"
    r"\s+(?:in\s+(?:her|his|their)\s+hands?|to\s+(?:film|record)))\b",
    re.IGNORECASE,
)


def require_camera_setup_directions(strategy: dict) -> None:
    """Validate unbudgeted direction before any prompt can reach a provider.

    Camera-specific scene fields are checked too, even though the lock omits
    them, so a strategy cannot claim it was reviewed for two different setups.
    Scripts are deliberately excluded: talking about a selfie is not filming one.
    """
    if (strategy or {}).get("camera_setup") != "fixed":
        return
    directions = {key: strategy.get(key) for key in (
        "strategy_summary", "hook_concept", "hook_action", "hook_dialogue",
    )}
    for section in ("scene", "performance", "camera_beat"):
        values = strategy.get(section)
        if isinstance(values, dict):
            directions.update({f"{section}.{key}": value for key, value in values.items()})
    for index, segment in enumerate(strategy.get("segments") or []):
        if isinstance(segment, dict):
            for key in ("goal", "action"):
                directions[f"segments.{index}.{key}"] = segment.get(key)
    for field, value in directions.items():
        # Carry negation only through a camera list, not unrelated prose like
        # "not polished, handheld selfie". Contrast words start a new direction.
        for sentence in re.split(r"[.!?;:\n]|\b(?:but|instead|however|then)\b", str(value or ""), flags=re.I):
            negative_list = False
            for clause in sentence.split(","):
                matches = list(_FIXED_CAMERA_CONFLICT.finditer(clause))
                previous_end = 0
                for match in matches:
                    prefix = clause[previous_end:match.start()]
                    previous_end = match.end()
                    negated = re.search(r"\b(?:no|not|never|without|avoid)\b", prefix, re.I)
                    if negated or (negative_list and re.fullmatch(r"\s*(?:(?:and|or)\s*)?", prefix, re.I)):
                        negative_list = True
                        continue
                    raise ValueError(
                        f"Fixed camera conflicts with {field}: {clause.strip()!r}. "
                        "Camera setup owns framing and camera movement. Edit this direction "
                        "or rebuild the strategy on Hook + Story for a stationary head-to-mid-thigh "
                        "shot, then review it again. No render was submitted."
                    )
                if not matches:
                    negative_list = False


# The hold follows the starting shot immediately in every prompt, so it names
# that framing ("that straight-on selfie framing") instead of restating the
# distance: the metre-away setup is stated once, directly above. The saved
# characters pay for the never-tighten rule at the end, which the fixed-text
# budget had no room left to absorb (ADR 0053).
_SELFIE_CAMERA_MOVE = (
    "Hold that straight-on selfie framing for the whole take — keep the phone "
    "steady, no push in, pull back, or zoom. In the same "
    "moment the actor makes one small story-specific action{gesture}. Keep it subtle "
    "and natural, eyes on the lens. No cut. Keep the full head, hair and chin inside "
    "frame; never tighten or crop the head."
)

# A Hook + CTA hook swaps the hold for its own move (ADR 0323, Kasra's
# ruling): the hook starts WIDE — waist up, the place visible around
# her — and her own hand eases the phone toward her face as she
# delivers the line, landing at the close framing by its end. Starting
# zoomed in is the fault the ruling names; arriving close is the
# design. Create Video's hold above is untouched: this text replaces
# it only on the hook surface, whose renders are handheld by rule
# (ADR 0252), so the two framings never share a prompt.
_HOOK_SELFIE_CAMERA_MOVE = (
    "START WIDE, LAND CLOSE (this hook's own framing): the take opens on the "
    "wide framing above — waist up, full head and all her hair in frame, the "
    "place visible around her — and as she delivers the line her own hand "
    "eases the phone naturally toward her face, landing at the close "
    "straight-on framing by the line's end. The move in is hers alone: "
    "unhurried, continuous, no zoom and no cut. Starting on her face "
    "filling the frame is a failed opening; arriving close is the design. "
    "In the same moment the actor makes one small story-specific "
    "action{gesture}. Keep it subtle and natural, eyes on the lens. No "
    "cut. Keep the full head, hair and chin inside frame throughout."
)

_CONDENSED_HOOK_SELFIE_CAMERA_MOVE = (
    "Start wide (waist up, the place visible around her); as she speaks, "
    "her own hand eases the phone toward her face, landing close by the "
    "line's end — no zoom, no cut; never open on a face filling the "
    "frame. Simultaneous actor gesture{gesture}; subtle, natural, eyes "
    "on lens. Never crop the head or hair."
)

_CONDENSED_SELFIE_CAMERA_MOVE = (
    "Hold that straight-on selfie framing — keep the phone steady, no zoom. "
    "Simultaneous actor gesture{gesture}; "
    "subtle, natural, eyes on lens. Never crop the head or hair."
)

_CAMERA_MOVE = (
    "When the story begins, make one smooth, small camera orbit {direction} to a "
    "three-quarter angle, keeping the same distance from the face, then hold that angle "
    "to the end. Do not push in, pull back, or zoom at any point. At the same moment, "
    "the actor makes one small story-specific action{gesture}. Keep it subtle and "
    "natural, with eyes on the lens. No cut. Keep the full head and chin visible."
)

# The ownership rule is essential, not optional direction that can be squeezed.
_CONDENSED_CAMERA_MOVE = (
    "When the story begins, small smooth orbit {direction} to three-quarter; same distance "
    "from the face, then hold. Do not push in, pull back, or zoom. Simultaneous actor "
    "gesture{gesture}; subtle, natural, eyes on lens."
)

# Fixed-camera only: the phone rises into view at the end and stays inside the
# central safe area of the later processing crop (including 1.12x), without asking
# the model to zoom or to show any screen content.
#
# A SELFIE render gets the physical ending instead (ADR 0093): the camera IS
# the phone in the character's hand, so nothing at the end can be a phone
# raised, held or shown. The beat is chosen per render (final_beat.pick) and
# reaches this builder on the strategy as `final_beat`, so consecutive renders
# of one project do not repeat the same ending.
_PHONE_HANDOFF_FRAMING = (
    "Final 1-2s: she raises the phone into view as she finishes saying she found it, "
    "back to camera, screen facing her; whole phone visible, uncropped, at chest height, "
    "clear margins, never behind hand/arm/face, eyes on the phone, excited to open it, "
    "never glancing away, through the last frame. Sharp, with the opening's energy. No screen/app use; head/chin/phone "
    "in central 88%."
)

# Condensed twin: every constraint survives. The no-screen rule is carried by the
# condensed handoff above, so it is not repeated here.
_CONDENSED_PHONE_HANDOFF_FRAMING = (
    "Final 1-2s: she raises the phone into view, back to camera, screen to her; whole "
    "phone visible, uncropped, clear margins, never behind hand/arm/face, eyes on it, "
    "excited, never glancing away, through the last frame; sharp, with the opening's energy; central 88%."
)

# The selfie ending: one short physical beat in the same final moment the
# phone handoff used to occupy, physical only, no extra words or time, with a
# split-second hold before the cut. The character can never reach toward,
# hold, raise or show a phone or camera, and one hand holds the camera so no
# action needs a second free hand. This is where the rule is stated: it is
# the only place in the prompt that has to carry it, so the rest of the fixed
# text can stay short enough for the tightest provider ceiling.
_SELFIE_FINAL_BEAT = (
    "Final 1-2s (selfie: the camera is the phone in their hand, so never reach toward, "
    "hold, raise or show a phone or camera, and never need a second free hand): "
    "{ending} Physical only \u2014 no new words, no "
    "extra time \u2014 sharp, no soft fade, no passive smile hold — hold the last pose a split second, face in "
    "the central 88% to the final frame."
)

_CONDENSED_SELFIE_FINAL_BEAT = (
    "Final 1-2s (selfie, never reach toward or show a phone/camera; one hand holds it): "
    "{ending} No words; sharp, opening energy; no fade, no passive smile hold; split-second hold before the cut; face central."
)


def camera_move_section(strategy: dict, hook_seconds=None, condensed: bool = False, hook_surface: bool = False) -> str:
    """Model-only orbit and gesture, not timestamped or synced to a spoken word.

    Timing is qualitative because generation cannot guarantee frame-exact action.
    Processing independently starts its single zoom at 70% of hook_seconds and
    completes its eased ramp about 0.6s later. It never supplies the orbit.
    A handheld selfie has no orbit at all — the held phone cannot be the
    framing and also move to a 3/4 angle, so its wording holds straight-on.

    A Hook + CTA hook (`hook_surface`, ADR 0323) is the one exception
    to the hold: it starts wide and lands close, its own move above.
    A fixed strategy keeps the fixed text whatever the surface — the
    hook surface is handheld by rule, so the exception can only ever
    meet a handheld strategy in production.
    """
    beat = (strategy or {}).get("camera_beat")
    beat = beat if isinstance(beat, dict) else {}
    direction = str(beat.get("direction") or "right").strip().lower()
    if direction not in ("left", "right"):
        raise ValueError("Camera orbit direction must be left or right; regenerate the strategy.")
    # Never budget-scale this short field: the orbit must keep its own gesture
    # even on a provider's last-resort squeeze. Snap a long legacy value at a word.
    gesture = " ".join(str(beat.get("gesture") or "").split())
    if len(gesture) > 90:
        gesture = gesture[:91].rsplit(" ", 1)[0]
    if gesture[:3].lower() == "as ":
        gesture = gesture[3:].lstrip(" ,—-")
    clause = f": {gesture}" if gesture else " (a slight head tilt or expression shift)"
    if hook_surface and (strategy or {}).get("camera_setup") != "fixed":
        template = _CONDENSED_HOOK_SELFIE_CAMERA_MOVE if condensed else _HOOK_SELFIE_CAMERA_MOVE
        return template.format(gesture=clause)
    if (strategy or {}).get("camera_setup") != "fixed":
        template = _CONDENSED_SELFIE_CAMERA_MOVE if condensed else _SELFIE_CAMERA_MOVE
        return template.format(gesture=clause)
    if (strategy or {}).get("camera_setup") == "fixed":
        return (
            "Camera stays locked for the whole take: no sway, orbit, pan, tracking or zoom. "
            "When the story begins, one small actor gesture" + clause + ". "
            "Natural expressions and small weight shifts; do not walk toward the lens. "
            "Keep head and both hands in frame; the recording phone is not in her hands."
        )
    template = _CONDENSED_CAMERA_MOVE if condensed else _CAMERA_MOVE
    return template.format(direction=direction, gesture=clause)


# How the opening plays, as a standing instruction on every studio render.
#
# The strategy supplies the specific beats; this is the requirement they have to
# satisfy, stated where the model is deciding what happens in the first frame.
# It is fixed text, so it is part of the measured floor below and gets a
# condensed twin for providers whose ceiling cannot carry the full set.
#
# What it forbids matters as much as what it asks for: the common failure this
# replaces was an opening that drifts in, settles into a neutral pose and then
# starts talking, which is exactly what a scrolling thumb ignores. The visible
# move in the first 1-2 seconds is the same rule stated as what MUST be on
# screen, not only what must not: the opening's first beat is something the
# viewer watches happen.
#
# ADR 0223 tightens the snap inside that window: the beat lands in the
# first half-second (the founder's settled doctrine — renders kept
# landing the energy near a full second in), the action is caught at
# its sharpest instant rather than led into or settled into, and the
# voice starts with the first frame instead of after the move — no
# silent beat before the hook's first sound. The growth is paid out of
# this same paragraph and the floor ledger below.
_OPENING_INTERRUPT = (
    "HOW THE OPENING MUST PLAY: the first frame is already in motion, "
    "and the first 1-2 seconds show a clearly visible movement, gesture or position "
    "change \u2014"
    " no neutral pose, no fade, drift or slow push-in, no "
    "greeting to camera. Inside the first half-second, ONE thing a "
    "thumb must pause for: the beat that physically performs this "
    "story's central action at its sharpest instant, through this video's channel (hand or "
    "fingers, a face, the mouth, the body, or a camera move "
    "toward the presenter) — snap done inside that half-second, no resting "
    "pose, no hand sitting on the chest, no slow settle. Beats escalate: two or three, "
    "each bigger than the last, never settling. The face, gaze, hands and posture carry it, "
    "and she is already speaking from the first frame — no silent beat first. "
    "Read the beats below as the physical score.\n"
    "Every beat comes out of THIS video\u2019s own situation \u2014 its props, place and "
    "problem \u2014 and leaves a question the rest answers."
)

# The same rule for a provider whose ceiling is too low for the full set. Every
# constraint above survives; only the examples of how to satisfy them go.
_CONDENSED_OPENING = (
    "Pattern interrupt: first frame is already moving, voice already speaking; "
    "1-2s: clearly visible movement, gesture or position change \u2014 "
    "no neutral pose, fade, greeting. "
    "One beat enacts this story's central action at its sharpest instant via this video's channel (hand, face, mouth, body, camera) — snap inside the first half-second; then escalate via face, gaze, hands, "
    "posture; no resting pose, hand on the chest, or slow settle. Follow the score. Ground beats in this video's own "
    "situation; leave a question the rest answers."
)

# The Hook + CTA hook's two extra requirements (ADR 0250). They ride
# only a hook-surface plan's prompt: the regular doctrine above lets
# the opening play through a face channel (ADR 0187), but a hook's
# central action is a physical gesture by construction — its hook
# line names a moment with props in it — and Kasra's live hook opened
# on a face-only flicker instead, with the chosen place nowhere in
# frame. So for this surface the opening's channel is narrowed to the
# gesture itself, and the place is required to render as a scene.
_HOOK_PHYSICAL_OPENING = (
    "FOR THIS HOOK, THE OPENING IS PHYSICAL: the opening movement MUST be the "
    "hook's physical gesture — the story's central action performed with the "
    "hands and body, visibly in frame, the presenter framed waist-up (head, "
    "all hair and hands in frame) and already mid-gesture in the first frame. "
    "A face-only change — eyes widening, brows lifting, an expression "
    "shifting — does NOT satisfy the opening beat when the scene has a "
    "physical action to perform; the face rides the gesture, it never "
    "replaces it."
)

_CONDENSED_HOOK_PHYSICAL_OPENING = (
    "This hook opens on its physical gesture: hands and body perform the "
    "story's central action, waist-up, already mid-gesture in frame one. "
    "A face-only change does not open this hook."
)

_HOOK_REAL_SCENE = (
    "THE PLACE MUST BE IN FRAME: the location above renders as a real scene "
    "behind the presenter — its surfaces, objects and light present and "
    "readable for the whole take, the presenter inside the place, not pasted "
    "in front of nothing. A plain, empty or white background is a failed render."
)

_CONDENSED_HOOK_REAL_SCENE = (
    "The location renders as a real scene behind the presenter for the whole "
    "take; a plain or white backdrop is a failed render."
)

# ADR 0352: a present scene can still be a frozen one. The real-scene
# rule above asks for surfaces, objects and light; nothing in it asks
# the scene to MOVE, so a compliant render could hold a still-photo
# room behind a moving presenter. On a five-second hook the eye reads
# that stillness instantly. The scene itself carries subtle, secondary
# motion for the whole take — alive behind her, never competing: the
# presenter stays the motion of the shot.
_HOOK_SCENE_MOTION = (
    "THE SCENE STAYS ALIVE: the place behind the presenter moves subtly for "
    "the whole take — light shifting across a surface, a curtain stirring, "
    "distant movement passing — quiet, secondary motion that never competes "
    "with the presenter, who stays the motion of the shot. A frozen, "
    "still-photo room is a failed render."
)

_CONDENSED_HOOK_SCENE_MOTION = (
    "The scene stays alive behind the presenter — light shifting, a curtain "
    "stirring — subtle and secondary; a frozen room is a failed render."
)

# The App Profile's must_not_show list, turned into a prompt section.
#
# This field's UI label used to promise "Must never be contradicted by promos"
# and nothing checked it: it was passed to the plan and strategy prompts as
# loose context and never reached a video prompt at all, so a model that
# contradicted it had no way of knowing. Emitting it here is the whole point of
# the rename — a founder who writes "never show a hospital corridor" now gets
# that instruction attached to the render that could break it.
def must_not_show_section(profile: dict) -> str:
    """
    The app-specific things that must never appear in frame.

    Returns "" when the profile records none, so the prompt is unchanged for
    the majority of profiles rather than carrying an empty rule.
    """
    raw = (profile or {}).get("must_not_show")
    if isinstance(raw, str):
        items = [part.strip() for part in raw.split("\n") if part.strip()]
    elif isinstance(raw, (list, tuple)):
        items = [str(part).strip() for part in raw if str(part).strip()]
    else:
        return ""
    if not items:
        return ""
    # Held whole on every attempt: a refit that clips a prohibition to a stub
    # sends noise, not a rule, while the founder believes the render was told.
    listed = "; ".join(_clip(part, 30, absolute=True) for part in items[:8])
    return (
        "MUST NOT APPEAR — recorded on this app's profile as things a promo must never "
        f"contradict or show: {listed}. Do not depict any of them, do not imply them, and "
        "do not use them as a Location or prop detail."
    )


def _format_beats(beats, duration: int, hook_seconds: int = 3) -> str:
    """
    Render the beat list, or a sensible default when the plan has none.

    `hook_seconds` is the opening segment's length. It was previously hardcoded
    to 3, which contradicted the template's own hook_seconds (2-3s) arriving
    in the same prompt — so a 2s-hook template was told to hold its hook for 3
    seconds. It is now threaded through from the caller.
    """
    hook = max(1, min(int(hook_seconds or 3), max(1, duration - 1)))
    if not beats:
        # Two sections, because two sections is the whole video. The middle
        # carries everything after the hook and ends at the moment the viewer
        # reaches for the app. There is no demonstration beat and no closing
        # beat: the founder's own recording supplies both, and a plan that
        # reserved seconds for them would render footage that runs out
        # mid-thought.
        return (
            f"- 0-{hook}s: hook — the only part of this {duration}s video with {hook}s "
            f"to stop the scroll\n"
            f"- {hook}-{duration}s: middle — develops the hook through the situation and "
            f"ends on them reaching for the app. Do NOT film the app working, and do not "
            f"ask for anything: the demo and the call to action are attached afterwards."
        )
    lines = []
    for beat in beats[:10]:
        try:
            start = float(beat.get("start", 0))
            end = float(beat.get("end", start + 1))
        except (TypeError, ValueError):
            continue
        label = str(beat.get("label") or "beat").strip()
        text = _clip(beat.get("text"), 100)
        if not text:
            continue
        lines.append(f"- {start:g}-{end:g}s [{label}]: {text}")
    return "\n".join(lines) or f"- 0-{duration}s: one continuous take"


def build_single_pass_prompt(
    plan: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 20,
    segment: str = "full",
    is_extension: bool = False,
    prompt_budget: Optional[int] = None,
    script_sacred: bool = False,
) -> str:
    """
    Build the render prompt for a project that has no video strategy yet.

    Same contract as `build_segment_prompt`, and now the same mechanism: the
    ceiling comes in, the fixed floor is subtracted before the variables get
    anything, and the scale is corrected from the measured length until the
    prompt fits.

    It accepted no budget before, which made it the one prompt in the codebase
    with no way to fit a tight ceiling — nothing in it could be squeezed and a
    prompt that did not fit could only be refused. The submit path refuses a
    strategy-less project before it builds any prompt, so this is not the path
    behind the 4,152-character HeyGen refusal of the refusal era; it is the
    same ceiling with no answer for it, and it now scales and tightens like
    its sibling instead of depending on a guard.

    `script_sacred` carries the same meaning as in `build_segment_prompt`: the
    founder's spoken words hold their full budget and the direction absorbs the
    squeeze, so fitting a tight ceiling never costs the script a character.
    """
    if prompt_budget is None:
        prompt_budget = RENDER_PROMPT_LIMIT
    try:
        budget = float(prompt_budget)
    except (TypeError, ValueError):
        budget = 0.0
    # A caller bug, not a tight budget: falling back to the measured default
    # keeps the prompt whole, exactly as the segment builder does.
    if budget <= 0:
        budget = float(RENDER_PROMPT_LIMIT)

    condensed = budget < CONDENSE_BELOW
    # The same arithmetic as _budget_scale, against this builder's own floor.
    scale = max(
        MIN_SCALE,
        min(1.0, (budget - SINGLE_PASS_PROMPT_FLOOR) / float(NATURAL_VARIABLE_SPACE)),
    )
    # A plan saved before the identity rule was enforced still carries its old
    # words; the prompt is the last place that matters (ADR 0089).
    plan = _neutral_plan(plan)

    prompt = ""
    for attempt in range(MAX_FIT_ATTEMPTS):
        t_scale = _PROMPT_SCALE.set(scale)
        t_condensed = _PROMPT_CONDENSED.set(condensed)
        t_protect = _PROMPT_PROTECT.set(attempt == 0)
        t_sacred = _PROMPT_SCRIPT_SACRED.set(bool(script_sacred))
        try:
            prompt = _assemble_single_pass_prompt(
                plan, profile, template, duration, segment, is_extension,
            )
        finally:
            _PROMPT_SCRIPT_SACRED.reset(t_sacred)
            _PROMPT_PROTECT.reset(t_protect)
            _PROMPT_CONDENSED.reset(t_condensed)
            _PROMPT_SCALE.reset(t_scale)
        if len(prompt) <= budget:
            return prompt
        if scale <= MIN_SCALE:
            break
        # Correct from the measured overshoot, dividing the variable text by the
        # variable room: the fixed instructions are most of what is left on a
        # tight provider and they do not scale at all.
        variable = max(1, len(prompt) - SINGLE_PASS_PROMPT_FLOOR)
        room = budget - SINGLE_PASS_PROMPT_FLOOR
        if room <= 0:
            break
        scale = max(MIN_SCALE, scale * room / variable * 0.99)
    # The same final walk its sibling takes (ADR 0255): this builder used
    # to return whatever the correction loop bottomed out with, so a
    # prose-saturated plan at a tight budget came back over it — the
    # builder's own contract, corrected from the measured length until
    # the prompt fits, was false exactly where the budget was tightest.
    # The walk only ever tightens the app's direction wording; the
    # spoken words ride under the same sacred rule as above.
    if len(prompt) > budget:
        variable = max(1, len(prompt) - SINGLE_PASS_PROMPT_FLOOR)
        room = budget - SINGLE_PASS_PROMPT_FLOOR
        step = min(1.0, room / variable * 0.95) if room > 0 else 1.0
        step = min(step, scale)
        for _ in range(FINAL_FIT_MAX_STEPS):
            final_scale = max(FINAL_SCALE, step)
            t_scale = _PROMPT_SCALE.set(final_scale)
            t_condensed = _PROMPT_CONDENSED.set(condensed)
            t_protect = _PROMPT_PROTECT.set(False)
            t_sacred = _PROMPT_SCRIPT_SACRED.set(bool(script_sacred))
            try:
                prompt = _assemble_single_pass_prompt(
                    plan, profile, template, duration, segment, is_extension,
                )
            finally:
                _PROMPT_SCRIPT_SACRED.reset(t_sacred)
                _PROMPT_PROTECT.reset(t_protect)
                _PROMPT_CONDENSED.reset(t_condensed)
                _PROMPT_SCALE.reset(t_scale)
            if len(prompt) <= budget or final_scale <= FINAL_SCALE:
                break
            step *= FINAL_FIT_DECAY
    # The tightest tier, as on the segment builder (ADR 0327): still over
    # at FINAL_SCALE means the fixed text itself gives up its remaining
    # redundant phrasing and the walk measures once more — never a refusal.
    if len(prompt) > budget:
        step = final_scale
        for _ in range(FINAL_FIT_MAX_STEPS):
            tight_scale = max(FINAL_SCALE, step)
            t_scale = _PROMPT_SCALE.set(tight_scale)
            t_condensed = _PROMPT_CONDENSED.set(condensed)
            t_protect = _PROMPT_PROTECT.set(False)
            t_sacred = _PROMPT_SCRIPT_SACRED.set(bool(script_sacred))
            t_tightest = _PROMPT_TIGHTEST.set(True)
            try:
                prompt = _assemble_single_pass_prompt(
                    plan, profile, template, duration, segment, is_extension,
                )
            finally:
                _PROMPT_TIGHTEST.reset(t_tightest)
                _PROMPT_SCRIPT_SACRED.reset(t_sacred)
                _PROMPT_PROTECT.reset(t_protect)
                _PROMPT_CONDENSED.reset(t_condensed)
                _PROMPT_SCALE.reset(t_scale)
            if len(prompt) <= budget or tight_scale <= FINAL_SCALE:
                break
            step *= FINAL_FIT_DECAY
    return prompt


def _assemble_single_pass_prompt(
    plan: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 20,
    segment: str = "full",
    is_extension: bool = False,
) -> str:
    """
    Build the prompt for ONE coherent generation covering the whole video.

    Args:
        plan: the reviewed studio plan (hook_line, script, beats...).
        profile: the approved App Profile, used only to keep the product name
            and category accurate in any spoken or depicted context.
        template: the hook template, for visual style and pacing direction.
        duration: seconds this generation must cover.
        segment: "full" for the primary generation, or "extension" when this
            job continues a previous one.
        is_extension: True when continuing a longer video. The prompt then
            asks the model to continue seamlessly rather than open cold.
    """
    app_name = _clip((profile or {}).get("brand_name"), APP_NAME_PROMPT_CHARS) or "the app"
    hook = _clip(plan.get("hook_line"), 150)
    script = _clip(plan.get("script"), 400)
    visual = _clip(plan.get("visual_direction"), 120)
    voice = _clip(plan.get("voice_direction"), 120)
    tpl = template or {}
    tone = _clip(plan.get("tone") or tpl.get("tone"), 120)

    # The template's own opening length, clamped. This is directorial — how much
    # of the opening the hook has to land in — and NOT a render length: the whole
    # piece is this one render.
    hook_seconds = max(
        2, min(4, int(tpl.get("hook_seconds") or plan.get("hook_seconds") or 3))
    )

    sections = []

    sections.append(
        f"Create ONE continuous {duration}-second vertical (9:16) promotional video "
        f"for the app {app_name}. It must be a single coherent take containing "
        f"both the opening hook and its middle, with no visible cut to a separate clip, "
        f"no black frames, and no title card."
    )

    fixed = str(plan.get("camera_setup") or "handheld") == "fixed"
    if is_extension:
        # Unreachable in the shipped flow: a video is one render, so nothing
        # extends anything. Kept so an old project saved with extend_intent set
        # cannot produce a prompt that instructs a model to continue a chain that
        # no longer exists.
        sections.append(
            "This clip CONTINUES an existing video. Open exactly as the previous clip "
            "ended, matching its subject, framing, lighting, and motion. Do not re-introduce "
            "the app or repeat the hook; move straight into developing the situation."
        )
    else:
        # Match the template's own opening length rather than asserting a
        # constant, so this line agrees with the beat layout below and with the
        # mechanism the founder selected.
        sections.append(
            f"The first {hook_seconds} seconds are the hook and must land immediately \u2014 "
            f"she is already speaking from the first frame, no lead-in pause or silent "
            f"beat before the first word: "
            f"{hook or 'open on the strongest visual beat'}."
        )
        sections.append(
            "Open mid-motion: the first frame catches a rapid movement already underway "
            "that physically performs the story's central action at its sharpest instant, through this video's "
            "own channel — a hand or fingers, a face or expression shift, the mouth, "
            "the body, or a camera move toward the presenter — its snap complete inside "
            "the first half second. Never a resting pose, a hand sitting on the "
            "chest, or a slow settle. Close with energy: the last second or two "
            "carries a sharp closing beat with the opening's energy, never a soft "
            "fade or a passive smile hold."
        )
        sections.append(
            f"The rest of the {duration} seconds are the middle: they develop the hook through "
            f"the situation, the friction, or the reaction, then the mechanism as the resulting "
            f"benefit, then the payoff stating the outcome directly — in that order — and they end "
            + (
                f"on the moment the presenter reaches for their phone. This is the last thing in the "
                f"video — the founder records their own product demo and adds their own call to action "
                f"after it, so do not film the app being used, do not show a screen, and do not ask the "
                f"viewer to do anything."
                if fixed else
                f"before the last second on the payoff words, then one short physical ending \u2014 "
                f"never reach toward, hold, raise or show a phone or camera, and never need a second "
                f"free hand (one hand holds the camera). This is the last thing in the "
                f"video — the founder records their own product demo and adds their own call to action "
                f"after it, so do not film the app being used, do not show a screen, and do not ask the "
                f"viewer to do anything."
            )
        )

    if script:
        sections.append(f"Spoken script, performed naturally on camera or as voiceover:\n\"{script}\"")

    sections.append(
        "Beat-by-beat timeline — follow these timings:\n"
        + _format_beats(plan.get("beat_timeline"), duration, hook_seconds)
    )

    sections.append(
        "No text appears on screen at all — no captions, no titles, no labels. "
        "Render a clean frame and do not draw any text yourself."
    )

    if visual:
        sections.append(f"Visual direction: {visual}")
    if tpl.get("visual_style"):
        sections.append(f"Visual style: {_clip(tpl['visual_style'], 100)}")
    # Template camera_pacing is deliberately not emitted: the fixed camera-move
    # section owns camera words (ADR 0108) and curated pacing values ("hard cut",
    # "slow push") contradict the one-take orbit rule there. The template's
    # middle_structure is the shape carrier, not its pacing.
    if tpl.get("middle_structure"):
        sections.append(f"Middle structure to honour: {_clip(tpl['middle_structure'], 100)}")
    if voice:
        sections.append(f"Voice direction: {voice}")
    else:
        # A plan with no voice direction still needs a delivery: without this
        # the model invents its own pace, usually slow and flat.
        sections.append(
            "Delivery: fast, upbeat, high-energy — brisk confident pace, "
            "like a creator talking to a friend."
        )
    if tone:
        sections.append(f"Tone: {tone}")
    # Voice-only audio, stated outright rather than read from the plan: music
    # is banned from these renders, so the founder's saved sound direction —
    # which this line used to print — is deliberately not read here.
    sections.append(
        _TIGHTEST_AUDIO
        if _PROMPT_TIGHTEST.get() else
        "The only audio is the presenter's spoken voice. No background music, "
        "no songs, no ambient music, no sound effects — voice only."
    )
    # No call to action is appended, deliberately. The plan no longer carries a
    # `cta` field and the strategy no longer carries `cta_strategy`; the founder
    # adds their own in their editor. Reading a stale value here would put a
    # closing instruction into a video that is supposed to stop at the moment
    # the viewer reaches for the app.

    sections.append(_UI_RENDERING_WARNING)

    forbidden = must_not_show_section(profile)
    if forbidden:
        sections.append(forbidden)

    # The attached face is covered by the person anchor below, and nothing
    # else can be attached — so there is no composited-assets section. Any
    # retired uploads still sitting on an old project are refused before any
    # prompt is built, and never reach here.
    person_anchor = person_anchor_notes(plan.get("assets") or [])
    if person_anchor:
        sections.append(person_anchor)
        # Same first-frame release as the main path, worded for a prompt with
        # no scene lock: this fallback renders from the plan alone, so the
        # place comes from the described scene rather than a locked one.
        # The tightest tier drops it (ADR 0327), as on the main path.
        if not (_PROMPT_CONDENSED.get() and _PROMPT_SCRIPT_SACRED.get()) and not _PROMPT_TIGHTEST.get():
            sections.append(
                "Open in the scene described above, never the photo's room: the "
                "photo supplies only the person."
            )

    sections.append(
        "Keep one consistent person, hand, or subject for the entire clip. Vertical framing "
        "throughout. The result must look like a single real take, not an edit."
    )

    return "\n\n".join(sections)


def is_recoverable_error(message: str) -> bool:
    """
    Whether retrying the same request could plausibly succeed.

    Rate limits, timeouts, and 5xx are worth another attempt. A rejected
    prompt, an unsupported parameter, or a content-policy refusal is not —
    retrying burns money and always fails the same way.
    """
    if not message:
        return False
    text = message.lower()
    permanent_markers = (
        "content policy",
        "content_policy",
        "safety",
        "moderation",
        "sensitive",
        "sensitive_content",
        "privacy",
        "contentdetect",
        "content_detect",
        "contentfilter",
        "content_filter",
        "policy_violation",
        "policyviolation",
        "inputimage",
        "input_image",
        "unsupported",
        "not supported",
        "not support",
        "does not support",
        "invalid parameter",
        "invalid_parameter",
        "invalid resolution",
        "invalid duration",
        "input_references",
        "frame_images",
        "aspect_ratio",
        "validation",
        "expired",
        "prompt is too long",
        "rejected this render before it started",
    )
    if any(marker in text for marker in permanent_markers):
        return False
    # A 404 during poll-visibility lag is retryable; only an expired job is
    # terminal. The poll layer phrases visibility lag as "not found (404)
    # yet" so it never matches the terminal expiry marker above.
    return _has_recoverable_marker(text)


def is_rate_limit_error(message: str) -> bool:
    """
    Whether a failure is provider throttling rather than a verdict on the
    work. Narrower than is_recoverable_error on purpose: a 500 is worth one
    more attempt, but only a 429 means "asked too often" — and a throttled
    status check must never read as a broken render.
    """
    if not message:
        return False
    text = message.lower()
    return (
        "429" in text
        or "rate limit" in text
        or "rate-limit" in text
        or "too many requests" in text
    )


# Single owner for the throttling words the API returns: submit never started
# (nothing produced, nothing charged — name the wait and the retry), poll is
# still going at the provider (the row is untouched, the page keeps waiting).
RATE_LIMIT_SUBMIT_DETAIL = (
    "The video provider is handling too many requests right now, "
    "so this render never started and nothing was charged. "
    "Wait a moment, then Render it again."
)
RATE_LIMIT_POLL_DETAIL = (
    "The video provider is rate limiting status checks right now. "
    "Your render is still going \u2014 this page keeps checking on its own."
)


def _has_recoverable_marker(text: str) -> bool:
    recoverable_markers = (
        "timeout",
        "timed out",
        "429",
        "rate limit",
        "500",
        "502",
        "503",
        "504",
        "temporarily",
        "overloaded",
        "connection",
        "eof occurred",
    )
    return any(marker in text for marker in recoverable_markers)


def person_anchor_notes(assets: list) -> str:
    """
    Return a prompt section locking the on-camera person to the project's
    attached character reference, or "" when none is attached.

    The reference image itself rides along as a model input (see server.py's
    _submit_generation, which carries it as the opening frame on the studio's
    one model, HeyGen Video). This text tells the
    model what that image IS: the exact person who must appear on camera. First matching character_reference asset wins —
    attach only one per project.

    Two things this deliberately does NOT say, both learned the hard way:

    - It used to require the clothing to match the photograph too. Clothing is
      now the one thing a scene may change (the strategy picks a wardrobe, see
      character_scene_lock), so requiring it here contradicted the rest of the
      prompt.
    - It used to say "animated rather than re-imagined". That is very likely
      what grew the invented hair: video models express motion in hair by
      making it longer and flowing, so asking for the person to be *animated*
      invites the model's most confident hair behaviour. Nothing in the prompt
      forbade adding hair — only matching it — which left the addition
      unspecified and therefore free. Hence the explicit no-additions clause.
    - It used to let the image speak for the place as well as the person.
      First-frame models open ON the attached photo, so the opening was the
      uploaded room and the prompted scene only arrived mid-clip. The image
      is now authority on the person only, and the surroundings are defocused
      out of the reference itself (face_crop.defocus_outside_person) — text
      saying "not the place" never removed the place from the pixels. With the
      garment blurred too, the claim below is limited to what the reference
      actually shows: face, hair and skin, not build.
    """
    if not assets:
        return ""
    for asset in assets:
        if not isinstance(asset, dict):
            continue
        if str(asset.get("kind") or "").strip().lower() != "character_reference":
            continue
        label = _clip(asset.get("name") or asset.get("label") or "the attached character reference", 60)
        if _PROMPT_CONDENSED.get() and _PROMPT_SCRIPT_SACRED.get():
            return (
                "The person on camera is the person in the attached character reference "
                f"({label}): same face, skin and age, and the same hair; no additions, "
                "removals, restyling or blending. The image is the only authority on the person, "
                "not the place; the scene sets clothing. Move and speak naturally."
            )
        return (
            "The person on camera is the person in the attached character reference "
            f"image ({label}). Copy that person exactly: same face, skin and age, "
            "and the same hair — same hairline, colour, length, texture and parting. "
            "Their appearance is fixed by that photograph: do not add, lengthen, restyle "
            "or recolour their hair, and do not add or remove anything absent from the "
            "image (hats, glasses, jewellery, makeup). Move and speak naturally, but do "
        "not change who they are. The image is the only authority on the person — "
        "face, hair and skin, not the place. Where this prompt states otherwise "
        "about who they are, ignore the text and follow the image. Do not invent "
        "a different person and do not blend "
        "them with anyone else. Their clothing is the one exception: the scene above "
        "sets it, and it need not match the photograph."
        )
    return ""


# ---------------------------------------------------------------------------
# App-specific influencer segments
# ---------------------------------------------------------------------------
# Below here is the segmented influencer workflow. build_single_pass_prompt()
# above stays as the one-shot path: it is correct for a single generation and
# is covered by its own tests. These builders differ in kind rather than degree
# — they take a video STRATEGY (app-specific concept, locked persona, locked
# scene, continuity contract) and emit the prompt for ONE segment of it.

_SECTION_LABELS = {
    "character": (
        ("appearance", "overall look"),
        ("facial_features", "face"),
        ("hairstyle", "hair"),
        ("age_range", "apparent age"),
        ("body_appearance", "build and posture"),
        ("wardrobe", "wardrobe"),
        ("styling_details", "styling details"),
        ("facial_expression", "expression"),
    ),
    "scene": (
        ("location", "Location"),
        ("camera_angle", "camera angle"),
        ("framing", "framing"),
        ("lighting", "lighting"),
        ("color_palette", "colour palette"),
        ("visual_style", "visual style"),
        ("character_positioning", "position in frame"),
        # Wardrobe is the one presentational field that reaches the lock. It is
        # chosen by the strategy to suit Location and holds for both
        # sections, which is why it belongs to the scene rather than to the
        # person: everything about the person is the photograph's job.
        ("wardrobe", "wardrobe"),
        ("props", "props"),
    ),
    "performance": (
        ("movement", "movement"),
        ("voice_delivery", "voice delivery"),
    ),
}


def character_scene_lock(strategy: dict, location: str = "") -> str:
    """
    Render the strategy's scene and performance as an explicit do-not-change
    block.

    A video model has no memory of the previous segment. Anything not restated
    is an invitation to reinvent it, and the attributes it reinvents most
    reliably are the scene, the wardrobe and the camera — so every attribute
    the strategy fixed is written out again, by name, as a locked value.

    The person's appearance is deliberately NOT restated. The on-camera person is
    copied from the founder's uploaded character reference image, and this
    function used to write a model's guess at that face, hair, age and wardrobe
    alongside the photograph, under a heading telling the provider both were
    locked. Strategies generated before that was removed still carry such a
    block, so "character" is skipped here by name rather than trusted.

    Wardrobe is the deliberate exception, and it sits in the scene rather than
    the person for a reason: the strategy chooses clothes to suit Location,
    and a scene that claims someone has to keep them in the same outfit for
    both sections. Locking it here is what makes "do not re-wardrobe" in the
    trailer below enforceable — the clothing is stated once, by the thing that
    decided it, instead of being left to the photograph and the model to
    reconcile.

    `location` is the plan's Location when one exists: the single source of
    truth for the place (ADR 0090). The lock's own location field is then
    skipped — the Location text above states the place once, and an older
    strategy copy naming a room again is exactly the contradiction that used
    to win over an edited Location. With no Location, the strategy's place
    field is what there is, and it is stated as before.

    Camera setup owns position and framing. Older camera_angle/framing fields
    are omitted; fixed-camera directions are validated before prompt assembly.
    The lock still owns the room, light, wardrobe and props. Only handheld
    footage receives the processing zoom.
    """
    strategy = strategy or {}
    lines = []
    # The place is named once, from the Location, whenever there is one. The
    # current schema's place field is "location"; the other three are legacy
    # split names an old row may still carry.
    skip = (
        {"location", "environment", "background", "setting"}
        if str(location or "").strip() else set()
    )
    for section, fields in _SECTION_LABELS.items():
        if section == "character":
            continue
        values = strategy.get(section)
        if not isinstance(values, dict):
            continue
        described = [
            f"{label}: {_clip(values.get(key), 300 if key == 'location' else 100, protect=True, absolute=key == 'location')}"
            for key, label in fields
            # The fixed selfie instruction replaces even an older strategy's
            # metre-based camera/framing fields, rather than contradicting them.
            # The Location owns place when it exists (ADR 0090).
            if not (section == "scene" and key in {"camera_angle", "framing"} | skip)
            and str(values.get(key) or "").strip()
        ]
        if described:
            lines.append("\n".join(f"  {item}" for item in described))

    if not lines:
        return ""
    lock = (
        "THE SCENE AND THE DELIVERY ARE LOCKED. Reproduce these exactly — same place, "
        "same light, same wardrobe and props, same way of moving and speaking:\n"
        + "\n".join(lines)
        + "\n\nDo not swap in a different location, prop or outfit, even if the "
        "later part of the story would seem to call for it."
    )
    # The block as a whole is capped, not just its values: scene fields come
    # first so a pathological strategy loses the performance tail, never the
    # location and light the render needs most. Sized to clear a realistic
    # full lock (~1,050 with every field populated) — anything lower
    # amputates pinned fields even for ordinary strategies.
    return _clip(lock, 1100, protect=True)


def _brief_field(value, limit: int) -> str:
    """Normalize one opening-brief value without touching prompt-budget state."""
    return " ".join(str(value or "").split())[:limit].rstrip()


# The person-describing fields of a plan and a strategy: everything a viewer
# hears or sees. They are neutralized again here because a project saved before
# the identity rule was enforced still carries its old words, and the render
# prompt is the last place that matters — the person on screen is the founder's
# uploaded photo, so a written gender or role is the one thing the model must
# never be told (ADR 0089). `demo_brief` is absent on purpose: it is addressed to
# the founder, not about the person on camera.
_PLAN_PERSON_FIELDS = (
    "hook_line", "script", "visual_direction", "voice_direction", "sound_direction",
)
_STRATEGY_PERSON_FIELDS = (
    "strategy_summary", "audience_problem", "hook_concept", "hook_line",
    "hook_promise", "hook_action", "hook_dialogue", "primary_feature",
    "desired_outcome", "mechanism_beat", "payoff_beat", "differentiation_beat",
)
_STRATEGY_PERSON_SECTIONS = ("scene", "performance")
_STRATEGY_PERSON_LISTS = ("emotional_triggers", "messaging_pillars")
_SEGMENT_PERSON_FIELDS = ("goal", "script", "action")


def _neutral_plan(plan) -> dict:
    """The plan with every line a viewer hears or sees made identity-neutral."""
    if not isinstance(plan, dict):
        return plan
    out = character_policy.neutralize_fields(plan, _PLAN_PERSON_FIELDS)
    beats = []
    for beat in out.get("beat_timeline") or []:
        if isinstance(beat, dict):
            beat = dict(beat)
            if isinstance(beat.get("text"), str):
                beat["text"] = character_policy.neutralize(beat["text"])
        beats.append(beat)
    if beats:
        out["beat_timeline"] = beats
    return out


def _neutral_strategy(strategy) -> dict:
    """The strategy with every person-describing field made identity-neutral."""
    if not isinstance(strategy, dict):
        return strategy
    out = character_policy.neutralize_fields(strategy, _STRATEGY_PERSON_FIELDS)
    for name in _STRATEGY_PERSON_SECTIONS:
        section = out.get(name)
        if isinstance(section, dict):
            out[name] = {
                key: character_policy.neutralize(value) if isinstance(value, str) else value
                for key, value in section.items()
            }
    for name in _STRATEGY_PERSON_LISTS:
        values = out.get(name)
        if isinstance(values, list):
            out[name] = [
                character_policy.neutralize(value) if isinstance(value, str) else value
                for value in values
            ]
    segments = out.get("segments")
    if isinstance(segments, list):
        neutral = []
        for segment in segments:
            if isinstance(segment, dict):
                segment = dict(segment)
                for key in _SEGMENT_PERSON_FIELDS:
                    if isinstance(segment.get(key), str):
                        segment[key] = character_policy.neutralize(segment[key])
            neutral.append(segment)
        out["segments"] = neutral
    return out


def strategy_brief(strategy: dict) -> str:
    """
    Render the app-specific strategy into prompt text.

    What is NOT here matters as much as what is. There is no cta line: a call to
    action is added by the founder in their own editor, and instructing the
    render to end on one would put a closing beat into footage that is supposed
    to stop at the moment the viewer reaches for the app. There is no
    "the one feature shown" line either, for the same reason the plan carries a
    demo_brief rather than a feature_emphasis: a feature instruction that
    reaches the render is a product demo being generated, and this workflow does
    not generate one. The differentiation and desired-outcome lines stay — they
    are how the middle frames the situation, not what it demonstrates.

    The problem, outcome and differentiation are restated rather than assumed to
    have been absorbed, so a single render cannot drift into a generic
    advertisement. The feature is named as subject matter only: what this app is
    about is what the middle is set in, not an instruction to film it working.
    The mechanism and payoff lines are the middle's pitch moments in order:
    benefit-framed how-it-helps first, the outcome stated directly last.
    """
    strategy = strategy or {}
    # Order is load-bearing: the brief is capped at 700 chars below, so the
    # pitch (problem/mechanism/payoff/differentiation) comes first and the
    # generic context (summary/triggers/pillars) last. Previously the summary
    # headed the brief and a realistic full brief was cut mid-payoff and never
    # reached differentiation.
    parts = []

    problem = _clip(strategy.get("audience_problem"), 200)
    if problem:
        parts.append(f"The problem this viewer actually has: {problem}")

    mechanism = _clip(strategy.get("mechanism_beat"), 200)
    if mechanism:
        # Benefit-framed how-it-works, not a filming order: the render shows
        # the situation the mechanism belongs to, the words carry the benefit.
        parts.append(f"Mechanism, as the resulting benefit (describe, never film working): {mechanism}")

    payoff = _clip(strategy.get("payoff_beat"), 200)
    if payoff:
        parts.append(f"Payoff, stated directly as the last thing said: {payoff}")

    diff = _clip(strategy.get("differentiation_beat"), 200)
    if diff:
        parts.append(f"How this app is different: {diff}")

    feature = _clip(strategy.get("primary_feature"), 200)
    if feature:
        # Subject matter, not an instruction. The old wording ("The one feature
        # shown: {feature}. Show it in use, not described.") was a direct
        # product-demo order reaching the render prompt on every generation.
        parts.append(
            f"What this app is about (the situation the middle is set in, never filmed "
            f"working): {feature}"
        )

    outcome = _clip(strategy.get("desired_outcome"), 200)
    if outcome:
        parts.append(f"Outcome the viewer should expect: {outcome}")

    triggers = [_clip(t, 80) for t in (strategy.get("emotional_triggers") or []) if str(t).strip()]
    if triggers:
        parts.append(f"Emotions to land: {'; '.join(triggers[:4])}")

    pillars = [_clip(p, 100) for p in (strategy.get("messaging_pillars") or []) if str(p).strip()]
    if pillars:
        # Outcome-framed by construction: the strategy prompt asks for
        # benefits here, never the feature spec, so the label says outcomes.
        parts.append("Outcomes that must be delivered: " + "; ".join(pillars[:4]))

    summary = _clip(strategy.get("strategy_summary"), 250)
    if summary:
        parts.append(f"Strategy for this video: {summary}")

    if not parts:
        return ""
    brief = "THIS APP-SPECIFIC STRATEGY — it governs this whole video:\n" + "\n".join(
        f"  {p}" for p in parts
    )
    # The brief as a whole is capped: its head (problem, mechanism, payoff,
    # differentiation) carries the pitch the render needs, so a pathological
    # strategy loses the generic tail (summary/triggers/pillars), never the
    # payoff. Sized to clear a realistic full brief — lower cuts context lines
    # out of ordinary strategies while keeping the pitch whole.
    return _clip(brief, 700, protect=True)


def story_brief_section(strategy) -> str:
    """The STORY FRAME section for a story render (ADR 0228).

    A story plan stores its frame brief on the strategy under
    `story_brief` (the type's name, the frame's seconds, the accepted
    screen text). When it is present, the prompt says what the render
    is: a single story frame of exactly that many seconds, one idea,
    with the placement discipline the native text sticker needs — the
    founder places the screen text at posting, so the presenter never
    gestures over the lower third where that sticker will sit. When it
    is absent — every hook-video render — this returns "" and the
    assembled prompt is byte-identical to before.
    """
    brief = strategy.get("story_brief") if isinstance(strategy, dict) else None
    if not isinstance(brief, dict):
        return ""
    seconds = int(brief.get("frame_seconds") or 0) or 10
    type_name = str(brief.get("story_type_name") or "Story").strip() or "Story"
    screen_text = str(brief.get("screen_text") or "").strip()
    lines = [
        "STORY FRAME:",
        f"- This render is a single story frame of {seconds} seconds "
        f"({type_name}) — one self-contained vertical story, not part of "
        "a longer video. Hold the frame's one idea for the whole "
        f"{seconds} seconds; nothing is cut or continued later.",
        "- The founder places the frame's on-screen text as a native "
        "text sticker after the render: keep the lower third of the "
        "frame visually clean — no gesturing over it, nothing important "
        "living there — so the placed text stays readable.",
    ]
    if screen_text:
        lines.append(
            f"- The placed text will read: \"{screen_text}\" — perform "
            "the moment it names; never mouth it as on-screen copy or "
            "point at where it will sit."
        )
    return "\n".join(lines)


def build_segment_prompt(
    strategy: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 4,
    assets: Optional[list] = None,
    plan: Optional[dict] = None,
    prompt_budget: Optional[int] = None,
    script_sacred: bool = False,
    angle: Optional[dict] = None,
) -> str:
    """
    Build the prompt for the whole generated piece: a hook and a middle.

    Thin wrapper that establishes the per-provider character ceiling and then
    hands off to the assembler. Split out so the scale is set and cleared around
    the whole assembly rather than inside it — the budget has to reach every
    _clip call, including the ones in the four helpers this calls, and those have
    no reason to know which provider is rendering.

    Args:
        strategy: the normalized app-specific strategy (see
            ai_service.normalize_strategy). Required: without it there is no
            app specificity to preserve.
        profile: the approved App Profile, for the accurate product name.
        template: the hook template, for mechanism and pacing language.
        duration: seconds the whole piece must cover.
        assets: the project's attached assets (character_reference etc).
        plan: the reviewed creative plan, read only for `hook_seconds` so the
            two sections are split at the boundary the plan and the strategy
            both agreed on. Nothing else is taken from it: the strategy already
            carries the approved words.
        prompt_budget: this render's character ceiling. Defaults to
            RENDER_PROMPT_LIMIT — HeyGen Video's 4,090, the only model's.
            A caller with a lower budget passes its own; every field budget is
            scaled down to fit rather than the tail being cut off. A ceiling low
            enough to leave the fixed instructions most of the budget (see
            CONDENSE_BELOW) also switches the fixed text to its condensed form,
            so a tight provider gets a shorter prompt rather than a truncated
            one. Both mean the same constraints, so the model sees the same
            rules from every provider — only the wording is tighter.

            Under a tight ceiling the spoken script, the on-camera action and
            the app's strategy and locked scene keep their full budgets and the
            descriptive text absorbs the squeeze, because a prompt missing half
            of what the founder is going to say is not a shorter prompt, it is
            a different video. Clipping also ends on a sentence or word
            boundary rather than mid-word. If the result is still over budget
            it is rebuilt with a smaller scale, so a very full strategy thins
            out instead of being refused.

        script_sacred: when True, the spoken script — the hook line and the two
            section scripts — holds its full budgets on EVERY attempt, and only
            the direction and template wording is trimmed to fit. Protection
            above is withdrawn after the first attempt; sacred never is. The
            server sets this for heygen-video-1, whose 4,090 ceiling tripped the
            withdrawal on ordinary strategies and ate the founder's own words.
        angle: the stored content-angle row for this project, when the caller
            has it. It carries the opening moment the plan Location must agree
            with. The server resolves it from the database and passes it here;
            this module stays pure. Absent means there is no row to compare.
    """
    require_camera_setup_directions(strategy)
    # A strategy stored before the identity rule was enforced still carries its
    # old words, and the prompt is the last place that matters (ADR 0089).
    strategy = _neutral_strategy(strategy)
    plan = _neutral_plan(plan)
    # The plan's Location is the single source of truth for the place
    # (ADR 0090). If the strategy's own scene still names a different room
    # — a pasted template Venue — the lock would carry both places and the
    # model would pick the pasted one. Overwrite the strategy's place
    # fields with the plan's Location so the lock states the place once.
    # The angle's own scene is the third carrier: its hook_promise names
    # the opening moment, and scene_location_guidance repeats it as
    # "ANGLE SCENE (outranks everything below)". When the founder edits
    # the Location, the angle rows themselves do not change, so a
    # Location garden-path-vs-sidewalk divergence would otherwise reach
    # the model as two places. Check the stored angle row against the
    # plan Location here and refuse when they contradict, rather than
    # rendering a two-place prompt.
    plan_location = (plan.get("location") if isinstance(plan, dict) else "") or ""
    plan_location = " ".join(str(plan_location).split()).strip()
    if plan_location and isinstance(strategy, dict):
        from angle_scene import angle_scene as _angle_scene_fn
        from angle_scene import conflict_reason as _conflict_fn
        angle = angle or (plan.get("angle") if isinstance(plan, dict) else None)
        # Legacy strategy rows carry the angle itself. Current callers pass
        # the stored row explicitly, because this module is pure and cannot
        # read the database. Missing both means there is no angle to compare
        # with the Location — not a reason to crash an otherwise ready render.
        if angle is None and isinstance(strategy.get("content_angle"), dict):
            angle = strategy.get("content_angle")
        if isinstance(angle, dict) and angle.get("hook_promise"):
            reason = _conflict_fn(plan_location, _angle_scene_fn(angle))
            if reason:
                raise ValueError(
                    f"This render was stopped before it cost anything: the Location "
                    f"is \u201c{plan_location}\u201d, but the selected angle opens "
                    f"\u201c{str(angle.get('hook_promise') or '')[:90]}\u201d, "
                    f"which {reason}. The angle's opening moment and the Location "
                    "must name the same place. Pick a different angle, or edit "
                    "the Location back to the angle's moment, then generate again. "
                    "Nothing has been charged."
                )
    if plan_location and isinstance(strategy, dict):
        scene = strategy.get("scene")
        if isinstance(scene, dict):
            stale = scene.get("location")
            if stale and " ".join(str(stale).split()).strip() != plan_location:
                import re as _re
                def _conflict(val):
                    text = _re.sub(r"\s+", " ", str(val or "")).strip()
                    if not text:
                        return False
                    # Location here is the plan's full precise phrase; a pasted
                    # Venue is a different room. Treat any non-empty strategy
                    # place that is not a substring of the plan Location (or
                    # vice versa) as a conflict.
                    return text.lower() not in plan_location.lower() and \
                           plan_location.lower() not in text.lower()
                if _conflict(stale):
                    scene["location"] = plan_location
    scale = 1.0
    condensed = False
    budget = 0.0
    # The default is the measured ceiling, as the docstring says it is.
    # It used to be no ceiling at all: a caller that passed nothing got a
    # prompt assembled at full size, which only stayed under 6,800 while
    # every field budget fitted inside it. The opening detail raised the
    # saturated worst case past the limit, and the overflow surfaced as a
    # provider refusal rather than as a prompt that was too long — the
    # same strategy still renders fine on every normal input. Enforcing the
    # default is what the parameter always claimed to do.
    if prompt_budget is None:
        prompt_budget = RENDER_PROMPT_LIMIT
    try:
        budget = float(prompt_budget)
    except (TypeError, ValueError):
        budget = 0.0
    # A zero, negative or non-numeric budget is a caller bug, not a tight
    # budget. Falling back to the measured default keeps the prompt whole;
    # clamping it would silently shrink every render to a tenth of
    # its detail because someone passed -1. The fallback budget derives
    # its condensed flag and scale like any other budget (ADR 0327):
    # normalizing only the number left a nonsense budget building the
    # full form at scale 1.0 and squeezing from there — a different
    # prompt from the default build it claims to fall back to, which
    # only stayed invisible while the default ceiling was roomy enough
    # for the two to coincide.
    if budget <= 0:
        budget = float(RENDER_PROMPT_LIMIT)
    condensed = budget < CONDENSE_BELOW
    # A hook-surface render carries its own fixed passages (ADRs
    # 0250/0352); its floor counts them (see _hook_floor_extra).
    hook_surface = str((plan or {}).get("surface") or "") == "hook_cta"
    scale = _budget_scale(budget, condensed, _prompt_floors(strategy, condensed, hook_surface))

    # Protected values hold their full budget, so the scale is no longer a
    # reliable predictor of the assembled length and can undershoot on a very
    # full strategy. Measure what was actually built and squeeze again rather
    # than hand back an over-budget prompt: an over-budget assembly makes the
    # model unusable for exactly the detailed founders who gave it the most
    # to work with.
    prompt = ""
    for attempt in range(MAX_FIT_ATTEMPTS):
        token = _PROMPT_SCALE.set(scale)
        token2 = _PROMPT_CONDENSED.set(condensed)
        token3 = _PROMPT_PROTECT.set(attempt == 0)
        token4 = _PROMPT_SCRIPT_SACRED.set(bool(script_sacred))
        try:
            prompt = _assemble_prompt(strategy, profile, template, duration, assets, plan)
        finally:
            _PROMPT_SCRIPT_SACRED.reset(token4)
            _PROMPT_PROTECT.reset(token3)
            _PROMPT_CONDENSED.reset(token2)
            _PROMPT_SCALE.reset(token)
        if not budget or len(prompt) <= budget:
            return prompt
        # Still over: correct the scale by the measured overshoot and reassemble.
        # Protection is already withdrawn from here, so this is the plain scaled
        # build. Falls back to a real reduction if the scale has bottomed out.
        #
        # The correction divides the VARIABLE text by the variable room, not the
        # whole prompt by the whole ceiling. The fixed instructions are most of
        # what is left on a tight provider and they do not scale at all, so
        # scaling by budget/length asks for far less squeeze than the variables
        # can actually give: the loop then crawls toward the ceiling and runs out
        # of attempts still over it. The floors are measured from exactly this
        # fixed text with no variables at all, so subtracting one lands the next
        # pass inside.
        if scale <= MIN_SCALE:
            break
        fixed = _prompt_floors(strategy, condensed, hook_surface)
        variable = max(1, len(prompt) - fixed)
        room = budget - fixed
        if room <= 0:
            break
        scale = max(MIN_SCALE, scale * room / variable * 0.99)

    # Still over after the correction loop. That means the scale bottomed out at
    # MIN_SCALE with the prompt above the ceiling, and in the refusal era the
    # remaining outcome was the submit guard refusing the render — the founder
    # reading that their script was too long when it was the description around
    # it that would not fit. That is the shape of the report this closes: a
    # project refused only by the tightest provider, with a prompt over its
    # ceiling by a little.
    #
    # MIN_SCALE is a readability floor, not a physical limit: it exists so a
    # prompt never reads as one-character stubs, not because a field cannot carry
    # less. So one final pass is allowed below it, sized from the measured
    # overshoot rather than guessed. The fixed instructions and the founder's
    # spoken words still do not move — they are what remains once everything else
    # has given way — so a terse brief that fits beats a refusal, and a provider
    # ceiling becomes a guarantee rather than a hope that every value reaching
    # the prompt happens to be clipped.
    if budget and len(prompt) > budget:
        fixed = _prompt_floors(strategy, condensed, hook_surface)
        variable = max(1, len(prompt) - fixed)
        room = budget - fixed
        # Walk the scale down and MEASURE, rather than predicting one value and
        # hoping. Two things made the old single-shot prediction wrong:
        #
        # 1. It clamped its own result to MIN_SCALE, so this fallback could only
        #    ever be maximally destructive. A prompt over its ceiling by one
        #    percent and one over by half were clamped to the same 0.1, and
        #    every variable came back a one-word stub.
        # 2. It assumed variable text scales linearly with the scale factor. It
        #    does not: _clip applies an effective limit per field, so a field
        #    already under its limit does not shrink at all and a field well
        #    over it shrinks far faster. Measured against a real prompt, the
        #    arithmetic above predicted reclaiming 133 characters per pass and
        #    reclaimed 11.
        #
        # Between them, a 101-character overflow produced a prompt mangled to
        # 4,969 characters, with the scene, the spoken words and both sections
        # truncated to about ten characters each. The correction loop cannot
        # close a gap that small in the six attempts it has, so every overflow
        # arrived here regardless of size.
        #
        # Stepping down until the assembled prompt actually fits is the only
        # version of this that can be trusted, and it costs one extra assembly
        # per step. FINAL_SCALE still bounds a hopeless case: at or below it the
        # walk stops, and a budget at or under the fixed floor makes room
        # non-positive so the first scale is already FINAL_SCALE.
        step = min(1.0, room / variable * 0.95) if room > 0 else 1.0
        # Never step UP from where the correction loop ended (ADR 0255).
        # The step above is sized from the current prompt's length as
        # though it were unscaled variable text, but the loop has already
        # squeezed that text: on the traced fixed-camera build the formula
        # proposed 0.83 while the loop had bottomed out at 0.10, and the
        # old eight-step cap decayed it only to ~0.069 — still above the
        # ~0.03 where that prompt fits — so the walk handed back the
        # over-budget assembly it was written to prevent, and the submit
        # guard refused a render whose words were never the problem. The
        # walk starts no higher than the loop's own scale and keeps
        # stepping until the prompt fits or FINAL_SCALE is reached.
        step = min(step, scale)
        for _ in range(FINAL_FIT_MAX_STEPS):
            final_scale = max(FINAL_SCALE, step)
            token = _PROMPT_SCALE.set(final_scale)
            token2 = _PROMPT_CONDENSED.set(condensed)
            token3 = _PROMPT_PROTECT.set(False)
            token4 = _PROMPT_SCRIPT_SACRED.set(bool(script_sacred))
            try:
                prompt = _assemble_prompt(
                    strategy, profile, template, duration, assets, plan)
            finally:
                _PROMPT_SCRIPT_SACRED.reset(token4)
                _PROMPT_PROTECT.reset(token3)
                _PROMPT_CONDENSED.reset(token2)
                _PROMPT_SCALE.reset(token)
            if len(prompt) <= budget or final_scale <= FINAL_SCALE:
                break
            step *= FINAL_FIT_DECAY

    # Still over at FINAL_SCALE: the unscalable mass alone — the condensed
    # fixed text, the absolutes, the sacred words — exceeds the budget.
    # Until ADR 0327 this prompt went back over budget and the submit path
    # refused the render, latterly suggesting the founder switch to the
    # roomier model. That model is gone and the refusal with it (Kasra's
    # order): the tightest tier engages instead — the fixed direction text
    # gives up its remaining redundant phrasing (see _PROMPT_TIGHTEST) —
    # and the same measured walk runs once more against the shorter text,
    # starting from the scale the walk bottomed out at. The spoken words
    # do not move at this tier either.
    if budget and len(prompt) > budget:
        step = final_scale
        for _ in range(FINAL_FIT_MAX_STEPS):
            tight_scale = max(FINAL_SCALE, step)
            token = _PROMPT_SCALE.set(tight_scale)
            token2 = _PROMPT_CONDENSED.set(condensed)
            token3 = _PROMPT_PROTECT.set(False)
            token4 = _PROMPT_SCRIPT_SACRED.set(bool(script_sacred))
            token5 = _PROMPT_TIGHTEST.set(True)
            try:
                prompt = _assemble_prompt(
                    strategy, profile, template, duration, assets, plan)
            finally:
                _PROMPT_TIGHTEST.reset(token5)
                _PROMPT_SCRIPT_SACRED.reset(token4)
                _PROMPT_PROTECT.reset(token3)
                _PROMPT_CONDENSED.reset(token2)
                _PROMPT_SCALE.reset(token)
            if len(prompt) <= budget or tight_scale <= FINAL_SCALE:
                break
            step *= FINAL_FIT_DECAY
    return prompt


def _assemble_prompt(
    strategy: dict,
    profile: dict,
    template: Optional[dict] = None,
    duration: int = 4,
    assets: Optional[list] = None,
    plan: Optional[dict] = None,
) -> str:
    """
    Assemble the render prompt. See build_segment_prompt for the arguments.

    The name of the public wrapper is historical. A video used to be assembled
    from separately rendered segments, one per beat, and the builder chose the
    prompt for whichever one was being made. Now the hook and the middle are a
    single render, so this builds the whole thing. There is no `segment_index`,
    `continuity`, `is_hook` or `previous_summary` argument: all four described a
    seam between two clips, and there is no seam.

    What holds the two sections together is the scene lock plus the app-specific
    brief, both of which apply to the whole piece.
    """
    strategy = strategy or {}
    tpl = template or {}
    plan = plan or {}
    app_name = _clip((profile or {}).get("brand_name"), APP_NAME_PROMPT_CHARS) or "the app"
    seconds = max(1, int(duration or 0))

    sections = []

    condensed = _PROMPT_CONDENSED.get()
    # The whole piece is one render with two sections, so both are always
    # described: index 0 is the hook and index 1 is the middle. Which is which
    # comes from the section's role, not its position, so a strategy whose
    # middle is missing still renders the hook and says plainly that it has no
    # middle to film rather than stretching the hook over the whole runtime.
    #
    # Condensed, the section structure is not restated here: the two headings
    # below carry the real durations and jobs, so this sentence would be saying
    # it a third time in shorter words.
    fixed = str(strategy.get("camera_setup") or "handheld") == "fixed"
    if not condensed:
        sections.append(
            f"Create ONE continuous {seconds}-second vertical (9:16) promotional video for the "
            f"app {app_name}, containing exactly TWO sections: a HOOK in the opening "
            f"seconds, then a MIDDLE that develops it. It must read as a single take — no visible "
            f"cut to a separate clip, no black frames, no title card."
        )
        # Stated up front rather than left to the beat list, because this is the
        # single most important constraint on the render and the model has a strong
        # prior towards resolving a promo on camera.
        sections.append(
            "This video ends before the product is shown. The founder records their own demo and "
            "attaches it after this footage, and adds their own call to action. So: do NOT film the "
            "app being used, do NOT show a screen or interface, do NOT describe the app working "
            "while something unrelated happens on camera, and do NOT ask the viewer to download, "
            + (
                "install or try anything. End on the moment the presenter reaches for their phone."
                if fixed else
                # No "End before the last second" here: the MIDDLE heading
                # states that boundary verbatim, in every build (ADR 0213
                # paid for the wider selfie framing out of this duplicate).
                "install or try anything."
            )
        )
    else:
        sections.append(
            f"Create ONE continuous {seconds}-second vertical (9:16) promotional video for the "
            f"app {app_name}, in two sections. "
            + (
                "End on the moment the presenter reaches for their phone, and do not ask the viewer "
                "to download or install anything."
                if fixed else
                "Then one short physical ending, and do not ask "
                "the viewer to download or install anything."
            )
        )
        sections.append(_TIGHTEST_HANDOFF if _PROMPT_TIGHTEST.get() else _CONDENSED_HANDOFF)

    # The requirement the beats below have to satisfy. Placed ahead of them, so
    # the model reads it as the standard for what follows rather than as another
    # fact about the video.
    sections.append(
        _TIGHTEST_OPENING
        if _PROMPT_TIGHTEST.get() and condensed else
        _CONDENSED_OPENING if condensed else _OPENING_INTERRUPT
    )

    # A hook render's opening is its physical gesture, not a face
    # channel (ADR 0250) — stated beside the general opening rule it
    # narrows, and only for the hook surface: every other plan's
    # prompt is byte-for-byte what it was.
    if str(plan.get("surface") or "") == "hook_cta":
        sections.append(
            _CONDENSED_HOOK_PHYSICAL_OPENING if condensed else _HOOK_PHYSICAL_OPENING
        )

    hook_line = _clip(strategy.get("hook_line"), 200, protect=True, sacred=True)
    hook_concept = _clip(strategy.get("hook_concept"), 120, protect=True)
    hook_action = _clip(strategy.get("hook_action"), 280, protect=True)
    hook_dialogue = _clip(strategy.get("hook_dialogue"), 75)
    promise = _clip(strategy.get("hook_promise"), 40)
    # bind_spoken_words copies the approved hook line into segments[0].script,
    # so the same words would otherwise be spoken three times (top-level hook
    # line, hook_dialogue, and the HOOK section below). The top-level line is
    # the canonical carrier and always emits; the section copy is dropped when
    # verbatim identical. hook_dialogue emits only when it adds delivery
    # direction beyond the hook line.
    _hook_section = next(
        (s for s in (strategy.get("segments") or [])
         if isinstance(s, dict) and str(s.get("role") or "").strip().lower() == "hook"),
        {},
    )
    _hook_script_raw = " ".join(str(_hook_section.get("script") or "").split()).strip()
    _hook_action_raw = " ".join(str(_hook_section.get("action") or "").split()).strip()
    _hook_line_raw = " ".join(str(strategy.get("hook_line") or "").split()).strip()
    _hook_dialogue_raw = " ".join(str(strategy.get("hook_dialogue") or "").split()).strip()
    _hook_action_top_raw = " ".join(str(strategy.get("hook_action") or "").split()).strip()
    if hook_concept:
        sections.append(f"What the opening must DO: {hook_concept}")
    if hook_line:
        sections.append(f"The spoken hook line, delivered on camera: \"{hook_line}\"")
    # The top-level hook action is the full score (280-char budget); the hook
    # section's copy is dropped when verbatim identical so the score is stated
    # once, whole. With no hook section the top-level line is the only carrier.
    if hook_action:
        sections.append(f"What the person physically does in the opening: {hook_action}")
    if hook_dialogue and _hook_dialogue_raw not in (
        _hook_line_raw, _hook_script_raw,
    ):
        sections.append(f"Dialogue and delivery: {hook_dialogue}")
    if promise:
        sections.append(f"What the hook promises: {promise}")

    # The Location, named once. It is the plan's own Location — the single
    # source of truth for where and when the video happens (ADR 0090) — and
    # the lock below skips its own place field whenever this exists, so an
    # older strategy's room text can no longer compete with it.
    # `visual_direction` is the legacy mirror for rows written before the
    # rename, so it is read as a fallback.
    location = _clip(
        plan.get("location") or plan.get("visual_direction"), 160, protect=True
    )
    if location:
        # The tightest tier shortens the label (ADR 0327): the scene lock
        # below carries the one-place rule in full, so the label's own
        # restatement is the redundancy that gives.
        sections.append(
            f"WHERE — one place, one time, whole take: {location}"
            if _PROMPT_TIGHTEST.get() else
            "WHERE THIS HAPPENS — one place, one time, for the whole take, and "
            f"every visual detail happens here: {location}"
        )
        # A hook render must actually show its place (ADR 0250):
        # Kasra's live hook rendered on a plain white backdrop
        # despite a chosen location, so the requirement is stated
        # as a defect to avoid, beside the place it governs.
        if str(plan.get("surface") or "") == "hook_cta":
            sections.append(
                _CONDENSED_HOOK_REAL_SCENE if condensed else _HOOK_REAL_SCENE
            )
            # And the scene must move, not merely be present (ADR
            # 0352): subtle, secondary motion behind the presenter
            # for the whole take, stated beside the presence rule it
            # extends, on this surface only.
            sections.append(
                _CONDENSED_HOOK_SCENE_MOTION if condensed else _HOOK_SCENE_MOTION
            )

    lock = character_scene_lock(strategy, location)
    if lock:
        sections.append(lock)

    brief = strategy_brief(strategy)
    if brief:
        sections.append(brief)

    story_brief = story_brief_section(strategy)
    if story_brief:
        sections.append(story_brief)

    # The seam block that used to live here is gone. It described carrying a
    # previous clip's frame, its established facts and its do-not-repeat list
    # into a continuation — all of which presupposed a second render. One
    # render has no previous clip, so the only thing that has to hold the two
    # sections together is the scene lock above.

    # Both sections, in order, so the model has the whole piece in front of it
    # rather than one beat at a time. Roles are read rather than assumed, so a
    # strategy that names them out of order still films the hook first.
    sections_by_role = {
        str(s.get("role") or "").strip().lower(): s
        for s in (strategy.get("segments") or []) if isinstance(s, dict)
    }
    # The section boundary. The plan's own hook length wins, because the founder
    # approved a plan whose two beats start and end at that second, and the
    # strategy's schema echoes the template's. Clamped to 2-4s because that is
    # the window a hook has to land in.
    hook_seconds = max(
        2, min(4, int(plan.get("hook_seconds") or tpl.get("hook_seconds") or 3))
    )
    middle_seconds = max(1, seconds - hook_seconds)

    # The purpose is a full clause, because these headings are read as
    # instructions: "its job is to stops the scroll" is a visible grammar fault
    # in a prompt someone may have to debug, and the model reads it as a
    # malformed instruction rather than a shorter one.
    # Per-role budgets for goal and action, because the two sections are not
    # the same job: the opening's action is the physical score for the seconds
    # that have to stop the scroll, so it is given room the middle does not need.
    middle_job = (
        "develop the hook and end at the reach"
        if fixed else
        "develop the hook and end before the last second"
    )
    for role, label, budget, purpose, goal_budget, action_budget in (
        ("hook", "HOOK", hook_seconds, "stop the scroll", 110, 220),
        ("middle", "MIDDLE", middle_seconds, middle_job, 85, 120),
    ):
        section = sections_by_role.get(role) or {}
        goal = _clip(section.get("goal"), goal_budget, protect=True)
        script = _clip(section.get("script"), 160, protect=True, sacred=True)
        action = _clip(section.get("action"), action_budget, protect=True)
        # The top-level hook lines already carry these verbatim (larger
        # budgets); the section copies are dropped when identical so each
        # spoken line and the physical score are stated once. With no hook
        # section the top-level lines are the only carriers.
        if role == "hook" and action and _hook_action_top_raw and _hook_action_top_raw == _hook_action_raw:
            action = ""
        if role == "hook" and script and _hook_line_raw and _hook_line_raw == _hook_script_raw:
            script = ""
        block = [f"{label} — {budget}s, and its job is to {purpose}:"]
        if goal:
            block.append(f"  what it must achieve: {goal}")
        if action:
            block.append(f"  what happens on camera: {action}")
        if script:
            block.append(f"  spoken, performed naturally: \"{script}\"")
        if not (goal or action or script):
            # A strategy missing a section is a real gap — a model that returned
            # one beat. Say what the section is for rather than borrowing the
            # other one's content, which is how the hook used to be restated.
            if condensed:
                block.append(
                    f"  unplanned here: write it to {purpose}, same scene, distinct "
                    f"from the other section."
                )
            else:
                block.append(
                    f"  the strategy did not plan this section in detail. Write it so it "
                    f"{purpose}, in this same scene, and keep it distinct from the other "
                    f"section."
                )
        sections.append("\n".join(block))

    # The strategy's scene is the angle's place and time (ADR 0084); template
    # staging that names another one is left out rather than fought over.
    _scene = strategy.get("scene") if isinstance(strategy.get("scene"), dict) else {}
    _locked = angle_scene.scene_of(str(_scene.get("location") or ""))

    def _fits_scene(text) -> bool:
        return not angle_scene.conflict_reason(str(text or ""), _locked)

    if tpl.get("opening_structure") and _fits_scene(tpl["opening_structure"]):
        sections.append(f"Hook mechanism to honour: {_clip(tpl['opening_structure'], 80)}")
    if tpl.get("middle_structure") and _fits_scene(tpl["middle_structure"]):
        sections.append(f"Middle structure to honour: {_clip(tpl['middle_structure'], 80)}")
    # Template visual_style and camera_pacing are deliberately not emitted:
    # visual_style duplicates the locked scene's style line, and curated pacing
    # values ("hard cut", "slow push") directly contradict the fixed one-take
    # orbit rule in camera_move_section. Setup owns camera words (ADR 0108);
    # the template's contribution that reaches render is its two structures.

    # After the sections it governs and before the general look, which is where
    # the opening-interrupt directive sits for the same reason: the model reads a
    # standard immediately before the material it is a standard for.
    sections.append(starting_shot(strategy.get("camera_setup")))
    sections.append(camera_move_section(
        strategy, hook_seconds, condensed,
        hook_surface=str(plan.get("surface") or "") == "hook_cta",
    ))
    # The final moment: the phone handoff when both hands are free, the chosen
    # physical ending when the camera is the phone in their hand (ADR 0093).
    if str(strategy.get("camera_setup") or "handheld") == "fixed":
        sections.append(
            _TIGHTEST_PHONE_HANDOFF_FRAMING
            if _PROMPT_TIGHTEST.get() and condensed else
            _CONDENSED_PHONE_HANDOFF_FRAMING if condensed else _PHONE_HANDOFF_FRAMING
        )
    else:
        ending = " ".join(str(strategy.get("final_beat") or "").split()).strip()
        if not ending:
            ending = final_beat.DEFAULT_ENDING
        template = _CONDENSED_SELFIE_FINAL_BEAT if condensed else _SELFIE_FINAL_BEAT
        sections.append(template.format(ending=ending))

    # No standalone no-text line here: _UI_RENDERING_WARNING below already
    # states "no text appears on screen at all" as part of the UI prohibition,
    # and the condensed handoff merges both. Emitting both said the same rule
    # twice on a tight budget.
    # Voice-only audio, stated outright: the model synthesizes dialogue and
    # music in one pass with no way to separate them afterwards, so without
    # this every render arrives with a music bed under the speech.
    sections.append(
        _TIGHTEST_AUDIO
        if _PROMPT_TIGHTEST.get() else
        "The only audio is the presenter's spoken voice. No background music, "
        "no songs, no ambient music, no sound effects — voice only."
    )
    # The condensed handoff block above already carries this prohibition, merged
    # so the same rule is not stated twice on a budget that cannot afford it.
    if not condensed:
        sections.append(_UI_RENDERING_WARNING)

    forbidden = must_not_show_section(profile)
    if forbidden:
        sections.append(forbidden)

    # The attached face is covered by the person anchor below, and nothing
    # else can be attached — so there is no composited-assets section here
    # either. Retired uploads are refused before any prompt is built.
    person_anchor = person_anchor_notes(assets or [])
    if person_anchor:
        sections.append(person_anchor)
        # A model that pins the photo as its first frame opens ON that photo:
        # without this the opening is the uploaded room and the prompted scene
        # only arrives mid-clip. HeyGen pins the photo as its first frame —
        # and even a *reference* image biases the room a model invents.
        # HeyGen's condensed anchor already carries that rule; other prompts state it here.
        # The tightest tier drops the line outright (ADR 0327): the scene
        # lock and the identity close carry the rule between them.
        if not (_PROMPT_CONDENSED.get() and _PROMPT_SCRIPT_SACRED.get()) and not _PROMPT_TIGHTEST.get():
            sections.append(
                "Open in the locked scene, never the photo's room: the photo "
                "supplies only the person."
            )

    if condensed:
        # The seconds are already stated in the opening sentence and in both
        # section headings, so the close states them once and carries only the
        # identity lock, which appears nowhere else.
        sections.append(_CONDENSED_IDENTITY_CLOSE)
    else:
        # Vertical + identity lock only: the one-take / no-cut / no-black-frame
        # / no-title-card rule is already stated in the opening sentence, so
        # restating it here spent ~90 chars saying the same thing twice.
        sections.append(
            f"Vertical 9:16 throughout. The person on camera is the same individual in "
            f"every frame, with their face and hair exactly as in the reference photograph, in "
            f"the one outfit this scene specifies, in the same place, under the same light."
        )

    return "\n\n".join(section for section in sections if section)
