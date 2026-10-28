/**
 * Pending-save outbox: failed Demo + CTA saves that created no server row.
 *
 * A 413 (or any save failure) leaves the export bytes in the editor but no
 * History row, so History would silently miss the clip. The save path records
 * the failure here — metadata in localStorage (survives navigation) plus the
 * bytes in a same-tab memory map (blobs cannot live in localStorage) — and
 * GenerationHistory reads it back as a retry/download repair card.
 *
 * Copy policy stays single-owned: entries carry the message the save path
 * already showed (via getErrorMessage), and History renders its own
 * historyActionError wording around them. This module stores and retries;
 * it never invents user-facing sentences.
 */

const STORAGE_KEY = "hookforge.demo-cta-pending-saves";
const MAX_ENTRIES = 10;
const EVENT_NAME = "hookforge:pending-saves-changed";

// Same-tab only: blobs cannot be serialized to localStorage, so the bytes
// live here while the tab does. Entries whose blob is gone (reload,
// another tab) still render — with a re-export step instead of Download.
const blobById = new Map();

function notify() {
  try {
    window.dispatchEvent(new CustomEvent(EVENT_NAME));
  } catch {
    // Non-browser (tests without jsdom globals): readers just poll on mount.
  }
}

function readStored() {
  try {
    const raw = localStorage.getItem(STORAGE_KEY);
    const parsed = raw ? JSON.parse(raw) : [];
    return Array.isArray(parsed) ? parsed : [];
  } catch {
    return [];
  }
}

function writeStored(entries) {
  try {
    localStorage.setItem(STORAGE_KEY, JSON.stringify(entries.slice(0, MAX_ENTRIES)));
  } catch {
    // Storage full or unavailable: the in-memory bytes still serve this tab.
  }
  notify();
}

function newEntryId() {
  try {
    if (typeof crypto !== "undefined" && typeof crypto.randomUUID === "function") {
      return crypto.randomUUID();
    }
  } catch {
    // Fall through to the Math.random fallback below.
  }
  return "xxxxxxxx-xxxx-4xxx-yxxx-xxxxxxxxxxxx".replace(/[xy]/g, (c) => {
    const r = (Math.random() * 16) | 0;
    return (c === "x" ? r : (r & 0x3) | 0x8).toString(16);
  });
}

/**
 * Record a save that failed before any server row existed. Returns the entry.
 */
export function recordFailedSave({ generationId = null, filename = "demo-cta.mp4", size = 0, mime = "video/mp4", message = "", blob = null }) {
  const entry = {
    id: newEntryId(),
    generationId,
    filename,
    size,
    mime,
    message,
    at: new Date().toISOString(),
  };
  if (blob) blobById.set(entry.id, blob);
  // Evict oldest first; drop evicted bytes so a long session cannot grow RAM.
  const next = [entry, ...readStored()].slice(0, MAX_ENTRIES);
  const kept = new Set(next.map((e) => e.id));
  for (const id of [...blobById.keys()]) {
    if (!kept.has(id)) blobById.delete(id);
  }
  writeStored(next);
  return entry;
}

/** Newest-first metadata for every still-pending failed save. */
export function listPendingSaves() {
  return readStored();
}

/** The failed-save bytes for this tab, or null (reload, another tab, evicted). */
export function getPendingBlob(id) {
  return blobById.get(id) || null;
}

/** Drop one entry (after a successful retry, a dismissal, or a re-export). */
export function clearPendingSave(id) {
  blobById.delete(id);
  writeStored(readStored().filter((e) => e.id !== id));
}

/** Drop only retries of these exact bytes, never other edits sharing a filename. */
export function clearPendingSavesFor({ generationId = null, filename = "", blob = null } = {}) {
  if (!blob) return;
  const remaining = readStored().filter(
    (e) => !(e.filename === filename && (e.generationId || null) === (generationId || null) && blobById.get(e.id) === blob)
  );
  if (remaining.length !== readStored().length) {
    const kept = new Set(remaining.map((e) => e.id));
    for (const id of [...blobById.keys()]) {
      if (!kept.has(id)) blobById.delete(id);
    }
    writeStored(remaining);
  }
}

/**
 * Retry one pending save through the real save function
 * (`api.saveDemoCtaExport`). Resolves to the saved row and clears the entry;
 * rejects with the save error and refreshes the entry's message and time.
 */
export async function retryPendingSave(id, saveFn) {
  const entry = readStored().find((e) => e.id === id);
  if (!entry) throw new Error("That pending export is no longer listed. Re-export it from the editor.");
  const blob = blobById.get(id);
  if (!blob) throw new Error("The file bytes are gone (the tab reloaded). Re-export it from the editor.");
  try {
    const row = await saveFn(entry.generationId || null, blob, entry.filename);
    clearPendingSave(id);
    return row;
  } catch (err) {
    const message = err?.response?.data?.detail || err?.message || "The retry failed. Try again.";
    writeStored(readStored().map((e) => (e.id === id ? { ...e, message, at: new Date().toISOString() } : e)));
    throw err;
  }
}

/** Test seam: forget everything, including in-memory bytes. */
export function __resetPendingSavesForTests() {
  blobById.clear();
  try {
    localStorage.removeItem(STORAGE_KEY);
  } catch {
    // Ignore: no storage in this environment.
  }
}
