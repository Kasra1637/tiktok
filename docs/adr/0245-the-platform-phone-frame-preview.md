# 0245 — The platform phone-frame preview joins Hook + CTA and Create Video

Status: accepted

## Context

On the Nov 20 2026 evening call, with the Hook + CTA page (ADR 0244)
just landed, Kasra ordered the phone-mockup preview the retired
Stories page had — "place the preview video where it makes sense
best. And allow user to toggle between TikTok and Instagram. So
they get a realistic view of their video" — and approved adding it
to the Create Video pages as well, with spacing and UI fine-tuned
and polished. The point is judgment before posting: the founder
sees the finished clip inside a phone frame, under each platform's
own furniture, while there is still time to re-render.

ADR 0243 deleted that preview with the Stories page
(`StoryPreview.jsx`, removed in commit 06015f1). Its safe-zone
geometry was settled and Kasra-approved in ADR 0236, so this
decision recovers it rather than reinventing it.

## Decision

1. **One shared component, recovered.** `PlatformPreview.jsx`
   (components/studio) is adapted from the retired
   `StoryPreview.jsx` at `06015f1^`: same zone math on the
   1080×1920 canvas (Instagram — top 250, bottom 340, sides 65, no
   rail; TikTok — top 240, bottom 660, sides 120, plus the 300px
   right rail from y≈840), same dashed-guide bands and labels, same
   platform pill toggle (Instagram first, TikTok second), same
   frame. What changes is only what it previews and where it sits.
   The retired component's screen-text sticker is NOT carried over:
   neither host surface has screen text (ADR 0244's page has none
   by design), so there is nothing for a sticker to preview.

2. **Hook + CTA placement.** The frame stands at the foot of
   `HookRenderPanel`, inside the Render card: the stage where the
   finished 4–5s hook appears, before it flows into the Demo + CTA
   finish. Before any render exists the frame holds the retired
   preview's honest placeholder ("The frame previews here once it
   renders") — never a fake video; once a render completes, the
   clip plays in the frame. The panel's bare player and its broken
   box are replaced by the frame; the badges, the storage alert and
   Download MP4 stay in the completed block above it.

3. **Create Video placement.** The frame stands in
   `GenerationPanel`'s finished block, in the 280px column beside
   the frozen post kit, replacing the bare player there — inside
   the celebration wrapper, so a live generating→completed
   transition still bursts around the arriving clip. That block is
   where the founder judges the presenter segment (~15s hook +
   story) before finishing, which is why the frame goes there and
   not in the Demo + CTA step: that step's editor and its own
   preview machinery (ADR 0007 composition) are untouched. The
   finished presenter video also appears in History and in the
   Demo + CTA editor; those are the record and the composition
   tool, not the judging moment, so the frame does not follow it
   there.

4. **Viewer-only rules.** The toggle switches only the overlay
   zones and the platform label — never the video. The zones are
   guides, not masks: the clip stays fully visible beneath them.
   Nothing is burned in; this is a preview of a finished clip URL,
   nothing more. The clip keeps the ADR 0137 native-controls
   contract (controlsList, disablePictureInPicture), which now
   rides on the frame's own video element.

5. **Broken clips.** The host panels own the preview-broken state,
   as they did for their bare players: a clip the browser cannot
   play says "Preview unavailable — download it to view." inside
   the frame. GenerationPanel keeps its "Try the preview again"
   retry, now under the frame; HookRenderPanel offered no retry
   and gains none.
