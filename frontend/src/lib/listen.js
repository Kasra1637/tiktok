/**
 * Local voice reader for text-heavy surfaces.
 *
 * Every listen control renders through the browser's own `speechSynthesis`,
 * so the text being read never leaves the device: no backend, no key, no
 * network. Speech text is built from the data model (labels and values) —
 * never scraped from the DOM — so a glyph, button label or test id can never
 * end up in the audio.
 *
 * One voice at a time: starting a section stops whatever came before it, and
 * nothing ever autoplays — speech begins on a click and only a click. Where
 * the API is missing the controls do not render at all (feature-detect, not
 * a broken button).
 *
 * Provider voices (server TTS cached in R2) are deliberately parked: if the
 * host voices prove too coarse, they arrive behind this same module without
 * a page changing. See ADR 0088.
 */

export const LISTEN_RATES = [0.75, 1, 1.25, 1.5];
const DEFAULT_RATE = 1;
const RATE_KEY = "hookforge_voice_rate";
const MAX_CHUNK = 280;

let synth = null;
let chosenVoice;
let runToken = 0;
let activeBlocks = null;
const subscribers = new Set();

let current = { id: null, label: null, status: "idle", error: null, rate: loadRate() };

/** True when this browser can actually speak; checked before any control renders. */
export function speechSupported() {
  return (
    typeof window !== "undefined" &&
    "speechSynthesis" in window &&
    typeof window.SpeechSynthesisUtterance === "function"
  );
}

function engine() {
  if (!synth) synth = window.speechSynthesis;
  return synth;
}

function loadRate() {
  try {
    const raw = Number(window.localStorage.getItem(RATE_KEY));
    return LISTEN_RATES.includes(raw) ? raw : DEFAULT_RATE;
  } catch {
    return DEFAULT_RATE;
  }
}

function saveRate(rate) {
  try {
    window.localStorage.setItem(RATE_KEY, String(rate));
  } catch {
    // Private mode: the preference just will not persist.
  }
}

export function listenState() {
  return current;
}

export function subscribe(listener) {
  subscribers.add(listener);
  return () => subscribers.delete(listener);
}

function emit(patch) {
  current = { ...current, ...patch };
  subscribers.forEach((listener) => listener(current));
}

/**
 * One consistent English voice per session. Hosts differ wildly, so prefer
 * the platform default English voice and fall back to any English voice.
 */
function pickVoice() {
  if (chosenVoice !== undefined) return chosenVoice;
  try {
    const voices = engine().getVoices() || [];
    chosenVoice =
      voices.find((voice) => voice.default && /^en/i.test(voice.lang)) ||
      voices.find((voice) => /^en/i.test(voice.lang)) ||
      null;
  } catch {
    chosenVoice = null;
  }
  return chosenVoice;
}

function normalizeLine(value) {
  const clean = String(value ?? "")
    .replace(/&/g, " and ")
    .replace(/[`*#_]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
  if (!clean) return "";
  return /[.!?]$/.test(clean) ? clean : `${clean}.`;
}

/**
 * Build speakable chunks from labelled blocks. Pure: same input, same output.
 *
 * Blocks are `{ label?, values? }` or plain strings; a sentence is always
 * "Label. value." so a field never runs into the next one without a pause.
 * Long text is split at sentence ends so the engine never truncates it.
 */
export function buildSpeechText(blocks) {
  const sentences = [];
  for (const block of blocks || []) {
    if (!block) continue;
    if (typeof block === "string") {
      const clean = normalizeLine(block);
      if (clean) sentences.push(clean);
      continue;
    }
    const label = String(block.label ?? "").trim();
    const values = (block.values || []).map(normalizeLine).filter(Boolean);
    if (!values.length) continue;
    const spoken = values.join(" ");
    sentences.push(label ? `${label}. ${spoken}` : spoken);
  }
  const joined = sentences.join(" ");
  if (!joined) return [];
  const chunks = [];
  let rest = joined;
  while (rest.length > MAX_CHUNK) {
    const cut = rest.lastIndexOf(". ", MAX_CHUNK);
    const at = cut > 40 ? cut + 1 : rest.indexOf(" ", MAX_CHUNK);
    if (at <= 0) break;
    chunks.push(rest.slice(0, at).trim());
    rest = rest.slice(at).trim();
  }
  if (rest) chunks.push(rest);
  return chunks;
}

/**
 * Start reading `blocks` for one section id. Cancels anything already playing.
 * Returns false when there is nothing to say or the browser cannot speak.
 */
export function speak(id, blocks, label = null) {
  if (!speechSupported()) return false;
  const chunks = buildSpeechText(blocks);
  if (!chunks.length) return false;
  const token = ++runToken;
  activeBlocks = blocks;
  try {
    engine().cancel();
  } catch {
    // A cancel failure cannot matter: the next speak re-queues fresh ways.
  }
  emit({ id, label, status: "speaking", error: null });
  const last = chunks.length - 1;
  chunks.forEach((text, index) => {
    const utterance = new window.SpeechSynthesisUtterance(text);
    utterance.rate = current.rate;
    utterance.lang = "en-US";
    const voice = pickVoice();
    if (voice) utterance.voice = voice;
    utterance.onend = () => {
      if (token !== runToken) return;
      if (index === last) {
        activeBlocks = null;
        emit({ id: null, label: null, status: "idle" });
      }
    };
    utterance.onerror = (event) => {
      if (token !== runToken) return;
      const reason = String(event?.error || "unknown");
      if (reason === "interrupted" || reason === "canceled") return;
      activeBlocks = null;
      emit({ id, label, status: "idle", error: `Voice stopped: ${reason}.` });
    };
    try {
      engine().speak(utterance);
    } catch {
      if (token === runToken) {
        activeBlocks = null;
        emit({ id, label, status: "idle", error: "Voice stopped: this browser refused to play it." });
      }
    }
  });
  return true;
}

export function pause() {
  if (!speechSupported() || current.status !== "speaking") return;
  try {
    engine().pause();
    emit({ status: "paused" });
  } catch {
    // Safari without pause support keeps speaking; the dock still shows stop.
  }
}

export function resume() {
  if (!speechSupported() || current.status !== "paused") return;
  try {
    engine().resume();
    emit({ status: "speaking" });
  } catch {
    // Nothing to do: the next stop/speak resets the engine.
  }
}

export function stop() {
  if (!speechSupported()) return;
  runToken += 1;
  activeBlocks = null;
  try {
    engine().cancel();
  } catch {
    // Cancel on an already-idle engine is a no-op on every browser we target.
  }
  emit({ id: null, label: null, status: "idle", error: null });
}

/** Persisted rate. Applies to the next utterance; a running one restarts in place. */
export function setRate(rate) {
  const next = LISTEN_RATES.includes(Number(rate)) ? Number(rate) : DEFAULT_RATE;
  saveRate(next);
  const restart = current.status !== "idle" && current.id && activeBlocks;
  const id = current.id;
  const label = current.label;
  const blocks = activeBlocks;
  emit({ rate: next });
  if (restart) speak(id, blocks, label);
}
