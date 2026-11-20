/**
 * A media-element-shaped clock for an image sequence (ADR 0237).
 *
 * The Demo + CTA preview transport is built around two media elements —
 * play, pause, seek, timeupdate, ended — and an image sequence has no
 * element. This player exposes the slice of that interface the transport
 * actually reads, driven by requestAnimationFrame, so the sequence takes
 * the second slot's place in the joined timeline without the transport
 * learning a second shape: seeks land on it, trims park it, the end of
 * the base hands off to it, and the CTA replay window owns it, exactly
 * as they own a clip. It owns no pixels: `frameCanvas()` asks the
 * caller's compositor for the frame at the player's own time, and the
 * painter treats that canvas like any decoded clip frame.
 */
export function createImageSequencePlayer({ duration = 0, frameAt = null } = {}) {
  const listeners = new Map();
  let total = Math.max(0, Number(duration) || 0);
  let time = 0;
  let playing = false;
  let raf = null;
  let lastStamp = null;
  let disposed = false;

  const emit = (type) => {
    const set = listeners.get(type);
    if (set) [...set].forEach((fn) => fn());
  };

  const stopClock = () => {
    if (raf !== null) cancelAnimationFrame(raf);
    raf = null;
    lastStamp = null;
  };

  const tick = (stamp) => {
    raf = null;
    if (!playing || disposed) return;
    if (lastStamp === null) lastStamp = stamp;
    // A backgrounded tab can hand the clock minutes at once; the sequence
    // advances in steps of at most half a second, never in one leap.
    const delta = Math.min(0.5, Math.max(0, (stamp - lastStamp) / 1000));
    lastStamp = stamp;
    time += delta;
    if (time >= total) {
      time = total;
      playing = false;
      emit("timeupdate");
      if (player.loop && total > 0) {
        time = 0;
        playing = true;
        emit("timeupdate");
      } else {
        emit("ended");
        return;
      }
    } else {
      emit("timeupdate");
    }
    raf = requestAnimationFrame(tick);
  };

  const player = {
    // Stored, media-shaped no-ops: the transport writes these on whichever
    // source it owns (mute rides preview only; a sequence is silent).
    muted: true,
    volume: 1,
    loop: false,

    get duration() { return total; },
    get paused() { return !playing; },
    get ended() { return !playing && total > 0 && time >= total; },
    get currentTime() { return time; },
    set currentTime(next) {
      const value = Number(next);
      time = Number.isFinite(value) ? Math.min(Math.max(0, value), total) : 0;
      emit("seeked");
      emit("timeupdate");
    },

    play() {
      if (disposed) return Promise.resolve();
      if (time >= total && total > 0) time = 0; // a media element replays from the top
      if (!playing) {
        playing = true;
        emit("play");
        stopClock();
        raf = requestAnimationFrame(tick);
      }
      return Promise.resolve();
    },
    pause() {
      if (!playing) return;
      playing = false;
      stopClock();
      emit("pause");
    },

    addEventListener(type, fn) {
      if (!listeners.has(type)) listeners.set(type, new Set());
      listeners.get(type).add(fn);
    },
    removeEventListener(type, fn) {
      listeners.get(type)?.delete(fn);
    },

    /** The sequence changed length under the player: re-time, keep the place. */
    setDuration(next) {
      total = Math.max(0, Number(next) || 0);
      if (time > total) time = total;
    },

    /** The composed frame for the player's own time, or null. */
    frameCanvas() {
      return frameAt ? frameAt(time) : null;
    },

    dispose() {
      disposed = true;
      playing = false;
      stopClock();
      listeners.clear();
    },
  };
  return player;
}
