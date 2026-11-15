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

describe("directionDrifted with direction_saved (ADR 0146)", () => {
  // A plan-written Location can carry an object clause the editor's
  // display strips: the saved value and the strategy's stamp both hold
  // the raw text, the payload's top-level `location` holds the stripped
  // display text. The gate answers to the saved value, never the display.
  const RAW_LOCATION =
    "A quiet garden bench, with the phone lying face-down beside the person";
  const RAW = { ...SNAPSHOT, location: RAW_LOCATION };

  test("a display-stripped location is not drift when the saved value matches the stamp", () => {
    expect(
      directionDrifted({
        strategy: { direction_snapshot: { ...RAW } },
        ...RAW,
        location: "A quiet garden bench",
        direction_saved: { ...RAW },
      })
    ).toBe(false);
  });

  test("a saved location that moved is drift even when the display text matches the stamp", () => {
    expect(
      directionDrifted({
        strategy: { direction_snapshot: { ...SNAPSHOT } },
        ...SNAPSHOT,
        direction_saved: { ...SNAPSHOT, location: "A bus stop bench" },
      })
    ).toBe(true);
  });

  test("a saved field that moved is drift even when its display text matches the stamp", () => {
    expect(
      directionDrifted({
        strategy: { direction_snapshot: { ...RAW } },
        ...RAW,
        direction_saved: { ...RAW, visual_direction: "Wide, 9:16, street." },
      })
    ).toBe(true);
  });

  test("an empty saved location is not drift just because the display filled it from the scene", () => {
    expect(
      directionDrifted({
        strategy: {
          direction_snapshot: { ...SNAPSHOT, location: "" },
          scene: { location: "A quiet garden bench" },
        },
        ...SNAPSHOT,
        location: "A quiet garden bench",
        direction_saved: { ...SNAPSHOT, location: "" },
      })
    ).toBe(false);
  });
});
