import { UPSCALE, upscaleTarget } from "./enhanceVideo";

describe("upscaleTarget", () => {
  test("a 720p portrait phone clip lands on 1080x1920", () => {
    expect(upscaleTarget(720, 1280)).toEqual({ width: 1080, height: 1920 });
  });

  test("a 480p landscape clip lands on 1920x1080", () => {
    expect(upscaleTarget(854, 480)).toEqual({ width: 1920, height: 1080 });
  });

  test("a square clip lands on 1080x1080", () => {
    expect(upscaleTarget(640, 640)).toEqual({ width: 1080, height: 1080 });
  });

  test("a 720p clip upscales to full HD", () => {
    expect(upscaleTarget(1280, 720)).toEqual({ width: 1920, height: 1080 });
  });

  test("already-HD sources are not eligible", () => {
    expect(upscaleTarget(1920, 1080)).toBeNull();
    expect(upscaleTarget(1080, 1920)).toBeNull();
    expect(upscaleTarget(1920, 1200)).toBeNull();
    expect(upscaleTarget(1080, 1080)).toBeNull();
  });

  test("a tiny clip stays capped at the long-side ceiling", () => {
    const target = upscaleTarget(160, 120);
    expect(Math.max(target.width, target.height)).toBeLessThanOrEqual(UPSCALE.maxSide + 2);
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
