import { UPSCALE, upscaleTarget } from "./sizing";

describe("upscaleTarget", () => {
  test("a 540p portrait phone clip lands on 1080x1920", () => {
    expect(upscaleTarget(540, 960)).toEqual({ width: 1080, height: 1920 });
  });

  test("a 540p landscape clip lands on 1920x1080", () => {
    expect(upscaleTarget(960, 540)).toEqual({ width: 1920, height: 1080 });
  });

  test("a square clip lands on 1080x1080", () => {
    expect(upscaleTarget(540, 540)).toEqual({ width: 1080, height: 1080 });
  });

  test("a 720p clip upscales to 1080p", () => {
    expect(upscaleTarget(1280, 720)).toEqual({ width: 1920, height: 1080 });
  });

  test("a 4:3 clip keeps its aspect and hits 1080 on the short side", () => {
    expect(upscaleTarget(640, 480)).toEqual({ width: 1440, height: 1080 });
  });

  test("the export target is 1080p, not 4K", () => {
    // The page promises a 1080p export; a 4K target here would quietly ship
    // files four times the pixel count the copy names.
    expect(UPSCALE.targetMinSide).toBe(1080);
    expect(UPSCALE.maxSide).toBe(1920);
  });

  test("already-1080p sources are not eligible", () => {
    expect(upscaleTarget(1920, 1080)).toBeNull();
    expect(upscaleTarget(1080, 1920)).toBeNull();
    expect(upscaleTarget(1920, 1200)).toBeNull();
    expect(upscaleTarget(1080, 1080)).toBeNull();
  });

  test("larger-than-1080p sources are not eligible either", () => {
    expect(upscaleTarget(3840, 2160)).toBeNull();
    expect(upscaleTarget(2160, 3840)).toBeNull();
    expect(upscaleTarget(1440, 2560)).toBeNull();
  });

  test("a wide clip that already fills the long side is refused, not re-exported", () => {
    // 1920x800 has a short side under 1080 but no room on the long side, so
    // the only possible "1080p" export is the input's own dimensions. Null
    // makes the page say so instead of handing back an un-enlarged file.
    expect(upscaleTarget(1920, 800)).toBeNull();
    expect(upscaleTarget(2000, 800)).toBeNull();
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
