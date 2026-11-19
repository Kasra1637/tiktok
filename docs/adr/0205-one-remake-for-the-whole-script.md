# 0205 — One remake for the whole script replaces the per-sentence rewrites

Status: accepted

## Context

In Review, the Script section carried one "Suggest a clearer line"
button per sentence of the script: `ScriptLineRewrites` split the
script into its sentence spans and rendered one `LineRewriteAction`
per span — three sentences, three buttons — and accepting a
suggestion replaced only that sentence's characters, leaving the
founder's other words byte-for-byte intact. On the Nov 18 2026 call
Kasra ordered the three buttons converted into one that remakes the
whole thing in a single pass. He chose the verb himself — the button
reads "Remake the script", "remake" over "rewrite", and not "Remake
the whole script" — and he named a requirement for the remake's
output: it opens on the moment.

## Decision

1. **One control under the script field.** `ScriptRewrite` replaces
   `ScriptLineRewrites`: a single `LineRewriteAction` whose line is
   the entire script, with the button "Remake the script", the busy
   label "Remaking script" and the accept button "Use this script"
   (`LineRewriteAction` gains an `acceptLabel` prop defaulting to
   "Use this line", so the hook's existing use is untouched); the
   dismiss stays "Keep mine". The helper text is one line: the
   script can be remade in one go, as one suggestion for the whole
   story, and nothing changes until it is accepted. Accepting
   replaces the ENTIRE script through the same draft edit the
   textarea makes. The hook's "Suggest a clearer hook" stays exactly
   as it is, and the script textarea stays the editor.
2. **The stale guard works at script scale.** The action's existing
   rule — a suggestion hides if the line changed since it was made —
   now has the whole script as its line, so any edit in the textarea
   stales a standing suggestion; it can never overwrite the founder's
   newer words. `splitScriptSentences` / `replaceScriptSentence` and
   the per-line group CSS (`.script-line-group` / `.script-line-row`)
   are removed with the component; nothing else used them.
3. **A third role on the rewrite endpoint.** `POST
   /studio/projects/{id}/rewrite-line` grows role `"script"`: the
   payload's line is the whole current script (falling back to the
   project's saved script, the way the hook role falls back to the
   saved hook). `rewrite_whole_script` makes ONE model call that
   rewrites the whole spoken story coherently — same moment, same
   facts, the hook untouched — riding the shared spoken-line rules
   block, so the ADR 0201 craft lessons come with it. The instruction
   states Kasra's requirement in his words: the remake opens on the
   moment itself — its first sentence stands in the scene, names the
   place and answers the hook in the same sentence, with no
   looking-back preamble before it; no sentence past 18 words, every
   sentence finished, statements only, the ending open on the
   strongest concrete line, never a vague stand-in payoff. The
   model's answer is taken whole — whitespace tidied, the identity
   rule applied — never cut to its first sentence: the answer IS the
   whole script. An unchanged reply, a question, or an over-ceiling
   reply gets one bounded correction, then a named refusal, the
   family's honesty contract.
4. **Length discipline at the scale of the whole script.** The
   suggestion is bounded by the script's full set-length ceiling
   from `check_spoken_story` — the whole middle budget, not a
   per-line share — and an over-ceiling suggestion is rejected,
   never trimmed (ADR 0130). When the current script already exceeds
   the ceiling, a shorter compliant remake is exactly the fix, so
   the script role has no equivalent of the middle role's no-room
   refusal.
5. **The other roles stand.** "hook" and "middle" work exactly as
   before; the middle role simply becomes unused by the frontend and
   stays as part of the endpoint's contract.

## Consequences

The per-sentence rewrite UI shipped in the Nov 12 2026 delivery
(commit 145f8b6) without an ADR of its own, so no ADR is superseded
here; ADR 0130's per-line share rule stands for the middle role, and
its set-length principle is extended to the whole script. The
suggestion-then-accept contract is preserved — nothing is saved by
the server, and accepting goes through the normal draft edit — at
the scale of the whole story instead of one sentence.
