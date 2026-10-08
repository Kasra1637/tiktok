"""
What the durable-save dry run would do with a row, as a decision.

Split out of repair_failed_saves.py so it can be asserted without booting the
server, loading .env, or touching a database. That is not a stylistic
preference: importing the script does all three at module scope, which means a
test of this decision would silently run against whatever keys the developer's
.env happens to hold -- and this decision is precisely the one that was wrong.

The bug it exists for
---------------------
The report used to decide "would repair" from whether a URL *string* was
non-empty. A row whose stored provider link had already expired, and whose job
id could not be turned into a working endpoint, still had a non-empty string, so
it was reported as repairable. The founder then spent a repair on it and was
told the video was gone. "Would repair" is worth nothing unless it distinguishes
"this link still answers" from "this link used to exist".
"""

# Probe verdicts, and what each one means for whether a repair can work.
#
#   alive         - it served bytes just now
#   refused       - 401/403, i.e. the credentials or the signature are rejected
#   missing       - 404/410, i.e. the object is gone
#   server-error  - 5xx, i.e. their side is broken, not the link
#   unreachable   - DNS/connection failure, which says nothing about the object
#   unknown       - rate limited, or a status we do not interpret
#   None          - the source exists but was not probed (--no-probe)
#
# Only `refused` and `missing` are treated as evidence the object is gone.
# `server-error`, `unreachable` and `unknown` are all reasons a repair MIGHT
# still work later, and reporting them as "gone" would throw away rows that are
# only temporarily out of reach.
DEAD_VERDICTS = ("refused", "missing")


def recovery_verdict(usable_local, is_native_export, statuses):
    """
    What would happen to this row, as (sentence, is_unrecoverable).

    `statuses` is [(source label, probe verdict)] in preference order.

    Ordered so the cheapest truth wins: a usable file on disk makes the whole
    question moot, and a native export is decided by what it is rather than by
    what it might reach.
    """
    if usable_local:
        return ("would repair from the local copy already on disk (no download)", False)

    if is_native_export:
        return (
            "UNRECOVERABLE (a native Demo + CTA export has no provider rendition; "
            "re-export it in the editor)",
            True,
        )

    if not statuses:
        return ("UNRECOVERABLE (no local copy and no provider source)", True)

    unreachable = [
        f"{label} {verdict}"
        for label, verdict in statuses
        if verdict is None or verdict not in DEAD_VERDICTS
    ]
    if unreachable:
        # The FIRST source that might work, which is not always the first one
        # listed: a dead stored link must not hide a live content endpoint.
        return (f"would repair via {unreachable[0]}", False)

    dead = "; ".join(f"{label} {verdict}" for label, verdict in statuses)
    return (
        f"UNRECOVERABLE NOW (sources exist but none respond: {dead}). "
        "Re-running will not help until the provider restores them",
        True,
    )
