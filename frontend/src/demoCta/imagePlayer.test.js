import { createImageSequencePlayer } from "./imagePlayer";

// The player's clock is rAF-driven; the tests own the frame queue so time
// advances exactly when they say it does.
let rafQueue;
let rafId;
beforeEach(() => {
  rafQueue = new Map();
  rafId = 0;
  jest.spyOn(global, "requestAnimationFrame").mockImplementation((cb) => {
    rafId += 1;
    rafQueue.set(rafId, cb);
    return rafId;
  });
  jest.spyOn(global, "cancelAnimationFrame").mockImplementation((id) => {
    rafQueue.delete(id);
  });
});
afterEach(() => {
  jest.restoreAllMocks();
});
const stepFrames = (stamp) => {
  const pending = [...rafQueue.values()];
  rafQueue.clear();
  pending.forEach((cb) => cb(stamp));
};

describe("the image sequence player", () => {
  test("starts paused at zero with the sequence's duration", () => {
    const player = createImageSequencePlayer({ duration: 5, frameAt: () => null });
    expect(player.paused).toBe(true);
    expect(player.currentTime).toBe(0);
    expect(player.duration).toBe(5);
    expect(player.ended).toBe(false);
  });

  test("play advances the clock on frame stamps and reports timeupdate", () => {
    const player = createImageSequencePlayer({ duration: 5, frameAt: () => null });
    const seen = [];
    player.addEventListener("timeupdate", () => seen.push(player.currentTime));
    const plays = [];
    player.addEventListener("play", () => plays.push(true));
    player.play();
    expect(player.paused).toBe(false);
    expect(plays).toHaveLength(1);
    stepFrames(1000); // first stamp only arms the clock
    stepFrames(1500);
    stepFrames(2000);
    expect(player.currentTime).toBeCloseTo(1);
    expect(seen.length).toBeGreaterThanOrEqual(2);
    expect(seen[seen.length - 1]).toBeCloseTo(1);
  });

  test("pause halts the clock and says so", () => {
    const player = createImageSequencePlayer({ duration: 5, frameAt: () => null });
    let pauses = 0;
    player.addEventListener("pause", () => { pauses += 1; });
    player.play();
    stepFrames(0);
    stepFrames(400);
    player.pause();
    expect(player.paused).toBe(true);
    expect(pauses).toBe(1);
    stepFrames(900);
    expect(player.currentTime).toBeCloseTo(0.4);
  });

  test("reaching the end parks on the last frame and fires ended once", () => {
    const player = createImageSequencePlayer({ duration: 1, frameAt: () => null });
    let ended = 0;
    player.addEventListener("ended", () => { ended += 1; });
    player.play();
    stepFrames(0);
    stepFrames(400);
    stepFrames(800);
    stepFrames(1200);
    expect(player.currentTime).toBe(1);
    expect(player.paused).toBe(true);
    expect(player.ended).toBe(true);
    expect(ended).toBe(1);
    stepFrames(2200);
    expect(ended).toBe(1);
  });

  test("seeking clamps and fires seeked so the preview can repaint", () => {
    const player = createImageSequencePlayer({ duration: 5, frameAt: () => null });
    let seeked = 0;
    player.addEventListener("seeked", () => { seeked += 1; });
    player.currentTime = 2.5;
    expect(player.currentTime).toBe(2.5);
    expect(seeked).toBe(1);
    player.currentTime = 99;
    expect(player.currentTime).toBe(5);
    player.currentTime = -2;
    expect(player.currentTime).toBe(0);
  });

  test("playing from the end restarts, like a media element", () => {
    const player = createImageSequencePlayer({ duration: 1, frameAt: () => null });
    player.play();
    stepFrames(0);
    stepFrames(500);
    stepFrames(1000);
    expect(player.ended).toBe(true);
    player.play();
    expect(player.currentTime).toBe(0);
    expect(player.paused).toBe(false);
  });

  test("frameCanvas hands the compositor the player's own time", () => {
    const frameAt = jest.fn(() => "frame");
    const player = createImageSequencePlayer({ duration: 5, frameAt });
    player.currentTime = 1.25;
    expect(player.frameCanvas()).toBe("frame");
    expect(frameAt).toHaveBeenCalledWith(1.25);
  });

  test("a duration change (an image added, a hold lengthened) re-times in place", () => {
    const player = createImageSequencePlayer({ duration: 5, frameAt: () => null });
    player.currentTime = 4;
    player.setDuration(2.5);
    expect(player.duration).toBe(2.5);
    expect(player.currentTime).toBe(2.5);
    player.setDuration(9);
    expect(player.duration).toBe(9);
    expect(player.currentTime).toBe(2.5);
  });

  test("removed listeners stop hearing events, and dispose silences the clock", () => {
    const player = createImageSequencePlayer({ duration: 5, frameAt: () => null });
    let heard = 0;
    const onTime = () => { heard += 1; };
    player.addEventListener("timeupdate", onTime);
    player.removeEventListener("timeupdate", onTime);
    player.play();
    stepFrames(0);
    stepFrames(100);
    expect(heard).toBe(0);
    player.dispose();
    stepFrames(200);
    expect(player.currentTime).toBeCloseTo(0.1);
  });
});
