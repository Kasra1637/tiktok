# HookForge — Unified Location Field

> Status: implemented historical spec for Unified Location (ADR 0090).
> Canonical architecture is `docs/architecture.md`; this file is not a current
> inventory and must not be treated as one.

## Original problem statement

In the Hook + Story strategy render and prompt scene section, replace the separate Environment, Background, and Setting fields with one field named **Location** everywhere: strategy output, scene display, editable Review fields, strategy JSON, visual/audio direction, render prompts, and results. A selected Location direction must update the same Location value used by rendering. Existing saved work must remain compatible by merging the three legacy values.

## Architecture decisions

- `scene.location` is the only current place field in strategy JSON and render planning.
- `studio_projects.location` is the editable Review source of truth; selecting a Location direction updates this same field.
- `generations.location` stores an immutable snapshot of the Location used for each submitted render.
- Legacy `environment`, `background`, and `setting` values are normalized into one Unicode-safe, deduplicated Location when older strategies are read or edited.
- Explicit Location edits replace legacy place data rather than appending to it.
- Lighting and wardrobe remain visual-direction details and cannot overwrite Location.

## Implemented

- Updated creative-plan and strategy schemas, prompts, normalization, direction options, strategy generation, render prompt construction, database storage, and API serializers.
- Added one editable Review Location field, renamed the direction control to Location, and reduced the strategy scene display to one Location row.
- Added Location to generation History context and its context filtering/deep-link behavior.
- Added migrations for project and generation Location fields and compatibility for previously saved strategies.
- Added backend and frontend regression coverage for legacy merging, Unicode content, replacement semantics, selected-Location precedence, prompt labels, immutable result snapshots, scene display, and History filtering.

## Prioritized backlog

### P0

- None for the unified Location workflow.

### P1

- Refine normalization for unusually conflicting legacy descriptions beyond exact and subsumed repetition.
- Add concise, render-ready Location writing guidance and validation feedback.

### P2

- Add reusable Location presets per app.
- Add Location edit history and comparison across strategy revisions.

## Next tasks

1. Review real older projects with especially long or contradictory place descriptions.
2. Consider saved Location presets for frequently reused filming scenarios.
3. Consider showing Location revision history beside strategy versions.