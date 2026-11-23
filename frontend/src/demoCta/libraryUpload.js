import { api } from "../lib/api";

/**
 * ADR 0274: everything a founder adds in Demo + CTA is also held in the
 * Assets library — one copy, stored on the server at the moment it is
 * added, under the file's own name so the library's search finds it.
 *
 * This upload is a side effect of the add, never a step in it: the editor
 * keeps working from the local blob exactly as before, and a failed
 * library upload resolves to null here instead of surfacing in the
 * editor. There is deliberately no retry and no founder-facing error —
 * the file is safe in the draft either way, and the library is a filing
 * copy, not the working one.
 *
 * `sent` is the caller's set of draft-entry ids already filed. An entry
 * is marked before the request goes out, so a re-render, an undo/redo
 * restore, or a second call for the same entry can never file it twice;
 * replacing a clip mints a new entry, which files the replacement.
 *
 * Without a profile id there is no library to file into — the editor
 * opened without an app (a blank standalone session) — so nothing is
 * sent and nothing is marked: if an app is chosen later, the entries
 * added from then on file as usual.
 */
export function uploadEntryToLibrary({
  profileId,
  entryId,
  file,
  kind,
  sent,
  uploadAsset = api.uploadAsset,
}) {
  if (!profileId || !entryId || !file || !kind || !sent) return Promise.resolve(null);
  if (sent.has(entryId)) return Promise.resolve(null);
  sent.add(entryId);
  try {
    const form = new FormData();
    form.append("kind", kind);
    // The filename rides explicitly: the server names the asset from it, so
    // the founder's own name for the file is what the library stores and
    // what search matches — never a browser-normalized substitute.
    form.append("file", file, file.name || "file");
    // The founder picked this file off their own device to put in their
    // video; the upload asserts the same right the presenter-photo upload
    // asserts.
    form.append("rights_confirmed", "true");
    return Promise.resolve(uploadAsset(profileId, form)).catch(() => null);
  } catch {
    // Even building the form must never throw into the editor: the add
    // that triggered this filing has already succeeded on the local blob.
    return Promise.resolve(null);
  }
}
