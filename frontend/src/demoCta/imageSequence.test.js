import {
  IMAGE_SECONDS,
  IMAGE_PUSH_IN,
  IMAGE_FADE_SECONDS,
  DEFAULT_IMAGE_MOTION,
  clampImageSeconds,
  imageSequenceDuration,
  imageFrameAt,
  pushInScale,
  normalizeImageMotion,
  imageMotionAt,
  imageFadeAt,
  composeImageFrame,
} from "./imageSequence";

const seq = (...seconds) => seconds.map((s) => ({ seconds: s }));

describe("image sequence timing", () => {
  test("seconds clamp to the slot's band, with the default for junk", () => {
    expect(clampImageSeconds(2.5)).toBe(2.5);
    expect(clampImageSeconds(0.2)).toBe(IMAGE_SECONDS.min);
    expect(clampImageSeconds(60)).toBe(IMAGE_SECONDS.max);
    expect(clampImageSeconds(undefined)).toBe(IMAGE_SECONDS.default);
    expect(clampImageSeconds("nope")).toBe(IMAGE_SECONDS.default);
  });

  test("the sequence lasts the sum of its images", () => {
    expect(imageSequenceDuration(seq(2, 3.5, 1))).toBeCloseTo(6.5);
    expect(imageSequenceDuration([])).toBe(0);
    expect(imageSequenceDuration(null)).toBe(0);
    expect(imageSequenceDuration([{}])).toBe(IMAGE_SECONDS.default);
  });

  test("frame lookup walks the images in order", () => {
    const images = seq(2, 3, 1);
    expect(imageFrameAt(images, 0)).toMatchObject({ index: 0, local: 0, progress: 0 });
    expect(imageFrameAt(images, 1)).toMatchObject({ index: 0, local: 1, progress: 0.5 });
    expect(imageFrameAt(images, 2)).toMatchObject({ index: 1, local: 0, progress: 0 });
    expect(imageFrameAt(images, 4.5)).toMatchObject({ index: 1, local: 2.5 });
    expect(imageFrameAt(images, 5.5)).toMatchObject({ index: 2, local: 0.5, progress: 0.5 });
  });

  test("frame lookup clamps outside the sequence instead of running off", () => {
    const images = seq(2, 1);
    expect(imageFrameAt(images, -3)).toMatchObject({ index: 0, local: 0 });
    expect(imageFrameAt(images, 99)).toMatchObject({ index: 1, local: 1, progress: 1 });
    expect(imageFrameAt([], 1)).toBeNull();
  });
});

describe("the gentle push-in", () => {
  test("starts still and ends at the full push, easing out", () => {
    expect(pushInScale(0)).toBe(1);
    expect(pushInScale(1)).toBeCloseTo(1 + IMAGE_PUSH_IN);
    expect(pushInScale(0.5)).toBeGreaterThan(1 + IMAGE_PUSH_IN * 0.5);
    let last = 1;
    for (let p = 0; p <= 1.0001; p += 0.1) {
      expect(pushInScale(p)).toBeGreaterThanOrEqual(last);
      last = pushInScale(p);
    }
  });

  test("reduced motion parks the push-in", () => {
    expect(pushInScale(0.5, true)).toBe(1);
    expect(pushInScale(1, true)).toBe(1);
  });
});

