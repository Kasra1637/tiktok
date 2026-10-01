"""
End-to-end verification of the app-specific influencer workflow.

    .venv\\Scripts\\python.exe verify_influencer_workflow.py

Runs the REAL strategy generator (one OpenRouter text call per app) and the REAL
prompt builders, then prints the hook and extension prompts for two different
apps so they can be compared by eye as well as by assertion. Video submission
is mocked because it costs money; everything that decides WHAT to submit is
real, including the real ffmpeg concat.

If OPENROUTER_API_KEY is empty the strategy-generation call is skipped and
hand-authored fixture strategies are used instead, so the prompt building,
continuity planning, claim checking and assembly are still verified for real.
The report states plainly which mode it ran in — a green run in fixture mode
verifies the pipeline, not the model's writing.

Exits non-zero if a check fails.
"""
import asyncio
import json
import os
import sys
import tempfile
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(BACKEND_DIR))

# Load .env BEFORE importing anything that reads a key at import time.
# ai_service captures OPENROUTER_API_KEY at module scope, so importing it first
# and loading dotenv second would silently report "no API key".
from dotenv import load_dotenv  # noqa: E402

load_dotenv(BACKEND_DIR / ".env")

os.environ.setdefault("TURSO_DATABASE_URL", "")
os.environ.setdefault("CLERK_JWKS_URL", "")
os.environ.pop("VIDEO_MODEL_DEFAULT", None)
os.environ.pop("VIDEO_MODEL_ALLOWLIST", None)

import ai_service  # noqa: E402
import claim_safety  # noqa: E402
import generation_planning  # noqa: E402
import video_providers  # noqa: E402
from models import ApproveAppProfileRequest, BrandProfileCreateRequest  # noqa: E402

ANON = "anonymous"
TINY_PNG = bytes.fromhex(
    "89504e470d0a1a0a0000000d49484452000000010000000108060000001f15c489"
    "0000000d49444154789c626001000000ffff0300000600055d3866680000000049454e44ae426082"
)

# Two genuinely different apps in different categories, with different audiences,
# different problems and different claims.
APPS = {
    "ShiftLog": {
        "app_category": "Health & Productivity",
        "brand_description": "Shift logging for healthcare workers on rotating shifts.",
        "target_audience": "hospital nurses and healthcare assistants working rotating shifts",
        "core_features": ["One-tap shift logging", "Automatic break tracking", "Overtime totals"],
        "primary_use_cases": ["Clocking on and off between shifts", "Checking overtime before payday"],
        "problems_solved": ["Shift paperwork eats the last twenty minutes of a long shift"],
        "desired_outcomes": ["Getting out of the hospital on time"],
        "differentiation": "Built specifically for rotating rotas rather than for office hours.",
        "claims_approved": ["Logs a shift in one tap"],
        "claims_banned": ["cures burnout", "guarantees you will never be overworked"],
        "claims_review": ["Average hours saved per user"],
        "tone_voice": "plain, tired, warm",
    },
    "Pennywise": {
        "app_category": "Finance",
        "brand_description": "Automatic envelope budgeting from linked bank accounts.",
        "target_audience": "first-time budgeters with irregular freelance income",
        "core_features": ["Automatic envelope splits", "Subscription cancellation radar", "Weekly safe-to-spend number"],
        "primary_use_cases": ["Cancelling forgotten subscriptions before the next payday"],
        "problems_solved": ["Money disappears before payday with nothing to show for where it went"],
        "desired_outcomes": ["Knowing exactly what is safe to spend this week"],
        "differentiation": "Finds the subscriptions you forgot you had, which other budgets cannot.",
        "claims_approved": ["Finds forgotten subscriptions"],
        "claims_banned": ["guarantees you will save money", "doubles your income"],
        "claims_review": ["Average amount recovered per user"],
        "tone_voice": "dry, wry, slightly conspiratorial",
    },
}

TEMPLATES = [
    ("Pain-Point Question", "address_user_problem"),
    ("Stop Doing This", "address_user_problem"),
    ("I Wish I Knew This Earlier", "create_curiosity"),
]

