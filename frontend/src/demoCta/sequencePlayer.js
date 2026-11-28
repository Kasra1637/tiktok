/**
 * A media-element-shaped clock for a mixed second-clip sequence.
 *
 * The image-sequence player (imagePlayer.js) covers a stills-only slot;
 * a sequence that also holds clips needs the same shape with one extra
 * job: the clips inside it are real media elements, and something has
 * to keep the active one playing in step with the sequence's own
 * clock. That is `syncAt` — called on every tick, seek, play and pause
 * with the player's time and play state, the editor answers it by
 * starting, stopping and drift-correcting whichever element the time
 * lands in. The player owns no pixels and no elements: `frameCanvas()`
 * asks the caller's compositor for the frame at the player's own time,
 * exactly like the image player's.
 *
 * Preview only. The export never plays a sequence — it decodes each
 * entry's bytes in order — so a preview drift costs nothing in the
 * file, and the sync tolerance below is a viewing tolerance.
 */
export function createSequencePlayer({ duration = 0, frameAt = null, syncAt = null } = {}) {
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

  const sync = () => {
    if (syncAt) syncAt(time, playing);
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
    // A backgrounded tab can hand the clock minutes at once; the
    // sequence advances in steps of at most half a second, never in
    // one leap — the same guard the image player's clock keeps.
    const delta = Math.min(0.5, Math.max(0, (stamp - lastStamp) / 1000));
    lastStamp = stamp;
    time += delta;
    if (time >= total) {
      time = total;
      playing = false;
      sync();
      emit("timeupdate");
      if (player.loop && total > 0) {
        time = 0;
        playing = true;
        sync();
        emit("timeupdate");
      } else {
        emit("ended");
        return;
      }
    } else {
      sync();
      emit("timeupdate");
    }
    raf = requestAnimationFrame(tick);
  };

  const player = {
    // Stored, media-shaped no-ops: the transport writes these on
    // whichever source it owns. A sequence's own monitor state is the
    // editor's business; the elements inside answer their own mute.
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
      sync();
      emit("seeked");
      emit("timeupdate");
    },

    play() {
      if (disposed) return Promise.resolve();
      if (time >= total && total > 0) time = 0; // a media element replays from the top
      if (!playing) {
        playing = true;
        sync();
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
      sync();
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
      sync();
      listeners.clear();
    },
  };
  return player;
}