describe("the crossfade between images", () => {
  test("no fade outside the window, none after the last image", () => {
    const images = seq(2, 2);
    expect(imageFadeAt(images, 0.5)).toBeNull();
    expect(imageFadeAt(images, 3.9)).toBeNull();
    expect(imageFadeAt(images, 4)).toBeNull();
  });

  test("alpha ramps across the window into the next image", () => {
    const images = seq(2, 2);
    const start = imageFadeAt(images, 2 - IMAGE_FADE_SECONDS);
    expect(start).toMatchObject({ index: 1 });
    expect(start.alpha).toBeCloseTo(0, 2);
    const mid = imageFadeAt(images, 2 - IMAGE_FADE_SECONDS / 2);
    expect(mid.alpha).toBeGreaterThan(0.2);
    expect(mid.alpha).toBeLessThan(0.8);
    const end = imageFadeAt(images, 1.999);
    expect(end.alpha).toBeGreaterThan(0.9);
  });

  test("a short image fades only near its own end", () => {
    const images = seq(0.5, 2); // first clamps to the minimum
    const first = clampImageSeconds(images[0].seconds);
    const fade = imageFadeAt(images, first - first / 4);
    expect(fade).not.toBeNull();
    expect(imageFadeAt(images, first / 4)).toBeNull();
  });

  test("reduced motion cuts instead of fading", () => {
    const images = seq(2, 2);
    expect(imageFadeAt(images, 1.9, true)).toBeNull();
  });
});

describe("the composed frame", () => {
  const fakeImage = (w, h) => ({ width: w, height: h, naturalWidth: w, naturalHeight: h });
  const fakeCanvas = () => {
    const calls = [];
    const ctx = {
      globalAlpha: 1,
      fillStyle: null,
      calls,
      clearRect() {},
      fillRect() {},
      save() {},
      restore() {},
      drawImage(img, dx, dy, dw, dh) { calls.push({ img, dx, dy, dw, dh, alpha: this.globalAlpha }); },
    };
    return { width: 0, height: 0, getContext: () => ctx, ctx };
  };

  test("sizes itself to the first image and covers it, still by default", () => {
    const canvas = fakeCanvas();
    const images = seq(2);
    const drawables = [fakeImage(100, 200)];
    const early = composeImageFrame(canvas, drawables, images, 0);
    expect(early).toBe(canvas);
    expect(canvas.width).toBe(100);
    expect(canvas.height).toBe(200);
    expect(canvas.ctx.calls).toHaveLength(1);
    expect(canvas.ctx.calls[0].dw).toBeCloseTo(100);
    composeImageFrame(canvas, drawables, images, 2);
    expect(canvas.ctx.calls).toHaveLength(2);
    expect(canvas.ctx.calls[1].dw).toBeCloseTo(100);
    expect(canvas.ctx.calls[1].dh).toBeCloseTo(200);
  });

  test("a Zoom in pick pushes in over the hold, as the automatic zoom used to", () => {
    const canvas = fakeCanvas();
    const images = [{ seconds: 2, motion: "zoom-in" }];
    const drawables = [fakeImage(100, 200)];
    composeImageFrame(canvas, drawables, images, 0);
    expect(canvas.ctx.calls[0].dw).toBeCloseTo(100);
    composeImageFrame(canvas, drawables, images, 2);
    expect(canvas.ctx.calls[1].dw).toBeCloseTo(100 * (1 + IMAGE_PUSH_IN));
    expect(canvas.ctx.calls[1].dh).toBeCloseTo(200 * (1 + IMAGE_PUSH_IN));
  });

  test("inside the fade both images paint, the next one translucent", () => {
    const canvas = fakeCanvas();
    const images = seq(2, 2);
    const drawables = [fakeImage(100, 200), fakeImage(100, 200)];
    composeImageFrame(canvas, drawables, images, 1.9);
    expect(canvas.ctx.calls).toHaveLength(2);
    expect(canvas.ctx.calls[0].img).toBe(drawables[0]);
    expect(canvas.ctx.calls[0].alpha).toBe(1);
    expect(canvas.ctx.calls[1].img).toBe(drawables[1]);
    expect(canvas.ctx.calls[1].alpha).toBeGreaterThan(0);
    expect(canvas.ctx.calls[1].alpha).toBeLessThan(1);
  });

  test("after the cut only the next image paints", () => {
    const canvas = fakeCanvas();
    const images = seq(2, 2);
    const drawables = [fakeImage(100, 200), fakeImage(100, 200)];
    composeImageFrame(canvas, drawables, images, 2.5);
    expect(canvas.ctx.calls).toHaveLength(1);
    expect(canvas.ctx.calls[0].img).toBe(drawables[1]);
  });

  test("nothing drawable is a null frame, never a throw", () => {
    const canvas = fakeCanvas();
    expect(composeImageFrame(canvas, [], seq(2), 0)).toBeNull();
    expect(composeImageFrame(canvas, [fakeImage(0, 0)], seq(2), 0)).toBeNull();
    expect(composeImageFrame(null, [fakeImage(10, 10)], seq(2), 0)).toBeNull();
  });

  test("a Pan right pick drifts the still across the frame at one overscan scale", () => {
    const canvas = fakeCanvas();
    const images = [{ seconds: 2, motion: "pan-right" }];
    const drawables = [fakeImage(100, 200)];
    composeImageFrame(canvas, drawables, images, 0);
    expect(canvas.ctx.calls[0].dw).toBeCloseTo(100 * (1 + IMAGE_PUSH_IN));
    expect(canvas.ctx.calls[0].dx).toBeCloseTo(0);
    composeImageFrame(canvas, drawables, images, 2);
    expect(canvas.ctx.calls[1].dw).toBeCloseTo(100 * (1 + IMAGE_PUSH_IN));
    expect(canvas.ctx.calls[1].dx).toBeCloseTo(-100 * IMAGE_PUSH_IN);
  });

  test("a Zoom out pick starts pushed in and settles on the still", () => {
    const canvas = fakeCanvas();
    const images = [{ seconds: 2, motion: "zoom-out" }];
    const drawables = [fakeImage(100, 200)];
    composeImageFrame(canvas, drawables, images, 0);
    expect(canvas.ctx.calls[0].dw).toBeCloseTo(100 * (1 + IMAGE_PUSH_IN));
    composeImageFrame(canvas, drawables, images, 2);
    expect(canvas.ctx.calls[1].dw).toBeCloseTo(100);
  });
});

