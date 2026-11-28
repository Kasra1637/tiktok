import {
  appendItemAt,
  appendSequenceDuration,
  appendShapeOf,
  composeAppendFrame,
  makeImageEntry,
  makeVideoEntry,
  migrateAppendEdit,
  migrateAppendItems,
} from "./appendSequence";

// The second slot's media model: one ordered sequence of clip and still
// entries. These tests pin the shape rules the editor's playback paths
// branch on, the migration every pre-sequence draft passes through, and
// the run math the preview and the export both read.

const videoMeta = (d) => ({ w: 1080, h: 1920, d });

describe("appendShapeOf", () => {
  test("an empty list is empty, one video is single, stills only is images", () => {
    expect(appendShapeOf([])).toBe("empty");
    expect(appendShapeOf([makeVideoEntry({}, "a.mp4")])).toBe("single");
    expect(appendShapeOf([makeImageEntry({}, "a.png"), makeImageEntry({}, "b.png")])).toBe("images");
  });

  test("several clips, or clips and stills together, are mixed", () => {
    expect(appendShapeOf([makeVideoEntry({}, "a.mp4"), makeVideoEntry({}, "b.mp4")])).toBe("mixed");
    expect(appendShapeOf([makeVideoEntry({}, "a.mp4"), makeImageEntry({}, "a.png")])).toBe("mixed");
    expect(appendShapeOf([makeImageEntry({}, "a.png")])).toBe("images");
  });
});

describe("the draft migration", () => {
  test("a lone appendMedia becomes a one-entry video sequence", () => {
    const legacy = { id: "e1", blob: { size: 1 }, name: "clip.mp4" };
    const items = migrateAppendItems({ appendMedia: legacy });
    expect(items).toHaveLength(1);
    expect(items[0].kind).toBe("video");
    expect(items[0].name).toBe("clip.mp4");
    expect(items[0].blob).toBe(legacy.blob);
  });

  test("an appendImages list becomes image entries in order, kinds added", () => {
    const items = migrateAppendItems({
      appendImages: [
        { id: "i1", blob: {}, name: "a.png", seconds: 3, motion: "still" },
        { id: "i2", blob: {}, name: "b.png", seconds: 2, motion: "still" },
      ],
    });
    expect(items.map((entry) => entry.name)).toEqual(["a.png", "b.png"]);
    expect(items.every((entry) => entry.kind === "image")).toBe(true);
    expect(items[0].seconds).toBe(3);
  });

  test("a clip and a still list migrate into one mixed sequence, clip first", () => {
    const items = migrateAppendItems({
      appendMedia: { id: "e1", blob: {}, name: "clip.mp4" },
      appendImages: [{ id: "i1", blob: {}, name: "a.png", seconds: 2 }],
    });
    expect(items.map((entry) => entry.kind)).toEqual(["video", "image"]);
  });

  test("a draft already carrying appendItems passes through untouched", () => {
    const items = [makeVideoEntry({}, "a.mp4"), makeImageEntry({}, "a.png")];
    const edit = { appendItems: items, appendStart: 1 };
    expect(migrateAppendEdit(edit)).toBe(edit);
    expect(migrateAppendItems(edit)).toBe(items);
  });

  test("an edit with neither field migrates to an empty sequence", () => {
    expect(migrateAppendItems({})).toEqual([]);
    expect(migrateAppendItems(null)).toEqual([]);
    expect(migrateAppendEdit(null)).toBe(null);
  });
});

describe("the run math", () => {
  const probed = new Map();
  const clipA = makeVideoEntry({}, "a.mp4");
  const still = makeImageEntry({}, "a.png");
  still.seconds = 2.5;
  const clipB = makeVideoEntry({}, "b.mp4");
  probed.set(clipA.id, videoMeta(4));
  probed.set(clipB.id, videoMeta(6));
  const items = [clipA, still, clipB];

  test("the run sums clip lengths and still holds in order", () => {
    expect(appendSequenceDuration(items, probed)).toBeCloseTo(12.5);
  });

  test("an unprobed clip contributes nothing yet", () => {
    expect(appendSequenceDuration(items, new Map())).toBeCloseTo(2.5);
  });

  test("appendItemAt names the entry under a time and its local offset", () => {
    expect(appendItemAt(items, probed, 0).item).toBe(clipA);
    const atStill = appendItemAt(items, probed, 5);
    expect(atStill.item).toBe(still);
    expect(atStill.local).toBeCloseTo(1);
    const atB = appendItemAt(items, probed, 12.4);
    expect(atB.item).toBe(clipB);
    expect(atB.local).toBeCloseTo(5.9);
  });

  test("times outside the run clamp to its ends", () => {
    expect(appendItemAt(items, probed, -3).item).toBe(clipA);
    expect(appendItemAt(items, probed, 99).item).toBe(clipB);
    expect(appendItemAt([], probed, 1)).toBe(null);
  });
});

describe("composeAppendFrame", () => {
  const makeCanvas = () => {
    const ctx = {
      clearRect: jest.fn(),
      fillRect: jest.fn(),
      drawImage: jest.fn(),
      save: jest.fn(),
      restore: jest.fn(),
      clip: jest.fn(),
      beginPath: jest.fn(),
      rect: jest.fn(),
    };
    return { width: 0, height: 0, getContext: () => ctx, ctx };
  };
  const drawable = (w, h) => ({ naturalWidth: w, naturalHeight: h, width: w, height: h });

  test("the canvas takes the first entry's size and a clip draws cover-fit", () => {
    const canvas = makeCanvas();
    const clip = makeVideoEntry({}, "a.mp4");
    const probed = new Map([[clip.id, videoMeta(4)]]);
    const frame = composeAppendFrame(canvas, [drawable(720, 1280)], [clip], probed, 1);
    expect(frame).toBe(canvas);
    expect(canvas.width).toBe(720);
    expect(canvas.height).toBe(1280);
    expect(canvas.ctx.drawImage).toHaveBeenCalled();
  });

  test("with nothing drawable the frame is skipped, not faked", () => {
    const canvas = makeCanvas();
    const clip = makeVideoEntry({}, "a.mp4");
    const probed = new Map([[clip.id, videoMeta(4)]]);
    expect(composeAppendFrame(canvas, [drawable(0, 0)], [clip], probed, 1)).toBe(null);
    expect(composeAppendFrame(canvas, [], [], probed, 0)).toBe(null);
  });
});
