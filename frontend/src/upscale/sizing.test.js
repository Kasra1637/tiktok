import { UPSCALE, upscaleTarget } from "./sizing";

describe("upscaleTarget", () => {
  test("a 540p portrait phone clip lands on 2160x3840", () => {
    expect(upscaleTarget(540, 960)).toEqual({ width: 2160, height: 3840 });
  });

  test("a 540p landscape clip lands on 3840x2160", () => {
    expect(upscaleTarget(960, 540)).toEqual({ width: 3840, height: 2160 });
  });

  test("a square clip lands on 2160x2160", () => {
    expect(upscaleTarget(540, 540)).toEqual({ width: 2160, height: 2160 });
  });

  test("a 720p clip upscales to 4K", () => {
    expect(upscaleTarget(1280, 720)).toEqual({ width: 3840, height: 2160 });
  });

  test("already-4K sources are not eligible", () => {
    expect(upscaleTarget(3840, 2160)).toBeNull();
    expect(upscaleTarget(2160, 3840)).toBeNull();
    expect(upscaleTarget(3840, 2400)).toBeNull();
    expect(upscaleTarget(2160, 2160)).toBeNull();
  });

  test("a tiny clip stays capped at the long-side ceiling", () => {
    const target = upscaleTarget(160, 120);
    expect(Math.max(target.width, target.height)).toBeLessThanOrEqual(UPSCALE.maxSide + 1);
    expect(target.width % 2).toBe(0);
    expect(target.height % 2).toBe(0);
  });

  test("dimensions stay even for AVC", () => {
    const target = upscaleTarget(853, 480);
    expect(target.width % 2).toBe(0);
    expect(target.height % 2).toBe(0);
  });

  test("unusable dimensions are refused", () => {
    expect(upscaleTarget(0, 480)).toBeNull();
    expect(upscaleTarget(NaN, 480)).toBeNull();
    expect(upscaleTarget(-640, 480)).toBeNull();
  });
});
