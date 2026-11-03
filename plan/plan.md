# Unified Location Field for Hook + Story Strategy

The Hook + Story workflow will use one **Location** description instead of separate Environment, Background, and Setting fields.
Location will remain consistent from strategy generation through review, direction selection, rendering, and final results.

## Who it's for

- App users creating and refining Hook + Story scene strategies.
- Users who need one clear, editable description of where a scene takes place.
- Users applying visual or audio direction choices before generating a render.

## Core features and experience

- Replace Environment, Background, and Setting with one field labeled **Location** everywhere in the Hook + Story workflow.
- Show one Location value in strategy output and scene displays.
- Provide one editable Location field during Review.
- Use a single `location` value in strategy JSON; new outputs will not contain separate environment, background, or setting values.
- Update every strategy, scene, review, visual-direction, audio-direction, and render prompt that currently reads any of the three old fields so it reads only Location.
- Rename the Setting label inside visual and audio direction controls to Location.
- When a user selects the Location section in visual or audio direction, apply that direction to the same Location card and value.
- Ensure the render prompt and displayed result use the final Location value only.
- Preserve existing work by merging legacy Environment, Background, and Setting content into one coherent Location description.

## User flow

1. A Hook + Story strategy is generated with one Location description.
2. The scene displays one Location card rather than three separate cards.
3. During Review, the user edits a single Location field.
4. If the user selects Location in visual or audio direction, the chosen direction updates the same Location card information.
5. Rendering uses only the final Location value.
6. The result displays the same unified Location information used for the render.
7. Previously saved scenes are opened with their old Environment, Background, and Setting text merged into one Location description.

## UI/UX feel

- Preserve the app's current visual language and layout.
- Replace the three stacked place-related sections with one clearly labeled Location card.
- Keep the unified description easy to scan and edit without repeating similar scene details.
- Use Location consistently in headings, labels, controls, review fields, and results so no old terminology remains visible.

## Implementation phases

### Phase 1 — MVP (built now)

- Consolidate all visible Environment, Background, and Setting fields into Location.
- Update strategy output, scene display, editable Review fields, strategy JSON, prompt inputs, render prompts, and result displays.
- Rename Setting to Location in visual and audio direction.
- Apply selected Location direction content to the same Location card used by rendering.
- Merge legacy three-field content into one Location description and prevent duplicate details where possible.

### Phase 2 — Content quality refinement

- Improve Location-description normalization for unusually repetitive or conflicting legacy text.
- Add clearer guidance for writing concise, render-ready Location descriptions.

### Phase 3 — Workflow enhancements

- Add optional Location presets or reusable saved locations.
- Add comparison or history tools for Location edits across scene revisions.

## Assumptions

- The new visible label is exactly **Location**, and the strategy JSON property is `location`.
- Environment, Background, and Setting are removed as independent concepts from this workflow rather than retained as hidden editable fields.
- Legacy values are merged in Environment, Background, then Setting order, with obvious repetition removed while preserving meaningful details.
- Visual and audio direction selections modify or enrich the same Location value; they do not create separate direction-only Location fields.
- The Location value shown in the final result matches the value supplied to the render prompt.
- Changes are limited to the Hook + Story strategy, scene, review, direction, prompt, render, and result paths that currently use these place-related fields.
- Existing styling and unrelated workflow behavior remain unchanged.