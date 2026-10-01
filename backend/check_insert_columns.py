"""Check every brand_profiles INSERT has matching column and placeholder counts.

A column added without its placeholder is invisible to a type-check and to the
build: it only surfaces as a sqlite3.OperationalError in whichever test happens
to insert a profile first, which is a slow and confusing way to find out.
"""
import re
import pathlib

source = pathlib.Path("server.py").read_text(encoding="utf-8")
pattern = re.compile(
    r"INSERT INTO brand_profiles\s*\(([\s\S]*?)\)\s*VALUES\s*\(([\s\S]*?)\)\"\"\""
)

bad = 0
for index, match in enumerate(pattern.finditer(source), start=1):
    columns = [c.strip() for c in match.group(1).split(",") if c.strip()]
    placeholders = match.group(2).count("?")
    ok = len(columns) == placeholders
    if not ok:
        bad += 1
    print(
        f"INSERT #{index}: columns={len(columns)} placeholders={placeholders} "
        f"{'OK' if ok else '<-- MISMATCH'}"
    )

raise SystemExit(1 if bad else 0)