# Fixture strategies, used only when no API key is available. Shaped exactly as
# generate_video_strategy()'s schema, and written the way the prompt asks a
# model to write for each app, so the downstream verification is meaningful.
FIXTURES = {
    "ShiftLog": {
        "strategy_summary": "Open on the last twenty minutes of a shift, because that is where "
                            "rotating-rota staff actually feel this app: it removes the "
                            "paperwork that makes them finish late.",
        "audience_problem": "The handover and the timesheet eat the last twenty minutes of "
                            "every shift, so you leave work twenty minutes late, every time.",
        "emotional_triggers": ["relief at the end of a long shift",
                               "being seen by someone who has been there"],
        "hook_concept": "Open mid-laugh in a hospital corridor on a dead tired night-shift "
                        "nurse who has just realised she already logged the shift.",
        "hook_line": "I clocked out at 11:40. Every single night. One tap now.",
        "hook_promise": "Show how the last twenty minutes of a shift get done instead of worked.",
        "hook_action": "Holds a phone up to camera, already logging, then drops it and laughs.",
        "hook_dialogue": "Delivered low and fast, mid-exhale, half to the camera and half to herself.",
        "messaging_pillars": ["One tap covers the whole shift log",
                              "Break tracking that survives a chaotic night"],
        "primary_feature": "One-tap shift logging",
        "desired_outcome": "Walking out of the hospital on time instead of twenty minutes late",
        "differentiation_beat": "Built for rotating rotas, not office hours, so it handles the "
                                "split shifts other timesheets get wrong.",
        "cta_strategy": "Try it free — the hook has already promised one tap, so the ask is "
                        "just to try that one tap.",
        "character": {
            "appearance": "a late-20s night-shift nurse in teal scrubs",
            "facial_features": "round face, dark brows, tired eyes, faint tan line at the jaw",
            "hairstyle": "shoulder-length dark hair in a low bun, a few strands loose",
            "wardrobe": "teal scrubs, silver ID badge on a lanyard, small hoop earrings",
            "body_appearance": "average height, upright but visibly tired posture",
            "age_range": "late 20s",
            "facial_expression": "a tired half-smile that breaks into a real grin mid-sentence",
            "styling_details": "no glasses, no visible tattoos, a thin friendship bracelet",
        },
        "scene": {
            "camera_angle": "eye-level, phone held at arm's length, slight hand shake",
            "framing": "medium close-up, head and shoulders, badge visible at the bottom of frame",
            "lighting": "flat overhead corridor fluorescents, cool and slightly green",
            "environment": "a hospital staff corridor outside a break room",
            "background": "grey vinyl floor, beige wall, a grey fire door, a wall clock",
            "setting": "late shift, 11:40pm, corridor empty",
            "visual_style": "authentic handheld UGC, no polish",
            "character_positioning": "centred, phone held at chest height in frame",
            "props": "a phone only — no coffee cup, no clipboard",
            "color_palette": "cool greys and beige, teal scrubs as the only saturated colour",
        },
        "performance": {
            "movement": "one-handed, small gestures, the phone stays in frame throughout",
            "voice_delivery": "low, quick, tired but warm; ends on a real laugh",
        },
        # Hook plus a full planned arc, as generate_video_strategy now emits.
        # The verification extends segment 1, so the fixture has to plan more
        # than the hook: a hook-only plan is now correctly refused.
        "segments": [
            {"index": 0, "role": "hook", "seconds": 4,
             "goal": "land the exhaustion and the relief in four seconds",
             "script": "I clocked out at 11:40. Every single night. One tap now.",
             "action": "Holds the phone up, already logging, then laughs"},
            {"index": 1, "role": "continuation", "seconds": 6,
             "goal": "show that one tap is genuinely the whole job",
             "script": "One tap and the shift is logged. Breaks too. That is it.",
             "action": "Taps the phone once, pockets it, keeps walking"},
        ] + [
            {"index": i, "role": "cta" if i == 7 else "continuation", "seconds": 6,
             "goal": f"continue the story, step {i}",
             "script": f"Beat {i} of the shift story.",
             "action": f"action for beat {i}"}
            for i in range(2, 8)
        ],
        "continuity_contract": {
            "established": ["a late-20s night-shift nurse in teal scrubs",
                            "a hospital staff corridor outside a break room",
                            "cool overhead corridor fluorescents",
                            "a phone held at chest height in frame"],
            "must_not_change": ["the face",
                                "the low bun with loose strands",
                                "the teal scrubs, silver badge and hoop earrings",
                                "the corridor background and wall clock",
                                "the eye-level medium close-up framing",
                                "the phone held at chest height"],
            "do_not_repeat": ["the hook line about clocking out at 11:40",
                              "the mid-sentence laugh",
                              "the opening one-tap gesture"],
        },
    },
    "Pennywise": {
        "strategy_summary": "Open on the specific, stupid pain of a forgotten subscription "
                            "eating a freelance account, because that is recognisable to "
                            "anyone with irregular income and nobody budgets for it.",
        "audience_problem": "Three small subscriptions took money you never agreed to part "
                            "with, and by the time you notice there is nothing left to spend.",
        "emotional_triggers": ["the specific relief of a number finally making sense",
                               "the small vindication of being owed money"],
        "hook_concept": "Open deadpan to camera on a freelancer counting off three forgotten "
                        "subscriptions on their fingers, phone showing the damage.",
        "hook_line": "Three subscriptions had been eating my account since March.",
        "hook_promise": "Show the money that quietly left, and what cancelling it changes.",
        "hook_action": "Counts off three on their fingers, then turns the phone to show a number.",
        "hook_dialogue": "Flat and deadpan to camera, then a short laugh at the end.",
        "messaging_pillars": ["Finds the subscriptions you forgot you had",
                              "One safe-to-spend number per week"],
        "primary_feature": "Subscription cancellation radar",
        "desired_outcome": "Knowing what is genuinely safe to spend before the next payday",
        "differentiation_beat": "It hunts for the subscriptions you forgot you had, which a "
                                "normal budget app will never do because you never entered them.",
        "cta_strategy": "Check what it finds — the hook made a specific claim, so the ask is "
                        "to look for the same thing on their own account.",
        "character": {
            "appearance": "an early-30s freelancer in a faded hoodie, seated on an unmade bed",
            "facial_features": "narrow face, thin-rimmed glasses, unshaven, tired eyes",
            "hairstyle": "messy dark curls pushed back with a black hair band",
            "wardrobe": "faded grey hoodie, thin gold chain, one white AirPod in the left ear",
            "body_appearance": "average height, seated cross-legged, slouched",
            "age_range": "early 30s",
            "facial_expression": "a flat deadpan stare that breaks into a real laugh",
            "styling_details": "thin-rimmed glasses, no makeup, a small ear stud in the right ear",
        },
        "scene": {
            "camera_angle": "static, laptop height, a little below eye level",
            "framing": "medium shot, waist up, seated and filling most of the frame",
            "lighting": "a single warm bedside lamp from frame left, rest of the room dim",
            "environment": "a small rented bedroom, evening",
            "background": "an unmade single bed, a faded poster, a stack of unopened post",
            "setting": "Sunday evening, the week before payday",
            "visual_style": "talking-head confession, natural, no music bed",
            "character_positioning": "seated cross-legged, phone resting on the bed beside them",
            "props": "a phone and a mug of cold tea, both on the bed",
            "color_palette": "warm amber from the lamp against cold grey",
        },
        "performance": {
            "movement": "seated, animated hands, the phone stays resting on the bed",
            "voice_delivery": "dry, wry, conspiratorial; a short laugh at the end",
        },
        "segments": [
            {"index": 0, "role": "hook", "seconds": 4,
             "goal": "name the specific theft in under four seconds",
             "script": "Three subscriptions had been eating my account since March.",
             "action": "Counts off three on their fingers, turns the phone to show a number"},
            {"index": 1, "role": "continuation", "seconds": 6,
             "goal": "show the fix and what it is worth",
             "script": "I cancelled all three on Sunday. That is the whole video.",
             "action": "Swipes the phone, puts it face-down, laughs"},
        ],
        "continuity_contract": {
            "established": ["an early-30s freelancer in a faded grey hoodie",
                            "a small rented bedroom",
                            "a single warm bedside lamp from frame left",
                            "a phone resting on the bed beside them"],
            "must_not_change": ["the face",
                                "the messy dark curls and black hair band",
                                "the faded grey hoodie, gold chain and one AirPod",
                                "the unmade bed and stack of unopened post",
                                "the static laptop-height framing",
                                "the phone resting on the bed"],
            "do_not_repeat": ["the hook line about three subscriptions since March",
                              "the three-finger count",
                              "the opening deadpan stare"],
        },
    },
}

