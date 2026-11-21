# 0247 — The founder steers the hook: focus, tone and shape picks on Hook + CTA

Kasra's order (2026-11-20, the same evening the page landed): the
founder gets direction and customization over the generated hook
line, so the line is tailored to their app in the way THEY want.
His framing of what makes the hook good: it is tied to the app's
features, capabilities and outcome; it names a feeling or a pain
point fast, as a quick question or a bold statement; and it holds
the answer back. He was explicit about what this is NOT: the
retired angle picker does not come back — no angle list, no new
angle machinery, no stored angles. Three simple picks, set before
generating, steer the one line this page writes.

**The three picks, each defaulting to today's behavior.** FOCUS —
which of the app's real outcomes the hook leads with, chosen from
the profile's own outcome lines, or "Let the app choose". TONE —
plain, warm or bold, or the app's choice. SHAPE — a question or a
statement, or the app's choice. An untouched set of picks
generates exactly the hook the page has always generated: the
generation prompt with no picks is byte-identical to the
pre-change prompt, pinned by a test, because the steering arrives
as one appended block (below) that is empty when nothing is
picked. The doctrine still governs the line itself — goal-first,
first person, the resolution withheld for the demo, one finished
sentence — and the picks steer INSIDE it: they never override the
frame's word budget (4s ≤ 9 words, 5s ≤ 12), its character
budget, or the finished-sentence gate (ADR 0231), which a test
pins by forcing an over-budget question through the question pick
and watching it correct exactly as an over-budget statement does.

**Focus is grounded by construction, twice.** The choices are the
profile's outcome lines (`profile_outcome_lines`: the evidenced
outcome statements' outcomes first, then the flat desired
outcomes they do not already say, deduped, uncapped — the same
facts `generate_hook_line` already grounds in), and the picked
line's text is what persists, verbatim, in a new nullable
`hook_focus` column. The studio PATCH proves membership: a focus
that is not one of the profile's own outcome lines is refused
with a 400 naming the rule, so the column can only ever hold a
real outcome or nothing. Generation re-resolves the pick against
the profile as it stands when the hook is written: a pick the
profile no longer carries steers nothing — the hook falls back to
the app's choice, never an error and never a different outcome
silently substituted — and the page shows such a pick as "Let the
app choose" without rewriting the row. The page reads the
profile's detail for the options (the profiles list endpoint is a
trimmed picker projection that carries no outcomes), and a failed
read degrades quietly to the app's choice, the drafts read's rule,
rather than failing the page over one control's options.

**Tone rides the column that already exists.** The projects table
has carried a `tone` column since the wizard's plan tone, and the
Hook + CTA create already writes it; no second tone column is
added. On hook_cta rows the PATCH validates it as the closed set
("", plain, warm, bold) — a value outside the set is a 400 — while
wizard rows keep the free text they have always had. On this
surface the tone is a pick, not content: changing it never bumps
the script version or un-readies anything, because no word of the
project moves when a pick does. (The wizard's own tone stays
content there, untouched.)

**Shape is enforced beside the budgets, in the gate.** A new
`hook_shape` column (`TEXT NOT NULL DEFAULT 'auto'`; migration
step 11 adds it and `hook_focus` together) carries the pick into
`generate_hook_line`, whose validation loop now calls the spoken
gate with `allows_question` set by the pick: a question pick lets
a question pass — where this page's gate refused every question
before — and the loop additionally requires the line to actually
end in one, correcting a statement reply once with the founder's
pick named, then refusing as today. A statement pick keeps
today's refusal of questions. The steering block itself is
appended after the hook rules, immediately before the JSON return
instruction — FOCUS naming the picked outcome as the one the line
leads with, TONE and SHAPE as plain instructions — and a test pins
that a picked prompt differs from the default prompt by exactly
that block and nothing else.

**The clearer-hook surfaces are steered too.** The page's "Suggest
a clearer hook" runs the studio rewrite-line endpoint into
`rewrite_hook_line`, and the standalone rewrite-hook endpoint
beside it; both now hand a hook_cta row's picks to the rewrite, so
a suggestion honors the same focus, tone and shape the generation
did. Inside the rewrite a shape pick governs the question rule,
outranking the preserve-the-founder's-form default — on this page
the pick IS the founder's standing request — while wizard rows
receive no steering at all and rewrite exactly as before.

**The picks live in the Hook card, above Generate.** A new
`HookPicksControl` mirrors the voice pick's pattern (ADR 0246):
the focus as a select over the profile's outcome lines, tone and
shape as pill sets, helper lines under the focus and the shape.
Changing a pick over a written hook marks the line as predating
the picks — a note in the control says so and names the remedy —
and nothing regenerates on its own: generation stays
click-to-generate (ADR 0122), and the note clears when the founder
regenerates or opens another draft. The picks persist server-side
through the draft PATCH, exactly like the voice pick, and do NOT
join the Demo + CTA editor's browser-local draft snapshot, so
draft parity is untouched. Create Video is unchanged — these
picks are this page's alone.
