import { directionDrifted } from "./strategyStaleness";

const SNAPSHOT = {
  location: "A quiet garden bench",
  visual_direction: "Close, 9:16, garden.",
  voice_direction: "Calm.",
  sound_direction: "Room tone.",
};

const CURRENT = {
  strategy: { direction_snapshot: { ...SNAPSHOT } },
  ...SNAPSHOT,
};

describe("directionDrifted", () => {
  test("no snapshot is missing history, not drift", () => {
    expect(directionDrifted({ strategy: {}, ...SNAPSHOT })).toBe(false);
  });

  test("no strategy at all is not drift", () => {
    expect(directionDrifted({ ...SNAPSHOT })).toBe(false);
  });

  test("a matching direction is not drift, even with extra spaces", () => {
    expect(
      directionDrifted({
        ...CURRENT,
        location: "  A quiet garden bench  ",
      })
    ).toBe(false);
  });

  test("each direction field on its own owes a rebuild", () => {
    for (const field of Object.keys(SNAPSHOT)) {
      expect(
        directionDrifted({ ...CURRENT, [field]: "Something else entirely." })
      ).toBe(true);
    }
  });

  test("a location filled only by the strategy scene's display fallback is not drift", () => {
    // The payload fills an empty saved location from the strategy scene for
    // display; the saved value is still empty, exactly as the server's diff
    // sees it.
    expect(
      directionDrifted({
        strategy: {
          direction_snapshot: { ...SNAPSHOT, location: "" },
          scene: { location: "A quiet garden bench" },
        },
        ...SNAPSHOT,
        location: "A quiet garden bench",
      })
    ).toBe(false);
  });

  test("a location the founder actually set is drift even when the snapshot was empty", () => {
    expect(
      directionDrifted({
        strategy: {
          direction_snapshot: { ...SNAPSHOT, location: "" },
          scene: { location: "A quiet garden bench" },
        },
        ...SNAPSHOT,
        location: "A bus stop bench",
      })
    ).toBe(true);
  });
});