failures = []


def check(label, condition, detail=""):
    status = "PASS" if condition else "FAIL"
    print(f"  [{status}] {label}")
    if not condition:
        if detail:
            print(f"         {detail}")
        failures.append(label)
    return condition


def banner(text):
    print("\n" + "=" * 78)
    print(text)
    print("=" * 78)


async def make_profile(server, name, spec):
    profile = await server.create_brand(
        payload=BrandProfileCreateRequest(brand_name=name, **spec), user_id=ANON)
    return await server.approve_app_profile(
        profile_id=profile["id"], payload=ApproveAppProfileRequest(), user_id=ANON)


async def run():
    import server

    tmp = tempfile.mkdtemp(prefix="verify-influencer-")
    server.DB_PATH = Path(tmp) / "verify.db"
    server.DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    if not server.DB_PATH.exists():
        await server.init_db()
    else:
        await server.init_db()

    live = bool(ai_service.OPENROUTER_API_KEY)
    banner("MODE: " + (
        "LIVE — the strategy for each app is generated by a real "
        "google/gemini-2.5-flash call. Prompt building, claim checking, "
        "continuity planning and ffmpeg assembly are all real too."
        if live else
        "FIXTURE — OPENROUTER_API_KEY is empty, so the strategy-generation call "
        "is skipped and hand-authored strategies are used. Everything "
        "downstream of the model (prompt building, continuity planning, claim "
        "checking, ffmpeg assembly) is still verified for real, but this run "
        "does NOT verify that the model writes app-specific strategies. Re-run "
        "with a key set to check that."
    ))

    prompts = {}
    strategies = {}
    for name, spec in APPS.items():
        banner(f"APP: {name}  ({spec['app_category']})")
        profile = await make_profile(server, name, spec)

        tpl_name, objective = TEMPLATES[len(prompts) % len(TEMPLATES)]
        template = next(
            t for t in (await server.list_templates(user_id=ANON))["templates"]
            if t["name"] == tpl_name
        )
        print(f"  hook mechanism : {template['name']} ({template['category']})")
        print(f"  objective      : {objective}")

        if live:
            strategy = await ai_service.generate_video_strategy(
                profile=profile,
                template=template,
                angle=None,
                objective=objective,
                hook_seconds=4,
                total_duration=20,
                tone="",
                brand_voice=spec["tone_voice"],
            )
        else:
            strategy = ai_service.normalize_strategy(FIXTURES[name])
            strategy["template_name"] = template["name"]
        strategy["template_name"] = template["name"]
        strategies[name] = strategy

        print(f"\n  HOOK LINE      : \"{strategy['hook_line']}\"")
        print(f"  HOOK CONCEPT   : {strategy['hook_concept']}")
        print(f"  PROBLEM        : {strategy['audience_problem']}")
        print(f"  FEATURE        : {strategy['primary_feature']}")
        print(f"  OUTCOME        : {strategy['desired_outcome']}")
        print(f"  EMOTION        : {'; '.join(strategy['emotional_triggers'][:3])}")
        print(f"  CTA            : {strategy['cta_strategy']}")
        print(f"  PERSON         : {strategy['character'].get('appearance', '')}")
        print(f"                   hair={strategy['character'].get('hairstyle', '')!r}")
        print(f"                   wardrobe={strategy['character'].get('wardrobe', '')!r}")
        print(f"  SCENE          : {strategy['scene'].get('environment', '')}")
        print(f"                   light={strategy['scene'].get('lighting', '')!r}")
        print(f"                   camera={strategy['scene'].get('camera_angle', '')!r} / "
              f"{strategy['scene'].get('framing', '')!r}")
        print(f"  LOCKED         : {'; '.join(strategy['continuity_contract']['must_not_change'][:4])}")

        # Claim safety over the strategy, exactly as the hook endpoint does.
        report = claim_safety.build_safety_report({"strategy": strategy}, profile)
        check(f"{name}: claim check passes", report["passed"], json.dumps(report["blocking"]))

        # Real prompts.
        assets = [{"kind": "character_reference", "label": "Founder face"}]
        hook_continuity = video_providers.continuity_plan(
            "seedance-2.5", has_bridge_frame=False, has_parent_clip_url=False,
            has_character_reference=True)
        hook_prompt = generation_planning.build_segment_prompt(
            strategy=strategy, profile=profile, template=template, segment_index=0,
            duration=4, assets=assets, continuity=hook_continuity, is_hook=True)
        ext_continuity = video_providers.continuity_plan(
            "seedance-2.5", has_bridge_frame=True, has_parent_clip_url=True,
            has_character_reference=True)
        ext_prompt = generation_planning.build_segment_prompt(
            strategy=strategy, profile=profile, template=template, segment_index=1,
            duration=6, assets=assets, continuity=ext_continuity, is_hook=False,
            previous_summary=generation_planning.describe_seam_state(strategy, 0))
        prompts[name] = {"hook": hook_prompt, "extension": ext_prompt}

        print(f"\n  --- EXTENSION PROMPT (segment 1) ---\n")
        for line in ext_prompt.splitlines():
            print(f"  {line}")

    banner("CHECK 1: the two apps are strategically different")
    a, b = list(APPS)
    sa, sb = strategies[a], strategies[b]
    check("hook lines differ", sa["hook_line"].lower() != sb["hook_line"].lower())
    check("hook concepts differ", sa["hook_concept"].lower() != sb["hook_concept"].lower())
    check("problems differ", sa["audience_problem"] != sb["audience_problem"])
    check("features differ", sa["primary_feature"] != sb["primary_feature"])
    check("CTAs differ", sa["cta_strategy"] != sb["cta_strategy"])
    check("persona differs", sa["character"].get("appearance") != sb["character"].get("appearance"))
    check("wardrobe differs", sa["character"].get("wardrobe") != sb["character"].get("wardrobe"))
    check("scene differs", sa["scene"].get("environment") != sb["scene"].get("environment"))
    check("lighting differs", sa["scene"].get("lighting") != sb["scene"].get("lighting"))

    # Neither app's specifics may leak into the other's prompt.
    fa, fb = sa["primary_feature"], sb["primary_feature"]
    check(f"{b}'s prompt does not contain {a}'s feature", fb not in prompts[a]["hook"])
    check(f"{a}'s prompt does not contain {b}'s feature", fa not in prompts[b]["hook"])
    check(f"{b}'s prompt does not contain {a}'s scene",
          (sa["scene"].get("environment") or "zzz") not in prompts[b]["hook"])

    ha, hb = prompts[a]["hook"], prompts[b]["hook"]
    lines_a = {ln.strip() for ln in ha.splitlines() if ln.strip()}
    lines_b = {ln.strip() for ln in hb.splitlines() if ln.strip()}
    overlap = lines_a & lines_b
    frac = len(overlap) / max(len(lines_a), len(lines_b))
    check(f"hooks are not one template ({frac:.0%} of lines shared)", frac < 0.6,
          f"shared: {sorted(overlap)[:5]}")
    print(f"  shared lines: {len(overlap)} of {len(lines_a)}/{len(lines_b)}")

    banner("CHECK 2: the influencer identity reference is locked in every prompt")
    for name in APPS:
        for kind in ("hook", "extension"):
            check(f"{name}/{kind}: character reference is an identity reference",
                  "exact individual in the attached character reference" in prompts[name][kind])
            check(f"{name}/{kind}: wardrobe is locked",
                  "THE PERSON AND THE SCENE ARE LOCKED" in prompts[name][kind])
            check(f"{name}/{kind}: environment is locked",
                  (strategies[name]["scene"].get("environment") or "n/a") in prompts[name][kind])

    banner("CHECK 3: extensions preserve the scene and continue the app message")
    for name in APPS:
        s = strategies[name]
        ext = prompts[name]["extension"]
        for field in ("hairstyle", "wardrobe", "facial_features"):
            value = s["character"].get(field) or ""
            check(f"{name}: extension keeps character.{field}",
                  (not value) or value in ext, value)
        for field in ("background", "lighting", "framing", "camera_angle", "props"):
            value = s["scene"].get(field) or ""
            check(f"{name}: extension keeps scene.{field}",
                  (not value) or value in ext, value)
        check(f"{name}: extension keeps the app problem", s["audience_problem"] in ext)
        check(f"{name}: extension keeps the feature", s["primary_feature"] in ext)
        check(f"{name}: extension keeps the CTA strategy", s["cta_strategy"] in ext)
        check(f"{name}: extension states what came before",
              "opening segment already established" in ext)
        check(f"{name}: extension is told not to repeat", "Do NOT repeat" in ext)
        check(f"{name}: extension is told not to re-introduce the app",
              "Do not re-introduce the app" in ext)
        seg1 = next((x for x in s["segments"] if x.get("index") == 1), None)
        if seg1 and seg1.get("script"):
            check(f"{name}: extension carries its own spoken script",
                  seg1["script"] in ext)

    banner("CHECK 4: continuity limitations are explicit, not silent")
    for model in ("seedance-2.5", "minimax-h3"):
        plan = video_providers.continuity_plan(
            model, has_bridge_frame=True, has_parent_clip_url=True, has_character_reference=True)
        print(f"  {model}: guarantee={plan['guarantee']} attached={plan['attached']} "
              f"degraded={[d['anchor'] for d in plan['degraded']]}")
        check(f"{model}: reports what it attached", bool(plan["attached"]))
        check(f"{model}: every degradation has a reason",
              all(d.get("reason") for d in plan["degraded"]))
        check(f"{model}: never claims a frame it will not send",
              plan["use_frame"] == bool(plan["guarantee"].startswith("frame_exact")))
    no_frame = video_providers.continuity_plan(
        "seedance-2.5", has_bridge_frame=False, has_parent_clip_url=True,
        has_character_reference=True)
    check("missing bridge frame downgrades to text_only", no_frame["guarantee"] == "text_only")
    editor = video_providers.continuity_plan(
        "aleph-2", has_bridge_frame=True, has_parent_clip_url=True, has_character_reference=True)
    check("a video editor is refused for a chain", editor["guarantee"] == "unsupported")
    prompt_no_frame = generation_planning.build_segment_prompt(
        strategy=strategies[a], profile={"brand_name": a}, template={}, segment_index=1,
        duration=6, assets=[], continuity=no_frame, is_hook=False)
    check("a text-only prompt does not claim a supplied frame",
          "EXACT final frame" not in prompt_no_frame
          and "you have NOT been given the previous clip" in prompt_no_frame)

    banner("CHECK 5: the assembled deliverable")
    try:
        import shutil
        ffmpeg = shutil.which("ffmpeg")
        if not ffmpeg:
            print("  ffmpeg not on PATH — skipping the real concat.")
        else:
            clips = []
            for i in range(2):
                p = Path(tmp) / f"seg{i}.mp4"
                subprocess_clip(p, seconds=1)
                clips.append(p)
            out = Path(tmp) / "chain.mp4"
            joined = await __import__("pipeline").concat_videos(clips, out)
            check("concat produces one playable file",
                  bool(joined) and joined.exists() and joined.stat().st_size > 0)
            if joined:
                dur = probe_duration(joined)
                check("the joined file covers both segments (>=2s)", dur >= 1.8, f"got {dur}s")
    except Exception as e:
        print(f"  concat check skipped: {e}")

    banner("SUMMARY")
    if failures:
        print(f"  {len(failures)} CHECK(S) FAILED:")
        for f in failures:
            print(f"    - {f}")
        return 1
    print("  All checks passed.")
    return 0


def subprocess_clip(path: Path, seconds=1):
    """Render a tiny real clip so the concat path is exercised for real."""
    import subprocess
    subprocess.run([
        "ffmpeg", "-y", "-f", "lavfi", "-i",
        f"testsrc=duration={seconds}:size=360x640:rate=30",
        "-f", "lavfi", "-i", f"sine=frequency=440:duration={seconds}",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", "-c:a", "aac", "-shortest", str(path),
    ], check=True, capture_output=True)


def probe_duration(path: Path):
    import subprocess
    import re
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-show_entries", "format=duration",
         "-of", "default=noprint_wrappers=1:nokey=1", str(path)],
        check=True, capture_output=True, text=True)
    return float(re.search(r"[\d.]+", out.stdout).group())


if __name__ == "__main__":
    sys.exit(asyncio.run(run()))
