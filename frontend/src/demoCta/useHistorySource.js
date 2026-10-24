import { useCallback, useEffect, useRef, useState } from "react";
import { api, durableMediaUrl } from "../lib/api";

/**
 * A browser network failure surfaces as the raw TypeError text "Failed to
 * fetch", which names the mechanism instead of the remedy. Say what happened
 * and what fixes it: the clip's link may have expired or the connection may
 * have dropped, and refreshing loads it fresh.
 */
export function sourceErrorMessage(err, fallback) {
  const message = err?.message || "";
  if (/failed to fetch|network error/i.test(message)) {
    return "The clip couldn't be reached over the network. Check your connection, then refresh for a fresh link.";
  }
  return message || fallback;
}

/**
 * Owns the History-as-source picker: the open/rows/error/attaching state,
 * the one-shot list load, and the attach. Attaching fetches the render's
 * bytes and reuses the upload path through onAttachFile, so metadata
 * probing, zoom reset and Remove-reversibility behave exactly as if the
 * founder had uploaded the file — the error resets the inline version
 * carried are already done there, so attach does not repeat them. A ref,
 * not state, carries the callback: attach is async, and the callback must
 * be the latest render's without re-creating attach mid-flight.
 */
export function useHistorySource({ onAttachFile }) {
  // Null rows means never opened; an array (possibly empty) means loaded.
  const [historyOpen, setHistoryOpen] = useState(false);
  const [historyRows, setHistoryRows] = useState(null);
  const [historyError, setHistoryError] = useState(null);
  const [attachingId, setAttachingId] = useState(null);
  const onAttachFileRef = useRef(onAttachFile);
  useEffect(() => {
    onAttachFileRef.current = onAttachFile;
  });

  // Load the History list the first time the picker opens. Only completed
  // renders with a fetchable copy are listed — anything else cannot become
  // a source, and offering it would be a button that cannot act.
  useEffect(() => {
    if (!historyOpen || historyRows !== null) return;
    let cancelled = false;
    (async () => {
      try {
        const data = await api.getGenerationHistory({ limit: 50 });
        if (cancelled) return;
        const rows = (data?.generations || []).filter(
          (r) => r?.status === "completed" && durableMediaUrl(r)
        );
        setHistoryRows(rows);
      } catch (e) {
        if (!cancelled) setHistoryError(e?.message || "History could not be loaded. Try again.");
      }
    })();
    return () => { cancelled = true; };
  }, [historyOpen, historyRows]);

  // Attach a History render as the source: fetch its bytes and reuse the
  // upload path, so metadata probing, zoom reset and Remove-reversibility
  // all behave exactly as if the founder had uploaded the file.
  const attachHistoryVideo = useCallback(async (row) => {
    const url = durableMediaUrl(row);
    if (!url) {
      setHistoryError("That render has no playable copy, so it cannot be a source.");
      return;
    }
    setAttachingId(row.id);
    try {
      const res = await fetch(url);
      if (!res.ok) {
        const auth = res.status === 401 || res.status === 403;
        throw new Error(
          auth
            ? "This render's link needs a fresh credential. Reopen History and try again."
            : "That render could not be read. Try another one."
        );
      }
      const blob = await res.blob();
      const name = `${row.brand_name || "history-render"}-${String(row.id || "clip").slice(0, 8)}.mp4`;
      onAttachFileRef.current(new File([blob], name, { type: blob.type || "video/mp4" }), row);
      setHistoryOpen(false);
    } catch (e) {
      setHistoryError(e?.message || "That render could not be attached. Try another one.");
    } finally {
      setAttachingId(null);
    }
  }, []);

  return {
    historyOpen,
    setHistoryOpen,
    historyRows,
    historyError,
    attachingId,
    attachHistoryVideo,
  };
}
