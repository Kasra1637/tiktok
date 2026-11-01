# 0075 — Review checks lead to repair, not silent replacement

Status: accepted

## Context

Review separated the script from its findings and expanded all supporting evidence. A blocked founder had no action attached to the offending phrase. Draft resume, autosave, and plan/render tabs already exist and remain unchanged.

## Decision

Keep blockers beside the spoken script and supporting notes in a closed disclosure. Edit affected text selects the phrase in the hook, story, or a direction editor. A finding outside editable fields leads to the strategy rebuild surface and explains why. Regeneration reuses the existing generator and asks before replacing saved or unsaved work. Findings describe the saved plan, not unchecked edits.

Warnings and verification notes are explicitly nonblocking; app checks are not provider or TikTok approval. No claim rules, provider behavior, or approved dialogue change automatically.

## Alternatives and consequences

Blind phrase substitution was rejected: an approved claim may not make sense in the sentence, and the sacred script belongs to the founder. A wholesale wizard refactor was unnecessary. Existing design surfaces are reused without token changes.

Anchors: `frontend/src/components/SafetyPanel.jsx`; `frontend/src/pages/CreateVideo.jsx:editFlaggedClaim`; render checks prefixed `review checks`.
