import { useCallback, useEffect, useMemo, useRef, useState } from "react";
import {
  captureZoomLock as applyZoomLock,
  removeZoomKeyframe as dropZoomKeyframe,
  sortKeyframes,
} from "./zoom";

/**
 * Owns the zoom-lock keyframe list: the state, the sorted view the timeline
 * strip and the locked-segments list read, the ref mirror the export loop
 * reads (a ref, not state, because the encoder must see each lock the
 * instant it lands without re-creating its callback), and the three
 * mutations. Playhead time and slider snapshots stay with the caller — the
 * hook never touches the video element or the sliders.
 */
export function useZoomKeyframes() {
  const [zoomKeyframes, setZoomKeyframes] = useState([]);
  const zoomKeyframesRef = useRef([]);
  useEffect(() => {
    zoomKeyframesRef.current = sortKeyframes(zoomKeyframes);
  }, [zoomKeyframes]);
  const sortedKeyframes = useMemo(() => sortKeyframes(zoomKeyframes), [zoomKeyframes]);
  const captureZoomKeyframe = useCallback((t, snapshot) => {
    setZoomKeyframes((prev) => applyZoomLock(prev, t, snapshot));
  }, []);
  const removeZoomKeyframe = useCallback((id) => {
    setZoomKeyframes((prev) => dropZoomKeyframe(prev, id));
  }, []);
  const clearZoomKeyframes = useCallback(() => {
    setZoomKeyframes([]);
  }, []);
  return {
    zoomKeyframes,
    zoomKeyframesRef,
    sortedKeyframes,
    captureZoomKeyframe,
    removeZoomKeyframe,
    clearZoomKeyframes,
  };
}
