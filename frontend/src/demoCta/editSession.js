import { useCallback, useEffect, useRef, useState } from "react";
import { writeDraft } from "./draftStorage";

// Blob identities are represented by each source's id; JSON omits their bytes.
const keyOf = (edit) => JSON.stringify(edit);
const fieldsChanged = (a, b) => Object.keys(b).filter((key) => keyOf(a[key]) !== keyOf(b[key])).join(",");

/** One document history; playback/UI state never enters this hook. */
export function useEditSession({ draftKey, snapshot, restore, enabled }) {
  const history = useRef({ past: [], present: snapshot, future: [], group: "", at: 0 });
  const latest = useRef(snapshot);
  latest.current = snapshot;
  const restoreRef = useRef(restore);
  restoreRef.current = restore;
  const [, render] = useState(0);
  const [saveStatus, setSaveStatus] = useState("Loading draft…");
  const queue = useRef(Promise.resolve());
  const dirty = useRef(false);
  const mounted = useRef(true);
  const timer = useRef(null);
  const saveNow = useCallback(() => {
    clearTimeout(timer.current);
    if (!enabled) return Promise.resolve();
    const edit = latest.current;
    dirty.current = false;
    // Serialize writes so a slow save can never overwrite a newer document.
    queue.current = queue.current.catch(() => {}).then(() => writeDraft(draftKey, edit));
    return queue.current.then(() => {
      if (mounted.current && keyOf(edit) === keyOf(latest.current)) setSaveStatus("Draft saved on this device");
    }, () => {
      dirty.current = true;
      if (mounted.current) setSaveStatus("Draft not saved. Browser storage may be full; retry or free space.");
    });
  }, [draftKey, enabled]);
  const signature = keyOf(snapshot);
  useEffect(() => {
    if (!enabled) return;
    const snapshot = latest.current;
    const h = history.current;
    if (keyOf(h.present) !== signature) {
      const group = fieldsChanged(h.present, snapshot);
      const now = Date.now();
      if (group !== h.group || now - h.at > 500 || !h.past.length) h.past = [...h.past.slice(-49), h.present];
      h.present = snapshot;
      h.future = [];
      h.group = group;
      h.at = now;
      render((n) => n + 1);
    }
    dirty.current = true;
    setSaveStatus("Saving draft…");
    timer.current = setTimeout(saveNow, 500);
    return () => clearTimeout(timer.current);
  }, [signature, enabled, saveNow]);
  useEffect(() => {
    mounted.current = true;
    const flush = () => { if (dirty.current) saveNow(); };
    const hide = () => { if (document.visibilityState === "hidden") flush(); };
    window.addEventListener("pagehide", flush);
    document.addEventListener("visibilitychange", hide);
    return () => {
      mounted.current = false;
      clearTimeout(timer.current);
      flush();
      window.removeEventListener("pagehide", flush);
      document.removeEventListener("visibilitychange", hide);
    };
  }, [saveNow]);
  const travel = useCallback((forward) => {
    const h = history.current;
    const list = forward ? h.future : h.past;
    if (!list.length) return;
    const next = list[list.length - 1];
    if (forward) { h.future = h.future.slice(0, -1); h.past = [...h.past, h.present]; }
    else { h.past = h.past.slice(0, -1); h.future = [...h.future, h.present]; }
    h.present = next;
    h.group = "";
    restoreRef.current(next);
    render((n) => n + 1);
  }, []);
  const reset = useCallback((edit) => {
    history.current = { past: [], present: edit, future: [], group: "", at: 0 };
    render((n) => n + 1);
  }, []);
  return { undo: () => travel(false), redo: () => travel(true), canUndo: history.current.past.length > 0,
    canRedo: history.current.future.length > 0, saveStatus, saveNow, reset };
}
