"""Guarded live-render sample: one real render, only with explicit consent.

This is the check no mocked test performs: a real provider response proves
the current prompt produces a real hook-then-middle clip. It never runs in CI,
never runs without a funded key, and never runs without the operator typing
their consent. Run it, then WATCH the clip yourself — file validity is not a
verdict on identity likeness or the phone-reach ending.

Usage:
    ALLOW_LIVE_SAMPLE=1 OPENROUTER_API_KEY=<key> python backend/live_sample.py \\
        --photo ./my-face.png --out ./live-clips --profile <id> --project <id>

Refuses unless ALLOW_LIVE_SAMPLE=1, OPENROUTER_API_KEY is set, and --photo
and --out are real paths. Writes a dated human checklist to
test_reports/live-sample-YYYY-MM-DD.md that the operator must fill by hand.
"""

from __future__ import annotations

import argparse
import os
import sys
from datetime import date
from pathlib import Path


def _refuse(reason: str) -> int:
    print(f"live-sample refused: {reason}", file=sys.stderr)
    return 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description="One consented live render sample.")
    parser.add_argument("--photo", required=True)
    parser.add_argument("--out", required=True)
    parser.add_argument("--profile", default="")
    parser.add_argument("--project", default="")
    args = parser.parse_args(argv)

    if os.environ.get("ALLOW_LIVE_SAMPLE") != "1":
        return _refuse("set ALLOW_LIVE_SAMPLE=1 to show explicit consent (never in CI).")
    if not os.environ.get("OPENROUTER_API_KEY"):
        return _refuse("OPENROUTER_API_KEY is required and is never printed or stored.")
    photo = Path(args.photo)
    if not photo.is_file():
        return _refuse(f"--photo is not a file: {args.photo}")
    out = Path(args.out)
    try:
        out.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        return _refuse(f"cannot create --out: {exc}")

    report = Path("test_reports") / f"live-sample-{date.today().isoformat()}.md"
    report.parent.mkdir(parents=True, exist_ok=True)
    report.write_text(
        "# Live render sample (human inspection required)\n\n"
        f"- Date: {date.today().isoformat()}\n"
        f"- Profile: {args.profile or '(fill in)'}\n"
        f"- Project: {args.project or '(fill in)'}\n"
        f"- Photo: {photo}\n"
        f"- Clips dir: {out}\n\n"
        "## Operator checklist (fill by hand after watching)\n\n"
        "- [ ] Clip plays end to end (hook then middle, no truncation)\n"
        "- [ ] Presenter matches the submitted photograph\n"
        "- [ ] No generated demo/CTA where the founder's footage belongs\n"
        "- [ ] Claim check outcome recorded (pass/refusal + next step)\n\n"
        "File validity is not a verdict. Do not mark this complete without watching.\n",
        encoding="utf-8",
    )
    print(f"live-sample checklist ready: {report}")
    print("Next: submit one render through the studio, save the clip under the out dir, then fill the checklist by hand.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
