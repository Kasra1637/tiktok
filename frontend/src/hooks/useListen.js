import { useEffect, useState } from "react";
import { listenState, speak, stop, speechSupported, subscribe } from "../lib/listen";

/**
 * Subscribe one section to the shared voice controller.
 *
 * `getBlocks` is called at click time, not at render time, so the spoken text
 * is always the data on screen when the founder asked for it. The hook also
 * silences the section it belongs to when it unmounts — navigating away must
 * never leave a voice reading a page that no longer exists.
 */
export function useListen(id, getBlocks, label = null) {
  const supported = speechSupported();
  const [state, setState] = useState(() => listenState());

  useEffect(() => subscribe(setState), []);

  useEffect(
    () => () => {
      if (listenState().id === id) stop();
    },
    [id]
  );

  const present = state.id === id && state.status !== "idle";

  return {
    supported,
    present,
    speaking: state.id === id && state.status === "speaking",
    paused: state.id === id && state.status === "paused",
    error: state.id === id ? state.error : null,
    toggle: () => {
      if (present) stop();
      else speak(id, getBlocks(), label);
    },
  };
}

export default useListen;
