import { paintsEndCard, paintsHookStory } from "./overlays";

describe("end-card placement", () => {
  test("without a second clip the base is the whole timeline, so it keeps the card", () => {
    expect(paintsEndCard({ segment: 0, hasSecondClip: false })).toBe(true);
  });

  test("with a second clip the base never paints the card — it would flash mid-video", () => {
    expect(paintsEndCard({ segment: 0, hasSecondClip: true })).toBe(false);
  });

  test("with a second clip the appended segment closes the timeline with the card", () => {
    expect(paintsEndCard({ segment: 1, hasSecondClip: true })).toBe(true);
  });
});

describe("hook/story mirroring", () => {
  test("the base always opens with hook and story", () => {
    expect(paintsHookStory({ segment: 0, hasSecondClip: true, mirrorOverlays: false })).toBe(true);
    expect(paintsHookStory({ segment: 0, hasSecondClip: false, mirrorOverlays: false })).toBe(true);
  });

  test("the second clip only repeats them under the both-clips toggle", () => {
    expect(paintsHookStory({ segment: 1, hasSecondClip: true, mirrorOverlays: false })).toBe(false);
    expect(paintsHookStory({ segment: 1, hasSecondClip: true, mirrorOverlays: true })).toBe(true);
  });
});
