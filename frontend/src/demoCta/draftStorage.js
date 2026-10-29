/** Browser-local editing documents. IndexedDB preserves uploaded bytes, not expiring blob URLs. */
const DATABASE = "hookforge-demo-cta-drafts";
const STORE = "drafts";

function openDatabase() {
  return new Promise((resolve, reject) => {
    if (!window.indexedDB) return reject(new Error("Browser draft storage is unavailable."));
    const request = window.indexedDB.open(DATABASE, 1);
    request.onupgradeneeded = () => request.result.createObjectStore(STORE);
    request.onerror = () => reject(request.error);
    request.onblocked = () => reject(new Error("Close other HookForge tabs to enable draft storage."));
    request.onsuccess = () => resolve(request.result);
  });
}

async function transaction(key, value, writing) {
  const db = await openDatabase();
  try {
    return await new Promise((resolve, reject) => {
      const tx = db.transaction(STORE, writing ? "readwrite" : "readonly");
      const store = tx.objectStore(STORE);
      const request = writing ? store.put({ version: 1, savedAt: Date.now(), edit: value }, key) : store.get(key);
      tx.oncomplete = () => resolve(writing ? undefined : request.result);
      tx.onerror = () => reject(tx.error || request.error);
      tx.onabort = () => reject(tx.error || new Error("Draft storage was interrupted."));
    });
  } finally { db.close(); }
}

export async function readDraft(key) {
  const stored = await transaction(key, null, false);
  if (!stored) return null;
  if (stored.version !== 1 || !stored.edit || typeof stored.edit !== "object") {
    throw new Error("This draft cannot be opened by this version of HookForge.");
  }
  return stored.edit;
}
export function writeDraft(key, edit) { return transaction(key, edit, true); }