describe("per-image motion (ADR 0354)", () => {
  test("no stored pick — a fresh upload or an old draft — resolves to None", () => {
    expect(DEFAULT_IMAGE_MOTION).toBe("none");
    expect(normalizeImageMotion(undefined)).toBe("none");
    expect(normalizeImageMotion("bogus")).toBe("none");
    for (const id of ["zoom-in", "zoom-out", "pan-right", "pan-left", "pan-up", "pan-down"]) {
      expect(normalizeImageMotion(id)).toBe(id);
    }
  });

  test("None is the still itself at every progress", () => {
    for (const p of [0, 0.5, 1]) {
      expect(imageMotionAt({}, p)).toEqual({ scale: 1, anchorX: 0.5, anchorY: 0.5 });
      expect(imageMotionAt({ motion: "none" }, p)).toEqual({ scale: 1, anchorX: 0.5, anchorY: 0.5 });
    }
  });

  test("each Pan drifts its own anchor and no other", () => {
    expect(imageMotionAt({ motion: "pan-right" }, 1)).toEqual({ scale: 1 + IMAGE_PUSH_IN, anchorX: 1, anchorY: 0.5 });
    expect(imageMotionAt({ motion: "pan-left" }, 1)).toEqual({ scale: 1 + IMAGE_PUSH_IN, anchorX: 0, anchorY: 0.5 });
    expect(imageMotionAt({ motion: "pan-up" }, 1)).toEqual({ scale: 1 + IMAGE_PUSH_IN, anchorX: 0.5, anchorY: 0 });
    expect(imageMotionAt({ motion: "pan-down" }, 1)).toEqual({ scale: 1 + IMAGE_PUSH_IN, anchorX: 0.5, anchorY: 1 });
  });

  test("reduced motion parks every pick", () => {
    for (const motion of ["zoom-in", "zoom-out", "pan-right", "pan-left", "pan-up", "pan-down"]) {
      expect(imageMotionAt({ motion }, 0.5, true)).toEqual({ scale: 1, anchorX: 0.5, anchorY: 0.5 });
    }
  });
});
